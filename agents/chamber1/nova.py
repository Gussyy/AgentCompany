"""
NOVA — Head of Product Strategy (The Inventor)
Chamber 1 | Berlin
Turns friction data into a product blueprint.
Temperature 0.6 / top_p 0.95 for divergent ideation.
"""
from agents.base import BaseAgent
from models.schemas import FrictionReport, ProductBlueprint, CustomerSegment, MVPFeature


SYSTEM_PROMPT = """
You are NOVA, Head of Product Strategy at AgentCompany.
Your persona: non-obvious thinker, constraint-first designer.

You take a friction report and design the sharpest possible MVP —
not the biggest version of a product, but the minimum proof that it's worth building.

Rules you always follow:
1. One value proposition. One customer. One core problem.
2. MVP features list must include ONLY what proves the core promise.
3. 'Explicitly out of scope' must be as detailed as the feature list.
4. Diverge before converging — consider non-obvious angles.

Always output valid JSON.
""".strip()


class NOVA(BaseAgent):
    name       = "NOVA"
    role       = "Head of Product Strategy"
    department = "chamber1"
    emoji      = "💡"

    def design_blueprint(self, friction_report: FrictionReport) -> ProductBlueprint:
        friction_summary = "\n".join([
            f"- {fp.title} (severity {fp.severity}/10, WTP: {fp.willingness_to_pay}): {fp.description}"
            for fp in friction_report.friction_points
        ])

        prompt = f"""
Industry: {friction_report.industry}
Top opportunity: {friction_report.top_opportunity}

Friction points identified:
{friction_summary}

Design an MVP product that solves the highest-value friction point.
Be specific and non-obvious. Avoid copying what already exists.

Return JSON:
{{
  "product_name": "...",
  "value_proposition": "One sentence: who it helps, what it does, why it's different",
  "customer_segment": {{
    "name": "...",
    "description": "...",
    "job_to_be_done": "...",
    "decision_speed": "fast|medium|slow"
  }},
  "mvp_features": [
    {{"name": "...", "description": "...", "priority": 1}}
  ],
  "explicitly_out_of_scope": ["Feature X", "Integration Y"],
  "friction_addressed": "Which friction point this primarily solves"
}}
""".strip()

        data = self.run_json(SYSTEM_PROMPT, prompt)
        try:
            segment  = CustomerSegment(**data["customer_segment"])
            features = [MVPFeature(**f) for f in data.get("mvp_features", [])]
            blueprint = ProductBlueprint(
                product_name=data["product_name"],
                value_proposition=data["value_proposition"],
                customer_segment=segment,
                mvp_features=features,
                explicitly_out_of_scope=data.get("explicitly_out_of_scope", []),
                friction_addressed=data.get("friction_addressed", ""),
            )
        except Exception as e:
            raise ValueError(f"NOVA blueprint parsing failed: {e}\nRaw: {data}")
        self.flush_daily_log()
        return blueprint
