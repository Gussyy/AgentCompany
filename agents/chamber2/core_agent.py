"""
CORE — Lead Backend Engineer (The Brains Builder)
Chamber 2 | Austin
Builds server-side logic, databases, and APIs from ARCH's plan.
"""
from agents.base import BaseAgent
from models.schemas import TechnicalPlan, BuildArtifact


SYSTEM_PROMPT = """
You are CORE, Lead Backend Engineer at AgentCompany.
Your persona: precise, no improvisation, follows ARCH's plan exactly.

You implement backend systems: APIs, database schemas, business logic, authentication.
Rules you always follow:
1. Build only what ARCH specified. No scope creep.
2. Every function has a corresponding unit test description.
3. If you disagree with an architectural decision, flag it — don't work around it silently.
4. Always note which files you would create.

Respond with implementation plans and code outlines.
""".strip()


class CORE(BaseAgent):
    name       = "CORE"
    role       = "Lead Backend Engineer"
    department = "chamber2"
    emoji      = "⚡"

    def build_backend(self, plan: TechnicalPlan) -> BuildArtifact:
        tables_str = "\n".join([
            f"  Table '{t.name}': {', '.join(t.columns)}"
            for t in plan.database_tables
        ])
        routes_str = "\n".join([
            f"  {r.method} {r.path} — {r.description} (auth: {r.auth_required})"
            for r in plan.api_routes
        ])
        deps_str = ", ".join(plan.dependencies)

        prompt = f"""
Product: {plan.product_name}
Tech stack: {plan.tech_stack}
Dependencies: {deps_str}

Database tables to implement:
{tables_str}

API routes to implement:
{routes_str}

v1 scope: {', '.join(plan.v1_scope)}

Describe your backend implementation in detail:
1. File structure you will create
2. Key implementation decisions for each API route
3. Database setup approach
4. Authentication mechanism
5. Unit tests you will write for each module

Return JSON:
{{
  "agent": "CORE",
  "description": "Summary of backend implementation",
  "files": [
    "main.py",
    "models/user.py",
    "routers/auth.py",
    "tests/test_auth.py"
  ],
  "notes": "Any flags or concerns about the architecture"
}}
""".strip()

        data = self.run_json(SYSTEM_PROMPT, prompt)
        artifact = BuildArtifact(
            agent="CORE",
            description=data.get("description", "Backend implementation"),
            files=data.get("files", []),
            notes=data.get("notes", ""),
        )
        self.flush_daily_log()
        return artifact


    def generate_code(self, plan, build_artifact, project_root) -> dict:
        """
        Generate actual Python code files for the backend.
        Writes real .py files to project_root/src/backend/CODE/
        Returns dict of {filename: code_content}.
        """
        from pathlib import Path
        code_dir = Path(project_root) / "src" / "backend" / "CODE"
        code_dir.mkdir(parents=True, exist_ok=True)

        # Ask the LLM to generate the main entry point + models
        key_files = ["main.py", "database.py"]
        for route in (plan.api_routes or [])[:3]:
            key_files.append(f"routers/{route.path.split('/')[2] if len(route.path.split('/')) > 2 else 'api'}.py")

        stack = getattr(plan, 'tech_stack', {})
        tables_str = "\n".join([f"  - {t.name}: {', '.join(t.columns)}"
                                   for t in (plan.database_tables or [])])
        routes_str = "\n".join([f"  - {r.method} {r.path}: {r.description}"
                                   for r in (plan.api_routes or [])])

        code_prompt = f"""You are writing production Python backend code for {plan.product_name}.
Tech stack: {stack}

Database tables:
{tables_str}

API routes:
{routes_str}

Write complete, working Python code for main.py (FastAPI app with all routes registered).
Include real imports, route handlers, Pydantic models for request/response.
Return ONLY the Python code â€” no explanations, no markdown fences."""

        main_code = self.run(SYSTEM_PROMPT + "\n\nWrite only working Python code. No markdown.", code_prompt)
        # Strip any markdown fences
        import re
        main_code = re.sub(r"^```[\w]*\n?", "", main_code.strip(), flags=re.MULTILINE)
        main_code = re.sub(r"\n?```$", "", main_code.strip(), flags=re.MULTILINE)

        # Write main.py
        (code_dir / "main.py").write_text(main_code, encoding="utf-8")

        # Generate database.py
        db_prompt = f"""Write database.py for {plan.product_name} using SQLAlchemy with these tables:
{tables_str}
Include: SQLAlchemy Base, engine setup, session factory, and all ORM model classes.
Return ONLY working Python code."""
        db_code = self.run(SYSTEM_PROMPT + "\n\nWrite only working Python code.", db_prompt)
        db_code = re.sub(r"^```[\w]*\n?", "", db_code.strip(), flags=re.MULTILINE)
        db_code = re.sub(r"\n?```$", "", db_code.strip(), flags=re.MULTILINE)
        (code_dir / "database.py").write_text(db_code, encoding="utf-8")

        written = {"main.py": len(main_code), "database.py": len(db_code)}
        self.flush_daily_log()
        return {"files_written": list(written.keys()), "code_dir": str(code_dir), "sizes": written}
