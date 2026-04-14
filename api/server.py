"""
FastAPI server — CEO Dashboard API
Endpoints: dashboard, run, status, events, history, analytics, settings, chat
"""
import json, queue, threading
from pathlib import Path
from typing import Generator

BASE_DIR = Path(__file__).parent.parent

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

from models.schemas import AgentEvent

app = FastAPI(title="AgentCompany CEO Dashboard API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ── Shared state ─────────────────────────────────────────────────────────────
_run_result: dict = {}
_run_status: str = "idle"
_last_industry: str = ""
_last_budget: float = 500.0

# â”€â”€ Fan-out SSE: each browser tab gets its own queue + replay buffer â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

# â”€â”€ Simple SSE: single queue, reliable delivery â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
import queue as _queue_mod
_event_queue = _queue_mod.Queue(maxsize=1000)

def push_event(evt: AgentEvent) -> None:
    try:
        _event_queue.put_nowait(evt.model_dump())
    except _queue_mod.Full:
        try:
            _event_queue.get_nowait()  # drop oldest
        except _queue_mod.Empty:
            pass
        _event_queue.put_nowait(evt.model_dump())


def _sse_generator() -> Generator[str, None, None]:
    while True:
        try:
            evt = _event_queue.get(timeout=20)
            yield f"data: {json.dumps(evt)}\n\n"
        except _queue_mod.Empty:
            yield 'data: {"event_type":"heartbeat"}\n\n'

@app.get("/events")
def stream_events():
    return StreamingResponse(
        _sse_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── Run trigger ──────────────────────────────────────────────────────────────
class RunRequest(BaseModel):
    industry: str
    ad_budget_usd: float = 500.0


@app.post("/run")
def start_run(req: RunRequest):
    global _run_status, _last_industry, _last_budget
    if _run_status == "running":
        return {"error": "A run is already in progress."}
    _run_status = "running"
    _last_industry = req.industry
    _last_budget = req.ad_budget_usd

    def _thread():
        global _run_status, _run_result
        from orchestrator import Orchestrator
        from utils.history_logger import save_run
        orch = Orchestrator(industry=req.industry, ad_budget_usd=req.ad_budget_usd, event_callback=push_event)
        result = orch.run()
        _run_result = result
        _run_status = result.get("status", "done")
        try:
            save_run(result, req.industry, req.ad_budget_usd)
        except Exception:
            pass

    threading.Thread(target=_thread, daemon=True).start()
    return {"message": f"Run started for: {req.industry}"}


@app.get("/status")
def get_status():
    return {"status": _run_status, "result": _run_result}


# ── CEO Chat ─────────────────────────────────────────────────────────────────
class ChatRequest(BaseModel):
    message: str
    ad_budget_usd: float = 500.0


@app.post("/chat")
def ceo_chat(req: ChatRequest):
    """
    CEO sends a natural-language message. We parse intent:
      - "@AGENT message"  -> run that specific agent with the message as context
      - "Run X industry"  -> trigger a full run for industry X
      - "Analyse X"       -> trigger a full run for X
      - Anything else     -> trigger a full run with message as industry/context
    """
    global _run_status
    if _run_status == "running":
        return {"error": "A run is already in progress. Wait for it to finish."}

    msg = req.message.strip()
    import re

    # Detect "@AGENT directive"
    agent_match = re.match(r"@([A-Z0-9\-]+)[:\s]+(.+)", msg, re.IGNORECASE)
    if agent_match:
        target_agent = agent_match.group(1).upper()
        directive = agent_match.group(2).strip()
        return _run_chat_task(directive, req.ad_budget_usd, ceo_directive=msg, target_agent=target_agent)

    # Detect "run X" or "analyse X" or "analyse X" or "create X"
    run_match = re.match(r"(?:run|analyse|analyze|create|build|research|explore)[:\s]+(.+)", msg, re.IGNORECASE)
    if run_match:
        industry_or_task = run_match.group(1).strip()
        return _run_chat_task(industry_or_task, req.ad_budget_usd, ceo_directive=msg)

    # Default: treat message as industry/task description
    return _run_chat_task(msg, req.ad_budget_usd, ceo_directive=msg)


def _run_chat_task(industry: str, budget: float, ceo_directive: str = "", target_agent: str = None):
    global _run_status, _last_industry, _last_budget
    _run_status = "running"
    _last_industry = industry
    _last_budget = budget

    def _thread():
        global _run_status, _run_result
        from orchestrator import Orchestrator
        from utils.history_logger import save_run
        orch = Orchestrator(
            industry=industry,
            ad_budget_usd=budget,
            event_callback=push_event,
            ceo_directive=ceo_directive,
            target_agent=target_agent,
        )
        result = orch.run()
        _run_result = result
        _run_status = result.get("status", "done")
        try:
            save_run(result, industry, budget)
        except Exception:
            pass

    threading.Thread(target=_thread, daemon=True).start()
    return {"message": f"Task started: {industry}", "directive": ceo_directive}


# ── History ──────────────────────────────────────────────────────────────────
@app.get("/history")
def get_history():
    from utils.history_logger import get_history
    return {"runs": get_history()}


@app.get("/analytics")
def get_analytics():
    from utils.history_logger import get_analytics
    return get_analytics()


# ── Settings ─────────────────────────────────────────────────────────────────
@app.get("/settings")
def get_settings():
    from utils.settings_manager import load
    return load()


class SettingsPatch(BaseModel):
    gate_pass_threshold: Optional[float] = None
    daily_budget_usd: Optional[float] = None
    default_ad_budget_usd: Optional[float] = None
    default_industry: Optional[str] = None
    notion_enabled: Optional[bool] = None
    ceo_name: Optional[str] = None
    agent_models: Optional[dict] = None


@app.post("/settings")
def update_settings(patch: SettingsPatch):
    from utils.settings_manager import update
    data = {k: v for k, v in patch.model_dump().items() if v is not None}
    return update(data)


# ── Agent Memory ─────────────────────────────────────────────────────────────
AGENTS = ["SENTRY","ARIA","NOVA","QUANT","GATE","LEDGER",
          "ARCH","PIXEL","CORE","VIGIL","APEX","HAVEN","ORCA-1"]

@app.get("/memory")
def all_memory_stats():
    """Return node/edge counts for every agent's memory graph + short-term stats."""
    from utils.agent_memory import AgentMemoryGraph
    from utils.short_term_memory import get_run_memory
    result = []
    for name in AGENTS:
        try:
            g = AgentMemoryGraph(name)
            s = g.stats()
            g.close()
            result.append(s)
        except Exception as e:
            result.append({"agent": name, "nodes": 0, "edges": 0, "error": str(e)})
    # Short-term memory stats for the current run
    stm = get_run_memory()
    stm_stats = stm.stats() if stm else {"total_entries": 0}
    return {"agents": result, "short_term": stm_stats}

@app.get("/memory/{agent_name}")
def agent_memory(agent_name: str):
    """Return the full knowledge graph for one agent."""
    from utils.agent_memory import AgentMemoryGraph
    try:
        g = AgentMemoryGraph(agent_name.upper())
        data = g.get_full_graph()
        g.close()
        return data
    except Exception as e:
        return JSONResponse(status_code=404, content={"error": str(e)})

@app.delete("/memory/{agent_name}")
def clear_agent_memory(agent_name: str):
    """Wipe an agent's memory graph (fresh start)."""
    from pathlib import Path
    db = Path(BASE_DIR) / "data" / "memory" / f"{agent_name.upper()}.db"
    if db.exists():
        db.unlink()
        return {"message": f"{agent_name} memory cleared."}
    return {"message": "No memory found."}


# ── Kaggle / DataScience Chamber ─────────────────────────────────────────────
_kaggle_result: dict = {}
_kaggle_status: str  = "idle"

class KaggleRequest(BaseModel):
    competition_slug: Optional[str] = None   # None = let SCOUT choose
    target_type:      str = "tabular"        # tabular, nlp, image


@app.post("/kaggle/run")
def run_kaggle(req: KaggleRequest):
    global _kaggle_status, _kaggle_result
    if _kaggle_status == "running":
        return {"error": "A Kaggle run is already in progress."}
    _kaggle_status = "running"

    def _thread():
        global _kaggle_status, _kaggle_result
        from chambers.kaggle.kaggle_chamber import KaggleChamber
        chamber = KaggleChamber(
            event_callback    = push_event,
            target_type       = req.target_type,
            competition_slug  = req.competition_slug,
        )
        result = chamber.run()
        _kaggle_result = result
        _kaggle_status = result.get("status", "done")

    threading.Thread(target=_thread, daemon=True).start()
    return {"message": "Kaggle run started", "competition": req.competition_slug or "auto-select"}


@app.get("/kaggle/status")
def kaggle_status():
    return {"status": _kaggle_status, "result": _kaggle_result}


@app.get("/kaggle/competitions")
def list_kaggle_competitions():
    """List downloaded competitions (data on disk)."""
    from utils.code_executor import KAGGLE_DIR
    if not KAGGLE_DIR.exists():
        return {"competitions": []}
    comps = []
    for d in KAGGLE_DIR.iterdir():
        if d.is_dir():
            csvs = list(d.glob("*.csv"))
            comps.append({
                "slug":       d.name,
                "files":      [f.name for f in csvs],
                "has_submission": (d / "submission.csv").exists(),
            })
    return {"competitions": comps}


# ── Dashboard HTML ────────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
def dashboard():
    html_path = BASE_DIR / "frontend" / "dashboard.html"
    with open(html_path, "r", encoding="utf-8") as f:
        return f.read()

# â”€â”€ Stop + Mid-run CEO Comments â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
_stop_requested: bool = False
_ceo_comments: list = []   # mid-run messages injected between agents

@app.post("/stop")
def stop_run():
    global _stop_requested
    _stop_requested = True
    return {"message": "Stop requested â€” current agent will finish then run will halt."}

@app.post("/comment")
def add_comment(req: ChatRequest):
    """Inject a CEO comment/directive into the currently running pipeline."""
    global _ceo_comments
    _ceo_comments.append(req.message)
    push_event(AgentEvent(
        event_type="ceo_action", agent_name="YOU (CEO)", chamber="ceo",
        status=__import__("models.schemas", fromlist=["AgentStatus"]).AgentStatus("running"),
        message=f"ðŸ’¬ CEO comment injected: {req.message}", data={"type": "mid_run_comment"}
    ))
    return {"message": "Comment added to pipeline", "queue_length": len(_ceo_comments)}

@app.get("/stop/status")
def stop_status():
    return {"stop_requested": _stop_requested, "pending_comments": _ceo_comments}

@app.post("/stop/reset")
def reset_stop():
    global _stop_requested, _ceo_comments
    _stop_requested = False
    _ceo_comments = []
    return {"message": "Stop flag and comments cleared"}



