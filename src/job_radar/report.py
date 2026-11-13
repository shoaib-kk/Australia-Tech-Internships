"""Write results: CSV + JSON of everything open, Markdown digest of what's new."""
from __future__ import annotations

import csv
import json
from collections import Counter
from datetime import date
from pathlib import Path

from .models import Job

CSV_FIELDS = ["score", "category", "company", "title", "location", "posted", "first_seen",
              "employment_type", "source", "url", "reasons", "key", "source_id"]


def _rows(jobs: list[Job], first_seen: dict[str, str]) -> list[dict]:
    rows = []
    for j in jobs:
        r = j.to_row()
        r["first_seen"] = first_seen.get(j.key, "")
        rows.append({k: r.get(k, "") for k in CSV_FIELDS})
    return rows


def write_outputs(out_dir: Path, all_jobs: list[Job], new_jobs: list[Job],
                  first_seen: dict[str, str], errors: list[str], today: date,
                  stats: dict) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    all_jobs = sorted(all_jobs, key=lambda j: (-j.score, j.company.lower()))
    new_jobs = sorted(new_jobs, key=lambda j: (-j.score, j.company.lower()))

    rows = _rows(all_jobs, first_seen)
    with open(out_dir / "openings.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        w.writeheader()
        w.writerows(rows)

    (out_dir / "openings.json").write_text(json.dumps({
        "generated": today.isoformat(),
        "stats": stats,
        "errors": errors,
        "new": _rows(new_jobs, first_seen),
        "all": rows,
    }, indent=1))

    (out_dir / "new_this_week.md").write_text(render_markdown(new_jobs, all_jobs, errors, today, stats))


def _md_table(jobs: list[Job]) -> list[str]:
    lines = ["| Score | Company | Role | Category | Location | Posted | Link |",
             "|---:|---|---|---|---|---|---|"]
    for j in jobs:
        title = j.title.replace("|", "/")
        loc = (j.location or "").replace("|", "/")[:60]
        lines.append(f"| {j.score:g} | {j.company} | {title} | {j.category} | {loc} | "
                     f"{j.posted or '-'} | [apply]({j.url}) |")
    return lines


def render_markdown(new_jobs, all_jobs, errors, today, stats) -> str:
    out = [f"# Tech internship & grad openings - {today.isoformat()}", ""]
    out.append(f"**{len(new_jobs)} new** this run · {len(all_jobs)} matching roles open in total · "
               f"{stats.get('fetched', 0)} postings scanned from {stats.get('boards_ok', 0)} boards.")
    out.append("")
    cats = Counter(j.category for j in new_jobs)
    if cats:
        out.append("New by category: " + ", ".join(f"{c} {n}" for c, n in cats.most_common()))
        out.append("")
    out.append("## New since last run")
    out.append("")
    out += _md_table(new_jobs) if new_jobs else ["_Nothing new this week._"]
    out.append("")
    out.append("## Still open (top 30 by score)")
    out.append("")
    still = [j for j in all_jobs if j not in new_jobs][:30]
    out += _md_table(still) if still else ["_None._"]
    if errors:
        out += ["", "## Boards that failed this run", ""] + [f"- {e}" for e in errors]
    out.append("")
    return "\n".join(out)
