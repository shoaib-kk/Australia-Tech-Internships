"""Workday career sites.

Every Workday careers page (https://{tenant}.wdN.myworkdayjobs.com/{site}) is
backed by a public JSON search endpoint that the page itself calls. We use the
same endpoint with a few early-career search terms, which keeps request counts
low on very large boards (banks, telcos).
"""
from __future__ import annotations

from ..http import pause, post_json
from ..models import Job

DEFAULT_TERMS = ["intern", "graduate", "vacation", "summer", "student", "cadet"]
PAGE = 20        # Workday caps page size at 20
MAX_PAGES = 5    # per search term


def fetch_workday(session, board: dict) -> list[Job]:
    tenant, wd, site = board["tenant"], board["wd"], board["site"]
    host = f"https://{tenant}.{wd}.myworkdayjobs.com"
    api = f"{host}/wday/cxs/{tenant}/{site}/jobs"
    terms = board.get("search_terms") or DEFAULT_TERMS

    seen, jobs = set(), []
    for term in terms:
        for page in range(MAX_PAGES):
            data = post_json(session, api, {
                "appliedFacets": {}, "limit": PAGE, "offset": page * PAGE, "searchText": term,
            })
            postings = data.get("jobPostings", []) or []
            for p in postings:
                path = p.get("externalPath", "")
                if not path or path in seen:
                    continue
                seen.add(path)
                jobs.append(Job(
                    source="workday",
                    source_id=path.rsplit("_", 1)[-1],
                    company=board.get("name", tenant),
                    title=p.get("title", ""),
                    location=p.get("locationsText", ""),
                    url=f"{host}/en-US/{site}{path}",
                    # Workday only gives relative text like "Posted 3 Days Ago"
                    posted="",
                    employment_type=p.get("postedOn", ""),
                ))
            if len(postings) < PAGE or (page + 1) * PAGE >= data.get("total", 0):
                break
            pause()
        pause()
    return jobs
