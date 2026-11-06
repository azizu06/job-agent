#!/usr/bin/env python3
"""Local CSV job tracker. Standard library only.

Rows are unique by company plus requisition ID. When a posting has no
requisition ID, company plus role is the key instead.

Examples:
  python3 tracker_csv.py --file tracker.csv add --company Acme --role "SWE Intern" \
      --req-id R123 --link https://example.com/jobs/R123 --resume-used acme-swe.md
  python3 tracker_csv.py --file tracker.csv find --company Acme --req-id R123
  python3 tracker_csv.py --file tracker.csv update --company Acme --req-id R123 \
      --status Interview
  python3 tracker_csv.py --file tracker.csv count --status Submitted --date today
  python3 tracker_csv.py --file tracker.csv count --company Acme --since 2026-01-01
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import re
import sys
from pathlib import Path

COLUMNS = ["company", "role", "req_id", "link", "date", "resume_used", "status", "receipt_id", "notes"]
# Ready means filled and waiting for the human to press Submit.
# "Needs you: <reason>" means the applier parked the tab for the human.
STATUSES = ["Ready", "Submitted", "Assessment", "Interview", "Offer", "Rejected", "Withdrawn"]

_SUFFIXES = re.compile(r"\b(inc|llc|ltd|corp|corporation|co|company|plc|gmbh)\b\.?", re.IGNORECASE)


def norm_company(name: str) -> str:
    name = _SUFFIXES.sub(" ", name or "")
    return re.sub(r"[^a-z0-9]+", "", name.lower())


def norm_text(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (value or "").lower())


def row_key(row: dict) -> tuple[str, str]:
    company = norm_company(row.get("company", ""))
    req = norm_text(row.get("req_id", ""))
    if req:
        return (company, "req:" + req)
    return (company, "role:" + norm_text(row.get("role", "")))


def load(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    for row in rows:
        for col in COLUMNS:
            row.setdefault(col, "")
    return rows


def save(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    tmp.replace(path)


def find(rows: list[dict], company: str, req_id: str = "", role: str = "") -> dict | None:
    key = row_key({"company": company, "req_id": req_id, "role": role})
    for row in rows:
        if row_key(row) == key:
            return row
    return None


def add(rows: list[dict], new: dict) -> tuple[dict, bool]:
    """Return (row, created). An existing row is returned unchanged."""
    existing = find(rows, new.get("company", ""), new.get("req_id", ""), new.get("role", ""))
    if existing is not None:
        return existing, False
    row = {col: new.get(col, "") or "" for col in COLUMNS}
    row["date"] = row["date"] or dt.date.today().isoformat()
    row["status"] = row["status"] or "Ready"
    _check_status(row["status"])
    rows.append(row)
    return row, True


def update(rows: list[dict], company: str, req_id: str, role: str, changes: dict) -> dict | None:
    row = find(rows, company, req_id, role)
    if row is None:
        return None
    for col, value in changes.items():
        if value is None:
            continue
        if col == "status":
            _check_status(value)
        row[col] = value
    return row


def count(
    rows: list[dict],
    status: str | None = None,
    date: str | None = None,
    company: str | None = None,
    since: str | None = None,
) -> int:
    """Count rows. `date` matches one day; `since` keeps rows on or after a day."""
    n = 0
    for row in rows:
        if status and row["status"] != status:
            continue
        if date and row["date"] != date:
            continue
        if since and row["date"] < since:
            continue
        if company and norm_company(row["company"]) != norm_company(company):
            continue
        n += 1
    return n


NEEDS_YOU = "Needs you: "  # parked for the human, for example "Needs you: captcha"


def _check_status(status: str) -> None:
    if status in STATUSES:
        return
    if status.startswith(NEEDS_YOU) and status[len(NEEDS_YOU):].strip():
        return
    raise ValueError(f"status must be one of {', '.join(STATUSES)} or '{NEEDS_YOU}<reason>', got {status!r}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--file", required=True, help="path to tracker.csv")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def ident(p: argparse.ArgumentParser) -> None:
        p.add_argument("--company", required=True)
        p.add_argument("--req-id", default="")
        p.add_argument("--role", default="")

    p_add = sub.add_parser("add")
    ident(p_add)
    for col in ("link", "date", "resume-used", "status", "receipt-id", "notes"):
        p_add.add_argument("--" + col, default="")

    p_find = sub.add_parser("find")
    ident(p_find)

    p_up = sub.add_parser("update")
    ident(p_up)
    for col in ("link", "date", "resume-used", "status", "receipt-id", "notes"):
        p_up.add_argument("--" + col, default=None)

    p_count = sub.add_parser("count")
    p_count.add_argument("--status")
    p_count.add_argument("--date", help="YYYY-MM-DD, or 'today'")
    p_count.add_argument("--company")
    p_count.add_argument("--since", help="YYYY-MM-DD; counts rows on or after it (rolling caps)")

    sub.add_parser("list")

    args = ap.parse_args(argv)
    path = Path(args.file).expanduser()
    rows = load(path)

    try:
        if args.cmd == "add":
            new = {
                "company": args.company, "role": args.role, "req_id": args.req_id,
                "link": args.link, "date": args.date, "resume_used": args.resume_used,
                "status": args.status, "receipt_id": args.receipt_id, "notes": args.notes,
            }
            row, created = add(rows, new)
            if created:
                save(path, rows)
            print(json.dumps({"created": created, "row": row}))
        elif args.cmd == "find":
            row = find(rows, args.company, args.req_id, args.role)
            print(json.dumps({"found": row is not None, "row": row}))
            return 0 if row else 2
        elif args.cmd == "update":
            changes = {
                "link": args.link, "date": args.date, "resume_used": args.resume_used,
                "status": args.status, "receipt_id": args.receipt_id, "notes": args.notes,
            }
            row = update(rows, args.company, args.req_id, args.role, changes)
            if row is None:
                print(json.dumps({"updated": False, "error": "no matching row"}))
                return 2
            save(path, rows)
            print(json.dumps({"updated": True, "row": row}))
        elif args.cmd == "count":
            date = dt.date.today().isoformat() if args.date == "today" else args.date
            print(count(rows, args.status, date, args.company, args.since))
        elif args.cmd == "list":
            print(json.dumps(rows, indent=2))
    except ValueError as exc:
        print(json.dumps({"error": str(exc)}))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
