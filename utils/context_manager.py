"""
context_manager.py — Token counting + auto-compression for agent context windows.

Each DeepSeek model has a 128k token limit. This manager:
1. Estimates token count before every LLM call
2. If over budget, compresses context sections by priority
3. Agents can also self-summarize their own history

Token budget allocation (128k total):
  - System prompt core:     ~2k tokens (never compressed)
  - CEO directive:          ~500 tokens (never compressed)
  - Long-term memory:       up to 4k tokens (compressed if over)
  - Short-term memory:      up to 3k tokens (compressed if over)
  - Web search results:     up to 3k tokens (compressed if over)
  - User prompt (task):     up to 8k tokens (trimmed if over)
  - Reserved for response:  24k tokens (never touched)
  - Remaining:              available for context
"""
from __future__ import annotations


# ── Token estimation ─────────────────────────────────────────────────────────
# DeepSeek uses a BPE tokenizer. Rough approximation: 1 token ≈ 3.5 chars for English.
CHARS_PER_TOKEN = 3.5
MAX_CONTEXT_TOKENS = 128_000
RESPONSE_RESERVE   = 24_000   # leave room for model's response
MAX_INPUT_TOKENS   = MAX_CONTEXT_TOKENS - RESPONSE_RESERVE  # ~104k

# Per-section token budgets (soft limits — compressed if exceeded)
BUDGET = {
    "system_core":    4_000,   # the agent's base personality prompt
    "ceo_directive":  1_000,   # CEO chat instruction
    "long_term_mem":  4_000,   # graph memory recall
    "short_term_mem": 3_000,   # vector memory from this run
    "web_search":     3_000,   # search results injected by SENTRY/ARIA
    "user_prompt":   12_000,   # the actual task/question
    "overflow":      77_000,   # remaining budget if sections are small
}


def estimate_tokens(text: str) -> int:
    """Estimate token count from character length."""
    if not text:
        return 0
    return int(len(text) / CHARS_PER_TOKEN)


def is_over_budget(system_prompt: str, user_prompt: str) -> bool:
    total = estimate_tokens(system_prompt) + estimate_tokens(user_prompt)
    return total > MAX_INPUT_TOKENS


# ── Section detection ────────────────────────────────────────────────────────

def _find_section(text: str, marker_start: str, marker_end: str = None) -> tuple:
    """Find a section in text by markers. Returns (start_idx, end_idx, content)."""
    idx = text.find(marker_start)
    if idx == -1:
        return (-1, -1, "")
    if marker_end:
        end = text.find(marker_end, idx + len(marker_start))
        if end == -1:
            end = len(text)
    else:
        end = len(text)
    return (idx, end, text[idx:end])


# ── Compression strategies ───────────────────────────────────────────────────

def truncate_to_tokens(text: str, max_tokens: int) -> str:
    """Hard truncate text to fit within token budget."""
    max_chars = int(max_tokens * CHARS_PER_TOKEN)
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n[... truncated to fit context window ...]"


def compress_memory_section(text: str, max_tokens: int = 4000) -> str:
    """Compress a memory section by keeping only the most important lines."""
    if estimate_tokens(text) <= max_tokens:
        return text
    lines = text.split("\n")
    # Priority: keep header + bullet points, drop details
    important = []
    detail = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("[") or stripped.startswith("*") or stripped.startswith("-"):
            important.append(line)
        elif stripped.startswith("  -") or stripped.startswith("  *"):
            detail.append(line)  # sub-details, lower priority
        else:
            important.append(line)
    # Build result, adding details until budget reached
    result_lines = important[:]
    result = "\n".join(result_lines)
    for line in detail:
        candidate = result + "\n" + line
        if estimate_tokens(candidate) > max_tokens:
            break
        result = candidate
    return truncate_to_tokens(result, max_tokens)


def compress_search_results(text: str, max_tokens: int = 3000) -> str:
    """Compress search results by keeping fewer results with shorter bodies."""
    if estimate_tokens(text) <= max_tokens:
        return text
    # Split by result markers [1], [2], etc.
    import re
    results = re.split(r'\n(?=\[\d+\])', text)
    compressed = []
    budget_used = 0
    for r in results:
        tokens = estimate_tokens(r)
        if budget_used + tokens > max_tokens:
            # Truncate this result's body
            lines = r.split("\n")
            short = "\n".join(lines[:2])  # keep title + first line of body
            tokens = estimate_tokens(short)
            if budget_used + tokens <= max_tokens:
                compressed.append(short)
                budget_used += tokens
            break
        compressed.append(r)
        budget_used += tokens
    return "\n".join(compressed)


# ── Main compression pipeline ────────────────────────────────────────────────

def compress_context(system_prompt: str, user_prompt: str) -> tuple:
    """
    Compress system_prompt and user_prompt to fit within the context window.
    Returns (compressed_system, compressed_user).

    Compression order (lowest priority compressed first):
    1. Web search results → truncate to 3k tokens
    2. Short-term memory → truncate to 3k tokens
    3. Long-term memory → truncate to 4k tokens
    4. User prompt → truncate to 12k tokens
    5. System prompt core → never compressed
    """
    total = estimate_tokens(system_prompt) + estimate_tokens(user_prompt)
    if total <= MAX_INPUT_TOKENS:
        return system_prompt, user_prompt  # fits, no compression needed

    # ── Compress web search results in user_prompt ────────────────────────
    for marker in ["=== REAL-TIME WEB SEARCH RESULTS", "=== WEB SEARCH RESULTS"]:
        start = user_prompt.find(marker)
        if start != -1:
            end = user_prompt.find("=== END", start)
            if end == -1:
                end = len(user_prompt)
            else:
                end = user_prompt.find("\n", end) + 1
            section = user_prompt[start:end]
            compressed = compress_search_results(section, BUDGET["web_search"])
            user_prompt = user_prompt[:start] + compressed + user_prompt[end:]

    # ── Compress short-term memory in user_prompt ─────────────────────────
    stm_marker = "[SHORT-TERM RUN MEMORY"
    stm_start = user_prompt.find(stm_marker)
    if stm_start != -1:
        stm_section = user_prompt[stm_start:]
        user_prompt = user_prompt[:stm_start] + compress_memory_section(stm_section, BUDGET["short_term_mem"])

    # ── Compress long-term memory in system_prompt ────────────────────────
    ltm_marker = "[" # Memory sections start with [AGENT_NAME LONG-TERM MEMORY
    for marker in ["LONG-TERM MEMORY"]:
        ltm_start = system_prompt.find(marker)
        if ltm_start != -1:
            # Find the start of the memory block (go back to find '[')
            block_start = system_prompt.rfind("[", 0, ltm_start)
            if block_start == -1:
                block_start = ltm_start
            ltm_section = system_prompt[block_start:]
            system_prompt = system_prompt[:block_start] + compress_memory_section(ltm_section, BUDGET["long_term_mem"])

    # ── Truncate user prompt if still over ────────────────────────────────
    total = estimate_tokens(system_prompt) + estimate_tokens(user_prompt)
    if total > MAX_INPUT_TOKENS:
        user_budget = MAX_INPUT_TOKENS - estimate_tokens(system_prompt)
        user_prompt = truncate_to_tokens(user_prompt, max(user_budget, 2000))

    # ── Last resort: truncate system prompt ───────────────────────────────
    total = estimate_tokens(system_prompt) + estimate_tokens(user_prompt)
    if total > MAX_INPUT_TOKENS:
        sys_budget = MAX_INPUT_TOKENS - estimate_tokens(user_prompt)
        system_prompt = truncate_to_tokens(system_prompt, max(sys_budget, 2000))

    return system_prompt, user_prompt


# ── Self-summarization prompt ────────────────────────────────────────────────

SUMMARIZE_PROMPT = """Compress the following text into a concise summary.
Keep: key facts, numbers, decisions, names, dates, conclusions.
Drop: examples, verbose explanations, repeated information.
Target: reduce to ~30% of original length.

TEXT TO COMPRESS:
{text}

COMPRESSED SUMMARY:"""


def build_self_summary_prompt(text: str) -> str:
    """Build a prompt that asks the agent to summarize its own output."""
    return SUMMARIZE_PROMPT.format(text=text[:8000])
