"""Fetch -> filter -> dedupe -> diff against last run -> write outputs."""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import yaml

from .filters import JobFilter
from .http import make_session
from .models import Job
from .report import write_outputs
from .sources import FETCHERS, fetch_adzuna
from .store import SeenStore, already_applied, load_applied

log = logging.getLogger("job_radar")


@dataclass
class Paths:
    root: Path

    @property
    def companies(self): return self.root / "config" / "companies.yaml"
    @property
    def filters(self): return self.root / "config" / "filters.yaml"
    @property
    def applied(self): return self.root / "config" / "applied.csv"
    @property
    def seen(self): return self.root / "data" / "seen.json"
    @property
    def output(self): return self.root / "output"


@dataclass
class FetchResult:
    jobs: list[Job] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    boards_ok: int = 0


def board_label(kind: str, board: dict) -> str:
    return f"{board.get('name') or board.get('id') or board.get('tenant')} ({kind})"


def fetch_all(companies: dict, session=None, workers: int = 6, use_adzuna: bool = True) -> FetchResult:
    session = session or make_session()
    tasks = [(kind, b) for kind in FETCHERS for b in companies.get(kind) or []]
    res = FetchResult()

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = {pool.submit(FETCHERS[kind], session, b): (kind, b) for kind, b in tasks}
        for fut in as_completed(futs):
            kind, b = futs[fut]
            try:
                jobs = fut.result()
                res.jobs.extend(jobs)
                res.boards_ok += 1
                log.info("%-40s %4d postings", board_label(kind, b), len(jobs))
            except Exception as e:  # one broken board must not kill the run
                msg = f"{board_label(kind, b)}: {type(e).__name__}: {str(e)[:120]}"
                res.errors.append(msg)
                log.warning(msg)

    az = companies.get("adzuna") or {}
    if use_adzuna and az.get("queries"):
        try:
            jobs = fetch_adzuna(session, az["queries"], az.get("max_days_old", 14),
                                az.get("pages_per_query", 2))
            res.jobs.extend(jobs)
            res.boards_ok += 1
            log.info("%-40s %4d postings", "Adzuna (search)", len(jobs))
        except Exception as e:
            res.errors.append(f"Adzuna: {str(e)[:160]}")
            log.warning("Adzuna: %s", e)
    return res


def dedupe(jobs: list[Job]) -> list[Job]:
    """Keep one job per key; prefer a direct company source over the Adzuna redirect."""
    def rank(j: Job):
        return (j.source != "adzuna", j.score)

    best: dict[str, Job] = {}
    for j in jobs:
        cur = best.get(j.key)
        if cur is None or rank(j) > rank(cur):
            best[j.key] = j
    return list(best.values())


def run(root: Path, today: date | None = None, session=None, use_adzuna: bool = True,
        dry_run: bool = False) -> dict:
    today = today or date.today()
    p = Paths(root)
    companies = yaml.safe_load(p.companies.read_text())
    jf = JobFilter(yaml.safe_load(p.filters.read_text()), today=today)
    applied = load_applied(p.applied)

    fetched = fetch_all(companies, session=session, use_adzuna=use_adzuna)
    kept = [j for j in fetched.jobs if jf.evaluate(j)]
    skipped_applied = [j for j in kept if already_applied(j, applied)]
    skip_ids = {id(j) for j in skipped_applied}
    kept = dedupe([j for j in kept if id(j) not in skip_ids])

    store = SeenStore(p.seen)
    new = store.mark(kept, today)
    first_seen = {j.key: store.first_seen(j) for j in kept}
    stats = {
        "fetched": len(fetched.jobs),
        "boards_ok": fetched.boards_ok,
        "boards_failed": len(fetched.errors),
        "matched": len(kept),
        "new": len(new),
        "skipped_already_applied": len(skipped_applied),
    }
    if not dry_run:
        store.prune(today)
        store.save()
        write_outputs(p.output, kept, new, first_seen, fetched.errors, today, stats)
    log.info("Done: %s", stats)
    return {"stats": stats, "new": new, "all": kept, "errors": fetched.errors}


def validate(root: Path, session=None) -> list[tuple[str, str]]:
    """Hit every configured board once and report OK / error with posting counts."""
    companies = yaml.safe_load(Paths(root).companies.read_text())
    session = session or make_session()
    results = []
    for kind, fetch in FETCHERS.items():
        for b in companies.get(kind) or []:
            try:
                n = len(fetch(session, b))
                results.append((board_label(kind, b), f"OK  {n} postings"))
            except Exception as e:
                results.append((board_label(kind, b), f"ERR {type(e).__name__}: {str(e)[:80]}"))
    return results
