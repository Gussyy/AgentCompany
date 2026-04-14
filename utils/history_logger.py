"""
history_logger.py — saves every completed run to history.json
"""
import json, os
from datetime import datetime
from pathlib import Path

HISTORY_PATH = Path(__file__).parent.parent / "data" / "history.json"


def _load() -> list:
    HISTORY_PATH.parent.mkdir(exist_ok=True)
    if not HISTORY_PATH.exists():
        return []
    try:
        return json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []


def save_run(result: dict, industry: str, ad_budget_usd: float = 500):
    """Append a completed run record to history.json."""
    runs = _load()

    daily = result.get("daily_report") or {}
    gate_scores = result.get("gate_scores") or {}
    fm = result.get("financial_model") or {}
    product = result.get("product_design") or {}
    token_usage = daily.get("token_usage") or {}

    # Determine overall outcome
    status = result.get("status", "unknown")
    passed = status == "complete"

    # Best composite score from any gate
    composite = None
    for v in gate_scores.values():
        if isinstance(v, dict):
            s = v.get("composite_score")
            if s is not None:
                composite = s
                break

    record = {
        "id": len(runs) + 1,
        "date": datetime.now().strftime("%Y-%m-%d"),
        "time": datetime.now().strftime("%H:%M"),
        "industry": industry,
        "status": status,
        "passed": passed,
        "product_name": product.get("name", "—"),
        "gate_composite": composite,
        "total_cost_usd": daily.get("total_spend_usd", 0) or token_usage.get("cost_usd", 0),
        "token_total": token_usage.get("total_tokens", 0),
        "token_calls": token_usage.get("total_calls", 0),
        "gross_margin_pct": fm.get("gross_margin_pct"),
        "tam_usd": fm.get("tam_usd"),
        "ad_budget_usd": ad_budget_usd,
        "action_items": daily.get("action_items", []),
    }
    runs.append(record)
    HISTORY_PATH.write_text(json.dumps(runs, indent=2, ensure_ascii=False), encoding="utf-8")
    return record


def get_history() -> list:
    return list(reversed(_load()))   # newest first


def get_analytics() -> dict:
    runs = _load()
    if not runs:
        return {"total_runs": 0, "pass_rate": 0, "total_cost": 0, "industries": []}

    total = len(runs)
    passed = sum(1 for r in runs if r.get("passed"))
    total_cost = sum(r.get("total_cost_usd", 0) for r in runs)
    avg_cost = total_cost / total if total else 0

    # Industry frequency
    from collections import Counter
    ind_counts = Counter(r.get("industry", "unknown") for r in runs)

    return {
        "total_runs": total,
        "passed": passed,
        "killed": total - passed,
        "pass_rate": round(passed / total * 100, 1),
        "total_cost": round(total_cost, 4),
        "avg_cost_per_run": round(avg_cost, 4),
        "industries": [{"industry": k, "count": v} for k, v in ind_counts.most_common(10)],
    }
