"""
PIXEL — Lead Frontend Engineer (The Face Builder)
Chamber 2 | Tokyo
Builds user-facing interfaces in TypeScript + React.
"""
from agents.base import BaseAgent
from models.schemas import TechnicalPlan, BuildArtifact


SYSTEM_PROMPT = """
You are PIXEL, Lead Frontend Engineer at AgentCompany.
Your persona: user-obsessed, zero ambiguous states, mobile-first.

You build interfaces that earn trust in the first 30 seconds.
Rules you always follow:
1. Mobile-first, then desktop.
2. Zero ambiguous UI states — the interface always tells the user what's happening.
3. Every error message tells the user what to do next, not just what went wrong.
4. No dead ends — every flow has a way out.
5. Sub-200ms interaction response for all primary actions.

Respond with implementation plans and component outlines.
""".strip()


class PIXEL(BaseAgent):
    name       = "PIXEL"
    role       = "Lead Frontend Engineer"
    department = "chamber2"
    emoji      = "🎨"

    def build_frontend(self, plan: TechnicalPlan, backend_artifact: BuildArtifact) -> BuildArtifact:
        routes_str = "\n".join([
            f"  {r.method} {r.path} — {r.description}"
            for r in plan.api_routes
        ])

        prompt = f"""
Product: {plan.product_name}
Backend files available: {', '.join(backend_artifact.files[:10])}

API routes to connect to:
{routes_str}

v1 scope: {', '.join(plan.v1_scope)}

Describe your frontend implementation:
1. Component structure (pages + shared components)
2. State management approach
3. How you handle loading states, errors, and empty states
4. Mobile-first breakpoints
5. How you connect to each backend API route

Return JSON:
{{
  "agent": "PIXEL",
  "description": "Summary of frontend implementation",
  "files": [
    "src/App.tsx",
    "src/pages/Dashboard.tsx",
    "src/components/Button.tsx"
  ],
  "notes": "Any UX decisions or concerns"
}}
""".strip()

        data = self.run_json(SYSTEM_PROMPT, prompt)
        artifact = BuildArtifact(
            agent="PIXEL",
            description=data.get("description", "Frontend implementation"),
            files=data.get("files", []),
            notes=data.get("notes", ""),
        )
        self.flush_daily_log()
        return artifact
