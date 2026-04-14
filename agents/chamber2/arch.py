"""
ARCH — Principal Systems Architect (The Blueprint Maker)
Chamber 2 | Toronto
Turns approved product blueprints into technical execution plans.
"""
from agents.base import BaseAgent
from models.schemas import ProductBlueprint, TechnicalPlan, DatabaseTable, APIRoute


SYSTEM_PROMPT = """
You are ARCH, Principal Systems Architect at AgentCompany.
Your persona: dependency-first, zero ambiguity, scope-enforcing.

You translate approved product blueprints into technical execution plans.
Rules you always follow:
1. Map every dependency before writing a single schema.
2. Define exactly what is in v1 scope and what is deferred.
3. Every API route has an input/output contract.
4. No scope creep — build only what was approved.

Always output valid JSON.
""".strip()


class ARCH(BaseAgent):
    name       = "ARCH"
    role       = "Principal Systems Architect"
    department = "chamber2"
    emoji      = "📐"

    def create_technical_plan(self, blueprint: ProductBlueprint) -> TechnicalPlan:
        features = "\n".join([
            f"- P{f.priority}: {f.name} — {f.description}"
            for f in blueprint.mvp_features
        ])
        out_of_scope = "\n".join([f"- {s}" for s in blueprint.explicitly_out_of_scope])

        prompt = f"""
Approved product: {blueprint.product_name}
Value prop: {blueprint.value_proposition}
Customer: {blueprint.customer_segment.name}

MVP features (P1=must, P2=should, P3=nice):
{features}

Explicitly out of scope for v1:
{out_of_scope}

Create a technical execution plan.

Return JSON:
{{
  "product_name": "{blueprint.product_name}",
  "tech_stack": {{
    "backend": "Python/FastAPI",
    "database": "PostgreSQL",
    "frontend": "React + TypeScript",
    "hosting": "Railway or Render"
  }},
  "database_tables": [
    {{
      "name": "users",
      "columns": ["id", "email", "created_at"],
      "indexes": ["email"]
    }}
  ],
  "api_routes": [
    {{
      "method": "POST",
      "path": "/api/auth/signup",
      "description": "User registration",
      "auth_required": false
    }}
  ],
  "dependencies": ["PostgreSQL", "SendGrid", "Stripe"],
  "v1_scope": ["Feature A", "Feature B"],
  "deferred_to_v2": ["Feature C"]
}}
""".strip()

        data = self.run_json(SYSTEM_PROMPT, prompt)
        try:
            tables = [DatabaseTable(**t) for t in data.get("database_tables", [])]
            routes = [APIRoute(**r) for r in data.get("api_routes", [])]
            plan = TechnicalPlan(
                product_name=data["product_name"],
                tech_stack=data.get("tech_stack", {}),
                database_tables=tables,
                api_routes=routes,
                dependencies=data.get("dependencies", []),
                v1_scope=data.get("v1_scope", []),
                deferred_to_v2=data.get("deferred_to_v2", []),
            )
        except Exception as e:
            raise ValueError(f"ARCH plan parsing failed: {e}")
        self.flush_daily_log()
        return plan
