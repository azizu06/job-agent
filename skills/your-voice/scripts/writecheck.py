#!/usr/bin/env python3
"""Character and pattern check for a written application answer. Stdlib only.

Run it on every drafted answer before it is typed into a form. It catches what
an eye misses: dashes, curly quotes, invisible Unicode, odd spaces, the length
cap, common AI vocabulary and selection narration ("one project that stands
out"). It never rewrites wording; the agent fixes the draft and runs it again.

Commands:
  check FILE|-   check one answer. Exit 0 when CLEAN, 1 when not.
      --max-chars N    fail above N characters (the form's limit)
      --max-words N    fail above N words
      --allow-dashes   the user's own samples use dashes (see voice/profile.md)
      --allow WORD     a listed AI word the user really uses; repeatable
      --fix OUT        also write a copy with quotes, invisible characters and
                       odd spaces normalized (never edits FILE in place)
      --json           print the result as JSON
  stats FILE...  measure writing samples for voice/profile.md: sentence length,
                 contractions, dashes, common openers and connectives.

Examples:
  python3 writecheck.py check answer.txt --max-chars 1000
  python3 writecheck.py stats ~/.job-agent/voice/samples/*
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

DASHES = "—–"
CURLY = {"‘": "'", "’": "'", "“": '"', "”": '"'}
INVISIBLE = {0x200B, 0x200C, 0x200D, 0x2060, 0xFEFF, 0x00AD, 0x180E, 0x061C, 0x200E, 0x200F}
ODD_SPACES = {0x00A0, 0x2002, 0x2003, 0x2007, 0x2009, 0x202F, 0x205F, 0x3000}

AI_WORDS = [
    "delve", "delves", "delving", "foster", "fostering", "garner", "landscape", "pivotal",
    "showcase", "showcasing", "testament", "underscore", "underscores", "crucial", "vibrant",
    "robust", "seamless", "seamlessly", "leverage", "leveraging", "tapestry", "realm",
    "multifaceted", "synergy", "cutting-edge", "passionate", "thrilled", "resonates",
]

META = [
    r"\bI'?d (?:point|highlight|pick|choose|start with|lead with)\b",
    r"\b(?:want|like) to (?:highlight|showcase|mention|share)\b",
    r"\bstands? out\b", r"\bcomes? to mind\b", r"\bif I had to (?:pick|choose)\b",
    r"\bbest showcases?\b", r"\bwalk you through\b",
    r"\bworth (?:mentioning|highlighting|noting)\b",
    r"\bthe project that best\b",
]

OPENER_FILLER = [
    r"^\s*I am (?:thrilled|excited|delighted|eager) to\b",
    r"^\s*As a (?:passionate|driven|motivated)\b",
]

CONNECTIVES = ["also", "so", "because", "but", "and", "then", "still", "plus", "though", "since"]


def _is_invisible(c: str) -> bool:
    o = ord(c)
    return o in INVISIBLE or 0xE0000 <= o <= 0xE007F


def check(text: str, max_chars: int | None = None, max_words: int | None = None,
          allow_dashes: bool = False, allow_words: list[str] | None = None) -> dict:
    """Return counts and a list of problems. Empty problems means CLEAN."""
    words = len(text.split())
    chars = len(text)
    dashes = sum(text.count(d) for d in DASHES)
    curly = sum(text.count(c) for c in CURLY)
    invisible = [f"U+{ord(c):04X} {unicodedata.name(c, '?')}" for c in text if _is_invisible(c)]
    odd = [f"U+{ord(c):04X} {unicodedata.name(c, '?')}" for c in text if ord(c) in ODD_SPACES]
    lower = text.lower()
    allowed = {w.lower() for w in (allow_words or [])}
    ai = sorted({w for w in AI_WORDS if w not in allowed and re.search(rf"\b{re.escape(w)}\b", lower)})
    meta = [m.group(0) for pat in META for m in re.finditer(pat, text, re.I)]
    filler = [m.group(0).strip() for pat in OPENER_FILLER for m in re.finditer(pat, text, re.I | re.M)]

    problems: list[str] = []
    if max_chars is not None and chars > max_chars:
        problems.append(f"LENGTH {chars} chars, limit is {max_chars}")
    if max_words is not None and words > max_words:
        problems.append(f"WORDS {words} words, limit is {max_words}")
    if dashes and not allow_dashes:
        problems.append(f"DASH {dashes} em or en dash(es): rewrite with a period, comma or 'and'")
    if curly:
        problems.append(f"CURLY {curly} curly quote(s): use straight quotes")
    if invisible:
        problems.append(f"INVISIBLE {len(invisible)}: {invisible[:5]}")
    if odd:
        problems.append(f"SPACE {len(odd)} non-standard space(s): {odd[:5]}")
    if ai:
        problems.append(f"AI-WORDS {ai}: use a plain word or cut")
    if meta:
        problems.append(f"META {meta[:5]}: delete the sentence and open with the work")
    if filler:
        problems.append(f"OPENER {filler}: start with the content")
    return {"words": words, "chars": chars, "problems": problems, "clean": not problems}


def normalize(text: str) -> str:
    """Fix only what is safe to fix mechanically. Wording is left alone."""
    out = []
    for c in text:
        if c in CURLY:
            out.append(CURLY[c])
        elif _is_invisible(c):
            continue
        elif ord(c) in ODD_SPACES:
            out.append(" ")
        else:
            out.append(c)
    return "".join(out)


def sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", re.sub(r"\s+", " ", text.strip()))
    return [p for p in parts if len(p.split()) >= 2]


def stats(texts: list[str]) -> dict:
    """Measure samples so the agent can write voice/profile.md from numbers."""
    sents = [s for t in texts for s in sentences(t)]
    lengths = sorted(len(s.split()) for s in sents)
    words = [w for t in texts for w in re.findall(r"[A-Za-z']+", t)]
    lower = [w.lower() for w in words]
    contractions = sum(1 for w in words if "'" in w.strip("'"))
    openers = Counter(s.split()[0].strip(",.;:").lower() for s in sents if s.split())
    conn = Counter(w for w in lower if w in CONNECTIVES)
    median = lengths[len(lengths) // 2] if lengths else 0
    return {
        "samples": len(texts),
        "sentences": len(sents),
        "words": len(words),
        "median_sentence_words": median,
        "shortest_sentence_words": lengths[0] if lengths else 0,
        "longest_sentence_words": lengths[-1] if lengths else 0,
        "contractions_per_100_words": round(100 * contractions / len(words), 1) if words else 0.0,
        "dashes": sum(t.count(d) for t in texts for d in DASHES),
        "exclamations": sum(t.count("!") for t in texts),
        "top_openers": openers.most_common(8),
        "connectives": conn.most_common(8),
    }


def _read(path: str) -> str:
    if path == "-":
        return sys.stdin.read()
    return Path(path).expanduser().read_text(encoding="utf-8", errors="replace")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check")
    c.add_argument("file")
    c.add_argument("--max-chars", type=int)
    c.add_argument("--max-words", type=int)
    c.add_argument("--allow-dashes", action="store_true")
    c.add_argument("--allow", action="append", default=[])
    c.add_argument("--fix")
    c.add_argument("--json", action="store_true")
    s = sub.add_parser("stats")
    s.add_argument("files", nargs="+")
    args = ap.parse_args(argv)

    if args.cmd == "stats":
        print(json.dumps(stats([_read(f) for f in args.files]), indent=2))
        return 0

    text = _read(args.file)
    if text.endswith("\n"):
        text = text[:-1]
    result = check(text, args.max_chars, args.max_words, args.allow_dashes, args.allow)
    if args.fix:
        Path(args.fix).expanduser().write_text(normalize(text) + "\n", encoding="utf-8")
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"words  {result['words']}")
        print(f"chars  {result['chars']}")
        for p in result["problems"]:
            print(p)
        print("CLEAN" if result["clean"] else "NOT CLEAN")
        if args.fix:
            print(f"wrote {args.fix} (original untouched)")
    return 0 if result["clean"] else 1


if __name__ == "__main__":
    sys.exit(main())
