"""Amazon / AWS jobs, from the JSON search endpoint behind amazon.jobs."""
from __future__ import annotations

from datetime import datetime

from ..http import get_json, pause
from ..models import Job

DEFAULT_TERMS = ["intern", "graduate", "university", "new grad"]


def _date(text: str) -> str:
    try:
        return datetime.strptime(text.strip(), "%B %d, %Y").date().isoformat()
    except (ValueError, AttributeError):
        return ""


def fetch_amazon(session, board: dict) -> list[Job]:
    seen, jobs = set(), []
    for term in board.get("search_terms") or DEFAULT_TERMS:
        data = get_json(session, "https://www.amazon.jobs/en/search.json", params={
            "normalized_country_code[]": board.get("country", "AUS"),
            "base_query": term, "result_limit": 100, "sort": "recent",
        })
        for j in data.get("jobs", []):
            jid = str(j.get("id_icims") or j.get("id"))
            if jid in seen:
                continue
            seen.add(jid)
            jobs.append(Job(
                source="amazon",
                source_id=jid,
                company=board.get("name", "Amazon"),
                title=j.get("title", ""),
                location=j.get("normalized_location") or j.get("location", ""),
                url="https://www.amazon.jobs" + j.get("job_path", ""),
                posted=_date(j.get("posted_date", "")),
                description=(j.get("basic_qualifications") or "")[:2000],
            ))
        pause()
    return jobs
