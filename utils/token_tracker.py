"""
Token tracker — records every DeepSeek API call's token usage.
Agents call record() after each API response; LEDGER reads the summary.

Usage pattern:
    from utils.token_tracker import token_tracker
    token_tracker.record("GATE", "deepseek-reasoner", response.usage)
    summary = token_tracker.summary()
"""
from dataclasses import dataclass, field
from typing import Any


# ── DeepSeek pricing (USD per 1 million tokens, cache-miss) ──────────────
# Source: platform.deepseek.com/api-docs/pricing (as of April 2026)
PRICING = {
    "deepseek-chat": {
        "input_per_1m":  0.27,   # cache miss
        "output_per_1m": 1.10,
    },
    "deepseek-reasoner": {
        "input_per_1m":  0.55,
        "output_per_1m": 2.19,   # includes reasoning tokens
    },
}


@dataclass
class CallRecord:
    agent:             str
    model:             str
    prompt_tokens:     int
    completion_tokens: int
    reasoning_tokens:  int   # only for deepseek-reasoner
    total_tokens:      int
    cost_usd:          float


class TokenTracker:
    """Thread-safe (append-only) token usage log for one company run."""

    def __init__(self):
        self._calls: list[CallRecord] = []

    def reset(self):
        """Call at the start of each new Orchestrator run."""
        self._calls.clear()

    def record(self, agent: str, model: str, usage: Any) -> None:
        """
        Record one API call's usage.
        `usage` is the openai.types.CompletionUsage object from the response.
        """
        if usage is None:
            return

        prompt_tokens     = getattr(usage, "prompt_tokens",     0) or 0
        completion_tokens = getattr(usage, "completion_tokens", 0) or 0
        total_tokens      = getattr(usage, "total_tokens",      0) or 0

        # DeepSeek Reasoner exposes reasoning tokens in completion_tokens_details
        reasoning_tokens = 0
        details = getattr(usage, "completion_tokens_details", None)
        if details:
            reasoning_tokens = getattr(details, "reasoning_tokens", 0) or 0

        price = PRICING.get(model, PRICING["deepseek-chat"])
        cost  = (
            (prompt_tokens     / 1_000_000) * price["input_per_1m"] +
            (completion_tokens / 1_000_000) * price["output_per_1m"]
        )

        self._calls.append(CallRecord(
            agent=agent,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            reasoning_tokens=reasoning_tokens,
            total_tokens=total_tokens,
            cost_usd=round(cost, 6),
        ))

    # ── Aggregation helpers ────────────────────────────────────────

    def summary(self) -> dict:
        """Return a full token+cost summary for the run."""
        if not self._calls:
            return {
                "total_calls": 0,
                "total_prompt_tokens": 0,
                "total_completion_tokens": 0,
                "total_reasoning_tokens": 0,
                "total_tokens": 0,
                "total_cost_usd": 0.0,
                "per_agent": {},
                "per_model": {},
                "calls": [],
            }

        per_agent: dict[str, dict] = {}
        per_model: dict[str, dict] = {}

        for c in self._calls:
            # per-agent
            if c.agent not in per_agent:
                per_agent[c.agent] = {
                    "calls": 0,
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "reasoning_tokens": 0,
                    "total_tokens": 0,
                    "cost_usd": 0.0,
                    "model": c.model,
                }
            a = per_agent[c.agent]
            a["calls"]             += 1
            a["prompt_tokens"]     += c.prompt_tokens
            a["completion_tokens"] += c.completion_tokens
            a["reasoning_tokens"]  += c.reasoning_tokens
            a["total_tokens"]      += c.total_tokens
            a["cost_usd"]          += c.cost_usd
            a["cost_usd"]           = round(a["cost_usd"], 6)

            # per-model
            if c.model not in per_model:
                per_model[c.model] = {
                    "calls": 0,
                    "total_tokens": 0,
                    "cost_usd": 0.0,
                }
            m = per_model[c.model]
            m["calls"]        += 1
            m["total_tokens"] += c.total_tokens
            m["cost_usd"]     += c.cost_usd
            m["cost_usd"]      = round(m["cost_usd"], 6)

        return {
            "total_calls":             len(self._calls),
            "total_prompt_tokens":     sum(c.prompt_tokens     for c in self._calls),
            "total_completion_tokens": sum(c.completion_tokens for c in self._calls),
            "total_reasoning_tokens":  sum(c.reasoning_tokens  for c in self._calls),
            "total_tokens":            sum(c.total_tokens       for c in self._calls),
            "total_cost_usd":          round(sum(c.cost_usd     for c in self._calls), 6),
            "per_agent":               per_agent,
            "per_model":               per_model,
            "calls": [
                {
                    "agent":             c.agent,
                    "model":             c.model,
                    "prompt_tokens":     c.prompt_tokens,
                    "completion_tokens": c.completion_tokens,
                    "reasoning_tokens":  c.reasoning_tokens,
                    "total_tokens":      c.total_tokens,
                    "cost_usd":          c.cost_usd,
                }
                for c in self._calls
            ],
        }


# ── Singleton ─────────────────────────────────────────────────────────────
token_tracker = TokenTracker()
