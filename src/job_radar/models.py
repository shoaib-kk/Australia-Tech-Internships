"""Core data model shared by every source."""
from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass, field


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()


@dataclass
class Job:
    source: str            # greenhouse | lever | ashby | smartrecruiters | workday | adzuna
    source_id: str         # id inside that source
    company: str
    title: str
    location: str
    url: str
    posted: str = ""       # ISO date (YYYY-MM-DD) when known
    employment_type: str = ""
    description: str = ""  # plain text, may be truncated

    # filled in by the filter/scoring stage
    category: str = ""
    score: float = 0.0
    reasons: list[str] = field(default_factory=list)

    @property
    def key(self) -> str:
        """Cross-source dedupe key: same company + title + city counts as one role."""
        city = _norm(self.location).split(" ")[0] if self.location else ""
        raw = f"{_norm(self.company)}|{_norm(self.title)}|{city}"
        return hashlib.sha1(raw.encode()).hexdigest()[:16]

    def to_row(self) -> dict:
        d = asdict(self)
        d["reasons"] = "; ".join(self.reasons)
        d.pop("description", None)
        d["key"] = self.key
        return d
