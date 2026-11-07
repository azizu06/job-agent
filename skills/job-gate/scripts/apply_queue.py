#!/usr/bin/env python3
"""The apply queue: jobs that passed the gate and are waiting, filled or parked.

state/queue.json is {"entries": [...], "removed": [...]}. An older plain
list of queue items is read as entries in state QUEUED.

Entry states:
  QUEUED          passed the gate, not filled yet
  WAIT-REFERRAL   a referral ask is pending; do not fill until it resolves
  FILLED          filled to the final control; waiting for the user to submit
  NEEDS YOU: <r>  parked for the user (sign-in, captcha, ...); tab left open
  DROPPED: <r>    the user or the gate dropped it; never re-added

Rules:
  - Dedupe by company plus req ID (company plus title plus link without a
    req ID), never company alone. A different req at the same company is a
    different entry.
  - An entry leaves the queue only with a receipt (`remove --receipt <id>`),
    and it moves to "removed" with that receipt. Nothing else deletes it.
  - A DROPPED entry stays in the file so the gate never adds it again.
  - `next --limit N` gives up to N QUEUED entries for this run; the rest wait.

  apply_queue.py --queue state/queue.json list [--state QUEUED]
  apply_queue.py --queue state/queue.json next --limit 10
  apply_queue.py --queue state/queue.json set --company C --req-id R --state "FILLED" [--note TEXT]
  apply_queue.py --queue state/queue.json remove --company C --req-id R --receipt <message id>
  apply_queue.py --queue state/queue.json add --json '{"company": ..., "title": ..., "req_id": ...}'
Standard library only.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent / "tracker" / "scripts"))

import tracker_csv  # noqa: E402

QUEUED = "QUEUED"
WAIT_REFERRAL = "WAIT-REFERRAL"
FILLED = "FILLED"
NEEDS_YOU = "NEEDS YOU"
DROPPED = "DROPPED"


def empty() -> dict:
    return {"entries": [], "removed": []}


def load(path: Path) -> dict:
    if not path or not path.exists():
        return empty()
    data = json.loads(path.read_text(encoding="utf-8") or "{}")
    if isinstance(data, list):  # older shape: a plain list of queue items
        data = {"entries": [dict(e, state=e.get("state") or QUEUED) for e in data], "removed": []}
    data.setdefault("entries", [])
    data.setdefault("removed", [])
    return data


def save(path: Path, queue: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(queue, indent=1) + "\n", encoding="utf-8")
    tmp.replace(path)


def key(entry: dict) -> tuple:
    company = tracker_csv.norm_company(entry.get("company", ""))
    req = tracker_csv.norm_text(entry.get("req_id", ""))
    if req:
        return (company, "req:" + req)
    return (company, "title:" + tracker_csv.norm_text(entry.get("title", "")), tracker_csv.norm_text(entry.get("link", "")))


def find(queue: dict, ident: dict, include_removed: bool = False) -> dict | None:
    k = key(ident)
    for e in queue["entries"] + (queue["removed"] if include_removed else []):
        if key(e) == k:
            return e
    return None


def check_state(state: str) -> str:
    if state in (QUEUED, WAIT_REFERRAL, FILLED):
        return state
    for prefix in (NEEDS_YOU, DROPPED):
        if state.startswith(prefix + ": ") and state[len(prefix) + 2:].strip():
            return state
    raise ValueError(f"state must be {QUEUED}, {WAIT_REFERRAL}, {FILLED}, '{NEEDS_YOU}: <reason>' or "
                     f"'{DROPPED}: <reason>', got {state!r}")


def _now(now: dt.datetime | None) -> str:
    return (now or dt.datetime.now(dt.timezone.utc)).replace(microsecond=0).isoformat()


def add(queue: dict, entry: dict, now: dt.datetime | None = None) -> tuple[dict, bool]:
    """Add an entry unless the same req is already there (in any state, dropped included)."""
    existing = find(queue, entry)
    if existing is not None:
        return existing, False
    e = dict(entry)
    e["state"] = check_state(e.get("state") or QUEUED)
    e.setdefault("added_at", _now(now))
    queue["entries"].append(e)
    return e, True


def set_state(queue: dict, ident: dict, state: str, note: str = "", now: dt.datetime | None = None) -> dict | None:
    e = find(queue, ident)
    if e is None:
        return None
    e["state"] = check_state(state)
    e["updated_at"] = _now(now)
    if note:
        e["notes"] = (e.get("notes", "") + " | " if e.get("notes") else "") + note
    return e


def remove(queue: dict, ident: dict, receipt: str, now: dt.datetime | None = None) -> dict | None:
    """Move an entry to `removed`. Only a receipt (message ID or confirmation number) may do this."""
    if not (receipt or "").strip():
        raise ValueError("an entry leaves the queue only with a receipt: pass the message ID or confirmation number")
    e = find(queue, ident)
    if e is None:
        return None
    queue["entries"].remove(e)
    e = dict(e, receipt=receipt, removed_at=_now(now))
    queue["removed"].append(e)
    return e


def next_batch(queue: dict, limit: int) -> list[dict]:
    return [e for e in queue["entries"] if e.get("state") == QUEUED][:max(limit, 0)]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--queue", required=True)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("list")
    p.add_argument("--state")
    p = sub.add_parser("next")
    p.add_argument("--limit", type=int, default=10)
    for name in ("set", "remove"):
        p = sub.add_parser(name)
        p.add_argument("--company", required=True)
        p.add_argument("--req-id", default="")
        p.add_argument("--title", default="")
        p.add_argument("--link", default="")
        if name == "set":
            p.add_argument("--state", required=True)
            p.add_argument("--note", default="")
        else:
            p.add_argument("--receipt", required=True)
    p = sub.add_parser("add")
    p.add_argument("--json", required=True)
    args = ap.parse_args(argv)

    path = Path(args.queue).expanduser()
    queue = load(path)
    try:
        if args.cmd == "list":
            items = [e for e in queue["entries"] if not args.state or e["state"].startswith(args.state)]
            print(json.dumps(items, indent=1))
            return 0
        if args.cmd == "next":
            print(json.dumps(next_batch(queue, args.limit), indent=1))
            return 0
        if args.cmd == "add":
            e, created = add(queue, json.loads(args.json))
            if created:
                save(path, queue)
            print(json.dumps({"created": created, "entry": e}))
            return 0
        ident = {"company": args.company, "req_id": args.req_id, "title": args.title, "link": args.link}
        e = set_state(queue, ident, args.state, args.note) if args.cmd == "set" else remove(queue, ident, args.receipt)
        if e is None:
            print(json.dumps({"error": "no matching queue entry"}))
            return 2
        save(path, queue)
        print(json.dumps({"ok": True, "entry": e}))
        return 0
    except ValueError as exc:
        print(json.dumps({"error": str(exc)}))
        return 1


if __name__ == "__main__":
    sys.exit(main())
