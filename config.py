"""
Central configuration for AgentCompany.
All model choices, thresholds, and constants live here.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ── DeepSeek models ────────────────────────────────────────────
MODEL_CHAT     = "deepseek-chat"       # DeepSeek-V3 — general agents
MODEL_REASONER = "deepseek-reasoner"   # DeepSeek-R1 — analytical agents

# ── Agent → model mapping ──────────────────────────────────────
AGENT_MODELS = {
    "ARIA":   MODEL_CHAT,
    "NOVA":   MODEL_CHAT,       # high temperature for creativity
    "QUANT":  MODEL_REASONER,   # needs precise math reasoning
    "GATE":   MODEL_REASONER,   # strict logical scoring
    "ARCH":   MODEL_CHAT,
    "CORE":   MODEL_CHAT,
    "PIXEL":  MODEL_CHAT,
    "VIGIL":  MODEL_REASONER,   # security + logic
    "APEX":   MODEL_CHAT,
    "HAVEN":  MODEL_CHAT,
    "SENTRY": MODEL_CHAT,
    "LEDGER": MODEL_REASONER,
}

# ── Agent temperature settings ─────────────────────────────────
AGENT_TEMPERATURE = {
    "ARIA":   0.2,
    "NOVA":   0.6,   # divergent creative thinking
    "QUANT":  0.0,   # pure precision
    "GATE":   0.0,   # no creativity — strict scoring only
    "ARCH":   0.2,
    "CORE":   0.2,
    "PIXEL":  0.3,
    "VIGIL":  0.0,
    "APEX":   0.4,
    "HAVEN":  0.3,
    "SENTRY": 0.2,
    "LEDGER": 0.0,
}

AGENT_TOP_P = {
    "NOVA": 0.95,  # only NOVA gets non-default top_p
}

# ── Gate composite score thresholds ───────────────────────────
GATE_COMPOSITE_THRESHOLD = 6.0   # out of 10

# Weights for GATE scoring (must sum to 1.0)
GATE_WEIGHTS = {
    "margin_pct":          0.30,
    "tam_size":            0.25,
    "time_to_build":       0.25,
    "competitive_density": 0.20,
}

# ── Smoke Test thresholds ──────────────────────────────────────
SMOKE_TEST_CTR_THRESHOLD       = 0.02   # 2% click-through rate
SMOKE_TEST_CONVERSION_THRESHOLD = 0.01  # 1% Buy Now conversion

# ── Soft Launch thresholds ─────────────────────────────────────
SOFT_LAUNCH_DAY7_RETENTION = 0.30   # 30% day-7 retention
SOFT_LAUNCH_ACTIVATION     = 0.50   # 50% activation rate
SOFT_LAUNCH_NPS_THRESHOLD  = 20     # NPS ≥ 20

# ── VIGIL Definition of Done ───────────────────────────────────
DOD_COVERAGE_THRESHOLD = 80  # percent test coverage

# ── Notion integration ─────────────────────────────────────────
NOTION_API_KEY           = os.getenv("NOTION_API_KEY", "")
NOTION_TEAM_DIR_PAGE_ID  = "341f877e-9f0d-81b8-a2f1-ca4689928bc1"

# ── Logging paths ──────────────────────────────────────────────
import pathlib
BASE_DIR  = pathlib.Path(__file__).parent
LOGS_DIR  = BASE_DIR / "logs"
LOG_DIRS  = {
    "chamber1":   LOGS_DIR / "chamber1",
    "chamber2":   LOGS_DIR / "chamber2",
    "chamber3":   LOGS_DIR / "chamber3",
    "ceo_reports": LOGS_DIR / "ceo_reports",
    "sentinel":   LOGS_DIR / "sentinel",
}

for d in LOG_DIRS.values():
    d.mkdir(parents=True, exist_ok=True)
