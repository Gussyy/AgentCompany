"""
QUANT — Head of Financial Intelligence (The Accountant)
Chamber 1 | New York
Runs the numbers. Median-case assumptions. Explicit projections vs actuals.
"""
from agents.base import BaseAgent
from models.schemas import ProductBlueprint, FinancialModel, SmokeTestResult


SYSTEM_PROMPT = """
You are QUANT, Head of Financial Intelligence at AgentCompany.
Your persona: numbers-first, no optimistic bias, median-case assumptions.

You model the financial viability of product ideas with precision.
Pre-Smoke Test numbers are projections — you label them explicitly.
Post-Smoke Test, you update with real acquisition data.

You always stress-test the downside: what if CAC is 2x higher and conversion is 30% lower?

Always output valid JSON.
""".strip()


class QUANT(BaseAgent):
    name       = "QUANT"
    role       = "Head of Financial Intelligence"
    department = "chamber1"
    emoji      = "🧮"

    def model_financials(self, blueprint: ProductBlueprint) -> FinancialModel:
        features = "\n".join([f"- {f.name}: {f.description}" for f in blueprint.mvp_features])

        prompt = f"""
Product: {blueprint.product_name}
Value Prop: {blueprint.value_proposition}
Customer: {blueprint.customer_segment.name} — {blueprint.customer_segment.job_to_be_done}
Decision speed: {blueprint.customer_segment.decision_speed}
MVP features:
{features}

Model the financial viability. Use realistic median-case assumptions.
All numbers are PROJECTIONS at this stage (pre-Smoke Test).

Return JSON:
{{
  "tam_usd": 5000000000,
  "build_cost_usd": 80000,
  "projected_cac_usd": 120,
  "real_cac_usd": null,
  "price_per_user_usd": 49,
  "monthly_revenue_target": 50000,
  "gross_margin_pct": 72.5,
  "payback_months": 3,
  "roi_12m_pct": 180,
  "is_post_smoke_test": false,
  "notes": "Assumptions: SaaS B2B pricing, 12-month payback horizon, 30% churn stress test applied"
}}
""".strip()

        data = self.run_json(SYSTEM_PROMPT, prompt)
        data["is_post_smoke_test"] = False
        try:
            model = FinancialModel(**data)
        except Exception as e:
            raise ValueError(f"QUANT model parsing failed: {e}")
        self.flush_daily_log()
        return model

    def update_with_smoke_test(
        self, original: FinancialModel, smoke_result: SmokeTestResult
    ) -> FinancialModel:
        prompt = f"""
Original financial model (projections):
- Projected CAC: ${original.projected_cac_usd}
- Gross margin: {original.gross_margin_pct}%
- Price per user: ${original.price_per_user_usd}
- TAM: ${original.tam_usd:,.0f}

Smoke Test results (REAL DATA):
- Ad spend: ${smoke_result.ad_spend_usd}
- Impressions: {smoke_result.impressions:,}
- Clicks: {smoke_result.clicks:,}
- CTR: {smoke_result.ctr:.2%}
- Buy Now conversions: {smoke_result.buy_now_conversions}
- Conversion rate: {smoke_result.conversion_rate:.2%}
- Real CAC: ${smoke_result.real_cac_usd:.2f}

Update the financial model with real CAC data.
Recalculate payback_months, roi_12m_pct, and gross_margin_pct.
Mark is_post_smoke_test as true.

Return the same JSON structure with updated values.
""".strip()

        data = self.run_json(SYSTEM_PROMPT, prompt)
        data["real_cac_usd"]       = smoke_result.real_cac_usd
        data["is_post_smoke_test"] = True
        try:
            updated = FinancialModel(**data)
        except Exception:
            # Patch the original model with real CAC if parsing fails
            updated = original.model_copy(update={
                "real_cac_usd": smoke_result.real_cac_usd,
                "is_post_smoke_test": True,
            })
        self.flush_daily_log()
        return updated
