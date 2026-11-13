"""Turn an "Add a role" issue form into an entry in config/manual_roles.yaml."""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

import yaml

FIELDS = {"company": "Company", "title": "Role title", "location": "Location",
          "url": "Link to apply", "closes": "Closing date (optional)"}


def parse_issue(body: str) -> dict:
    """GitHub renders issue forms as '### Label' headings followed by the answer."""
    sections = {}
    for block in re.split(r"^###\s+", body or "", flags=re.M)[1:]:
        label, _, value = block.partition("\n")
        value = value.strip()
        sections[label.strip()] = "" if value == "_No response_" else value
    role = {key: sections.get(label, "").strip() for key, label in FIELDS.items()}

    missing = [FIELDS[k] for k in ("company", "title", "location", "url") if not role[k]]
    if missing:
        raise ValueError("Missing: " + ", ".join(missing))
    if not re.match(r"https?://\S+$", role["url"]):
        raise ValueError(f"Not a valid link: {role['url']}")
    if role["closes"]:
        try:
            date.fromisoformat(role["closes"])
        except ValueError:
            raise ValueError(f"Closing date should look like 2027-03-31, got: {role['closes']}")
    return role


def append_role(path: Path, role: dict, today: date | None = None) -> bool:
    """Append the role unless its link is already listed. Returns True if added."""
    text = path.read_text(encoding="utf-8") if path.exists() else "roles:\n"
    existing = (yaml.safe_load(text) or {}).get("roles") or []
    if any(r.get("url") == role["url"] for r in existing):
        return False
    if re.search(r"^roles:\s*\[\]\s*$", text, flags=re.M):
        text = re.sub(r"^roles:\s*\[\]\s*$", "roles:", text, flags=re.M)
    if not text.endswith("\n"):
        text += "\n"
    # json.dumps gives valid, safely quoted YAML scalars
    lines = [f"  - company: {json.dumps(role['company'])}",
             f"    title: {json.dumps(role['title'])}",
             f"    location: {json.dumps(role['location'])}",
             f"    url: {json.dumps(role['url'])}",
             f"    posted: {(today or date.today()).isoformat()}"]
    if role.get("closes"):
        lines.append(f"    closes: {role['closes']}")
    path.write_text(text + "\n".join(lines) + "\n", encoding="utf-8")
    return True
