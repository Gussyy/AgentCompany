"""
SENTRY — Competitive Intelligence Lead
Always On | London
Monitors competitor moves using REAL internet searches, fires Priority Alerts to CEO.
"""
from agents.base import BaseAgent
from utils.web_search import news_search, search, format_search_results


SYSTEM_PROMPT = """
You are SENTRY, Competitive Intelligence Lead at AgentCompany.
Your persona: vigilant, low noise, high signal. Ex-intelligence analyst.

You have access to REAL-TIME web search results provided below.
Use these results as your primary source — do NOT fabricate competitor news.
Only alert the CEO when a move materially threatens the financial model.

Minor price changes = data point. Direct competitor entering the exact segment = RED ALERT.
Output valid JSON only.
""".strip()


class SENTRY(BaseAgent):
    name       = "SENTRY"
    role       = "Competitive Intelligence Lead"
    department = "sentinel"
    emoji      = "🔍"

    def scan_competitive_landscape(self, industry: str, product_name: str) -> dict:

        # ── Step 1: Real internet searches ──────────────────────────────────
        self._emit_status("Searching the web for competitive intelligence…")

        queries = [
            f"{industry} startup funding 2025 2026",
            f"{industry} competitor news latest",
            f"{industry} market trends 2026",
        ]
        if product_name and product_name != "Unknown":
            queries.append(f"{product_name} competitors alternatives")

        all_results = []
        for q in queries:
            results = news_search(q, max_results=5)
            if not results or "unavailable" in (results[0].get("body","")).lower():
                results = search(q, max_results=5)
            all_results.extend(results)

        # Deduplicate by title
        seen, unique = set(), []
        for r in all_results:
            t = r.get("title","")
            if t and t not in seen:
                seen.add(t)
                unique.append(r)

        web_context = format_search_results(unique[:12])

        # ── Step 2: Ask LLM to analyse the real search results ────────────
        prompt = f"""
Industry: {industry}
Our product concept: {product_name}

=== REAL-TIME WEB SEARCH RESULTS (use these as your source) ===
{web_context}
=== END SEARCH RESULTS ===

Based on the search results above, analyse the competitive landscape and return JSON:
{{
  "industry": "{industry}",
  "search_queries_used": {queries},
  "competitors": [
    {{
      "name": "CompetitorName",
      "positioning": "what they do",
      "recent_move": "specific news from search results",
      "threat_level": "green|yellow|red",
      "source": "URL from search results if available"
    }}
  ],
  "market_trends": ["trend 1 from search", "trend 2 from search"],
  "alert_level": "green|yellow|red",
  "ceo_alert_message": null,
  "recommended_response": "specific actionable response"
}}

IMPORTANT: Base competitor moves on ACTUAL search results, not invented data.
If a result mentions a specific company, funding round, or product launch — include it.
""".strip()

        data = self.run_json(SYSTEM_PROMPT, prompt)

        # Attach raw search snippet count so CEO knows searches were real
        data["_web_results_found"] = len(unique)
        data["_searches_performed"] = queries

        self.flush_daily_log()
        return data

    def _emit_status(self, msg: str):
        """Emit a status message to the dashboard without calling the LLM."""
        from agents.base import _emit
        _emit("agent_start", self.name, self.department, "running", msg)
