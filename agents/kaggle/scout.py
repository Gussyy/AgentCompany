"""
SCOUT — Competition Research Agent
Searches Kaggle for suitable active competitions, picks the best one,
downloads the dataset, and writes a competition brief.
"""
import json
import os
import subprocess
import sys
from pathlib import Path
from agents.base import BaseAgent
from utils.code_executor import get_competition_dir, VENV_PYTHON, KAGGLE_EXE, kaggle_env
from utils.web_search import search, format_search_results

SYSTEM_PROMPT = """
You are SCOUT, Competition Research Agent at AgentCompany DataScience Division.
Your persona: tactical, opportunistic, always hunting for winnable competitions.

You evaluate Kaggle competitions on:
- Achievability: can we realistically reach top 10% with tabular/structured data?
- Prize & prestige: worth the effort?
- Data size: fits in memory (<2GB raw)?
- Competition type: tabular/structured preferred over image/NLP (we're best at tables)
- Deadline: must have >2 weeks remaining

Output valid JSON only.
""".strip()


class SCOUT(BaseAgent):
    name       = "SCOUT"
    role       = "Competition Research Agent"
    department = "kaggle"
    emoji      = "🔭"

    def find_competition(self, target: str = "tabular") -> dict:
        """Search for and select the best active Kaggle competition."""

        # ── Real web search for active competitions ────────────────────────
        queries = [
            f"kaggle competition active {target} 2025 2026 tabular data",
            f"kaggle getting started {target} competition beginner friendly",
            f"site:kaggle.com/competitions active {target}",
        ]
        results = []
        for q in queries:
            results.extend(search(q, max_results=5))
        web_context = format_search_results(results[:10])

        # Check memory for competitions we've tried before
        mem_context = self.recall_memory("kaggle_competitions")

        prompt = f"""
Find the best active Kaggle competition for us to enter right now.

Target type: {target} (prefer tabular/structured data competitions)

=== WEB SEARCH RESULTS ===
{web_context}
=== END SEARCH ===

{mem_context if mem_context else ""}

Select ONE competition that we can realistically reach top 10% on.
Prefer: Titanic, House Prices, Spaceship Titanic, Playground Series, or any active tabular competition.

Return JSON:
{{
  "competition_slug": "titanic",
  "competition_name": "Titanic - Machine Learning from Disaster",
  "competition_url": "https://www.kaggle.com/c/titanic",
  "problem_type": "binary_classification",
  "target_column": "Survived",
  "metric": "accuracy",
  "data_description": "Passenger survival prediction from demographic features",
  "why_chosen": "Classic entry-level competition, extensive community solutions to learn from",
  "estimated_top10_score": 0.80,
  "baseline_approach": "LightGBM with feature engineering on Age, Fare, Pclass",
  "deadline_days_remaining": 9999,
  "has_prize": false
}}
""".strip()

        data = self.run_json(SYSTEM_PROMPT, prompt)
        self.flush_daily_log()
        return data

    def download_data(self, competition_slug: str) -> dict:
        """Download competition data using the Kaggle API."""
        import zipfile as zf
        comp_dir = get_competition_dir(competition_slug)
        kaggle   = str(KAGGLE_EXE) if KAGGLE_EXE.exists() else str(VENV_PYTHON)

        # Download (no --unzip flag — unzip manually after)
        result = subprocess.run(
            [kaggle, "competitions", "download",
             "-c", competition_slug, "-p", str(comp_dir)],
            capture_output=True, text=True,
            timeout=180, env=kaggle_env(),
        )

        # Unzip any downloaded .zip files
        for zip_path in comp_dir.glob("*.zip"):
            try:
                with zf.ZipFile(zip_path) as z:
                    z.extractall(str(comp_dir))
            except Exception:
                pass

        files = list(comp_dir.glob("*.csv")) + list(comp_dir.glob("**/*.csv"))
        return {
            "success":    result.returncode == 0 or len(files) > 0,
            "competition": competition_slug,
            "directory":  str(comp_dir),
            "files":      [str(f.relative_to(comp_dir)) for f in files],
            "stdout":     result.stdout[-500:],
            "stderr":     result.stderr[-300:],
            "file_count": len(files),
        }
