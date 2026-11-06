#!/usr/bin/env python3
"""Apply status-sync rules to a list of email messages and a CSV tracker.

The agent finds candidate messages (Gmail MCP by default, or the mock inbox
through ../../tracker/scripts/mock_inbox.py), then this script classifies them,
matches each to one tracker row, and applies the update rules from the
status-sync skill. It prints a JSON report. Nothing is written without
--apply.

Messages are JSON objects: {"id", "from", "subject", "date" (ISO), "body"}.

Usage:
  sync_status.py --tracker tracker.csv --messages found.json [--since ISO] [--apply] [--state status-sync.json]
  sync_status.py --tracker tracker.csv --inbox DIR [--since ISO] [--apply] [--state status-sync.json]

--since defaults to "last_sync" in --state, else 14 days ago. With --apply
and --state, last_sync is saved only after every update succeeded.
Standard library only.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent / "tracker" / "scripts"))

import mock_inbox as mbox  # noqa: E402
import tracker_csv as tc  # noqa: E402

RULES = [
    ("Offer", re.compile(r"\b(offer letter|pleased to (offer|extend)|extend (you )?an offer|congratulations[^.]{0,60}offer)\b", re.I)),
    ("Rejected", re.compile(r"\b(unfortunately|not (be )?moving forward|other candidates|decided not to|no longer under consideration|will not be proceeding)\b", re.I)),
    ("Assessment", re.compile(r"\b(online assessment|coding (challenge|assessment)|hackerrank|codesignal|codility|take-home|technical assessment)\b", re.I)),
    ("Interview", re.compile(r"\b(interview|schedule (a|your) (call|chat|conversation)|phone screen|meet with (our|the) team)\b", re.I)),
]
FROZEN = {"Offer", "Withdrawn"}


def classify(msg: dict) -> str | None:
    text = f"{msg.get('subject', '')}\n{msg.get('body', '')}"
    if mbox.RECEIPT_WORDS.search(text) and not any(rx.search(text) for _, rx in RULES):
        return None
    for status, rx in RULES:
        if rx.search(text):
            return status
    return None


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (s or "").lower())


def match(msg: dict, rows: list[dict]) -> tuple[dict | None, str]:
    """Return (row, how) where how is req_id, company_role, company_only, ambiguous or none."""
    text = _norm(f"{msg.get('subject', '')}\n{msg.get('body', '')}")
    by_req = [r for r in rows if r.get("req_id") and _norm(r["req_id"]) in text]
    if len(by_req) == 1:
        return by_req[0], "req_id"
    if len(by_req) > 1:
        return None, "ambiguous"
    by_company = [r for r in rows if tc.norm_company(r["company"]) and tc.norm_company(r["company"]) in text]
    by_role = [r for r in by_company if r.get("role") and _norm(r["role"]) in text]
    if len(by_role) == 1:
        return by_role[0], "company_role"
    if len(by_role) > 1:
        return None, "ambiguous"
    open_rows = [r for r in by_company if r["status"] not in ("Rejected", "Withdrawn", "Offer")]
    if len(open_rows) == 1:
        return open_rows[0], "company_only"
    return None, "ambiguous" if by_company else "none"


def plan(msgs: list[dict], rows: list[dict]) -> dict:
    changes: list[dict] = []
    skipped: list[dict] = []
    latest: dict[int, tuple[dict, str, str]] = {}
    for msg in sorted(msgs, key=lambda m: mbox.parse_time(m["date"])):
        status = classify(msg)
        if status is None:
            continue
        row, how = match(msg, rows)
        if row is None:
            skipped.append({"id": msg.get("id"), "subject": msg.get("subject"), "status": status, "reason": how})
            continue
        latest[id(row)] = (msg, status, how)
    for row in rows:
        if id(row) not in latest:
            continue
        msg, status, how = latest[id(row)]
        old = row["status"]
        if old == status:
            continue
        if old in FROZEN:
            skipped.append({"id": msg.get("id"), "subject": msg.get("subject"), "status": status,
                            "reason": f"row is {old}; ask the user before changing it"})
            continue
        if old == "Rejected" and status in ("Interview", "Assessment") and how != "req_id":
            skipped.append({"id": msg.get("id"), "subject": msg.get("subject"), "status": status,
                            "reason": "row is Rejected and the message does not name the req ID"})
            continue
        changes.append({"company": row["company"], "role": row["role"], "req_id": row["req_id"], "old": old,
                        "new": status, "date": msg["date"], "matched_by": how, "message_id": msg.get("id"),
                        "subject": msg.get("subject")})
    return {"changes": changes, "skipped": skipped}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tracker", required=True)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--messages", help="JSON file with a list of messages")
    src.add_argument("--inbox", help="mock inbox folder (see mock_inbox.py)")
    ap.add_argument("--since")
    ap.add_argument("--state", help="status-sync.json holding last_sync")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args(argv)

    state_path = Path(args.state).expanduser() if args.state else None
    since = args.since
    if not since and state_path and state_path.exists():
        since = json.loads(state_path.read_text(encoding="utf-8")).get("last_sync")
    if not since:
        since = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=14)).replace(microsecond=0).isoformat()
    started = dt.datetime.now(dt.timezone.utc).isoformat()

    if args.messages:
        msgs = json.loads(Path(args.messages).read_text(encoding="utf-8"))
    else:
        msgs = mbox.load(Path(args.inbox).expanduser())
    msgs = mbox.search(msgs, since=since)

    tracker = Path(args.tracker).expanduser()
    rows = tc.load(tracker)
    report = plan(msgs, rows)
    report.update({"since": since, "messages_read": len(msgs), "applied": False})
    if args.apply:
        for ch in report["changes"]:
            note = f"{ch['date'][:10]} {ch['new']}: {ch['subject']}"
            current = tc.find(rows, ch["company"], ch["req_id"], ch["role"])
            if current is not None and current.get("notes"):
                note = current["notes"] + " | " + note  # keep earlier notes, such as the pre-submit read-back path
            row = tc.update(rows, ch["company"], ch["req_id"], ch["role"], {"status": ch["new"], "notes": note})
            if row is None:
                print(json.dumps(report, indent=1))
                print(f"update failed for {ch['company']}; last_sync not saved", file=sys.stderr)
                return 1
        tc.save(tracker, rows)
        report["applied"] = True
        if state_path:
            state_path.parent.mkdir(parents=True, exist_ok=True)
            state_path.write_text(json.dumps({"last_sync": started}) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
