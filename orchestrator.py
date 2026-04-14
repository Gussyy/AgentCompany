"""
Orchestrator (ORCA-1) — The Rule Enforcer
Manages sequential chamber execution, budget tracking, and event routing.
This is not an agent — it's the infrastructure every agent runs inside.
"""
import asyncio
import json
import os
import re
from pathlib import Path
from typing import Callable, Optional
from datetime import date

from utils.logger import chamber_banner, ceo_prompt, info, success, warning, error
from utils.notion_logger import post_ceo_daily_report, post_weekly_summary
from utils.token_tracker import token_tracker
from agents.base import subscribe_events
from models.schemas import (
    GateVerdict, LoopClassification, CEODailyReport, AgentEvent,
    SmokeTestResult, SoftLaunchMetrics,
)

# ── Agents ──────────────────────────────────────────────────────
from agents.chamber1.aria   import ARIA
from agents.chamber1.nova   import NOVA
from agents.chamber1.quant  import QUANT
from agents.chamber1.gate   import GATE
from agents.chamber2.arch   import ARCH
from agents.chamber2.core_agent import CORE
from agents.chamber2.pixel  import PIXEL
from agents.chamber2.vigil  import VIGIL
from agents.chamber3.apex   import APEX
from agents.chamber3.haven  import HAVEN
from agents.sentinel        import SENTRY
from agents.ledger          import LEDGER

MAX_QA_RETRY_CYCLES = 3


class Orchestrator:
    """
    ORCA-1: Routes work between chambers.
    Enforces sequencing, tracks costs, and emits events for the dashboard.
    """

    def __init__(
        self,
        industry: str,
        ad_budget_usd: float = 500.0,
        event_callback: Optional[Callable] = None,
        ceo_directive: str = "",
        target_agent: Optional[str] = None,
    ):
        self.industry      = industry
        self.ad_budget     = ad_budget_usd
        self.ceo_directive = ceo_directive   # injected into agent prompts
        self.target_agent  = target_agent    # if set, only run this one agent
        self.run_context   = {
            "industry": industry,
            "compute_cost_usd": 0.0,
            "ad_spend_usd": 0.0,
            "revenue_usd": 0.0,
            "ceo_directive": ceo_directive,
        }

        # Instantiate all agents
        self.aria   = ARIA()
        self.nova   = NOVA()
        self.quant  = QUANT()
        self.gate   = GATE()
        self.arch   = ARCH()
        self.core   = CORE()
        self.pixel  = PIXEL()
        self.vigil  = VIGIL()
        self.apex   = APEX()
        self.haven  = HAVEN()
        self.sentry = SENTRY()
        self.ledger = LEDGER()

        if event_callback:
            subscribe_events(event_callback)

    # ── Main execution loop ─────────────────────────────────────

    def run(self) -> dict:
        """
        Full company run: Chamber 1 → 1.5 → 2 → 2.5 → 3
        Returns a summary dict for the CEO dashboard.
        """
        # Reset token tracker so each run gets a clean slate
        token_tracker.reset()

        # Create a fresh short-term vector memory for this run
        from utils.short_term_memory import new_run_memory
        run_memory = new_run_memory()

        all_agents = [self.sentry, self.aria, self.nova, self.quant,
                      self.gate, self.ledger, self.arch, self.core,
                      self.pixel, self.vigil, self.apex, self.haven]

        # Tell every agent the current industry (for long-term memory recall)
        for agent in all_agents:
            agent.set_industry(self.industry)

        # Inject the shared short-term memory store into every agent
        for agent in all_agents:
            agent.set_run_memory(run_memory)

        # Inject CEO directive into every agent (if CEO Chat triggered this run)
        if self.ceo_directive:
            for agent in [self.sentry, self.aria, self.nova, self.quant,
                          self.gate, self.ledger, self.arch, self.core,
                          self.pixel, self.vigil, self.apex, self.haven]:
                agent.set_ceo_directive(self.ceo_directive)

        result = {
            "status": "running",
            "industry": self.industry,
            "product_name": None,
            "gate_decisions": [],
            "smoke_test": None,
            "soft_launch": None,
            "campaign": None,
            "financial_model": None,
            "daily_report": None,
        }

        try:
            # ── SENTRY scan (always-on) ────────────────────────
            info("SENTRY scanning competitive landscape…")
            sentry_report = self.sentry.scan_competitive_landscape(
                self.industry, "TBD"
            )
            if sentry_report.get("alert_level") == "red":
                warning(f"⚠️  SENTRY RED ALERT: {sentry_report.get('ceo_alert_message')}")

            # ── CHAMBER 1: Truth Seekers ───────────────────────
            chamber_banner(1, "Truth Seekers — Validation")

            friction = self.aria.run_friction_report(self.industry)
            blueprint = self.nova.design_blueprint(friction)
            financials = self.quant.model_financials(blueprint)

            result["product_name"] = blueprint.product_name

            decision1 = self.gate.evaluate(blueprint, financials, is_post_smoke_test=False)
            result["gate_decisions"].append({"stage": "pre_smoke_test", "verdict": decision1.verdict.value})

            if decision1.verdict == GateVerdict.KILL:
                result["status"] = "killed_chamber1"
                info(f"Project killed. Reason: {decision1.reason}")
                self._finalize(result)
                return result

            if decision1.verdict == GateVerdict.PIVOT:
                info(f"Pivot instruction: {decision1.pivot_brief}")
                # Re-run Chamber 1 with pivot instruction
                friction = self.aria.run_friction_report(
                    f"{self.industry} — pivot focus: {decision1.pivot_brief}"
                )
                blueprint  = self.nova.design_blueprint(friction)
                financials = self.quant.model_financials(blueprint)
                decision1  = self.gate.evaluate(blueprint, financials)
                if decision1.verdict != GateVerdict.GO:
                    result["status"] = "killed_after_pivot"
                    self._finalize(result)
                    return result

            success("Chamber 1 passed. Unlocking Smoke Test.")

            # ── CHAMBER 1.5: Smoke Test ────────────────────────
            chamber_banner(1.5, "Smoke Test — 72-hour Validation")

            smoke = self.apex.run_smoke_test(blueprint, financials, self.ad_budget)
            self.run_context["ad_spend_usd"] += smoke.ad_spend_usd
            result["smoke_test"] = smoke.model_dump()

            if not smoke.passed:
                result["status"] = "killed_smoke_test"
                error(f"Smoke Test failed. CTR: {smoke.ctr:.2%}, Conv: {smoke.conversion_rate:.2%}")
                self._finalize(result)
                return result

            success(f"Smoke Test passed. Real CAC: ${smoke.real_cac_usd:.2f}")

            # Update financials with real data, re-gate
            financials = self.quant.update_with_smoke_test(financials, smoke)
            result["financial_model"] = financials.model_dump()

            decision2 = self.gate.evaluate(blueprint, financials, is_post_smoke_test=True)
            result["gate_decisions"].append({"stage": "post_smoke_test", "verdict": decision2.verdict.value})

            ceo_prompt(
                f"CEO REVIEW REQUIRED\n"
                f"Product: {blueprint.product_name}\n"
                f"Real CAC: ${smoke.real_cac_usd:.2f} | Margin: {financials.gross_margin_pct}%\n"
                f"Gate verdict: {decision2.verdict.value}\n"
                f"Type GO to proceed or KILL to abort."
            )

            if decision2.verdict == GateVerdict.KILL:
                result["status"] = "killed_post_smoke"
                self._finalize(result)
                return result

            success("CEO approved. Unlocking Chamber 2.")

            # ── CHAMBER 2: Factory ─────────────────────────────
            chamber_banner(2, "The Factory — Build")

            # Create local project folder as soon as the build starts
            project_root = self._scaffold_project_folder(blueprint.product_name)

            tech_plan     = self.arch.create_technical_plan(blueprint)
            self._write_specs(project_root, tech_plan)

            backend_build = self.core.build_backend(tech_plan)
            frontend_build = self.pixel.build_frontend(tech_plan, backend_build)

            # QA loop — max 3 retry cycles
            qa_attempts = 0
            qa_report = None
            while qa_attempts < MAX_QA_RETRY_CYCLES:
                qa_report = self.vigil.inspect(backend_build, frontend_build, tech_plan)
                if qa_report.definition_of_done_passed:
                    break
                qa_attempts += 1
                warning(f"QA failed (attempt {qa_attempts}/{MAX_QA_RETRY_CYCLES}). P0 bugs: {len(qa_report.p0_bugs)}")
                # Re-build affected components
                for bug in qa_report.p0_bugs:
                    if bug.route_to == "CORE":
                        backend_build = self.core.build_backend(tech_plan)
                    elif bug.route_to == "PIXEL":
                        frontend_build = self.pixel.build_frontend(tech_plan, backend_build)

            if not qa_report or not qa_report.definition_of_done_passed:
                result["status"] = "blocked_qa"
                error(f"QA failed after {MAX_QA_RETRY_CYCLES} attempts.")
                self._write_build_artifacts(project_root, backend_build, frontend_build)
                self._write_qa_report(project_root, qa_report)
                self._finalize(result)
                return result

            self._write_build_artifacts(project_root, backend_build, frontend_build)
            self._write_qa_report(project_root, qa_report)
            # ── Generate actual code files ─────────────────────────────────
            try:
                code_result = self.core.generate_code(tech_plan, backend_build, project_root)
                success(f"Code generated: {code_result.get('files_written', [])} → {code_result.get('code_dir', '')}")
                result["code_files"] = code_result
            except Exception as _ce:
                pass
            success("Chamber 2 passed. Product approved. Unlocking Soft Launch.")

            # ── CHAMBER 2.5: Soft Launch ───────────────────────
            chamber_banner(2.5, "Soft Launch — 50 Users / 2 Weeks")

            soft_metrics = self.haven.monitor_soft_launch(blueprint, cohort_size=50)
            result["soft_launch"] = soft_metrics.model_dump()

            ceo_prompt(
                f"CEO REVIEW — Soft Launch Results\n"
                f"Day-7 retention: {soft_metrics.day7_retention_rate:.0%} "
                f"(target: {30:.0%})\n"
                f"Activation: {soft_metrics.activation_rate:.0%} "
                f"(target: {50:.0%})\n"
                f"NPS: {soft_metrics.nps} (target: ≥20)\n"
                f"Passed: {'✅ YES' if soft_metrics.passed else '❌ NO — iterate'}"
            )

            if not soft_metrics.passed:
                result["status"] = "soft_launch_iterate"
                self._finalize(result)
                return result

            success("Soft Launch cleared. Unlocking Chamber 3.")

            # ── CHAMBER 3: Market ──────────────────────────────
            chamber_banner(3, "The Market — Full Scale Growth")

            campaign = self.apex.build_outreach_campaign(blueprint, financials)
            result["campaign"] = campaign.model_dump()
            self._write_campaign(project_root, campaign)

            # Simulate post-launch feedback for the Loop
            sample_feedback = soft_metrics.top_complaints + soft_metrics.top_praises
            loop_feedback = self.haven.classify_feedback(sample_feedback, blueprint.product_name)

            info(f"Loop classification: {loop_feedback.classification.value}")
            info(f"Route: {loop_feedback.route_description}")

            result["status"] = "complete"

            # Write final README with full run summary
            smoke_obj = SmokeTestResult(**result["smoke_test"]) if result.get("smoke_test") else None
            soft_obj  = SoftLaunchMetrics(**result["soft_launch"]) if result.get("soft_launch") else None
            self._write_readme(project_root, blueprint, financials, smoke_obj, soft_obj, "complete")

            success(f"🎉 Company run complete. Product '{blueprint.product_name}' is live.")

        except Exception as e:
            result["status"] = "error"
            error(f"Orchestrator error: {e}")

        finally:
            self._finalize(result)

        return result

    # ── Project folder helpers ─────────────────────────────────

    @staticmethod
    def _slug(name: str) -> str:
        """Turn a product name into a safe folder name."""
        slug = name.lower().strip()
        slug = re.sub(r"[^\w\s-]", "", slug)
        slug = re.sub(r"[\s_-]+", "_", slug)
        return slug[:64]

    def _scaffold_project_folder(self, product_name: str) -> Path:
        """
        Create the project directory tree under projects/<slug>/.
        Returns the project root Path.
        """
        slug  = self._slug(product_name)
        root  = Path("projects") / slug

        subdirs = [
            root / "specs",
            root / "src" / "backend",
            root / "src" / "frontend",
            root / "tests",
            root / "marketing",
            root / "logs",
        ]
        for d in subdirs:
            d.mkdir(parents=True, exist_ok=True)

        info(f"📁  Project folder created → {root}")
        self.run_context["project_folder"] = str(root)
        return root

    def _write_specs(self, root: Path, tech_plan) -> None:
        """Dump ARCH's technical plan as markdown."""
        out = root / "specs" / "technical_plan.md"
        lines = [
            f"# Technical Plan — {tech_plan.product_name}",
            "",
            "## Tech Stack",
        ]
        for k, v in tech_plan.tech_stack.items():
            lines.append(f"- **{k}**: {v}")

        lines += ["", "## Database Tables"]
        for t in tech_plan.database_tables:
            lines.append(f"### {t.name}")
            lines.append("Columns: " + ", ".join(t.columns))
            if t.indexes:
                lines.append("Indexes: " + ", ".join(t.indexes))

        lines += ["", "## API Routes"]
        for r in tech_plan.api_routes:
            auth = "🔒" if r.auth_required else "🔓"
            lines.append(f"- `{r.method} {r.path}` {auth} — {r.description}")

        lines += ["", "## V1 Scope"]
        for s in tech_plan.v1_scope:
            lines.append(f"- {s}")

        lines += ["", "## Deferred to V2"]
        for s in tech_plan.deferred_to_v2:
            lines.append(f"- {s}")

        out.write_text("\n".join(lines), encoding="utf-8")
        info(f"   ✍️  Specs written → {out}")

    def _write_build_artifacts(self, root: Path, backend, frontend) -> None:
        """Write CORE + PIXEL build manifests."""
        be_out = root / "src" / "backend" / "build_manifest.md"
        be_out.write_text(
            f"# Backend Build — {backend.agent}\n\n"
            f"{backend.description}\n\n"
            "## Files\n" + "\n".join(f"- {f}" for f in backend.files) +
            (f"\n\n## Notes\n{backend.notes}" if backend.notes else ""),
            encoding="utf-8",
        )

        fe_out = root / "src" / "frontend" / "build_manifest.md"
        fe_out.write_text(
            f"# Frontend Build — {frontend.agent}\n\n"
            f"{frontend.description}\n\n"
            "## Files\n" + "\n".join(f"- {f}" for f in frontend.files) +
            (f"\n\n## Notes\n{frontend.notes}" if frontend.notes else ""),
            encoding="utf-8",
        )
        info(f"   ✍️  Build manifests written → {root / 'src'}")

    def _write_qa_report(self, root: Path, qa_report) -> None:
        """Dump VIGIL's QA report."""
        out = root / "tests" / "qa_report.md"
        dod = "✅ PASSED" if qa_report.definition_of_done_passed else "❌ FAILED"
        lines = [
            "# QA Report",
            "",
            f"- **Definition of Done**: {dod}",
            f"- **Test coverage**: {qa_report.test_coverage_pct:.1f}%",
            f"- **Critical vulnerabilities**: {qa_report.critical_vulnerabilities}",
            f"- **Performance**: {'✅' if qa_report.performance_passed else '❌'}",
        ]
        if qa_report.p0_bugs:
            lines += ["", "## P0 Bugs"]
            for b in qa_report.p0_bugs:
                lines.append(f"- [{b.component}] {b.description} → route to {b.route_to}")
        if qa_report.p1_bugs:
            lines += ["", "## P1 Bugs"]
            for b in qa_report.p1_bugs:
                lines.append(f"- [{b.component}] {b.description}")
        if qa_report.notes:
            lines += ["", "## Notes", qa_report.notes]

        out.write_text("\n".join(lines), encoding="utf-8")
        info(f"   ✍️  QA report written → {out}")

    def _write_campaign(self, root: Path, campaign) -> None:
        """Dump APEX's outreach campaign."""
        out = root / "marketing" / "outreach_campaign.md"
        lines = [
            "# Outreach Campaign",
            "",
            f"## ICP\n{campaign.icp_description}",
            "",
            "## Prospects",
        ]
        for p in campaign.prospects:
            lines += [
                f"### {p.name} — {p.role} @ {p.company}",
                f"- Pain: {p.pain_point}",
                f"- Angle: {p.outreach_angle}",
            ]
        lines += [
            "",
            "## Email Template",
            "```",
            campaign.email_template,
            "```",
            "",
            f"## Follow-up Cadence\n{campaign.follow_up_cadence}",
        ]
        out.write_text("\n".join(lines), encoding="utf-8")
        info(f"   ✍️  Campaign written → {out}")

    def _write_readme(self, root: Path, blueprint, financials, smoke, soft, status: str) -> None:
        """Write a developer-focused README — HOW TO USE the product. NOT an analysis report."""
        today = date.today().isoformat()
        pname = getattr(blueprint, 'product_name', root.name)
        vp    = getattr(blueprint, 'value_proposition', '')
        features = getattr(blueprint, 'mvp_features', []) or []
        stack_raw = getattr(blueprint, 'tech_stack', {})
        stack = stack_raw if isinstance(stack_raw, dict) else {}
        report_file = pname.lower().replace(' ', '_') + '_report.md'

        lines = [
            f"# {pname}",
            f"> {vp}",
            "",
            f"_Generated by AgentCompany on {today} | Status: `{status}`_",
            "",
            "## Quick Start",
            "```bash",
            "# 1. Install dependencies",
            "pip install -r requirements.txt",
            "",
            "# 2. Configure environment",
            "cp .env.example .env  # fill in your keys",
            "",
            "# 3. Run",
            "uvicorn src.backend.CODE.main:app --reload",
            "```",
            "",
            "## Tech Stack",
        ]
        for k, v in stack.items():
            lines.append(f"- **{k}**: {v}")

        if features:
            lines += ["", "## MVP Features (V1)"]
            for f in features[:6]:
                prio = {1: "Must", 2: "Should", 3: "Nice"}.get(getattr(f, 'priority', 3), "?")
                fname = getattr(f, 'name', str(f))
                fdesc = getattr(f, 'description', '')
                lines.append(f"- [{prio}] **{fname}**: {fdesc}")

        lines += [
            "",
            "## Project Structure",
            "```",
            "src/backend/CODE/    <- Generated Python backend (CORE)",
            "src/frontend/        <- Frontend build specs (PIXEL)",
            "specs/               <- Full technical plan (ARCH)",
            "tests/               <- QA report + test plan (VIGIL)",
            "marketing/           <- Outreach campaign (APEX)",
            "```",
            "",
            "## Business Analysis Report",
            f"See `reports/{report_file}` for the full AgentCompany analysis:",
            "- Gate decision + composite score",
            "- Financial model (TAM, margins, CAC, payback)",
            "- Competitive intelligence",
            "- Smoke test results",
            "- CEO action items",
        ]
        (root / "README.md").write_text("\n".join(lines), encoding="utf-8")
        info(f"README written")
        return  # everything below is replaced — keep old code below for reference
    # ── Finalization ───────────────────────────────────────────

    def _finalize(self, result: dict) -> None:
        """Generates daily reports, flushes logs, and saves agent memories."""
        daily = self.ledger.generate_daily_report(self.run_context)
        result["daily_report"] = daily

        # ── Save long-term memory for every agent ──────────────────────────
        try:
            for agent in [self.sentry, self.aria, self.nova, self.quant,
                          self.gate, self.ledger, self.arch, self.core,
                          self.pixel, self.vigil, self.apex, self.haven]:
                agent.save_memory(self.industry, result)
        except Exception:
            pass  # memory errors never break a run

        # Build CEO report text
        report_md = self._format_ceo_report(result, daily)
        post_ceo_daily_report(report_md)

        # Weekly summaries (in production you'd check day-of-week)
        post_weekly_summary("chamber1", self._format_weekly("Chamber 1 — Truth Seekers", result))
        post_weekly_summary("chamber2", self._format_weekly("Chamber 2 — The Factory", result))
        post_weekly_summary("chamber3", self._format_weekly("Chamber 3 — The Market", result))

        success("Daily logs and CEO report written to disk and Notion.")

        # ── Always write a final project report to the project folder ─────────
        try:
            self._write_final_report(result, daily)
        except Exception as e:
            from utils.logger import warning
            warning(f"Could not write final report: {e}")


    def _to_dict(self, obj) -> dict:
        """Convert Pydantic model or dict to plain dict safely."""
        if obj is None:
            return {}
        if isinstance(obj, dict):
            return obj
        try:
            return obj.model_dump()
        except AttributeError:
            try:
                return obj.dict()
            except Exception:
                return {}
    def _write_final_report(self, result: dict, daily: dict) -> None:
        """
        Write a comprehensive FINAL_REPORT.md to the project folder.
        Always written — regardless of whether the run passed or was killed.
        """
        product_name = result.get("product_name") or self.industry.replace(" ", "_").lower()
        # Report goes to reports/ folder (separate from project folder)
        reports_root = Path(__file__).parent / "reports"
        reports_root.mkdir(parents=True, exist_ok=True)
        report_filename = product_name.lower().replace(" ", "_") + "_report.md"
        # Project folder for code/specs
        project_root = Path(__file__).parent / "projects" / product_name.lower().replace(" ", "_")
        project_root.mkdir(parents=True, exist_ok=True)

        status   = result.get("status", "unknown")
        industry = result.get("industry", self.industry)
        is_pass  = status == "complete"

        lines = [
            f"# 📋 Final Report — {product_name}",
            f"> Generated by AgentCompany · {date.today().isoformat()} · Industry: {industry}",
            "",
            f"## Outcome",
            f"**Status:** `{status}`",
            f"**Decision:** {'✅ PASSED — product built and launched' if is_pass else '❌ STOPPED — ' + status.replace('_', ' ')}",
            "",
        ]

        # ── Financial summary ──────────────────────────────────────────────────
        lines += ["## Financial Summary"]
        if daily:
            lines += [
                f"- Total API cost: **${daily.get('total_spend_usd', 0):.4f}**",
                f"- Ad spend: **${self.run_context.get('ad_spend_usd', 0):.2f}**",
                f"- Revenue: **${daily.get('revenue_usd', 0):.2f}**",
            ]
            tu = daily.get("token_usage") or {}
            if tu:
                lines += [
                    f"- Total tokens used: **{tu.get('total_tokens', 0):,}**",
                    f"- API calls: **{tu.get('total_calls', 0)}**",
                ]
        lines.append("")

        # ── Product design ─────────────────────────────────────────────────────
        product = self._to_dict(result.get("product_design"))
        if product:
            lines += [
                "## Product Design (NOVA)",
                f"**Product:** {product.get('name', '—')}",
                f"**Value proposition:** {product.get('value_proposition', '—')}",
                f"**Pricing:** ${product.get('price_monthly_usd', '?')}/month",
            ]
            seg = product.get("customer_segment") or {}
            if seg:
                lines += [f"**Target segment:** {seg.get('name', '—')} — {seg.get('description', '')}"]
            features = product.get("core_features") or []
            if features:
                lines += ["", "**Core features:**"]
                for f_item in features[:5]:
                    if isinstance(f_item, dict):
                        lines.append(f"- **{f_item.get('name','?')}** (P{f_item.get('priority','?')}): {f_item.get('description','')}")
                    else:
                        lines.append(f"- {f_item}")
            lines.append("")

        # ── Financial model ────────────────────────────────────────────────────
        fm = self._to_dict(result.get("financial_model"))
        if fm:
            lines += [
                "## Financial Model (QUANT)",
                f"- TAM: **${fm.get('tam_usd', 0):,.0f}**",
                f"- Gross margin: **{fm.get('gross_margin_pct', 0):.1f}%**",
                f"- Real CAC: **${fm.get('real_cac_usd', 0):.2f}**",
                f"- Payback period: **{fm.get('payback_period_months', '?')} months**",
                "",
            ]

        # ── Gate decisions ─────────────────────────────────────────────────────
        gate_scores = result.get("gate_scores") or {}
        if gate_scores:
            lines += ["## GATE Decisions"]
            for stage, scores in gate_scores.items():
                if isinstance(scores, dict):
                    verdict = scores.get("verdict", "?")
                    composite = scores.get("composite_score", "?")
                    icon = "✅" if verdict == "GO" else "❌"
                    lines.append(f"- **{stage}**: {icon} {verdict} (score: {composite}/10)")
                    reason = scores.get("reason") or scores.get("reasoning", "")
                    if reason:
                        lines.append(f"  > {str(reason)[:200]}")
            lines.append("")

        # ── Smoke test ─────────────────────────────────────────────────────────
        smoke = result.get("smoke_test") or {}
        if smoke:
            passed = smoke.get("passed", False)
            lines += [
                "## Smoke Test (APEX)",
                f"- Result: {'✅ PASSED' if passed else '❌ FAILED'}",
                f"- Ad spend: ${smoke.get('ad_spend_usd', 0):.2f}",
                f"- Impressions: {smoke.get('impressions', 0):,}",
                f"- CTR: {smoke.get('ctr', 0):.2%}",
                f"- Conversions: {smoke.get('buy_now_conversions', 0)}",
                f"- Real CAC: ${smoke.get('real_cac_usd', 0):.2f}",
            ]
            if smoke.get("notes"):
                lines.append(f"- Notes: {smoke['notes'][:200]}")
            lines.append("")

        # ── Competitive intel ──────────────────────────────────────────────────
        sentry = self._to_dict(result.get("competitive_intel"))
        if sentry:
            alert = sentry.get("alert_level", "green")
            lines += [
                "## Competitive Intelligence (SENTRY)",
                f"- Alert level: **{alert.upper()}**",
            ]
            for comp in (sentry.get("competitors") or [])[:3]:
                lines.append(f"- {comp.get('name','?')}: {comp.get('threat_level','?')} threat — {comp.get('recent_move','')[:100]}")
            lines.append("")

        # ── Tech plan (if built) ───────────────────────────────────────────────
        if (project_root / "specs" / "technical_plan.md").exists():
            lines += [
                "## Technical Plan",
                "_See `specs/technical_plan.md` for full tech stack, database schema, and API routes._",
                "",
            ]

        # ── CEO action items ───────────────────────────────────────────────────
        action_items = daily.get("action_items", []) if daily else []
        if action_items:
            lines += ["## CEO Action Items"]
            for item in action_items:
                lines.append(f"- ⚡ {item}")
            lines.append("")

        # ── Project structure ──────────────────────────────────────────────────
        lines += [
            "## Where to Find Things",
            "```",
            f"reports/{report_filename}",
            "  <- This AgentCompany analysis report",
            "",
            f"projects/{product_name.lower().replace(' ', '_')}/",
            "  README.md          <- How to run the product",
            "  specs/             <- ARCH technical plan",
            "  src/backend/CODE/  <- Generated Python code",
            "  src/frontend/      <- PIXEL frontend build",
            "  tests/             <- VIGIL QA report",
            "  marketing/         <- APEX outreach campaign",
            "```",
            "---",
            f"*Generated by AgentCompany · CEO: {self.run_context.get('ceo_name', 'Rachata P.')}*",
        ]

        report_path = reports_root / report_filename
        report_path.write_text("\n".join(lines), encoding="utf-8")
        success(f"   📋  Report written → {report_path}")

    def _format_ceo_report(self, result: dict, daily: dict) -> str:
        today = date.today().isoformat()
        lines = [
            f"# 👤 CEO Daily Report — {today}",
            f"",
            f"## Status",
            f"- Run status: **{result['status']}**",
            f"- Industry: {result['industry']}",
            f"- Product: {result.get('product_name', 'N/A')}",
            f"",
            f"## Financial",
            f"- Total spend: ${daily.get('total_spend_usd', 0):.2f}",
            f"- Revenue: ${daily.get('revenue_usd', 0):.2f}",
            f"- Ad spend: ${self.run_context.get('ad_spend_usd', 0):.2f}",
            f"",
            f"## Gate Decisions",
        ]
        for g in result.get("gate_decisions", []):
            lines.append(f"- {g['stage']}: **{g['verdict']}**")

        if result.get("smoke_test"):
            st = result["smoke_test"]
            lines += [
                f"",
                f"## Smoke Test",
                f"- CTR: {st.get('ctr', 0):.2%}",
                f"- Real CAC: ${st.get('real_cac_usd', 0):.2f}",
                f"- Passed: {st.get('passed')}",
            ]

        if result.get("soft_launch"):
            sl = result["soft_launch"]
            lines += [
                f"",
                f"## Soft Launch",
                f"- Day-7 retention: {sl.get('day7_retention_rate', 0):.0%}",
                f"- NPS: {sl.get('nps', 0)}",
                f"- Passed: {sl.get('passed')}",
            ]

        action_items = daily.get("action_items", [])
        if action_items:
            lines += ["", "## Action Items for CEO"]
            for item in action_items:
                lines.append(f"- {item}")

        return "\n".join(lines)

    def _format_weekly(self, department: str, result: dict) -> str:
        return (
            f"# {department} — Weekly Summary\n\n"
            f"Status: {result['status']}\n"
            f"Industry: {result['industry']}\n"
            f"Product: {result.get('product_name', 'N/A')}\n"
        )
