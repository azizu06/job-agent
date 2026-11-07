#!/usr/bin/env python3
"""Run guard, run log and final banner for job-run. Standard library only.

  run_state.py lock    --dir state/run.lock [--stale-hours 3]
        exit 0: lock taken (prints whether a stale lock from a hung run was replaced)
        exit 3: another run holds a fresh lock; end this run with one line
  run_state.py unlock  --dir state/run.lock
  run_state.py preflight [--log state/run-log.md]
        exit 0 when the screen is unlocked; exit 4 logs "BLOCKED: screen locked"
  run_state.py blocked --log state/run-log.md --cause "Chrome did not attach"
        logs "BLOCKED: <cause>"; prints notify=yes when the previous entry was
        also BLOCKED (two in a row is the only blocked case that pings)
  run_state.py log     --log state/run-log.md --entry "text"
  run_state.py banner  [--ready "Acme SWE Intern"]... [--genai "Acme SWE Intern"]... [--alert "Assessment from Acme, due Nov 12"]
        prints the run's final lines: "READY: <banner>" or "NOTHING READY",
        then "ALERT: <banner>" for each alert. Banners name forms only (no pay,
        counts or coverage), drop quotes and apostrophes, and stay under 150
        characters.

A locked screen or a browser that does not attach is BLOCKED: log one line and
stop. Never ask for a password.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

MAX_BANNER = 149
BLOCKED = "BLOCKED: "


def now_utc() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0)


def take_lock(path: Path, stale_hours: float = 3, now: dt.datetime | None = None) -> dict:
    """mkdir is atomic: whoever creates the folder owns the run."""
    now = now or now_utc()
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.mkdir()
    except FileExistsError:
        info = path / "owner.json"
        try:
            started = dt.datetime.fromisoformat(json.loads(info.read_text(encoding="utf-8"))["started"])
        except (OSError, ValueError, KeyError):
            started = dt.datetime.fromtimestamp(path.stat().st_mtime, dt.timezone.utc)
        age_h = (now - started).total_seconds() / 3600
        if age_h < stale_hours:
            return {"locked": False, "reason": f"another run started {started.isoformat()} ({age_h:.1f}h ago) holds the lock"}
        shutil.rmtree(path, ignore_errors=True)
        path.mkdir()
        (path / "owner.json").write_text(json.dumps({"started": now.isoformat()}), encoding="utf-8")
        return {"locked": True, "replaced_stale": True,
                "reason": f"replaced a lock from {started.isoformat()} ({age_h:.1f}h old): the last run hung"}
    (path / "owner.json").write_text(json.dumps({"started": now.isoformat()}), encoding="utf-8")
    return {"locked": True, "replaced_stale": False, "reason": "lock taken"}


def release_lock(path: Path) -> None:
    shutil.rmtree(path, ignore_errors=True)


def screen_locked_from_ioreg(text: str) -> bool:
    return re.search(r'"CGSSessionScreenIsLocked"\s*=\s*Yes', text or "") is not None


def screen_locked() -> bool | None:
    """True or False on macOS, None where it cannot be told."""
    if sys.platform != "darwin":
        return None
    try:
        out = subprocess.run(["ioreg", "-n", "Root", "-d1"], capture_output=True, text=True, timeout=10).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    return screen_locked_from_ioreg(out)


def entries(log: Path) -> list[str]:
    if not log.exists():
        return []
    return [l[2:] for l in log.read_text(encoding="utf-8").splitlines() if l.startswith("- ")]


def append(log: Path, text: str, now: dt.datetime | None = None) -> str:
    line = f"{(now or now_utc()).isoformat()} {text}"
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a", encoding="utf-8") as fh:
        fh.write(f"- {line}\n")
    return line


def _body(entry: str) -> str:
    return entry.split(" ", 1)[1] if " " in entry else entry


def record_blocked(log: Path, cause: str, now: dt.datetime | None = None) -> dict:
    prev = entries(log)
    twice = bool(prev) and _body(prev[-1]).startswith(BLOCKED)
    append(log, BLOCKED + cause, now)
    return {"blocked": cause, "notify": twice,
            "banner": clean(f"Job loop blocked: {cause}") if twice else ""}


def clean(text: str) -> str:
    text = re.sub(r"[\"'‘’“”`]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text if len(text) <= MAX_BANNER else text[:MAX_BANNER - 3].rstrip() + "..."


def ready_banner(ready: list[str], genai: list[str] | None = None) -> str:
    """'Acme SWE Intern ready to review and submit' or '3 ready to review and submit: A, B, C'."""
    genai = set(genai or [])
    names = [n + (" GenAI rule in posting" if n in genai else "") for n in ready]
    if not names:
        return ""
    if len(names) == 1:
        text = f"{names[0]} ready to review and submit"
    else:
        text = f"{len(names)} ready to review and submit: " + ", ".join(names)
    return clean(text)


def final_lines(ready: list[str], genai: list[str] | None = None, alerts: list[str] | None = None) -> list[str]:
    banner = ready_banner(ready, genai)
    lines = ["READY: " + banner if banner else "NOTHING READY"]
    lines += ["ALERT: " + clean(a) for a in alerts or [] if a.strip()]
    return lines


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("lock", "unlock"):
        p = sub.add_parser(name)
        p.add_argument("--dir", required=True)
        if name == "lock":
            p.add_argument("--stale-hours", type=float, default=3)
    p = sub.add_parser("preflight")
    p.add_argument("--log")
    p = sub.add_parser("blocked")
    p.add_argument("--log", required=True)
    p.add_argument("--cause", required=True)
    p = sub.add_parser("log")
    p.add_argument("--log", required=True)
    p.add_argument("--entry", required=True)
    p = sub.add_parser("banner")
    p.add_argument("--ready", action="append", default=[])
    p.add_argument("--genai", action="append", default=[])
    p.add_argument("--alert", action="append", default=[])
    args = ap.parse_args(argv)

    if args.cmd == "lock":
        res = take_lock(Path(args.dir).expanduser(), args.stale_hours)
        print(json.dumps(res))
        return 0 if res["locked"] else 3
    if args.cmd == "unlock":
        release_lock(Path(args.dir).expanduser())
        print(json.dumps({"unlocked": True}))
        return 0
    if args.cmd == "preflight":
        locked = screen_locked()
        if locked:
            res = record_blocked(Path(args.log).expanduser(), "screen locked") if args.log else {"blocked": "screen locked"}
            print(json.dumps(res))
            return 4
        print(json.dumps({"screen_locked": locked}))
        return 0
    if args.cmd == "blocked":
        print(json.dumps(record_blocked(Path(args.log).expanduser(), args.cause)))
        return 0
    if args.cmd == "log":
        print(append(Path(args.log).expanduser(), args.entry))
        return 0
    print("\n".join(final_lines(args.ready, args.genai, args.alert)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
