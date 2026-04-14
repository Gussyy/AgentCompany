"""
Notion logger — posts daily department logs and weekly summaries
to the AgentCompany Notion workspace using the Notion API directly.

Requires NOTION_API_KEY in .env.
Page IDs are sourced from config.py.
"""
import os
import json
import requests
from datetime import datetime, date
from pathlib import Path
from typing import Optional
from config import NOTION_API_KEY, NOTION_TEAM_DIR_PAGE_ID


NOTION_VERSION = "2022-06-28"
BASE_URL = "https://api.notion.com/v1"


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Content-Type": "application/json",
        "Notion-Version": NOTION_VERSION,
    }


def _is_configured() -> bool:
    return bool(NOTION_API_KEY)


# ── Low-level helpers ──────────────────────────────────────────

def _create_page(parent_id: str, title: str, content_md: str) -> Optional[str]:
    """Creates a Notion page under parent_id. Returns the new page ID."""
    if not _is_configured():
        return None

    # Build blocks from markdown-like content (paragraphs)
    blocks = []
    for line in content_md.split("\n"):
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("## "):
            blocks.append({
                "object": "block", "type": "heading_2",
                "heading_2": {"rich_text": [{"type": "text", "text": {"content": stripped[3:]}}]}
            })
        elif stripped.startswith("### "):
            blocks.append({
                "object": "block", "type": "heading_3",
                "heading_3": {"rich_text": [{"type": "text", "text": {"content": stripped[4:]}}]}
            })
        elif stripped.startswith("- "):
            blocks.append({
                "object": "block", "type": "bulleted_list_item",
                "bulleted_list_item": {"rich_text": [{"type": "text", "text": {"content": stripped[2:]}}]}
            })
        elif stripped.startswith("> "):
            blocks.append({
                "object": "block", "type": "quote",
                "quote": {"rich_text": [{"type": "text", "text": {"content": stripped[2:]}}]}
            })
        else:
            blocks.append({
                "object": "block", "type": "paragraph",
                "paragraph": {"rich_text": [{"type": "text", "text": {"content": stripped}}]}
            })

    payload = {
        "parent": {"page_id": parent_id},
        "properties": {
            "title": {"title": [{"type": "text", "text": {"content": title}}]}
        },
        "children": blocks[:100],  # Notion API limit per request
    }

    resp = requests.post(f"{BASE_URL}/pages", headers=_headers(), json=payload)
    if resp.status_code == 200:
        return resp.json().get("id")
    return None


def _append_blocks(page_id: str, content_md: str) -> bool:
    """Appends markdown-like content as blocks to an existing Notion page."""
    if not _is_configured():
        return False

    blocks = []
    for line in content_md.split("\n"):
        stripped = line.strip()
        if not stripped:
            continue
        blocks.append({
            "object": "block", "type": "paragraph",
            "paragraph": {"rich_text": [{"type": "text", "text": {"content": stripped}}]}
        })

    payload = {"children": blocks[:100]}
    resp = requests.patch(
        f"{BASE_URL}/blocks/{page_id}/children",
        headers=_headers(),
        json=payload,
    )
    return resp.status_code == 200


# ── Public interface ───────────────────────────────────────────

def post_daily_log(department: str, agent_name: str, log_content: str) -> None:
    """
    Posts a daily log entry to Notion under the Team Directory.
    Also saves locally to logs/<department>/<date>.md
    """
    today = date.today().isoformat()
    title = f"📋 {agent_name} Daily Log — {today}"

    # Always save locally first
    from config import LOG_DIRS
    log_dir = LOG_DIRS.get(department, LOG_DIRS["chamber1"])
    log_file = log_dir / f"{today}.md"
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"\n\n---\n## {agent_name} — {datetime.now().strftime('%H:%M')}\n\n")
        f.write(log_content)
        f.write("\n")

    # Post to Notion if configured
    if _is_configured():
        _create_page(NOTION_TEAM_DIR_PAGE_ID, title, log_content)


def post_weekly_summary(department: str, summary: str) -> None:
    """Posts a weekly summary page to Notion."""
    from datetime import date
    week = date.today().strftime("Week of %B %d, %Y")
    title = f"📊 {department} Weekly Summary — {week}"

    if _is_configured():
        _create_page(NOTION_TEAM_DIR_PAGE_ID, title, summary)

    # Also save locally
    from config import LOG_DIRS
    log_dir = LOG_DIRS.get(department, LOG_DIRS["chamber1"])
    summary_file = log_dir / f"weekly_{date.today().isoformat()}.md"
    with open(summary_file, "w", encoding="utf-8") as f:
        f.write(f"# {title}\n\n{summary}")


def post_ceo_daily_report(report: str) -> None:
    """
    Saves the daily CEO report locally and posts it to Notion.
    """
    today = date.today().isoformat()
    title = f"👤 CEO Daily Report — {today}"

    # Save locally
    from config import LOG_DIRS
    report_file = LOG_DIRS["ceo_reports"] / f"{today}.md"
    with open(report_file, "w", encoding="utf-8") as f:
        f.write(f"# {title}\n\n{report}")

    # Post to Notion
    if _is_configured():
        _create_page(NOTION_TEAM_DIR_PAGE_ID, title, report)

    return str(report_file)
