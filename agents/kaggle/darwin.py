"""
DARWIN — Data Explorer Agent
Performs EDA, understands the target variable, identifies feature opportunities,
and writes a data strategy brief for FORGE to implement.
Executes real Python code to explore the actual data.
"""
from agents.base import BaseAgent
from utils.code_executor import run_code, format_result, extract_code, get_competition_dir

SYSTEM_PROMPT = """
You are DARWIN, Data Exploration Lead at AgentCompany DataScience Division.
Your persona: meticulous, pattern-seeking, never skips EDA.

You write Python code that runs against real data files to understand:
- Target distribution, class balance
- Missing values, data types
- Feature correlations with target
- Outliers, skewness
- Potential feature engineering opportunities

Write clean, executable Python. Include print() statements for all findings.
Output valid JSON only when asked for strategy.
""".strip()


class DARWIN(BaseAgent):
    name       = "DARWIN"
    role       = "Data Exploration Lead"
    department = "kaggle"
    emoji      = "🔬"

    def explore(self, competition_brief: dict) -> dict:
        slug        = competition_brief.get("competition_slug", "unknown")
        target_col  = competition_brief.get("target_column", "target")
        problem     = competition_brief.get("problem_type", "classification")
        metric      = competition_brief.get("metric", "accuracy")
        comp_dir    = get_competition_dir(slug)

        # ── Step 1: Write + execute EDA code ──────────────────────────────
        eda_prompt = f"""
Write Python EDA code for this competition:
- Slug: {slug}
- Target: {target_col}
- Problem: {problem}
- Metric: {metric}
- Data dir: {comp_dir}

The code should:
1. Load train.csv (and test.csv if present)
2. Print shape, dtypes, head(3)
3. Print target distribution / value_counts
4. Print missing value counts (columns with >0 missing)
5. Print correlations between numeric features and target (top 10)
6. Print basic stats: mean, std, min, max for numeric cols
7. Identify categorical vs numeric columns

Write ONLY executable Python code (no markdown, no explanations).
""".strip()

        code_response = self.run(SYSTEM_PROMPT, eda_prompt)
        code = extract_code(code_response)
        exec_result = run_code(code, slug, "eda.py", timeout=60)
        eda_output = format_result(exec_result)

        # ── Step 2: Ask LLM to interpret EDA and produce strategy ─────────
        strategy_prompt = f"""
You ran EDA on the {slug} competition. Here are the results:

{eda_output}

Competition info:
- Target: {target_col}
- Problem type: {problem}
- Metric: {metric}

Based on the EDA results, produce a feature engineering and modelling strategy.
Return JSON:
{{
  "target_column": "{target_col}",
  "problem_type": "{problem}",
  "metric": "{metric}",
  "numeric_features": ["list", "of", "numeric", "cols"],
  "categorical_features": ["list", "of", "categorical", "cols"],
  "high_missing_cols": ["cols with >20% missing"],
  "feature_engineering": [
    "Create FamilySize = SibSp + Parch + 1",
    "Extract Title from Name column",
    "Bin Age into 5 groups"
  ],
  "model_recommendation": "LightGBM with cross-validation",
  "cv_strategy": "StratifiedKFold(5)" ,
  "expected_baseline_cv": 0.78,
  "key_insights": ["insight 1", "insight 2"],
  "eda_output_summary": "one paragraph summary of findings"
}}
""".strip()

        strategy = self.run_json(SYSTEM_PROMPT, strategy_prompt)
        strategy["eda_exec"] = exec_result
        strategy["competition_slug"] = slug

        self.flush_daily_log()
        return strategy
