"""Persistent state: which roles we've seen before, and which you've applied to."""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

from .models import Job


class SeenStore:
    """data/seen.json maps job.key -> role details plus first_seen / last_seen.

    It doubles as the archive behind README.md: a role stays listed after its
    ad closes, and is only dropped once the calendar year it was last seen in
    is over.
    """

    def __init__(self, path: Path):
        self.path = path
        self.data: dict = json.loads(path.read_text()) if path.exists() else {}

    def mark(self, jobs: list[Job], today: date) -> list[Job]:
        """Record jobs as seen today; return only those never seen before."""
        new = []
        stamp = today.isoformat()
        for j in jobs:
            details = {"company": j.company, "title": j.title, "location": j.location,
                       "url": j.url, "category": j.category, "score": j.score,
                       "posted": j.posted}
            entry = self.data.get(j.key)
            if entry is None:
                self.data[j.key] = {"first_seen": stamp, "last_seen": stamp, **details}
                new.append(j)
            else:
                entry.update(details, last_seen=stamp)
        return new

    def first_seen(self, job: Job) -> str:
        return self.data.get(job.key, {}).get("first_seen", "")

    def prune(self, today: date) -> None:
        """Drop roles that closed in an earlier calendar year."""
        year = str(today.year)
        self.data = {k: v for k, v in self.data.items() if v["last_seen"][:4] >= year}

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, indent=1, sort_keys=True))


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def load_applied(path: Path) -> list[tuple[str, str]]:
    """config/applied.csv lines: `Company, Role` (role optional => whole company skipped)."""
    if not path.exists():
        return []
    out = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        company, _, role = line.partition(",")
        out.append((_norm(company), _norm(role)))
    return out


def already_applied(job: Job, applied: list[tuple[str, str]]) -> bool:
    c, t = _norm(job.company), _norm(job.title)
    for company, role in applied:
        if company and (company in c or c in company):
            if not role or role in t or t in role:
                return True
    return False
