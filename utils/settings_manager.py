"""
settings_manager.py — read/write UI-editable settings from data/settings.json
Falls back to config.py defaults if settings.json doesn't exist yet.
"""
import json
from pathlib import Path

SETTINGS_PATH = Path(__file__).parent.parent / "data" / "settings.json"

DEFAULTS = {
    "gate_pass_threshold": 6.0,
    "daily_budget_usd": 1000,
    "default_ad_budget_usd": 500,
    "default_industry": "productivity tools",
    "agent_models": {
        "SENTRY": "deepseek-chat",
        "ARIA":   "deepseek-chat",
        "NOVA":   "deepseek-chat",
        "QUANT":  "deepseek-chat",
        "GATE":   "deepseek-reasoner",
        "LEDGER": "deepseek-chat",
        "ARCH":   "deepseek-chat",
        "PIXEL":  "deepseek-chat",
        "CORE":   "deepseek-chat",
        "VIGIL":  "deepseek-chat",
        "APEX":   "deepseek-chat",
        "HAVEN":  "deepseek-chat",
        "ORCA-1": "deepseek-chat",
    },
    "notion_enabled": True,
    "ceo_name": "Rachata P.",
}


def load() -> dict:
    SETTINGS_PATH.parent.mkdir(exist_ok=True)
    if not SETTINGS_PATH.exists():
        save(DEFAULTS.copy())
        return DEFAULTS.copy()
    try:
        saved = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
        # Merge with defaults so new keys always exist
        merged = {**DEFAULTS, **saved}
        merged["agent_models"] = {**DEFAULTS["agent_models"], **saved.get("agent_models", {})}
        return merged
    except Exception:
        return DEFAULTS.copy()


def save(settings: dict):
    SETTINGS_PATH.parent.mkdir(exist_ok=True)
    SETTINGS_PATH.write_text(json.dumps(settings, indent=2, ensure_ascii=False), encoding="utf-8")


def update(patch: dict):
    current = load()
    if "agent_models" in patch and isinstance(patch["agent_models"], dict):
        current["agent_models"] = {**current.get("agent_models", {}), **patch["agent_models"]}
        patch = {k: v for k, v in patch.items() if k != "agent_models"}
    current.update(patch)
    save(current)
    return current
