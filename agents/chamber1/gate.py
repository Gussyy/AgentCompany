"""
GATE — Chief Risk Officer (The Gatekeeper)
Chamber 1 | Zurich
Multi-dimensional composite scorer. Says no more than yes.
"""
from agents.base import BaseAgent
from models.schemas import (
    ProductBlueprint, FinancialModel, GateDecision,
    GateVerdict, GateScore
)
from config import GATE_COMPOSITE_THRESHOLD
from utils.logger import gate_decision as log_gate


SYSTEM_PROMPT = """
You are GATE, Chief Risk Officer at AgentCompany.
Your persona: ruthless, precise, zero sentimentality.

Your job is to score every product on four dimensions and issue a Go/Kill/Pivot decision.
You do NOT kill on margin alone. You use a composite score.

Scoring rubric (each dimension 0-10):
- margin_pct_score:          10 = >70% margin, 5 = 40-70%, 2 = 20-40%, 0 = <20%
- tam_score:                 10 = >$10B TAM, 7 = $1B-$10B, 4 = $100M-$1B, 1 = <$100M
- time_to_build_score:       10 = <2 weeks build, 7 = 2-6 weeks, 4 = 6-12 weeks, 1 = >12 weeks
- competitive_density_score: 10 = no competitors, 6 = few weak competitors, 3 = moderate, 0 = entrenched giants

Composite = (margin*0.30) + (tam*0.25) + (time_to_build*0.25) + (competitive*0.20)
Threshold for GO = 6.0

If KILL: project is dead. Provide reason.
If PIVOT: project redirected. Provide specific pivot_brief instruction.
If GO: project proceeds.

Always output valid JSON.
""".strip()


class GATE(BaseAgent):
    name       = "GATE"
    role       = "Chief Risk Officer"
    department = "chamber1"
    emoji      = "🚧"

    def evaluate(
        self,
        blueprint: ProductBlueprint,
        financials: FinancialModel,
        is_post_smoke_test: bool = False,
    ) -> GateDecision:

        stage = "POST-SMOKE TEST (real CAC data available)" if is_post_smoke_test else "PRE-SMOKE TEST (projections)"
        cac_line = (
            f"Real CAC (from Smoke Test): ${financials.real_cac_usd:.2f}"
            if financials.real_cac_usd else
            f"Projected CAC: ${financials.projected_cac_usd:.2f}"
        )

        prompt = f"""
Evaluation stage: {stage}

Product: {blueprint.product_name}
Value Prop: {blueprint.value_proposition}
Customer: {blueprint.customer_segment.name}

Financial snapshot:
- TAM: ${financials.tam_usd:,.0f}
- Build cost: ${financials.build_cost_usd:,.0f}
- {cac_line}
- Price per user: ${financials.price_per_user_usd}/mo
- Gross margin: {financials.gross_margin_pct}%
- Payback: {financials.payback_months} months
- ROI 12m: {financials.roi_12m_pct}%

Score this product on all four dimensions and issue your decision.
Composite threshold for GO = {GATE_COMPOSITE_THRESHOLD}

Return JSON:
{{
  "verdict": "GO"|"KILL"|"PIVOT",
  "score": {{
    "margin_pct_score": 7.5,
    "tam_score": 8.0,
    "time_to_build_score": 6.0,
    "competitive_density_score": 5.0,
    "composite_score": 6.7
  }},
  "reason": "Clear explanation of the decision",
  "pivot_brief": null
}}
""".strip()

        data = self.run_json(SYSTEM_PROMPT, prompt)
        try:
            score    = GateScore(**data["score"])
            decision = GateDecision(
                verdict=GateVerdict(data["verdict"]),
                score=score,
                reason=data.get("reason", ""),
                pivot_brief=data.get("pivot_brief"),
            )
        except Exception as e:
            raise ValueError(f"GATE decision parsing failed: {e}\nRaw: {data}")

        log_gate(decision.verdict.value, decision.reason)
        self.flush_daily_log()
        return decision
