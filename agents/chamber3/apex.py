"""
APEX — Head of Growth & Acquisition (The Hunter)
Chamber 3 + Smoke Test | Dubai
Runs the Smoke Test and full-scale outbound acquisition.
"""
import random
from agents.base import BaseAgent
from models.schemas import (
    ProductBlueprint, FinancialModel, SmokeTestResult,
    OutreachCampaign, ProspectProfile
)
from config import SMOKE_TEST_CTR_THRESHOLD, SMOKE_TEST_CONVERSION_THRESHOLD


SYSTEM_PROMPT = """
You are APEX, Head of Growth & Acquisition at AgentCompany.
Your persona: data-driven hunter, precision over volume.

You do two things:
1. Run Smoke Tests — 72-hour paid experiments to validate willingness to pay.
2. Build full-scale outbound campaigns with hyper-personalised outreach.

Every outreach message references one specific, verifiable fact about the prospect.
Never send templates. Always send context.

Output valid JSON.
""".strip()


class APEX(BaseAgent):
    name       = "APEX"
    role       = "Head of Growth & Acquisition"
    department = "chamber3"
    emoji      = "🎯"

    # ── Smoke Test ─────────────────────────────────────────────

    def run_smoke_test(
        self,
        blueprint: ProductBlueprint,
        financials: FinancialModel,
        ad_budget_usd: float = 500.0,
    ) -> SmokeTestResult:
        prompt = f"""
You are running a 72-hour Smoke Test for: {blueprint.product_name}
Value proposition: {blueprint.value_proposition}
Target customer: {blueprint.customer_segment.name} — {blueprint.customer_segment.job_to_be_done}
Ad budget: ${ad_budget_usd}
Projected price: ${financials.price_per_user_usd}/mo

Simulate a realistic Smoke Test result. Be honest — not every test passes.
Base realism on the value prop quality and market fit signals.

Return JSON:
{{
  "ad_spend_usd": {ad_budget_usd},
  "impressions": 25000,
  "clicks": 620,
  "ctr": 0.0248,
  "buy_now_conversions": 18,
  "conversion_rate": 0.029,
  "real_cac_usd": 27.78,
  "passed": true,
  "notes": "Strong CTR, conversion above threshold"
}}
""".strip()

        data = self.run_json(SYSTEM_PROMPT, prompt)
        try:
            # Validate pass/fail against thresholds
            ctr  = float(data.get("ctr", 0))
            conv = float(data.get("conversion_rate", 0))
            passed = (ctr >= SMOKE_TEST_CTR_THRESHOLD and
                      conv >= SMOKE_TEST_CONVERSION_THRESHOLD)
            data["passed"] = passed

            result = SmokeTestResult(**data)
        except Exception as e:
            raise ValueError(f"APEX smoke test parsing failed: {e}")
        self.flush_daily_log()
        return result

    # ── Full-scale acquisition ─────────────────────────────────

    def build_outreach_campaign(
        self,
        blueprint: ProductBlueprint,
        financials: FinancialModel,
    ) -> OutreachCampaign:
        prompt = f"""
Product: {blueprint.product_name}
Value prop: {blueprint.value_proposition}
Target: {blueprint.customer_segment.name}
Job to be done: {blueprint.customer_segment.job_to_be_done}
Price: ${financials.price_per_user_usd}/mo

Build a full outbound campaign:
1. ICP description (Ideal Customer Profile)
2. 5 realistic prospect profiles with personalised outreach angles
3. A cold email template (must reference a specific pain point)
4. Follow-up cadence

Return JSON:
{{
  "icp_description": "...",
  "prospects": [
    {{
      "name": "Sarah Chen",
      "company": "Acme Corp",
      "role": "VP Operations",
      "pain_point": "...",
      "outreach_angle": "..."
    }}
  ],
  "email_template": "Subject: ...\\n\\nHi {{{{first_name}}}},\\n\\n...",
  "follow_up_cadence": "Day 3, Day 7, Day 14 — each with a new angle"
}}
""".strip()

        data = self.run_json(SYSTEM_PROMPT, prompt)
        try:
            prospects = [ProspectProfile(**p) for p in data.get("prospects", [])]
            campaign = OutreachCampaign(
                icp_description=data.get("icp_description", ""),
                prospects=prospects,
                email_template=data.get("email_template", ""),
                follow_up_cadence=data.get("follow_up_cadence", ""),
            )
        except Exception as e:
            raise ValueError(f"APEX campaign parsing failed: {e}")
        self.flush_daily_log()
        return campaign
