"""
FORGE — ML Engineer Agent
Takes the data strategy from DARWIN and writes a full ML pipeline:
feature engineering, model training, cross-validation, prediction generation.
Executes the code, reads CV scores, and iterates on errors.
"""
from agents.base import BaseAgent
from utils.code_executor import run_code, format_result, extract_code, get_competition_dir

SYSTEM_PROMPT = """
You are FORGE, ML Engineer at AgentCompany DataScience Division.
Your persona: pragmatic, results-driven, knows every sklearn/lgbm trick.

You write complete, production-quality ML pipelines that:
- Handle missing values, encode categoricals
- Engineer features from the strategy brief
- Train LightGBM (primary) and XGBoost (secondary) with StratifiedKFold CV
- Save OOF predictions and test predictions to CSV files
- Print CV score clearly at the end: "CV SCORE: 0.XXXX"
- Save submission.csv in the correct format

Always write code that handles errors gracefully and prints informative progress messages.
""".strip()


class FORGE(BaseAgent):
    name       = "FORGE"
    role       = "ML Engineer"
    department = "kaggle"
    emoji      = "⚙️"

    def build_pipeline(self, competition_brief: dict, data_strategy: dict,
                       iteration: int = 1) -> dict:
        slug        = competition_brief.get("competition_slug", "unknown")
        target      = data_strategy.get("target_column", "target")
        problem     = data_strategy.get("problem_type", "classification")
        metric      = data_strategy.get("metric", "accuracy")
        fe_steps    = data_strategy.get("feature_engineering", [])
        num_feats   = data_strategy.get("numeric_features", [])
        cat_feats   = data_strategy.get("categorical_features", [])
        cv_strategy = data_strategy.get("cv_strategy", "StratifiedKFold(5)")
        comp_dir    = get_competition_dir(slug)

        mem_context = self.recall_memory(f"kaggle_{slug}")

        code_prompt = f"""
Write a complete ML pipeline for the {slug} Kaggle competition.
Iteration: {iteration}

Competition details:
- Target column: {target}
- Problem type: {problem}
- Metric: {metric}
- CV strategy: {cv_strategy}
- Numeric features: {num_feats}
- Categorical features: {cat_feats}
- Feature engineering steps:
{chr(10).join(f"  - {s}" for s in fe_steps)}

{f"Previous learnings from memory:{chr(10)}{mem_context}" if mem_context else ""}

Requirements:
1. Load train.csv and test.csv from the current directory
2. Apply ALL feature engineering steps listed above
3. Handle missing values (median for numeric, mode for categorical)
4. Encode categoricals with LabelEncoder or pd.get_dummies
5. Train LightGBM with {cv_strategy} cross-validation
6. Print progress: fold number and fold CV score
7. Print final mean CV score as: "CV SCORE: 0.XXXX"
8. Generate test predictions (averaged over folds)
9. Save submission.csv with correct format (Id/PassengerId + target column)
10. Also save oof_predictions.csv for stacking

Use these imports at minimum:
  import pandas as pd, numpy as np
  from sklearn.model_selection import StratifiedKFold, KFold
  from sklearn.preprocessing import LabelEncoder
  from sklearn.metrics import accuracy_score, roc_auc_score, mean_squared_error
  import lightgbm as lgb
  import warnings; warnings.filterwarnings('ignore')

Write ONLY executable Python code. No markdown fences, no explanations.
""".strip()

        code_resp = self.run(SYSTEM_PROMPT, code_prompt)
        code = extract_code(code_resp)
        exec_result = run_code(code, slug, f"pipeline_v{iteration}.py", timeout=240)
        output_text = format_result(exec_result)

        # ── Extract CV score from output ───────────────────────────────────
        import re
        cv_match = re.search(r"CV SCORE[:\s]+([0-9.]+)", exec_result.get("stdout",""), re.IGNORECASE)
        cv_score = float(cv_match.group(1)) if cv_match else None

        # ── Check submission file was created ──────────────────────────────
        submission_exists = (comp_dir / "submission.csv").exists()

        result = {
            "iteration":          iteration,
            "competition_slug":   slug,
            "cv_score":           cv_score,
            "submission_created": submission_exists,
            "exec_result":        exec_result,
            "output_summary":     output_text[:2000],
            "code_written":       code[:500] + "..." if len(code) > 500 else code,
        }

        # ── If failed, try to auto-fix ─────────────────────────────────────
        if not exec_result["success"] and iteration < 3:
            fix_prompt = f"""
The pipeline code failed with this error:

{exec_result.get('stderr','')[:800]}

Full output:
{exec_result.get('stdout','')[:800]}

Original code (abbreviated):
{code[:1200]}

Rewrite the ENTIRE pipeline fixing the error. Focus on:
- Correct column names (check what columns actually exist)
- Proper handling of the specific error shown
- Keep the same structure but fix the bug

Write ONLY the fixed executable Python code.
""".strip()
            fix_resp = self.run(SYSTEM_PROMPT, fix_prompt)
            fixed_code = extract_code(fix_resp)
            fix_exec = run_code(fixed_code, slug, f"pipeline_v{iteration}_fix.py", timeout=240)
            cv_fix = re.search(r"CV SCORE[:\s]+([0-9.]+)", fix_exec.get("stdout",""), re.IGNORECASE)
            result["fix_attempt"] = {
                "success": fix_exec["success"],
                "cv_score": float(cv_fix.group(1)) if cv_fix else None,
                "exec": fix_exec,
            }
            if fix_exec["success"] and cv_fix:
                result["cv_score"] = float(cv_fix.group(1))
                result["submission_created"] = (comp_dir / "submission.csv").exists()

        self.flush_daily_log()
        return result
