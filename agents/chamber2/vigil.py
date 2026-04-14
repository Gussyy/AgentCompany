"""
VIGIL — Head of QA & Security (The Inspector)
Chamber 2 | Seoul
Enforces the Definition of Done. Tries to break the product.
"""
from agents.base import BaseAgent
from models.schemas import BuildArtifact, TechnicalPlan, QAReport, QAIssue
from config import DOD_COVERAGE_THRESHOLD


SYSTEM_PROMPT = """
You are VIGIL, Head of QA & Security at AgentCompany.
Your persona: adversarial tester, zero tolerance for P0 bugs.

Definition of Done (ALL must pass before you approve):
1. Test coverage ≥ 80%
2. Zero critical security vulnerabilities
3. All performance benchmarks met
4. Zero P0 bugs outstanding

If any criterion fails, you issue structured bug reports to the responsible engineer.
You do not accept "we'll fix it post-launch."

Simulate a QA inspection and return your findings as JSON.
""".strip()


class VIGIL(BaseAgent):
    name       = "VIGIL"
    role       = "Head of QA & Security"
    department = "chamber2"
    emoji      = "🔍"

    def inspect(
        self,
        backend: BuildArtifact,
        frontend: BuildArtifact,
        plan: TechnicalPlan,
    ) -> QAReport:

        all_files = backend.files + frontend.files

        prompt = f"""
Product: {plan.product_name}
Backend files: {', '.join(backend.files[:15])}
Frontend files: {', '.join(frontend.files[:15])}
Backend notes: {backend.notes}
Frontend notes: {frontend.notes}

Run a comprehensive QA and security inspection:
1. Assess test coverage (0-100%)
2. Check for security vulnerabilities (auth issues, injection risks, data leaks)
3. Assess performance (sub-200ms responses, no N+1 queries)
4. Identify any P0 bugs (core functionality broken)
5. Identify P1 bugs (significant but not blocking)

Be realistic — most first builds have some issues.

Return JSON:
{{
  "test_coverage_pct": 82.5,
  "critical_vulnerabilities": 0,
  "performance_passed": true,
  "p0_bugs": [],
  "p1_bugs": [
    {{
      "severity": "P1",
      "component": "backend",
      "description": "Missing rate limiting on /api/auth/signup",
      "route_to": "CORE"
    }}
  ],
  "definition_of_done_passed": true,
  "notes": "Summary of findings"
}}
""".strip()

        data = self.run_json(SYSTEM_PROMPT, prompt)
        try:
            p0 = [QAIssue(**b) for b in data.get("p0_bugs", [])]
            p1 = [QAIssue(**b) for b in data.get("p1_bugs", [])]

            # Recalculate DoD — don't trust the model to self-assess
            coverage_ok    = data.get("test_coverage_pct", 0) >= DOD_COVERAGE_THRESHOLD
            security_ok    = data.get("critical_vulnerabilities", 1) == 0
            perf_ok        = data.get("performance_passed", False)
            no_p0          = len(p0) == 0
            dod_passed     = coverage_ok and security_ok and perf_ok and no_p0

            report = QAReport(
                test_coverage_pct=data.get("test_coverage_pct", 0),
                critical_vulnerabilities=data.get("critical_vulnerabilities", 0),
                performance_passed=perf_ok,
                p0_bugs=p0,
                p1_bugs=p1,
                definition_of_done_passed=dod_passed,
                notes=data.get("notes", ""),
            )
        except Exception as e:
            raise ValueError(f"VIGIL report parsing failed: {e}")
        self.flush_daily_log()
        return report
