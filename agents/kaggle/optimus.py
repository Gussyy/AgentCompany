"""
OPTIMUS — Hyperparameter Optimization + Ensemble Agent
Takes FORGE's baseline, runs Optuna HPO, builds an ensemble,
and squeezes the last performance out before submission.
Updates long-term memory with winning hyperparameters.
"""
import re
from agents.base import BaseAgent
from utils.code_executor import run_code, format_result, extract_code, get_competition_dir

SYSTEM_PROMPT = """
You are OPTIMUS, Hyperparameter Optimization Lead at AgentCompany DataScience Division.
Your persona: relentless optimizer, ensemble master.

You improve models by:
1. Running Optuna HPO on LightGBM/XGBoost (30-50 trials)
2. Adding a Random Forest or ExtraTrees for diversity
3. Weighted-averaging predictions from multiple models
4. Applying post-processing (threshold tuning for classification)

Your goal: beat the baseline CV score and push toward top 10%.
Always print: "OPTIMIZED CV SCORE: 0.XXXX"
""".strip()


class OPTIMUS(BaseAgent):
    name       = "OPTIMUS"
    role       = "Hyperparameter Optimization Lead"
    department = "kaggle"
    emoji      = "🔧"

    def optimize(self, competition_brief: dict, forge_result: dict,
                 data_strategy: dict) -> dict:
        slug         = competition_brief.get("competition_slug", "unknown")
        target       = data_strategy.get("target_column", "target")
        problem      = data_strategy.get("problem_type", "classification")
        metric       = data_strategy.get("metric", "accuracy")
        baseline_cv  = forge_result.get("cv_score") or data_strategy.get("expected_baseline_cv", 0.75)
        comp_dir     = get_competition_dir(slug)
        mem_context  = self.recall_memory(f"kaggle_{slug}")

        optuna_prompt = f"""
Write an Optuna hyperparameter optimization script to improve on our baseline.

Competition: {slug}
Target: {target}
Problem type: {problem}
Metric: {metric}
Baseline CV: {baseline_cv}
Data directory: current directory (train.csv, test.csv available)

{f"Memory from previous runs:{chr(10)}{mem_context}" if mem_context else ""}

The script must:
1. Load train.csv and apply the same preprocessing as before
2. Define an Optuna objective function for LightGBM with these params to tune:
   - num_leaves: 20-300
   - learning_rate: 0.01-0.3
   - feature_fraction: 0.5-1.0
   - bagging_fraction: 0.5-1.0
   - min_child_samples: 5-100
   - lambda_l1: 0-5
   - lambda_l2: 0-5
3. Run 40 trials (n_trials=40) with a 5-fold CV
4. Use optuna.logging.set_verbosity(optuna.logging.WARNING) to suppress logs
5. After HPO, train final model with best params on all folds
6. ALSO train a sklearn RandomForestClassifier/Regressor as second model
7. Ensemble: 0.7 * lgb_preds + 0.3 * rf_preds
8. Generate final test predictions and save as submission.csv
9. Print: "OPTIMIZED CV SCORE: 0.XXXX"
10. Print: "BEST PARAMS: {{...}}"

Write ONLY executable Python code (no markdown).
""".strip()

        code_resp = self.run(SYSTEM_PROMPT, optuna_prompt)
        code = extract_code(code_resp)
        exec_result = run_code(code, slug, "optimus_hpo.py", timeout=600)  # 10 min for HPO

        # Extract optimized score
        cv_match = re.search(r"OPTIMIZED CV SCORE[:\s]+([0-9.]+)", exec_result.get("stdout",""), re.IGNORECASE)
        optimized_cv = float(cv_match.group(1)) if cv_match else None

        # Extract best params
        params_match = re.search(r"BEST PARAMS[:\s]+(\{.*?\})", exec_result.get("stdout",""), re.DOTALL)
        best_params = params_match.group(1) if params_match else None

        improvement = None
        if optimized_cv and baseline_cv:
            improvement = round(optimized_cv - baseline_cv, 5)

        result = {
            "competition_slug": slug,
            "baseline_cv":      baseline_cv,
            "optimized_cv":     optimized_cv,
            "improvement":      improvement,
            "best_params":      best_params,
            "exec_result":      exec_result,
            "success":          exec_result["success"] and optimized_cv is not None,
        }

        # Store winning params in long-term memory
        if optimized_cv and best_params:
            try:
                self.memory.add_node("Pattern", f"kaggle_{slug}_hpo", {
                    "competition": slug,
                    "metric": metric,
                    "best_cv": optimized_cv,
                    "best_params": str(best_params)[:500],
                    "date": __import__("datetime").date.today().isoformat(),
                })
                self.memory.add_edge("Industry", f"kaggle_{slug}", "LEARNED_FROM",
                                     "Pattern", f"kaggle_{slug}_hpo",
                                     {"cv": optimized_cv})
            except Exception:
                pass

        self.flush_daily_log()
        return result
