"""
BaseAgent — the foundation every agent inherits from.
Handles DeepSeek API calls, JSON parsing, daily logging, and event emission.
"""
import json
import re
from typing import Any, Callable, Optional
from datetime import datetime

from utils.client import get_client
from utils.logger import agent_start, agent_output, error as log_error
from utils.notion_logger import post_daily_log
from utils.token_tracker import token_tracker
from config import AGENT_MODELS, AGENT_TEMPERATURE, AGENT_TOP_P


# Global event bus — the API server subscribes to this
_event_listeners: list[Callable] = []

def subscribe_events(listener: Callable) -> None:
    _event_listeners.append(listener)

def _emit(event_type: str, agent_name: str, chamber: str,
          status: str, message: str, data: dict = None) -> None:
    from models.schemas import AgentEvent, AgentStatus
    evt = AgentEvent(
        event_type=event_type,
        agent_name=agent_name,
        chamber=chamber,
        status=AgentStatus(status),
        message=message,
        data=data or {},
    )
    for listener in _event_listeners:
        try:
            listener(evt)
        except Exception:
            pass


class BaseAgent:
    """
    Every AI employee inherits from this class.
    Provides:
      - run()         — calls DeepSeek, returns plain text
      - run_json()    — calls DeepSeek, parses and returns JSON dict
      - log()         — writes to daily log file + Notion
    """

    name:       str = "AGENT"
    role:       str = "Unknown"
    department: str = "chamber1"
    emoji:      str = "🤖"

    def __init__(self):
        self.client        = get_client()
        self.model         = AGENT_MODELS.get(self.name, "deepseek-chat")
        self.temperature   = AGENT_TEMPERATURE.get(self.name, 0.2)
        self.top_p         = AGENT_TOP_P.get(self.name, 1.0)
        self._daily_log: list[str] = []
        self._ceo_directive: str = ""    # injected by orchestrator for CEO chat
        self._current_industry: str = "" # set by orchestrator before each run
        # ── Long-term graph memory (FalkorDB → SQLite fallback) ───────────
        try:
            from utils.agent_memory import AgentMemoryGraph
            self.memory = AgentMemoryGraph(self.name)
        except Exception:
            self.memory = None
        # ── Short-term vector memory (shared per-run store) ───────────────
        # Injected by orchestrator at run start via set_run_memory()
        self._run_memory = None

    def set_ceo_directive(self, directive: str):
        self._ceo_directive = directive

    def set_industry(self, industry: str):
        """Called by orchestrator so memory context is injected automatically."""
        self._current_industry = industry

    def set_run_memory(self, run_memory):
        """Inject the shared short-term vector store for this run."""
        self._run_memory = run_memory

    def recall_memory(self, industry: str) -> str:
        """Retrieve relevant long-term memory for an industry."""
        if self.memory:
            try:
                return self.memory.recall_for_industry(industry)
            except Exception:
                pass
        return ""

    def save_memory(self, industry: str, result: dict):
        """Store run learnings into long-term memory and emit event."""
        if self.memory:
            try:
                before = self.memory.stats()
                self.memory.remember_run(industry, result)
                after = self.memory.stats()
                new_nodes = after.get("nodes",0) - before.get("nodes",0)
                new_edges = after.get("edges",0) - before.get("edges",0)
                if new_nodes > 0 or new_edges > 0:
                    _emit("agent_output", self.name, self.department, "done",
                          f"[MEMORY] {self.name} learned +{new_nodes} nodes, +{new_edges} edges about {industry} (total: {after.get('nodes',0)} nodes, {after.get('edges',0)} edges, backend: {after.get('backend','?')})",
                          {"memory_update": True, "new_nodes": new_nodes, "new_edges": new_edges})
            except Exception:
                pass

    # ── Core LLM call ──────────────────────────────────────────

    def run(self, system_prompt: str, user_prompt: str) -> str:
        """Call DeepSeek and return the raw text response."""
        # Inject CEO directive into system prompt if present
        if self._ceo_directive:
            system_prompt = (
                f"IMPORTANT CEO DIRECTIVE: {self._ceo_directive}\n"
                f"Take this directive into account in your analysis.\n\n"
                + system_prompt
            )
        # ── Inject long-term memory (graph, cross-run) ────────────────────
        if self._current_industry and self.memory:
            mem_context = self.recall_memory(self._current_industry)
            if mem_context:
                system_prompt = system_prompt + f"\n\n{mem_context}"

        # ── Inject short-term memory (vector, this run) ───────────────────
        if self._run_memory:
            try:
                query = user_prompt[:200]   # use the user prompt as search query
                stm_context = self._run_memory.build_context_for(self.name, query, top_k=3)
                if stm_context:
                    user_prompt = user_prompt + f"\n\n{stm_context}"
            except Exception:
                pass
        # â”€â”€ Auto-compress context if over token budget â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        try:
            from utils.context_manager import compress_context, estimate_tokens
            before = estimate_tokens(system_prompt) + estimate_tokens(user_prompt)
            system_prompt, user_prompt = compress_context(system_prompt, user_prompt)
            after = estimate_tokens(system_prompt) + estimate_tokens(user_prompt)
            if after < before:
                from utils.logger import info
                info(f"{self.name}: context compressed {before}â†’{after} tokens (saved {before-after})")
        except Exception:
            pass
        agent_start(self.name, user_prompt[:80] + ("…" if len(user_prompt) > 80 else ""))
        _emit("agent_start", self.name, self.department, "running",
              f"{self.name} is working…")
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                temperature=self.temperature,
                top_p=self.top_p,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": user_prompt},
                ],
            )
            result = response.choices[0].message.content.strip()
            # ── Track real token usage ──────────────────────────────
            token_tracker.record(self.name, self.model, response.usage)
            # Store output in short-term vector memory
            if self._run_memory and result:
                try:
                    # Store a SUMMARY (first 600 chars) not the full raw output
                    summary = result[:600] if len(result) > 600 else result
                    self._run_memory.store(self.name, summary,
                        metadata={"industry": self._current_industry, "model": self.model,
                                  "tokens_est": len(result)//4})
                except Exception:
                    pass
            # ───────────────────────────────────────────────────────
            agent_output(self.name, result[:600] + ("…" if len(result) > 600 else ""))
            _emit("agent_output", self.name, self.department, "done",
                  result, {"full_output": result})
            self._record_log(user_prompt, result)
            return result
        except Exception as e:
            log_error(f"{self.name} API call failed: {e}")
            _emit("error", self.name, self.department, "error", str(e))
            raise

    def run_json(self, system_prompt: str, user_prompt: str) -> dict:
        """
        Call DeepSeek with a JSON-output instruction appended.
        Parses and returns the JSON dict. Falls back gracefully.
        """
        json_instruction = (
            "\n\nIMPORTANT: Your entire response must be a single valid JSON object. "
            "No markdown fences, no explanation, just raw JSON."
        )
        raw = self.run(system_prompt + json_instruction, user_prompt)

        # Strip ```json ... ``` fences if present
        cleaned = re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.MULTILINE)
        cleaned = re.sub(r"\s*```$", "", cleaned.strip(), flags=re.MULTILINE)

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            # Last-resort: extract first {...} block
            match = re.search(r"\{.*\}", cleaned, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group())
                except Exception:
                    pass
            log_error(f"{self.name}: Could not parse JSON response. Returning raw.")
            return {"raw_response": raw}

    # ── Daily logging ──────────────────────────────────────────

    def _record_log(self, task: str, result: str) -> None:
        entry = (
            f"**{datetime.now().strftime('%H:%M')}** — Task: {task[:120]}\n\n"
            f"Result: {result[:300]}{'…' if len(result) > 300 else ''}\n"
        )
        self._daily_log.append(entry)

    def flush_daily_log(self) -> None:
        """
        Writes accumulated daily log entries to disk and Notion.
        Call at the end of each run.
        """
        if not self._daily_log:
            return
        content = f"## {self.emoji} {self.name} — {self.role}\n\n"
        content += "\n---\n".join(self._daily_log)
        post_daily_log(self.department, self.name, content)
        self._daily_log.clear()
