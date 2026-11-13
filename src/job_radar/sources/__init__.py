"""Job sources. Each fetcher takes (session, board_config) and returns list[Job]."""
from __future__ import annotations

import html
import re
from datetime import datetime, timezone

from .ats import fetch_ashby, fetch_greenhouse, fetch_lever, fetch_smartrecruiters
from .workday import fetch_workday

FETCHERS = {
    "greenhouse": fetch_greenhouse,
    "lever": fetch_lever,
    "ashby": fetch_ashby,
    "smartrecruiters": fetch_smartrecruiters,
    "workday": fetch_workday,
}

__all__ = ["FETCHERS", "strip_html", "to_date"]


def strip_html(text: str | None, limit: int = 4000) -> str:
    if not text:
        return ""
    text = html.unescape(text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)  # Greenhouse double-escapes content
    return re.sub(r"\s+", " ", text).strip()[:limit]


def to_date(value) -> str:
    """Accept ISO strings or epoch milliseconds; return YYYY-MM-DD or ''."""
    if value in (None, ""):
        return ""
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value / 1000, tz=timezone.utc).date().isoformat()
    s = str(value)
    m = re.match(r"(\d{4}-\d{2}-\d{2})", s)
    return m.group(1) if m else ""
