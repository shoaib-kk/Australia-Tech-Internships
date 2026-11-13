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
    }))
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
    ])
    # dropped: senior, US-only, "Internal" (not an intern), non-tech sales, global remote
    # one broken board is reported, not fatal
    assert len(res["errors"]) == 1 and "Broken Co" in res["errors"][0]

    out = project / "output"
    assert (out / "openings.csv").exists() and (out / "new_this_week.md").exists()
    md = (out / "new_this_week.md").read_text()
    assert "6 new" in md and "Broken Co" in md


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
    cfg = yaml.safe_load((ROOT / "config" / "filters.yaml").read_text(encoding="utf-8"))
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


@pytest.mark.parametrize("title,company", [
    ("Senior Software Engineer Intern Mentor", "A"), ("Internal Auditor", "A"),
    ("Engineering Manager, Graduates", "A"), ("International Sales Graduate", "A"),
    ("Junior VIP Host - English Speaking", "A"), ("Audit & Assurance Vacationer", "A"),
    ("Graduate Program - Melbourne", "BDO Australia"),
])
def test_rejects(title, company):
    cfg = yaml.safe_load((ROOT / "config" / "filters.yaml").read_text(encoding="utf-8"))
    j = Job("x", "1", company, title, "Melbourne", "u")
    assert not JobFilter(cfg, today=TODAY).evaluate(j)


def test_general_program_kept_when_no_stream_named():
    cfg = yaml.safe_load((ROOT / "config" / "filters.yaml").read_text(encoding="utf-8"))
    j = Job("x", "1", "CommBank", "2027 CommBank Graduate Campaign", "Sydney", "u")
    assert JobFilter(cfg, today=TODAY).evaluate(j) and j.category == "General program"


def test_workday_relative_dates():
    from job_radar.sources.workday import posted_date
    assert posted_date("Posted Today", TODAY) == "2026-11-15"
    assert posted_date("Posted Yesterday", TODAY) == "2026-11-14"
    assert posted_date("Posted 3 Days Ago", TODAY) == "2026-11-12"
    assert posted_date("Posted 30+ Days Ago", TODAY) == "2026-10-16"
    assert posted_date("", TODAY) == ""


def test_manual_roles_listed_until_closing_date(project):
    (project / "config" / "manual_roles.yaml").write_text(yaml.safe_dump({"roles": [
        {"company": "Acme", "title": "Data Science Intern 2027", "location": "Melbourne, VIC",
         "url": "https://acme/1", "closes": "2026-11-20"},
    ]}), encoding="utf-8")
    res = run(project, today=TODAY, session=FakeSession())
    acme = next(j for j in res["all"] if j.company == "Acme")
    assert acme.category == "Data / ML / AI"
    assert "https://acme/1" in (project / "README.md").read_text(encoding="utf-8").split("<details>")[0]
    res = run(project, today=date(2026, 11, 21), session=FakeSession())
    assert not any(j.company == "Acme" for j in res["all"])
    assert "Acme" in (project / "README.md").read_text(encoding="utf-8").split("<details>")[1]


class ClosingSession(FakeSession):
    """Same boards, but the KPMG vacationer ad has closed."""
    def get(self, url, **kw):
        if "smartrecruiters" in url:
            return FakeResp({"totalFound": 0, "content": []})
        return super().get(url, **kw)


def test_readme_keeps_closed_roles_until_year_end(project):
    run(project, today=TODAY, session=FakeSession())
    run(project, today=date(2026, 11, 22), session=ClosingSession())
    readme = (project / "README.md").read_text(encoding="utf-8")
    open_part, closed_part = readme.split("<details>")
    assert "KPMG Vacationer" in closed_part and "KPMG Vacationer" not in open_part
    assert "Graduate Software Developer" in open_part and "https://lever/a" in open_part

    # new year: the closed KPMG role is dropped, roles still open stay
    run(project, today=date(2027, 1, 3), session=ClosingSession())
    readme = (project / "README.md").read_text(encoding="utf-8")
    assert "KPMG Vacationer" not in readme
    assert "Graduate Software Developer" in readme


ISSUE_BODY = """### Company

Acme | Labs

### Role title

Software Engineer Intern "2027"

### Location

Sydney, NSW

### Link to apply

https://acme.com/jobs/1

### Closing date (optional)

_No response_
"""


def test_issue_form_becomes_manual_role(tmp_path):
    from job_radar.issue_form import append_role, parse_issue
    path = tmp_path / "manual_roles.yaml"
    path.write_text("# comment\nroles:\n", encoding="utf-8")
    role = parse_issue(ISSUE_BODY)
    assert role["company"] == "Acme | Labs" and role["closes"] == ""
    assert append_role(path, role, today=TODAY)
    assert not append_role(path, role, today=TODAY)  # same link twice is ignored
    roles = yaml.safe_load(path.read_text(encoding="utf-8"))["roles"]
    assert roles == [{"company": "Acme | Labs", "title": 'Software Engineer Intern "2027"',
                      "location": "Sydney, NSW", "url": "https://acme.com/jobs/1",
                      "posted": date(2026, 11, 15)}]
    with pytest.raises(ValueError):
        parse_issue(ISSUE_BODY.replace("https://acme.com/jobs/1", "not a link"))
