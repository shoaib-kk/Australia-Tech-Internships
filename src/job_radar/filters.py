"""Decide whether a Job is a tech early-career role in Australia, and score it."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta

from .models import Job


def _compile(patterns, flags=re.I):
    return [re.compile(p, flags) for p in patterns or []]


@dataclass
class Category:
    name: str
    weight: float
    patterns: list


class JobFilter:
    def __init__(self, cfg: dict, today: date | None = None):
        self.cfg = cfg
        self.today = today or date.today()
        self.early = _compile(cfg["early_career"])
        self.exclude = _compile(cfg["exclude_titles"])
        cs = cfg.get("case_sensitive") or {}
        self.categories = [
            Category(c["name"], float(c["weight"]),
                     _compile(c["patterns"]) + _compile(cs.get(c["name"]), flags=0))
            for c in cfg["categories"]
        ]
        self.general_exclude = _compile(cfg.get("general_program_exclude"))
        self.general_skip = {c.lower() for c in cfg.get("general_program_skip_companies") or []}
        self.loc_keep = _compile(cfg["locations_keep"])
        self.loc_bonus = [(re.compile(p, re.I), float(w))
                          for p, w in (cfg.get("locations_bonus") or {}).items()]
        self.skill_bonus = [(re.compile(rf"\b{p}\b" if p.isalpha() else p, re.I), float(w))
                            for p, w in (cfg.get("skill_bonus") or {}).items()]

    # ---- individual checks -------------------------------------------------

    def is_early_career(self, job: Job) -> bool:
        text = f"{job.title} {job.employment_type}"
        return any(p.search(text) for p in self.early)

    def is_excluded(self, job: Job) -> bool:
        return any(p.search(job.title) for p in self.exclude)

    def location_ok(self, job: Job) -> bool:
        loc = job.location or ""
        if any(p.search(loc) for p in self.loc_keep):
            return True
        if self.cfg.get("keep_global_remote") and re.search(r"remote|anywhere", loc, re.I):
            return True
        return False

    def categorise(self, job: Job) -> Category | None:
        for cat in self.categories:
            if any(p.search(job.title) for p in cat.patterns):
                return cat
        return None

    def too_old(self, job: Job) -> bool:
        if not job.posted:
            return False
        try:
            posted = date.fromisoformat(job.posted)
        except ValueError:
            return False
        return posted < self.today - timedelta(days=int(self.cfg.get("max_age_days", 60)))

    # ---- main entry point --------------------------------------------------

    def evaluate(self, job: Job) -> bool:
        """Return True if the job should be kept; fills category/score/reasons."""
        if not self.location_ok(job) or self.is_excluded(job) or not self.is_early_career(job):
            return False
        if self.too_old(job):
            return False
        return self.score(job)

    def evaluate_manual(self, job: Job) -> bool:
        """Hand-added roles were checked by a person: only categorise and score them."""
        if job.closes and job.closes < self.today.isoformat():
            return False
        return self.score(job, manual=True)

    def score(self, job: Job, manual: bool = False) -> bool:
        cat = self.categorise(job)
        if cat is None:
            if not self.cfg.get("keep_general_programs", True):
                return False
            if not manual and (job.company.lower() in self.general_skip or any(
                    p.search(job.title) for p in self.general_exclude)):
                return False
            job.category, score = "General program", float(self.cfg.get("general_program_weight", 4))
            job.reasons.append("early-career program (check for a tech stream)")
        else:
            job.category, score = cat.name, cat.weight
            job.reasons.append(cat.name.lower())

        if re.search(r"\bintern|vacation|summer|winter", job.title, re.I):
            score += 2
            job.reasons.append("internship")

        for pat, w in self.loc_bonus:
            if pat.search(job.location):
                score += w
                label = re.sub(r"\\b", "", pat.pattern)
                job.reasons.append(f"location: {label}")
                break

        text = f"{job.title} {job.description}"
        skills = [pat.pattern for pat, w in self.skill_bonus if pat.search(text)]
        score += sum(w for pat, w in self.skill_bonus if pat.pattern in skills)
        if skills:
            pretty = [re.sub(r"\\b", "", s) for s in skills]
            job.reasons.append("mentions " + ", ".join(pretty[:4]))

        if job.posted:
            age = (self.today - date.fromisoformat(job.posted)).days
            if age <= 7:
                score += 1
                job.reasons.append("posted this week")

        job.score = round(score, 1)
        return True
