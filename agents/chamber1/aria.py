"""
ARIA — Head of Market Research (The Observer)
Chamber 1 | San Francisco
Reads the market and produces a ranked friction report.
"""
import json
from agents.base import BaseAgent
from models.schemas import FrictionReport, FrictionPoint
from utils.web_search import search, news_search, format_search_results


SYSTEM_PROMPT = """
You are ARIA, Head of Market Research at AgentCompany.
Your persona: analytical, data-driven, zero editorialising.
You don't have opinions about which problem is interesting — you surface evidence.

Your job is to analyse a target industry using REAL web search results provided to you,
and produce a structured friction report. Focus on actual user complaints, forum threads,
app reviews, and support patterns found in the search results.

Always output valid JSON matching the FrictionReport schema exactly.
""".strip()


class ARIA(BaseAgent):
    name       = "ARIA"
    role       = "Head of Market Research"
    department = "chamber1"
    emoji      = "🔭"

    def run_friction_report(self, industry: str) -> FrictionReport:
        # ── Real web search for user pain points ─────────────────────────
        queries = [
            f"{industry} user complaints problems 2025 2026",
            f"{industry} app reviews negative feedback",
            f"{industry} reddit problems frustrations",
            f"biggest pain points {industry} customers",
        ]
        all_results = []
        for q in queries:
            all_results.extend(search(q, max_results=4))
        # Deduplicate
        seen, unique = set(), []
        for r in all_results:
            t = r.get("title", "")
            if t and t not in seen:
                seen.add(t); unique.append(r)
        web_context = format_search_results(unique[:12])

        prompt = f"""
Analyse the '{industry}' industry and identify the top 5 friction points users experience.

=== REAL-TIME WEB SEARCH RESULTS ===
{web_context}
=== END SEARCH RESULTS ===

Use the search results above as your PRIMARY evidence source.
Quote or reference specific findings where possible.

For each friction point provide:
- title: short name
- description: what exactly frustrates users (2-3 sentences)
- frequency: 1-10 (how often is this complained about)
- severity: 1-10 (how painful is it for users)
- emotional_heat: 1-10 (how much frustration is expressed)
- willingness_to_pay: true/false (do complaints mention paying for a solution)

Also provide:
- top_opportunity: the single best opportunity you identified (1 sentence)
- sources: list of source types you'd draw data from

Return JSON in this exact format:
{{
  "industry": "{industry}",
  "friction_points": [
    {{
      "title": "...",
      "description": "...",
      "frequency": 8,
      "severity": 7,
      "emotional_heat": 9,
      "willingness_to_pay": true
    }}
  ],
  "top_opportunity": "...",
  "sources": ["Reddit threads", "App store reviews", "..."]
}}
""".strip()

        data = self.run_json(SYSTEM_PROMPT, prompt)
        try:
            report = FrictionReport(**data)
        except Exception:
            # Fallback: construct from raw if parsing fails
            fps = [FrictionPoint(**fp) for fp in data.get("friction_points", [])]
            report = FrictionReport(
                industry=industry,
                friction_points=fps,
                top_opportunity=data.get("top_opportunity", "Unknown"),
                sources=data.get("sources", []),
            )
        self.flush_daily_log()
        return report
