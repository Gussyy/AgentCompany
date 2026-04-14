"""
HAVEN — Head of Customer Success (The Caretaker)
Chamber 3 | Amsterdam
Monitors Soft Launch cohort, classifies feedback, triggers the Loop.
"""
from agents.base import BaseAgent
from models.schemas import (
    ProductBlueprint, SoftLaunchMetrics, LoopFeedback,
    LoopClassification, FeedbackItem
)
from config import (
    SOFT_LAUNCH_DAY7_RETENTION,
    SOFT_LAUNCH_ACTIVATION,
    SOFT_LAUNCH_NPS_THRESHOLD,
)


SYSTEM_PROMPT = """
You are HAVEN, Head of Customer Success at AgentCompany.
Your persona: empathetic listener, ruthless classifier, feedback router.

You monitor customers after the sale and translate their experience into
actionable intelligence for the Loop.

The Loop has three re-entry points:
- CRITICAL_BUG: core functionality broken → direct to VIGIL → CORE/PIXEL
- FEATURE_IMPROVEMENT: users want something better → lightweight GATE → Chamber 2
- STRATEGIC_PIVOT: core assumption wrong → full Chamber 1 restart via ARIA

You never route ambiguously. Every piece of feedback gets a classification.
Output valid JSON.
""".strip()


class HAVEN(BaseAgent):
    name       = "HAVEN"
    role       = "Head of Customer Success"
    department = "chamber3"
    emoji      = "🤝"

    def monitor_soft_launch(
        self,
        blueprint: ProductBlueprint,
        cohort_size: int = 50,
    ) -> SoftLaunchMetrics:
        prompt = f"""
Product: {blueprint.product_name}
Value prop: {blueprint.value_proposition}
Customer: {blueprint.customer_segment.name}
Soft Launch cohort: {cohort_size} users, 2-week monitoring period.

Simulate realistic Soft Launch metrics. Be honest about issues.
A good product should show 30%+ day-7 retention, 50%+ activation, NPS ≥ 20.

Return JSON:
{{
  "cohort_size": {cohort_size},
  "day7_retention_rate": 0.38,
  "activation_rate": 0.62,
  "nps": 34,
  "top_complaints": ["Onboarding is confusing", "Missing export feature"],
  "top_praises": ["Saves so much time", "Dashboard is clean"],
  "passed": true,
  "recommendation": "Ready for full scale — address onboarding friction in next cycle"
}}
""".strip()

        data = self.run_json(SYSTEM_PROMPT, prompt)
        try:
            # Validate pass/fail against thresholds
            ret_ok  = data.get("day7_retention_rate", 0) >= SOFT_LAUNCH_DAY7_RETENTION
            act_ok  = data.get("activation_rate", 0) >= SOFT_LAUNCH_ACTIVATION
            nps_ok  = data.get("nps", 0) >= SOFT_LAUNCH_NPS_THRESHOLD
            passed  = ret_ok and act_ok and nps_ok
            data["passed"] = passed

            metrics = SoftLaunchMetrics(**data)
        except Exception as e:
            raise ValueError(f"HAVEN soft launch parsing failed: {e}")
        self.flush_daily_log()
        return metrics

    def classify_feedback(
        self,
        feedback_raw: list[str],
        product_name: str,
    ) -> LoopFeedback:
        feedback_str = "\n".join([f"- {f}" for f in feedback_raw])

        prompt = f"""
Product: {product_name}
Customer feedback received:
{feedback_str}

Classify this feedback and determine the correct Loop re-entry:
- CRITICAL_BUG: product is broken, users can't complete core actions
- FEATURE_IMPROVEMENT: product works but users want improvements
- STRATEGIC_PIVOT: core assumption was wrong, users want something fundamentally different

Return JSON:
{{
  "feedback_items": [
    {{
      "source": "support_email",
      "content": "...",
      "sentiment": "negative"
    }}
  ],
  "classification": "FEATURE_IMPROVEMENT",
  "priority_request": "Specific change request description",
  "route_description": "Routed to lightweight GATE → Chamber 2 rebuild cycle"
}}
""".strip()

        data = self.run_json(SYSTEM_PROMPT, prompt)
        try:
            items = [FeedbackItem(**f) for f in data.get("feedback_items", [])]
            loop = LoopFeedback(
                feedback_items=items,
                classification=LoopClassification(data["classification"]),
                priority_request=data.get("priority_request", ""),
                route_description=data.get("route_description", ""),
            )
        except Exception as e:
            raise ValueError(f"HAVEN feedback parsing failed: {e}")
        self.flush_daily_log()
        return loop
