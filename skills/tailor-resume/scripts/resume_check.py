#!/usr/bin/env python3
"""Text-level checks for a tailored resume against its master. Stdlib only.

Works on the Markdown layout in templates/master-resume.md: each entry is a
`###` heading and each bullet is a line starting with `- `. Lines inside
`<!-- alt -->` ... `<!-- /alt -->` blocks are alternates and are skipped.

Checks:
  BULLETS   an entry has more bullets than --max-bullets
  LENGTH    a bullet is longer than --max-chars (a rough proxy for 2 lines)
  METRIC    a number in the tailored copy that never appears in the master
  VERB      the same opening verb starts more than --max-verb-repeats bullets
  IDENTITY  the first bullet under a project entry has no "<noun> that/for"
            phrase saying what the project is (a heuristic; read it yourself)

Rendering checks (one page, no orphan lines, skills rows on one line) need
the real PDF and a look at a PNG render. This script cannot do those.

Example:
  python3 resume_check.py --master master.md --resume tailored.md
Exit code 1 when any check fails.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from pathlib import Path

METRIC_RE = re.compile(r"(?<![A-Za-z])\$?\d[\d,.]*\s*(?:%|x|k|m|b|ms|s|\+)?(?![A-Za-z])", re.IGNORECASE)
IDENTITY_RE = re.compile(
    r"\b(?:app|tool|service|platform|library|site|website|dashboard|bot|agent|api|cli|extension|"
    r"game|system|pipeline|engine|framework|plugin|model|robot|rover)\b[^.;]{0,40}?\b(?:that|for|which|to)\b",
    re.IGNORECASE,
)


def strip_alternates(text: str) -> str:
    return re.sub(r"<!--\s*alt\s*-->.*?<!--\s*/alt\s*-->", "", text, flags=re.DOTALL | re.IGNORECASE)


def parse_entries(text: str) -> list[dict]:
    """Return [{'title', 'section', 'bullets'}] in document order."""
    entries: list[dict] = []
    section = ""
    current: dict | None = None
    for raw in strip_alternates(text).splitlines():
        line = raw.rstrip()
        if line.startswith("## ") and not line.startswith("### "):
            section = line[3:].strip().lower()
            current = None
        elif line.startswith("### "):
            current = {"title": line[4:].strip(), "section": section, "bullets": []}
            entries.append(current)
        elif current is not None and re.match(r"^\s*[-*] ", line):
            current["bullets"].append(re.sub(r"^\s*[-*] ", "", line).strip())
    return entries


def metrics(text: str) -> set[str]:
    found = set()
    for m in METRIC_RE.finditer(text):
        token = m.group(0).strip().lower().replace(",", "")
        token = re.sub(r"\s+", "", token)
        # Years and single digits are too common to police.
        if re.fullmatch(r"(19|20)\d\d", token) or re.fullmatch(r"\d", token):
            continue
        found.add(token)
    return found


def run_checks(master: str, resume: str, max_bullets: int, max_chars: int, max_verb_repeats: int) -> list[str]:
    problems: list[str] = []
    entries = parse_entries(resume)
    bullets = [b for e in entries for b in e["bullets"]]

    for e in entries:
        if len(e["bullets"]) > max_bullets:
            problems.append(f"BULLETS {e['title']}: {len(e['bullets'])} bullets, cap is {max_bullets}")
        for b in e["bullets"]:
            if len(b) > max_chars:
                problems.append(f"LENGTH {e['title']}: {len(b)} chars: {b[:60]}...")
        if "project" in e["section"] and e["bullets"] and not IDENTITY_RE.search(e["bullets"][0]):
            problems.append(f"IDENTITY {e['title']}: first bullet does not say what the project is")

    master_metrics = metrics(master)
    for b in bullets:
        for m in sorted(metrics(b) - master_metrics):
            problems.append(f"METRIC {m!r} is not in the master: {b[:60]}...")

    verbs = Counter(b.split()[0].lower().strip(",.") for b in bullets if b.split())
    for verb, n in verbs.items():
        if n > max_verb_repeats:
            problems.append(f"VERB '{verb}' opens {n} bullets, limit is {max_verb_repeats}")
    return problems


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--master", required=True)
    ap.add_argument("--resume", required=True)
    ap.add_argument("--max-bullets", type=int, default=3)
    ap.add_argument("--max-chars", type=int, default=210)
    ap.add_argument("--max-verb-repeats", type=int, default=2)
    args = ap.parse_args(argv)
    master = Path(args.master).read_text(encoding="utf-8")
    resume = Path(args.resume).read_text(encoding="utf-8")
    problems = run_checks(master, resume, args.max_bullets, args.max_chars, args.max_verb_repeats)
    for p in problems:
        print(p)
    print("VERDICT: " + ("FAIL" if problems else "PASS"))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
