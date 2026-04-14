"""
web_search.py — real internet search for agents.
Uses ddgs (formerly duckduckgo_search) — no API key needed.
"""
from __future__ import annotations


def _get_ddgs():
    try:
        from ddgs import DDGS
    except ImportError:
        from duckduckgo_search import DDGS
    return DDGS


def search(query: str, max_results: int = 8, region: str = "wt-wt") -> list[dict]:
    """Web search. Returns [{"title", "href", "body"}, ...]"""
    try:
        DDGS = _get_ddgs()
        with DDGS() as ddgs:
            return list(ddgs.text(query, region=region, max_results=max_results)) or []
    except Exception as e:
        return [{"title": "Search unavailable", "href": "", "body": str(e)}]


def news_search(query: str, max_results: int = 8) -> list[dict]:
    """Recent news search. Returns [{"title", "url", "body", "date", "source"}, ...]"""
    try:
        DDGS = _get_ddgs()
        with DDGS() as ddgs:
            return list(ddgs.news(query, max_results=max_results)) or []
    except Exception as e:
        return [{"title": "News unavailable", "url": "", "body": str(e)}]


def format_search_results(results: list[dict], max_chars_per: int = 300) -> str:
    """Format results into a readable block for agent prompts."""
    if not results:
        return "No search results found."
    lines = []
    for i, r in enumerate(results, 1):
        title = r.get("title") or r.get("name", "")
        body  = r.get("body") or r.get("snippet", "")
        url   = r.get("href") or r.get("url", "")
        date  = r.get("date", "")
        body  = body[:max_chars_per] + "…" if len(body) > max_chars_per else body
        line  = f"[{i}] {title}"
        if date:
            line += f" ({date})"
        line += f"\n    {body}"
        if url:
            line += f"\n    Source: {url}"
        lines.append(line)
    return "\n\n".join(lines)
