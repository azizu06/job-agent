#!/usr/bin/env python3
"""Read a recent SMS verification code from macOS Messages. OPT-IN, macOS only.

Reads ~/Library/Messages/chat.db read-only and returns the code from the
newest incoming message within the last few minutes that looks like a
verification code. iPhone texts reach this database when "Text Message
Forwarding" is on for this Mac.

Permission: the app that runs your agent needs Full Disk Access
(System Settings > Privacy & Security > Full Disk Access). Without it the
database cannot be opened and this script says so.

By default the code goes to the clipboard (cleared after 30 s) and only the
sender and age are printed, so the code does not land in logs. Use --print
to print it instead.

Windows: Phone Link has no stable API, so SMS codes go to the human there.

Usage: sms_code.py [--minutes 5] [--sender TEXT] [--print] [--db PATH]
Standard library only.
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
import sqlite3
import sys
from pathlib import Path

APPLE_EPOCH = dt.datetime(2001, 1, 1, tzinfo=dt.timezone.utc)
CODE_HINT = re.compile(r"\b(code|passcode|verification|verify|otp|one[- ]time|pin|security)\b", re.IGNORECASE)
CODE_RE = re.compile(r"(?<![\d-])(\d{3}[- ]\d{3}|\d{4,8})(?![\d-])")


def apple_time_to_dt(value: int) -> dt.datetime:
    # Newer macOS stores nanoseconds since 2001-01-01; older stores seconds.
    seconds = value / 1e9 if value > 1e11 else float(value)
    return APPLE_EPOCH + dt.timedelta(seconds=seconds)


def dt_to_apple_ns(when: dt.datetime) -> int:
    return int((when - APPLE_EPOCH).total_seconds() * 1e9)


def text_from_attributed_body(blob: bytes | None) -> str:
    """Best-effort text from the typedstream blob newer macOS uses."""
    if not blob:
        return ""
    marker = blob.find(b"NSString")
    chunk = blob[marker + 8:] if marker >= 0 else blob
    return chunk.decode("utf-8", errors="ignore")


def extract_code(text: str) -> str | None:
    if not text or not CODE_HINT.search(text):
        return None
    m = CODE_RE.search(text)
    return re.sub(r"[- ]", "", m.group(1)) if m else None


def find_code(db_path: Path, minutes: float, sender: str | None, now: dt.datetime | None = None):
    now = now or dt.datetime.now(dt.timezone.utc)
    since = dt_to_apple_ns(now - dt.timedelta(minutes=minutes))
    uri = f"file:{db_path}?mode=ro"
    con = sqlite3.connect(uri, uri=True)
    try:
        rows = con.execute(
            """
            SELECT m.date, m.text, m.attributedBody, h.id
            FROM message m LEFT JOIN handle h ON m.handle_id = h.ROWID
            WHERE m.is_from_me = 0 AND m.date >= ?
            ORDER BY m.date DESC LIMIT 50
            """,
            (since,),
        ).fetchall()
    finally:
        con.close()
    for date, text, body, handle in rows:
        if sender and sender.lower() not in (handle or "").lower():
            content = (text or "") + " " + text_from_attributed_body(body)
            if sender.lower() not in content.lower():
                continue
        code = extract_code(text or "") or extract_code(text_from_attributed_body(body))
        if code:
            age = (now - apple_time_to_dt(date)).total_seconds()
            return {"code": code, "sender": handle or "unknown", "age_seconds": int(age)}
    return None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--minutes", type=float, default=5)
    ap.add_argument("--sender", help="part of the sender number, short code or text, for example the company name")
    ap.add_argument("--print", action="store_true", help="print the code instead of copying it")
    ap.add_argument("--db", help="Messages database (default ~/Library/Messages/chat.db)")
    args = ap.parse_args(argv)

    if sys.platform != "darwin" and not args.db:
        print("SMS codes are macOS only; hand this code to the user.", file=sys.stderr)
        return 2
    db = Path(args.db).expanduser() if args.db else Path.home() / "Library" / "Messages" / "chat.db"
    try:
        found = find_code(db, args.minutes, args.sender)
    except sqlite3.OperationalError as exc:
        print(f"cannot read Messages ({exc}). Grant Full Disk Access to the app running the agent, "
              "or hand this code to the user.", file=sys.stderr)
        return 3
    if not found:
        print(f"no code found in the last {args.minutes:g} minutes", file=sys.stderr)
        return 1
    if args.print:
        print(found["code"])
        return 0
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from portal_creds import copy_to_clipboard  # same clipboard helper as passwords

    copy_to_clipboard(found["code"], 30)
    print(f"code from {found['sender']} ({found['age_seconds']}s old) is on the clipboard for 30s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
