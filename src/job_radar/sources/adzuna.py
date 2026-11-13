"""Adzuna job-search API (aggregates SEEK-style listings from many smaller boards).

Free key: https://developer.adzuna.com  -> set ADZUNA_APP_ID and ADZUNA_APP_KEY.
Without a key this source is skipped.
"""
from __future__ import annotations

import os

from ..http import get_json, pause
from ..models import Job

API = "https://api.adzuna.com/v1/api/jobs/au/search/{page}"


def fetch_adzuna(session, queries: list[str], max_days_old: int = 14, pages: int = 2) -> list[Job]:
    from . import strip_html, to_date

    app_id, app_key = os.getenv("ADZUNA_APP_ID"), os.getenv("ADZUNA_APP_KEY")
    if not (app_id and app_key):
        raise RuntimeError("ADZUNA_APP_ID / ADZUNA_APP_KEY not set - skipping Adzuna")

    jobs, seen = [], set()
    for q in queries:
        for page in range(1, pages + 1):
            data = get_json(session, API.format(page=page), params={
                "app_id": app_id, "app_key": app_key, "what": q,
                "results_per_page": 50, "max_days_old": max_days_old,
                "sort_by": "date", "content-type": "application/json",
            })
            results = data.get("results", [])
            for r in results:
                rid = str(r.get("id"))
                if rid in seen:
                    continue
                seen.add(rid)
                jobs.append(Job(
                    source="adzuna",
                    source_id=rid,
                    company=(r.get("company") or {}).get("display_name", ""),
                    title=strip_html(r.get("title")),
                    location=(r.get("location") or {}).get("display_name", ""),
                    url=r.get("redirect_url", ""),
                    posted=to_date(r.get("created")),
                    employment_type=" ".join(
                        x for x in (r.get("contract_type"), r.get("contract_time")) if x),
                    description=strip_html(r.get("description")),
                ))
            if len(results) < 50:
                break
            pause(1.0)  # free tier is rate limited
    return jobs
