"""
LEDGER — Chief Financial Officer
Always On | Zurich
Tracks all real spend, burn rate, revenue, and produces daily CEO reports.
"""
import json
from agents.base import BaseAgent
from utils.token_tracker import token_tracker
from datetime import date


SYSTEM_PROMPT = """
You are LEDGER, CFO at AgentCompany.
Your persona: financial ground truth, no rounding, no optimism.

You track actual spend vs projected, per agent and per product track.
You reconcile QUANT's projections against reality after every cycle.
You fire Yellow/Red alerts immediately — not on the morning dashboard.

You now receive real token usage data from every DeepSeek API call made
during the run. Use this to calculate exact compute/API costs.

Output valid JSON.
""".strip()


class LEDGER(BaseAgent):
    name       = "LEDGER"
    role       = "Chief Financial Officer"
    department = "chamber1"
    emoji      = "📊"

    def generate_daily_report(self, run_context: dict) -> dict:
        """
        Generates a structured daily financial report from the run context.
        Includes real token usage and API cost data from token_tracker.
        """
        # Pull live token usage data from the singleton tracker
        token_summary = token_tracker.summary()

        # Build a readable per-agent token table for the prompt
        agent_rows = ""
        for agent, stats in token_summary.get("per_agent", {}).items():
            agent_rows += (
                f"  {agent}: {stats['calls']} call(s), "
                f"{stats['total_tokens']:,} tokens "
                f"(prompt={stats['prompt_tokens']:,}, "
                f"completion={stats['completion_tokens']:,}"
                + (f", reasoning={stats['reasoning_tokens']:,}" if stats.get("reasoning_tokens") else "")
                + f"), cost=${stats['cost_usd']:.6f}\n"
            )

        model_rows = ""
        for model, stats in token_summary.get("per_model", {}).items():
            model_rows += (
                f"  {model}: {stats['calls']} call(s), "
                f"{stats['total_tokens']:,} tokens, "
                f"cost=${stats['cost_usd']:.6f}\n"
            )

        prompt = f"""
Today's date: {date.today().isoformat()}

=== REAL TOKEN USAGE (from DeepSeek API responses) ===
Total API calls:          {token_summary['total_calls']}
Total prompt tokens:      {token_summary['total_prompt_tokens']:,}
Total completion tokens:  {token_summary['total_completion_tokens']:,}
Total reasoning tokens:   {token_summary['total_reasoning_tokens']:,}
Total tokens:             {token_summary['total_tokens']:,}
Total compute cost (USD): ${token_summary['total_cost_usd']:.6f}

Per-agent breakdown:
{agent_rows if agent_rows else '  (no calls recorded)'}

Per-model breakdown:
{model_rows if model_rows else '  (no calls recorded)'}

=== RUN CONTEXT ===
{json.dumps(run_context, indent=2, default=str)}

Generate the CEO's daily financial report with:
1. Total spend today broken down by: compute_api (from real token data above),
   marketing_ads (smoke test budget from run context), infrastructure
2. Revenue (if any product is live)
3. Burn rate vs target
4. Budget ceiling alerts (Yellow=80%, Red=100% of $1000 daily budget)
5. Per-product P&L if applicable
6. Token efficiency insight: cost per agent call, most expensive agent
7. Action items for CEO (specific, actionable)

Return JSON exactly matching this structure:
{{
  "date": "{date.today().isoformat()}",
  "total_spend_usd": 0.00,
  "revenue_usd": 0.0,
  "burn_rate_daily_usd": 0.00,
  "budget_alerts": [],
  "per_product_pnl": {{}},
  "spend_breakdown": {{
    "compute_api": {token_summary['total_cost_usd']:.6f},
    "marketing_ads": 0.0,
    "infrastructure": 0.0
  }},
  "token_usage": {{
    "total_calls": {token_summary['total_calls']},
    "total_tokens": {token_summary['total_tokens']},
    "total_prompt_tokens": {token_summary['total_prompt_tokens']},
    "total_completion_tokens": {token_summary['total_completion_tokens']},
    "total_reasoning_tokens": {token_summary['total_reasoning_tokens']},
    "cost_usd": {token_summary['total_cost_usd']:.6f},
    "most_expensive_agent": "",
    "cost_per_call_usd": 0.0,
    "per_agent": {{}}
  }},
  "action_items": [],
  "summary": ""
}}
""".strip()

        data = self.run_json(SYSTEM_PROMPT, prompt)

        # Ensure token_usage block is always accurate (overwrite LLM guesses with real data)
        data["token_usage"] = {
            "total_calls":             token_summary["total_calls"],
            "total_tokens":            token_summary["total_tokens"],
            "total_prompt_tokens":     token_summary["total_prompt_tokens"],
            "total_completion_tokens": token_summary["total_completion_tokens"],
            "total_reasoning_tokens":  token_summary["total_reasoning_tokens"],
            "cost_usd":                token_summary["total_cost_usd"],
            "cost_per_call_usd":       round(
                token_summary["total_cost_usd"] / token_summary["total_calls"], 6
            ) if token_summary["total_calls"] > 0 else 0.0,
            "most_expensive_agent":    max(
                token_summary["per_agent"],
                key=lambda a: token_summary["per_agent"][a]["cost_usd"],
                default="N/A"
            ) if token_summary["per_agent"] else "N/A",
            "per_agent":               token_summary["per_agent"],
            "per_model":               token_summary["per_model"],
            "all_calls":               token_summary["calls"],
        }

        # Also fix compute_api spend to match real token cost
        if "spend_breakdown" in data:
            data["spend_breakdown"]["compute_api"] = token_summary["total_cost_usd"]

        self.flush_daily_log()
        return data
