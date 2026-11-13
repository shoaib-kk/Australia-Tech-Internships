"""Offline tests: a fake HTTP session returns realistic API payloads for each source."""
from __future__ import annotations

import json
import shutil
from datetime import date
from pathlib import Path

import pytest
import yaml

from job_radar.filters import JobFilter
from job_radar.models import Job
from job_radar.pipeline import run

ROOT = Path(__file__).resolve().parents[1]
TODAY = date(2026, 11, 15)

GREENHOUSE = {"jobs": [
    {"id": 1, "title": "AEMO Internship Pool 2026/27", "location": {"name": "Melbourne, Victoria"},
     "absolute_url": "https://gh/1", "first_published": "2026-11-10T00:00:00Z",
     "content": "&lt;p&gt;Python, SQL and data science&lt;/p&gt;"},
    {"id": 2, "title": "Senior Data Engineer", "location": {"name": "Melbourne"},
     "absolute_url": "https://gh/2", "first_published": "2026-11-10"},
    {"id": 3, "title": "Software Engineer Intern (2027)", "location": {"name": "Austin, TX"},
     "absolute_url": "https://gh/3", "first_published": "2026-11-10"},
    {"id": 4, "title": "Internal Communications Specialist", "location": {"name": "Sydney"},
     "absolute_url": "https://gh/4", "first_published": "2026-11-10"},
]}
LEVER = [
    {"id": "a", "text": "Graduate Software Developer", "hostedUrl": "https://lever/a",
     "categories": {"location": "Sydney, NSW", "commitment": "Full-time"}, "createdAt": 1794441600000,
     "descriptionPlain": "Work with Python and React"},
    {"id": "b", "text": "Account Manager", "hostedUrl": "https://lever/b",
     "categories": {"location": "Sydney"}, "createdAt": 1794441600000},
]
ASHBY = {"jobs": [
    {"id": "x", "title": "Software Engineer Intern (Summer 2027)", "location": "Melbourne",
     "secondaryLocations": [{"location": "Sydney"}], "jobUrl": "https://ashby/x",
     "publishedAt": "2026-11-12T00:00:00Z", "employmentType": "Intern", "isListed": True},
    {"id": "y", "title": "Machine Learning Intern", "location": "Remote", "jobUrl": "https://ashby/y",
     "publishedAt": "2026-11-12", "isListed": True},
]}
SMARTR = {"totalFound": 1, "content": [
    {"id": "777", "name": "2026/27 KPMG Vacationer (Intern) Program", "releasedDate": "2026-10-01T00:00:00Z",
     "location": {"city": "Melbourne", "country": "au", "fullLocation": "Melbourne VIC, Australia"},
     "typeOfEmployment": {"label": "Internship"}},
]}
WORKDAY = {"total": 2, "jobPostings": [
    {"title": "2027 CommBank Graduate Campaign", "externalPath": "/job/Sydney/Grad_REQ1",
     "locationsText": "Sydney, NSW", "postedOn": "Posted 3 Days Ago"},
    {"title": "IT Service Desk Cadet", "externalPath": "/job/Melbourne/Cadet_REQ2",
     "locationsText": "Melbourne, VIC", "postedOn": "Posted Today"},
]}
ADZUNA = {"results": [
    # duplicate of the Lever role -> should collapse into the Lever one
    {"id": 99, "title": "Graduate Software Developer", "company": {"display_name": "Deputy"},
     "location": {"display_name": "Sydney, New South Wales"}, "redirect_url": "https://adz/99",
     "created": "2026-11-11T00:00:00Z", "description": "python"},
    {"id": 100, "title": "Junior Data Analyst", "company": {"display_name": "Small Co"},
     "location": {"display_name": "Geelong, Victoria"}, "redirect_url": "https://adz/100",
     "created": "2026-11-13T00:00:00Z", "description": "SQL and Power BI"},
]}


class FakeResp:
    def __init__(self, payload, status=200):
        self.payload, self.status_code = payload, status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return json.loads(json.dumps(self.payload))


class FakeSession:
    def get(self, url, **kw):
        if "greenhouse" in url:
            return FakeResp(GREENHOUSE if "/aemo/" in url else {}, 200 if "/aemo/" in url else 404)
        if "lever.co" in url:
            return FakeResp(LEVER)
        if "ashbyhq" in url:
            return FakeResp(ASHBY)
        if "smartrecruiters" in url:
            return FakeResp(SMARTR)
        if "adzuna" in url:
            return FakeResp(ADZUNA if url.endswith("/1") else {"results": []})
        raise AssertionError(url)

    def post(self, url, json=None, **kw):
        assert "myworkdayjobs" in url
        return FakeResp(WORKDAY if json["offset"] == 0 else {"total": 2, "jobPostings": []})


@pytest.fixture
def project(tmp_path, monkeypatch):
    shutil.copytree(ROOT / "config", tmp_path / "config")
    (tmp_path / "config" / "companies.yaml").write_text(yaml.safe_dump({
        "greenhouse": [{"id": "aemo", "name": "AEMO"}, {"id": "broken", "name": "Broken Co"}],
        "lever": [{"id": "deputy", "name": "Deputy"}],
        "ashby": [{"id": "airwallex", "name": "Airwallex"}],
        "smartrecruiters": [{"id": "KPMGAustralia1", "name": "KPMG Australia"}],
        "workday": [{"tenant": "cba", "wd": "wd3", "site": "CommBank_Careers", "name": "CommBank",
                     "search_terms": ["graduate"]}],
        "adzuna": {"queries": ["software intern"], "pages_per_query": 1},
    }))
    monkeypatch.setenv("ADZUNA_APP_ID", "x")
    monkeypatch.setenv("ADZUNA_APP_KEY", "y")
    return tmp_path


def titles(jobs):
    return sorted(j.title for j in jobs)


def test_end_to_end(project):
    res = run(project, today=TODAY, session=FakeSession())
    got = titles(res["all"])
    assert got == sorted([
        "AEMO Internship Pool 2026/27",
        "Graduate Software Developer",
        "Software Engineer Intern (Summer 2027)",
        "2026/27 KPMG Vacationer (Intern) Program",
        "2027 CommBank Graduate Campaign",
        "IT Service Desk Cadet",
        "Junior Data Analyst",
    ])
    # dropped: senior, US-only, "Internal" (not an intern), non-tech sales, global remote
    # the Adzuna duplicate of Deputy's role collapses onto the direct Lever link
    dev = next(j for j in res["all"] if j.title == "Graduate Software Developer")
    assert dev.source == "lever"
    # one broken board is reported, not fatal
    assert len(res["errors"]) == 1 and "Broken Co" in res["errors"][0]

    out = project / "output"
    assert (out / "openings.csv").exists() and (out / "new_this_week.md").exists()
    md = (out / "new_this_week.md").read_text()
    assert "7 new" in md and "Broken Co" in md


def test_second_run_only_reports_new(project):
    run(project, today=TODAY, session=FakeSession())
    res = run(project, today=date(2026, 11, 22), session=FakeSession())
    assert res["stats"]["new"] == 0 and res["stats"]["matched"] >= 6


def test_applied_list_excludes(project):
    (project / "config" / "applied.csv").write_text("# company, role\nKPMG Australia\nAirwallex, software engineer intern\n")
    res = run(project, today=TODAY, session=FakeSession())
    assert not any(j.company in ("KPMG Australia", "Airwallex") for j in res["all"])
    assert res["stats"]["skipped_already_applied"] == 2


def test_scoring_prefers_data_roles_in_melbourne():
    cfg = yaml.safe_load((ROOT / "config" / "filters.yaml").read_text())
    f = JobFilter(cfg, today=TODAY)
    data = Job("x", "1", "A", "Data Science Intern", "Melbourne, VIC", "u", posted="2026-11-14",
               description="python sql machine learning")
    sw = Job("x", "2", "B", "Graduate Software Engineer", "Perth, WA", "u")
    ai = Job("x", "3", "C", "AI Intern", "Sydney", "u")
    it = Job("x", "4", "D", "IT Graduate", "Brisbane QLD", "u")
    it_lower = Job("x", "5", "E", "Would it suit you? Graduate program", "Sydney", "u")
    assert all(f.evaluate(j) for j in (data, sw, ai, it, it_lower))
    assert data.score > sw.score
    assert ai.category == "Data / ML / AI"
    assert it.category == "IT / Tech"
    assert it_lower.category == "General program"  # lowercase "it" is not "IT"


@pytest.mark.parametrize("title", ["Senior Software Engineer Intern Mentor", "Internal Auditor",
                                   "Engineering Manager, Graduates", "International Sales Graduate"])
def test_rejects(title):
    cfg = yaml.safe_load((ROOT / "config" / "filters.yaml").read_text())
    j = Job("x", "1", "A", title, "Melbourne", "u")
    ok = JobFilter(cfg, today=TODAY).evaluate(j)
    if title == "International Sales Graduate":
        assert ok and j.category == "General program"  # kept but scored low
    else:
        assert not ok
