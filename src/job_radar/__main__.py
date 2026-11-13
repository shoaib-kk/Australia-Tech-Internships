"""CLI:  python -m job_radar run [--dry-run]
        python -m job_radar validate
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from .pipeline import run, validate

ROOT = Path(__file__).resolve().parents[2]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="job_radar", description=__doc__)
    ap.add_argument("command", choices=["run", "validate"])
    ap.add_argument("--root", type=Path, default=ROOT, help="project folder (config/, data/, output/)")
    ap.add_argument("--dry-run", action="store_true", help="don't write state or outputs")
    ap.add_argument("-q", "--quiet", action="store_true")
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.WARNING if a.quiet else logging.INFO,
                        format="%(levelname)-7s %(message)s")

    if a.command == "validate":
        bad = 0
        for label, status in validate(a.root):
            print(f"{label:45s} {status}")
            bad += status.startswith("ERR")
        return 1 if bad else 0

    result = run(a.root, dry_run=a.dry_run)
    print(f"\n{result['stats']['new']} new / {result['stats']['matched']} matching roles.")
    for j in sorted(result["new"], key=lambda j: -j.score)[:15]:
        print(f"  {j.score:>5g}  {j.company:22.22s} {j.title[:60]:60s} {j.location[:30]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
