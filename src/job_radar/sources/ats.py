"""Public job-board APIs offered by applicant-tracking systems.

These endpoints are published by each ATS specifically so job boards and
aggregators can read a company's open roles - no login, no HTML scraping.
"""
from __future__ import annotations

from ..http import get_json, pause
from ..models import Job


def _helpers():
    from . import strip_html, to_date  # local import avoids a circular import
    return strip_html, to_date


def fetch_greenhouse(session, board: dict) -> list[Job]:
    strip_html, to_date = _helpers()
    token = board["id"]
    data = get_json(session, f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs",
                    params={"content": "true"})
    jobs = []
    for j in data.get("jobs", []):
        jobs.append(Job(
            source="greenhouse",
            source_id=str(j.get("id")),
            company=board.get("name", token),
            title=j.get("title", ""),
            location=(j.get("location") or {}).get("name", ""),
            url=j.get("absolute_url", ""),
            posted=to_date(j.get("first_published") or j.get("updated_at")),
            description=strip_html(j.get("content")),
        ))
    return jobs


def fetch_lever(session, board: dict) -> list[Job]:
    strip_html, to_date = _helpers()
    site = board["id"]
    # Lever has separate global and EU hosts; most companies are on the global one.
    host = "api.eu.lever.co" if board.get("region") == "eu" else "api.lever.co"
    data = get_json(session, f"https://{host}/v0/postings/{site}", params={"mode": "json"})
    jobs = []
    for j in data or []:
        cats = j.get("categories") or {}
        locs = cats.get("allLocations") or [cats.get("location", "")]
        jobs.append(Job(
            source="lever",
            source_id=j.get("id", ""),
            company=board.get("name", site),
            title=j.get("text", ""),
            location=" / ".join(l for l in locs if l),
            url=j.get("hostedUrl", ""),
            posted=to_date(j.get("createdAt")),
            employment_type=cats.get("commitment", "") or "",
            description=strip_html(j.get("descriptionPlain") or j.get("description")),
        ))
    return jobs


def fetch_ashby(session, board: dict) -> list[Job]:
    strip_html, to_date = _helpers()
    name = board["id"]
    data = get_json(session, f"https://api.ashbyhq.com/posting-api/job-board/{name}")
    jobs = []
    for j in data.get("jobs", []):
        if j.get("isListed") is False:
            continue
        locs = [j.get("location", "")] + [
            s.get("location", "") for s in j.get("secondaryLocations") or []
        ]
        if j.get("isRemote"):
            locs.append("Remote")
        jobs.append(Job(
            source="ashby",
            source_id=j.get("id", ""),
            company=board.get("name", name),
            title=j.get("title", ""),
            location=" / ".join(l for l in locs if l),
            url=j.get("jobUrl", ""),
            posted=to_date(j.get("publishedAt")),
            employment_type=j.get("employmentType", "") or "",
            description=strip_html(j.get("descriptionPlain") or j.get("descriptionHtml")),
        ))
    return jobs


def fetch_smartrecruiters(session, board: dict) -> list[Job]:
    _, to_date = _helpers()
    cid = board["id"]
    jobs, offset, limit = [], 0, 100
    while True:
        params = {"limit": limit, "offset": offset}
        if board.get("country"):
            params["country"] = board["country"]  # e.g. "au" to keep big global boards small
        data = get_json(session, f"https://api.smartrecruiters.com/v1/companies/{cid}/postings",
                        params=params)
        content = data.get("content", [])
        for j in content:
            loc = j.get("location") or {}
            loc_text = loc.get("fullLocation") or ", ".join(
                x for x in (loc.get("city"), loc.get("region"), loc.get("country")) if x)
            if loc.get("remote"):
                loc_text += " / Remote"
            jobs.append(Job(
                source="smartrecruiters",
                source_id=str(j.get("id")),
                company=board.get("name") or (j.get("company") or {}).get("name", cid),
                title=j.get("name", ""),
                location=loc_text,
                url=f"https://jobs.smartrecruiters.com/{cid}/{j.get('id')}",
                posted=to_date(j.get("releasedDate")),
                employment_type=(j.get("typeOfEmployment") or {}).get("label", ""),
            ))
        offset += limit
        if offset >= data.get("totalFound", 0) or not content or offset >= 1000:
            break
        pause()
    return jobs
