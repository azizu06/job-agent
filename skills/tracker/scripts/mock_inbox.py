#!/usr/bin/env python3
"""Read a local folder of email messages: the mock inbox used by the e2e rig.

The real default is the Gmail MCP. This adapter is used only when
preferences set `email.receipts: mock` and `email.mock_inbox: <folder>`.
Each message is one JSON file:

  {"id": "...", "from": "...", "to": "...", "subject": "...", "date": "ISO time", "body": "..."}

The same shape is what status-sync expects when you hand it Gmail results.

Usage:
  mock_inbox.py --inbox DIR search [--since ISO] [--text WORDS] [--from TEXT]
  mock_inbox.py --inbox DIR receipt --company NAME [--req-id ID] [--role TEXT] [--since ISO]
  mock_inbox.py --inbox DIR add --from X --to Y --subject S --body B [--date ISO]

search prints matching messages newest first as JSON. --text matches when
any of its words appears in the subject or body (case-insensitive).
receipt prints the newest message that confirms an application to that
company (and req ID when given), or exits 2 when there is none.
Standard library only.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import secrets
import sys
from pathlib import Path

RECEIPT_WORDS = re.compile(r"thank you for (applying|your application)|application (has been )?received|we have received your application", re.I)


def parse_time(value: str) -> dt.datetime:
    t = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    return t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)


def load(inbox: Path) -> list[dict]:
    msgs = []
    for path in sorted(inbox.glob("*.json")):
        try:
            msg = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(msg, dict) and msg.get("date"):
            msgs.append(msg)
    msgs.sort(key=lambda m: parse_time(m["date"]), reverse=True)
    return msgs


def search(msgs: list[dict], since: str | None = None, text: str | None = None, sender: str | None = None) -> list[dict]:
    out = []
    words = [w.lower() for w in (text or "").split() if w]
    for m in msgs:
        if since and parse_time(m["date"]) < parse_time(since):
            continue
        if sender and sender.lower() not in m.get("from", "").lower():
            continue
        hay = (m.get("subject", "") + "\n" + m.get("body", "")).lower()
        if words and not any(w in hay for w in words):
            continue
        out.append(m)
    return out


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (s or "").lower())


def find_receipt(msgs: list[dict], company: str, req_id: str = "", role: str = "", since: str | None = None) -> dict | None:
    for m in search(msgs, since=since):
        text = m.get("subject", "") + "\n" + m.get("body", "")
        if not RECEIPT_WORDS.search(text):
            continue
        if _norm(company) not in _norm(text):
            continue
        if req_id and _norm(req_id) not in _norm(text):
            continue
        if role and not req_id and _norm(role) not in _norm(text):
            continue
        return m
    return None


def add(inbox: Path, sender: str, to: str, subject: str, body: str, date: str | None = None) -> dict:
    inbox.mkdir(parents=True, exist_ok=True)
    msg = {"id": "mock-" + secrets.token_hex(6), "from": sender, "to": to, "subject": subject,
           "date": date or dt.datetime.now(dt.timezone.utc).isoformat(), "body": body}
    (inbox / f"{msg['id']}.json").write_text(json.dumps(msg, indent=1), encoding="utf-8")
    return msg


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--inbox", required=True)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("search")
    s.add_argument("--since")
    s.add_argument("--text")
    s.add_argument("--from", dest="sender")
    r = sub.add_parser("receipt")
    r.add_argument("--company", required=True)
    r.add_argument("--req-id", default="")
    r.add_argument("--role", default="")
    r.add_argument("--since")
    a = sub.add_parser("add")
    a.add_argument("--from", dest="sender", required=True)
    a.add_argument("--to", required=True)
    a.add_argument("--subject", required=True)
    a.add_argument("--body", required=True)
    a.add_argument("--date")
    args = ap.parse_args(argv)
    inbox = Path(args.inbox).expanduser()

    if args.cmd == "add":
        print(json.dumps(add(inbox, args.sender, args.to, args.subject, args.body, args.date)))
        return 0
    msgs = load(inbox)
    if args.cmd == "search":
        print(json.dumps(search(msgs, args.since, args.text, args.sender), indent=1))
        return 0
    found = find_receipt(msgs, args.company, args.req_id, args.role, args.since)
    print(json.dumps({"found": found is not None, "message": found}, indent=1))
    return 0 if found else 2


if __name__ == "__main__":
    sys.exit(main())
