"""
HELM — Submission & Leaderboard Agent
Validates the submission file, submits to Kaggle, reads the public LB score,
and updates long-term memory with competition results.
"""
import subprocess
import sys
from pathlib import Path
from agents.base import BaseAgent
from utils.code_executor import get_competition_dir, VENV_PYTHON, KAGGLE_EXE, kaggle_env
from utils.web_search import search, format_search_results

SYSTEM_PROMPT = """
You are HELM, Submission Lead at AgentCompany DataScience Division.
Your persona: meticulous, never submits broken files.

You validate submissions, calculate the expected public LB score,
and write the final competition report.
Output valid JSON only.
""".strip()


class HELM(BaseAgent):
    name       = "HELM"
    role       = "Submission Lead"
    department = "kaggle"
    emoji      = "🚀"

    def validate_and_submit(self, competition_brief: dict,
                            final_cv: float,
                            data_strategy: dict) -> dict:
        slug     = competition_brief.get("competition_slug", "unknown")
        comp_dir = get_competition_dir(slug)
        sub_file = comp_dir / "submission.csv"
        kaggle = str(KAGGLE_EXE) if KAGGLE_EXE.exists() else str(VENV_PYTHON)
        env    = kaggle_env()

        # ── Validate submission file exists ────────────────────────────────
        if not sub_file.exists():
            return {"success": False, "error": "submission.csv not found", "slug": slug}

        # ── Submit via Kaggle API ──────────────────────────────────────────
        submit_cmd = [kaggle, "competitions", "submit",
                      "-c", slug, "-f", str(sub_file),
                      "-m", f"AgentCompany run — CV: {final_cv:.5f}"]
        submit_result = subprocess.run(
            submit_cmd, capture_output=True, text=True, timeout=60, env=env,
        )
        submitted = submit_result.returncode == 0

        # ── Check leaderboard position ─────────────────────────────────────
        lb_result = subprocess.run(
            [kaggle, "competitions", "leaderboard", "-c", slug, "--show", "--csv"],
            capture_output=True, text=True, timeout=30, env=env,
        )
        lb_text = lb_result.stdout[:3000] if lb_result.returncode == 0 else ""

        # ── Search web for top scores on this competition ─────────────────
        web_results = search(f"kaggle {slug} leaderboard top score solution", max_results=5)
        web_context = format_search_results(web_results)

        # ── Ask LLM to analyze our position ──────────────────────────────
        prompt = f"""
Competition: {competition_brief.get('competition_name', slug)}
Our CV score: {final_cv}
Submission: {'submitted successfully' if submitted else 'FAILED - ' + submit_result.stderr[:200]}
Metric: {competition_brief.get('metric', 'accuracy')}

Leaderboard data:
{lb_text[:1000] if lb_text else 'Not available'}

Web research on top scores:
{web_context}

Estimate our public leaderboard position and percentage. Provide the final report.
Return JSON:
{{
  "submission_success": {str(submitted).lower()},
  "cv_score": {final_cv},
  "estimated_lb_score": 0.0,
  "estimated_percentile": 0,
  "estimated_rank": "Unknown",
  "in_top_10_percent": false,
  "in_top_10": false,
  "gap_to_top_10": "What we need to improve",
  "next_steps": ["step 1", "step 2", "step 3"],
  "memory_update": "What we learned to store for next time",
  "competition_summary": "One paragraph summary"
}}
""".strip()

        report = self.run_json(SYSTEM_PROMPT, prompt)

        # ── Update long-term memory with competition result ────────────────
        try:
            if self.memory:
                self.memory.add_node("Industry", f"kaggle_{slug}", {
                    "competition": slug,
                    "cv_score": final_cv,
                    "submitted": submitted,
                    "run_count": 1,
                    "last_run": __import__("datetime").date.today().isoformat(),
                    "metric": competition_brief.get("metric"),
                })
                if report.get("in_top_10_percent"):
                    self.memory.add_node("Pattern", f"top10pct_{slug}", {
                        "competition": slug,
                        "cv_score": final_cv,
                        "achievement": "top_10_percent",
                    })
        except Exception:
            pass

        report["submitted"]        = submitted
        report["submission_file"]  = str(sub_file)
        report["lb_raw"]           = lb_text[:500]
        report["competition_slug"] = slug

        self.flush_daily_log()
        return report
