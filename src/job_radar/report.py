"""Write results: CSV + JSON of everything open, Markdown digest of what's new."""
from __future__ import annotations

import csv
import json
import re
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
    with open(out_dir / "openings.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        w.writeheader()
        w.writerows(rows)

    (out_dir / "openings.json").write_text(json.dumps({
        "generated": today.isoformat(),
        "stats": stats,
        "errors": errors,
        "new": _rows(new_jobs, first_seen),
        "all": rows,
    }, indent=1), encoding="utf-8")

    (out_dir / "new_this_week.md").write_text(render_markdown(new_jobs, all_jobs, errors, today, stats), encoding="utf-8")


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
    out.append(f"**{len(new_jobs)} new** in the last 7 days · {len(all_jobs)} matching roles open in total · "
               f"{stats.get('fetched', 0)} postings scanned from {stats.get('boards_ok', 0)} boards.")
    out.append("")
    cats = Counter(j.category for j in new_jobs)
    if cats:
        out.append("New by category: " + ", ".join(f"{c} {n}" for c, n in cats.most_common()))
        out.append("")
    out.append("## New in the last 7 days")
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


def _cell(text) -> str:
    return str(text or "").replace("|", "/").replace(chr(10), " ").strip()


REPO = "shoaib-kk/Australia-Tech-Internships"

# category name in filters.yaml -> (emoji, heading, anchor)
SECTIONS = {
    "Data / ML / AI": ("🤖", "Data, ML & AI", "data"),
    "Software engineering": ("💻", "Software Engineering", "software"),
    "Cloud / DevOps / Infra": ("☁️", "Cloud, DevOps & Infrastructure", "cloud"),
    "Cyber security": ("🔐", "Cyber Security", "cyber"),
    "IT / Tech": ("🖥️", "IT & Tech", "it"),
    "General program": ("🎓", "Graduate & Intern Programs (multiple streams)", "programs"),
}
CITIES = ["Sydney", "Melbourne", "Brisbane", "Perth", "Adelaide", "Canberra", "Hobart", "Darwin",
          "Gold Coast", "Geelong", "Newcastle", "Wollongong", "Remote"]


def _badge(label: str, value, color: str) -> str:
    def esc(s):
        return str(s).replace("-", "--").replace("_", "__").replace(" ", "_")
    return f"![{label}](https://img.shields.io/badge/{esc(label)}-{esc(value)}-{color})"


def _role_type(title: str) -> str:
    t = title.lower()
    if re.search(r"\b(interns?|internships?|vacation|vacationers?|summer|winter)\b", t):
        return "Internship"
    if "cadet" in t:
        return "Cadetship"
    if re.search(r"\b(grad|graduate|graduates)\b", t):
        return "Graduate"
    return "Entry level"


def _short_location(loc: str) -> str:
    found = [c for c in CITIES if c.lower() in (loc or "").lower()]
    if found:
        return ", ".join(found[:3]) + (f" +{len(found) - 3}" if len(found) > 3 else "")
    return _cell(loc)[:40] or "Australia"


def _apply(url: str) -> str:
    if not url:
        return "-"
    return f"[![Apply](https://img.shields.io/badge/Apply-2ea44f?style=flat-square)]({url})"


def render_readme(roles: dict, today: date) -> str:
    """All roles found this year: open ones by category, closed ones folded away."""
    stamp = today.isoformat()
    week_ago = date.fromordinal(today.toordinal() - 7).isoformat()
    entries = list(roles.values())
    # A role counts as open if seen in the last 2 days, so one failed fetch
    # doesn't flip it to "closed".
    grace = date.fromordinal(today.toordinal() - 2).isoformat()
    open_ = [e for e in entries if e.get("last_seen", "") >= grace]
    closed = sorted((e for e in entries if e.get("last_seen", "") < grace),
                    key=lambda e: (e.get("last_seen", ""), e["company"].lower()), reverse=True)
    companies = len({e["company"] for e in open_})
    new_count = sum(1 for e in open_ if e.get("first_seen", "") >= week_ago)

    def posted(e):
        return e.get("posted") or e.get("first_seen", "")

    def open_table(rows) -> list[str]:
        has_close = any(e.get("closes") for e in rows)
        out = ["| Company | Role | Type | Location | Posted |" + (" Closes |" if has_close else "") + " Apply |",
               "|---|---|---|---|---|" + ("---|" if has_close else "") + ":---:|"]
        for e in sorted(rows, key=lambda e: (posted(e), float(e.get("score") or 0)), reverse=True):
            new = " 🆕" if e.get("first_seen", "") >= week_ago else ""
            close = f" {e.get('closes') or '-'} |" if has_close else ""
            out.append(f"| **{_cell(e['company'])}** | {_cell(e['title'])}{new} | {_role_type(e['title'])} | "
                       f"{_short_location(e.get('location', ''))} | {posted(e)} |{close} {_apply(e.get('url'))} |")
        return out

    year = today.year + 1
    out = [
        '<div align="center">', "",
        f"# 🇦🇺 Australian Tech Internships & Graduate Programs {year}", "",
        "**Software · Data & AI · Cloud · Cyber · IT** internships, vacationer programs, cadetships and graduate "
        "roles across Sydney, Melbourne, Brisbane, Perth, Adelaide and Canberra, checked every day straight "
        "from employer career sites.", "",
        " ".join([_badge("open roles", len(open_), "2ea44f"), _badge("companies", companies, "blue"),
                  _badge("new this week", new_count, "orange"), _badge("updated", stamp, "lightgrey")]), "",
        "⭐ **Star this repo** so it's here when applications open &nbsp;·&nbsp; "
        f"🙏 **Found a role we missed? [Add it in a minute](https://github.com/{REPO}/issues/new?template=add-role.yml)**",
        "", "</div>", "", "---", "",
    ]

    by_cat: dict[str, list] = {}
    for e in open_:
        by_cat.setdefault(e.get("category") or "General program", []).append(e)
    order = [c for c in SECTIONS if c in by_cat] + [c for c in by_cat if c not in SECTIONS]

    out.append("### Browse by category")
    out.append("")
    for c in order:
        emoji, head, anchor = SECTIONS.get(c, ("📌", c, c.lower().replace(" ", "-")))
        out.append(f"- {emoji} **[{head}](#{anchor})** ({len(by_cat[c])})")
    out += ["", "📅 **[When do applications open?](APPLICATION_CALENDAR.md)**: the yearly timeline for "
            "Australian internships and grad programs.", "", "---", ""]

    if not open_:
        out += ["_No open roles right now. Star the repo and check back._", ""]
    for c in order:
        emoji, head, anchor = SECTIONS.get(c, ("📌", c, c.lower().replace(" ", "-")))
        out += [f'<a id="{anchor}"></a>', "", f"## {emoji} {head}", ""]
        if c == "General program":
            out += ["> Broad programs whose title doesn't name a stream. Most of these include "
                    "technology, data or cyber streams.", ""]
        out += open_table(by_cat[c]) + ["", "[⬆ Back to top](#)", ""]

    out += ["---", "", '<a id="closed"></a>', "", "<details>", f"<summary><b>🗄️ Closed roles from {today.year} ({len(closed)})</b>: "
            "useful for knowing who hires and when. Cleared at the end of the year.</summary>", ""]
    if closed:
        out += ["| Company | Role | Type | First seen | Last seen | Link |", "|---|---|---|---|---|:---:|"]
        for e in closed:
            link = f"[link]({e['url']})" if e.get("url") else "-"
            out.append(f"| {_cell(e['company'])} | {_cell(e['title'])} | {_role_type(e['title'])} | "
                       f"{e.get('first_seen', '')} | {e.get('last_seen', '')} | {link} |")
    else:
        out.append("_None yet._")
    out += ["", "</details>", "", "---", "",
            "### How this list works", "",
            "- A script checks the career sites of 50+ employers every day (Greenhouse, Lever, Ashby, "
            "SmartRecruiters, Workday and Amazon job feeds) and keeps early-career tech roles based in Australia.",
            "- 🆕 marks roles first seen in the last 7 days. Links go straight to the employer, not a job board.",
            "- When an ad comes down it moves to **Closed roles**. Closed roles are cleared each January.",
            f"- Want a company added? [Open an issue](https://github.com/{REPO}/issues/new?template=add-company.yml). "
            "Want to run it yourself? See [how it works](docs/HOW_IT_WORKS.md).", "",
            "<sub>Not affiliated with any employer. Always check eligibility and closing dates on the "
            "employer's site.</sub>", ""]
    return chr(10).join(out)


def write_readme(path: Path, roles: dict, today: date) -> None:
    path.write_text(render_readme(roles, today), encoding="utf-8")
