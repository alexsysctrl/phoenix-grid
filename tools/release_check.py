"""Refuse a release that reads like working notes.

Everything in this directory is meant to be public. Working notes are a different thing from a published record: they
name machines on a private network, point at files in a research repository that is not shipped here, carry decision
ids from a private log, or mention a person who is not part of the work. Their presence says the release was reviewed
by no one, so this runs the check mechanically over the files git would publish, before the push rather than after.

Usage: python3 tools/release_check.py

Files under `data/`, `decisions/` and `evidence/` are scanned too — a derived dataset should not smuggle a private
path or a private hostname into a public repository either.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Each pattern is a category rather than a banned word, so a new note in the same category is caught too.
CATEGORIES = {
    "private network address": r"\b192\.168\.\d+\.\d+\b|\b10\.\d+\.\d+\.\d+\b|\b172\.\d{2}\.\d+\.\d+\b",
    "hostname or ssh alias of a private machine": r"\blab97\b|\balexmac\b|\bAlexs-Air\b|\bpc@192|\bthis-mac\b|(?<![\d.])\.97\b",
    "path into a repository that is not shipped here": r"alex-workspace|~/Desktop|~/research|\.pi/agent|Time Capsule",
    "private decision or task id": r"\bD\d{3,4}\b(?![_a-z])",
    "notes-to-self phrasing": r"\bnext session\b|\bTODO\b|\bmy research repo\b|\bI told Jaiden\b|\bas we discussed\b",
    "a person who is not part of this work": r"\bJaiden\b|\bLumwanga\b|\bjlumwanga\b",
    "another project by the same author": r"\bsurvey-completion\b|\bsolarium\b|\bkelvar\b|\bsignalpost\b|\bbuilderr\b",
    "launchd or systemd unit of a private machine": r"\blaunchd\b|\bsystemctl\b|\bcom\.alexsys\b",
}

# Negative controls: the check has to fail on these, or it is not a check.
SAMPLES = {
    "private network address": "BASE = 'http://192.168.0.217:18765/api'",
    "hostname or ssh alias of a private machine": "copy it to lab97 and run it there",
    "path into a repository that is not shipped here": "see alex-workspace/decisions for the reasoning",
    "private decision or task id": "recorded as D213 in the decision log",
    "notes-to-self phrasing": "TODO: ask him before the next session",
    "a person who is not part of this work": "waiting on Jaiden for the go-ahead",
    "another project by the same author": "the same pattern as in survey-completion",
    "launchd or systemd unit of a private machine": "runs as com.alexsys.sitingwatch on launchd",
}

SCANNED_SUFFIXES = {".md", ".py", ".json"}


def tracked_files() -> list[Path]:
    try:
        out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
        files = [ROOT / line for line in out.splitlines() if line]
    except subprocess.CalledProcessError:
        files = [p for p in ROOT.rglob("*") if p.is_file()]
    return [f for f in files if f.suffix in SCANNED_SUFFIXES and f.name != Path(__file__).name]


def findings() -> list[tuple[str, str, int, str]]:
    hits = []
    for path in tracked_files():
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for number, line in enumerate(text.splitlines(), start=1):
            for category, pattern in CATEGORIES.items():
                match = re.search(pattern, line)
                if match:
                    hits.append((category, str(path.relative_to(ROOT)), number, line.strip()[:120]))
                    break
    return hits


def self_test():
    """The known-true side is the whole point of the release: an example of every category must be matched.
    The known-false side is a clean line that must not be matched by anything."""
    unmatched = [c for c, sample in SAMPLES.items() if not re.search(CATEGORIES[c], sample)]
    if unmatched:
        return f"self-test: categories that matched none of their own examples: {unmatched}"
    clean = "The Commission's decision 81564 was issued on 21 November 2025 and the docket status is Compliance Due."
    for category, pattern in CATEGORIES.items():
        if re.search(pattern, clean):
            return f"self-test: category {category!r} matches an ordinary sentence"
    return None


def main() -> int:
    problem = self_test()
    if problem:
        print(problem)
        return 1

    hits = findings()
    if not hits:
        print(f"release check: no private-workspace language found in {len(tracked_files())} published files")
        return 0

    print(f"release check: {len(hits)} places to fix before this goes public")
    for category, path, number, line in hits:
        print(f"  {category}\n    {path}:{number}: {line}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
