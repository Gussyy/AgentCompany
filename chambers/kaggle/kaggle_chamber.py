"""
KaggleChamber — Orchestrates SCOUT → DARWIN → FORGE → OPTIMUS → HELM
to attempt a top-10% finish on a Kaggle competition.

Emits events to the CEO dashboard in real time.
"""
from __future__ import annotations
from agents.kaggle.scout   import SCOUT
from agents.kaggle.darwin  import DARWIN
from agents.kaggle.forge   import FORGE
from agents.kaggle.optimus import OPTIMUS
from agents.kaggle.helm    import HELM
from utils.short_term_memory import new_run_memory


class KaggleChamber:
    def __init__(self, event_callback=None, target_type: str = "tabular",
                 competition_slug: str = None, kaggle_username: str = None):
        self.target_type       = target_type
        self.forced_slug       = competition_slug   # skip SCOUT if provided
        self.event_callback    = event_callback

        self.scout   = SCOUT()
        self.darwin  = DARWIN()
        self.forge   = FORGE()
        self.optimus = OPTIMUS()
        self.helm    = HELM()

        # Shared short-term memory for this run
        self.run_memory = new_run_memory()
        for agent in [self.scout, self.darwin, self.forge, self.optimus, self.helm]:
            agent.set_run_memory(self.run_memory)
            agent.set_industry("kaggle_datascience")
            if event_callback:
                from agents.base import subscribe_events
                subscribe_events(event_callback)

    def run(self) -> dict:
        result = {
            "status": "running",
            "competition": None,
            "cv_score": None,
            "optimized_cv": None,
            "submitted": False,
            "leaderboard_report": None,
            "short_term_memory_entries": 0,
        }

        try:
            # ── Phase 1: SCOUT — Find competition ─────────────────────────
            self._emit("🔭 SCOUT scanning for best Kaggle competition…")
            if self.forced_slug:
                comp_brief = {
                    "competition_slug":  self.forced_slug,
                    "competition_name":  self.forced_slug,
                    "problem_type":      "binary_classification",
                    "target_column":     "target",
                    "metric":            "accuracy",
                }
            else:
                comp_brief = self.scout.find_competition(self.target_type)

            slug = comp_brief.get("competition_slug", "titanic")
            result["competition"] = comp_brief
            self._emit(f"🔭 SCOUT selected: {comp_brief.get('competition_name', slug)}")

            # Download data
            self._emit(f"📥 Downloading data for {slug}…")
            download = self.scout.download_data(slug)
            if not download["success"] or download["file_count"] == 0:
                # Try titanic as fallback (always available)
                self._emit("⚠️  Download failed or no files. Using Titanic as fallback…")
                slug = "titanic"
                comp_brief["competition_slug"] = slug
                comp_brief["competition_name"] = "Titanic - Machine Learning from Disaster"
                comp_brief["target_column"] = "Survived"
                comp_brief["metric"] = "accuracy"
                download = self.scout.download_data(slug)
            result["download"] = download
            self._emit(f"✅ Data ready: {download.get('file_count', 0)} files in {download.get('directory','')}")

            # ── Phase 2: DARWIN — Explore data ────────────────────────────
            self._emit("🔬 DARWIN running EDA on the data…")
            data_strategy = self.darwin.explore(comp_brief)
            result["data_strategy"] = data_strategy
            cv_expected = data_strategy.get("expected_baseline_cv", "?")
            self._emit(f"🔬 DARWIN strategy ready. Expected baseline CV: {cv_expected}")
            self._emit(f"   Features: {len(data_strategy.get('numeric_features',[]))} numeric, {len(data_strategy.get('categorical_features',[]))} categorical")

            # ── Phase 3: FORGE — Build ML pipeline ────────────────────────
            self._emit("⚙️  FORGE building ML pipeline (iteration 1)…")
            forge_result = self.forge.build_pipeline(comp_brief, data_strategy, iteration=1)
            cv1 = forge_result.get("cv_score")
            result["cv_score"] = cv1
            if cv1:
                self._emit(f"⚙️  FORGE baseline CV: {cv1:.5f}")
            else:
                self._emit("⚠️  FORGE: Could not extract CV score from output")

            # ── Phase 4: OPTIMUS — HPO + Ensemble ─────────────────────────
            self._emit("🔧 OPTIMUS running hyperparameter optimization (40 trials + ensemble)…")
            optimus_result = self.optimus.optimize(comp_brief, forge_result, data_strategy)
            cv_opt = optimus_result.get("optimized_cv")
            result["optimized_cv"] = cv_opt
            if cv_opt:
                impr = optimus_result.get("improvement", 0) or 0
                self._emit(f"🔧 OPTIMUS optimized CV: {cv_opt:.5f} ({'+' if impr>=0 else ''}{impr:.5f} vs baseline)")
            else:
                self._emit("⚠️  OPTIMUS: HPO did not complete successfully, using FORGE submission")

            final_cv = cv_opt or cv1 or 0.0

            # ── Phase 5: HELM — Validate + Submit ─────────────────────────
            self._emit("🚀 HELM validating and submitting to Kaggle…")
            lb_report = self.helm.validate_and_submit(comp_brief, final_cv, data_strategy)
            result["submitted"]           = lb_report.get("submission_success", False)
            result["leaderboard_report"]  = lb_report
            result["status"]              = "complete"

            # Update short-term memory stats
            result["short_term_memory_entries"] = self.run_memory.stats()["total_entries"]

            top10 = lb_report.get("in_top_10_percent", False)
            rank  = lb_report.get("estimated_rank", "?")
            self._emit(f"🚀 HELM report: rank ~{rank} | top 10%: {'✅' if top10 else '❌'}")
            self._emit(f"💡 Next steps: {'; '.join(lb_report.get('next_steps', [])[:2])}")

        except Exception as e:
            import traceback
            result["status"] = "error"
            result["error"]  = str(e)
            result["trace"]  = traceback.format_exc()
            self._emit(f"❌ KaggleChamber error: {e}")

        return result

    def _emit(self, message: str):
        """Emit a status message to the CEO dashboard."""
        if self.event_callback:
            from models.schemas import AgentEvent, AgentStatus
            evt = AgentEvent(
                event_type="agent_output",
                agent_name="KAGGLE",
                chamber="kaggle",
                status=AgentStatus("running"),
                message=message,
                data={},
            )
            try:
                self.event_callback(evt)
            except Exception:
                pass
        print(f"[KAGGLE] {message}")
