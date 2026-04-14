"""
short_term_memory.py — Per-run vector memory for AgentCompany.

Each agent can store outputs here during a run. Other agents can query
semantically similar content from any previous agent in the same run.

Uses fastembed (ONNX, no GPU needed) for local embeddings and
numpy cosine similarity for retrieval.

Lifecycle:
  - Created once per run by the Orchestrator
  - All agents share the SAME instance per run
  - Automatically cleared when a new run starts

Example:
  ARIA stores: "Core pain point: notification overload wastes 47 min/day"
  NOVA queries for "user problem focus" → gets ARIA's finding back
  GATE queries for "risk factors" → gets relevant findings from all agents
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional
import numpy as np


# ── Embedding model (lazy-loaded on first use) ────────────────────────────────
_EMBED_MODEL = None
_MODEL_NAME  = "BAAI/bge-small-en-v1.5"   # ~130 MB, runs fully locally via ONNX


def _get_model():
    global _EMBED_MODEL
    if _EMBED_MODEL is None:
        from fastembed import TextEmbedding
        _EMBED_MODEL = TextEmbedding(model_name=_MODEL_NAME)
    return _EMBED_MODEL


def _embed(text: str) -> np.ndarray:
    model = _get_model()
    vecs = list(model.embed([text]))
    return np.array(vecs[0], dtype=np.float32)


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    na = np.linalg.norm(a)
    nb = np.linalg.norm(b)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


# ── Memory entry ──────────────────────────────────────────────────────────────
@dataclass
class MemoryEntry:
    agent:     str
    text:      str
    embedding: np.ndarray
    metadata:  dict = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self, include_embedding: bool = False) -> dict:
        d = {
            "agent":     self.agent,
            "text":      self.text[:400] + ("…" if len(self.text) > 400 else ""),
            "metadata":  self.metadata,
            "timestamp": self.timestamp,
        }
        if include_embedding:
            d["embedding_dim"] = len(self.embedding)
        return d


# ── Short-term store ──────────────────────────────────────────────────────────
class ShortTermMemory:
    """
    Shared in-run vector memory.
    One instance per run, injected into every agent by the Orchestrator.
    """

    def __init__(self):
        self._entries: list[MemoryEntry] = []
        self._embed_available = True

    # ── Write ─────────────────────────────────────────────────────────────────

    def store(self, agent: str, text: str, metadata: dict = None):
        """
        Store an agent's output as a vector embedding.
        Called automatically by BaseAgent after every successful LLM call.
        """
        if not text or not text.strip():
            return
        metadata = metadata or {}
        try:
            vec = _embed(text[:1000])   # embed first 1000 chars
        except Exception:
            # If embedding fails, store without vector (still searchable by agent)
            vec = np.zeros(384, dtype=np.float32)
            self._embed_available = False

        self._entries.append(MemoryEntry(
            agent=agent,
            text=text,
            embedding=vec,
            metadata=metadata,
        ))

    # ── Read ──────────────────────────────────────────────────────────────────

    def query(self, query_text: str, top_k: int = 3,
              exclude_agent: str = None, min_score: float = 0.3) -> list[dict]:
        """
        Retrieve the most semantically relevant entries for a query.
        Returns list of {agent, text, score, metadata}.
        """
        if not self._entries:
            return []

        candidates = [e for e in self._entries
                      if not exclude_agent or e.agent != exclude_agent]
        if not candidates:
            return []

        try:
            q_vec = _embed(query_text)
            scored = sorted(
                [{"entry": e, "score": _cosine(q_vec, e.embedding)}
                 for e in candidates],
                key=lambda x: x["score"],
                reverse=True,
            )
            results = []
            for s in scored[:top_k]:
                if s["score"] >= min_score:
                    d = s["entry"].to_dict()
                    d["score"] = round(s["score"], 3)
                    results.append(d)
            return results
        except Exception:
            # Fallback: return most recent entries without scoring
            return [e.to_dict() for e in reversed(candidates[-top_k:])]

    def get_by_agent(self, agent: str) -> list[dict]:
        """Get all entries from a specific agent."""
        return [e.to_dict() for e in self._entries if e.agent == agent]

    def get_all(self) -> list[dict]:
        """Get all entries (newest first)."""
        return [e.to_dict() for e in reversed(self._entries)]

    def build_context_for(self, agent: str, query: str, top_k: int = 4) -> str:
        """
        Build a formatted context string for injection into an agent's prompt.
        Retrieves top-k relevant memories from OTHER agents in this run.
        """
        results = self.query(query, top_k=top_k, exclude_agent=agent)
        if not results:
            return ""
        lines = ["[SHORT-TERM RUN MEMORY — relevant findings from this run:]"]
        for r in results:
            score_str = f" (relevance: {r['score']:.2f})" if 'score' in r else ""
            lines.append(f"• [{r['agent']}]{score_str}: {r['text'][:300]}")
        return "\n".join(lines)

    # ── Meta ──────────────────────────────────────────────────────────────────

    def stats(self) -> dict:
        agents = {}
        for e in self._entries:
            agents[e.agent] = agents.get(e.agent, 0) + 1
        return {
            "total_entries": len(self._entries),
            "embed_available": self._embed_available,
            "model": _MODEL_NAME,
            "by_agent": agents,
        }

    def clear(self):
        self._entries.clear()


# ── Global singleton (replaced each run by Orchestrator) ─────────────────────
current_run_memory: Optional[ShortTermMemory] = None


def get_run_memory() -> ShortTermMemory:
    global current_run_memory
    if current_run_memory is None:
        current_run_memory = ShortTermMemory()
    return current_run_memory


def new_run_memory() -> ShortTermMemory:
    """Call at the start of each run to get a fresh store."""
    global current_run_memory
    current_run_memory = ShortTermMemory()
    return current_run_memory
