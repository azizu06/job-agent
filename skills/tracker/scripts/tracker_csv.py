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
  python3 tracker_csv.py --file tracker.csv record-submit --company Acme --role "SWE Intern" \
      --req-id R123 --link <url> --resume-used /abs/path/uploaded.pdf \
      --read-back /abs/state/submissions/<job_key>.json --inbox <mock inbox> --since <submit time>
  python3 tracker_csv.py --file tracker.csv audit   # exit 1 lists submitted rows missing proof

resume_used must be the absolute path of a file that exists: the exact PDF
that was uploaded. record-submit writes the whole submitted row in one step
and, with --inbox, looks the receipt up itself (mock inbox, the e2e rig).
With Gmail, search first and pass the message ID as --receipt-id.
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


def check_resume(path: str) -> str:
    """Return the path unchanged if it is absolute and exists; raise otherwise."""
    if not path:
        raise ValueError("resume_used is required: the absolute path of the uploaded PDF")
    p = Path(path)
    if not p.is_absolute():
        raise ValueError(f"resume_used must be an absolute path, got {path!r}")
    if not p.is_file():
        raise ValueError(f"resume_used {path} does not exist")
    return str(p)


READ_BACK = "read-back: "
# Statuses that mean the application was sent; such rows need proof.
SENT = {"Submitted", "Assessment", "Interview", "Offer", "Rejected"}


def record_submit(rows: list[dict], ident: dict, resume_used: str, read_back: str, link: str = "",
                  date: str = "", receipt_id: str = "", inbox: str = "", since: str | None = None) -> dict:
    """Write or update the row for a pressed final control, with receipt and resume proof."""
    check_resume(resume_used)
    if not read_back:
        raise ValueError("read_back is required: the state/submissions/<job_key>.json path")
    if not receipt_id and inbox:
        import mock_inbox  # same folder
        msg = mock_inbox.find_receipt(mock_inbox.load(Path(inbox).expanduser()), ident["company"],
                                      ident.get("req_id", ""), ident.get("role", ""), since)
        receipt_id = msg["id"] if msg else ""
    row, _ = add(rows, dict(ident, link=link, date=date, status="Submitted"))
    old_notes = [n for n in row.get("notes", "").split(" | ") if n and not n.startswith(READ_BACK) and n != "no receipt yet"]
    notes = [READ_BACK + read_back] + old_notes + ([] if receipt_id else ["no receipt yet"])
    row.update({"status": "Submitted", "resume_used": resume_used, "receipt_id": receipt_id or row.get("receipt_id", ""),
                "notes": " | ".join(notes)})
    if link:
        row["link"] = link
    return row


def audit(rows: list[dict]) -> list[str]:
    """Problems on rows whose application was sent."""
    problems = []
    for row in rows:
        if row.get("status") not in SENT:
            continue
        name = f"{row['company']} {row.get('req_id') or row.get('role')}".strip()
        if not row.get("receipt_id") and "no receipt yet" not in row.get("notes", ""):
            problems.append(f"{name}: receipt_id is empty and notes do not say 'no receipt yet'")
        try:
            check_resume(row.get("resume_used", ""))
        except ValueError as exc:
            problems.append(f"{name}: {exc}")
        if not row.get("notes", "").startswith(READ_BACK):
            problems.append(f"{name}: notes do not start with the read-back path")
    return problems


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

    p_rec = sub.add_parser("record-submit", help="write the row for a pressed final control")
    ident(p_rec)
    p_rec.add_argument("--resume-used", required=True, help="absolute path of the uploaded PDF")
    p_rec.add_argument("--read-back", required=True, help="state/submissions/<job_key>.json path")
    p_rec.add_argument("--link", default="")
    p_rec.add_argument("--date", default="")
    p_rec.add_argument("--receipt-id", default="", help="Gmail message ID or portal confirmation number")
    p_rec.add_argument("--inbox", default="", help="mock inbox folder (email.receipts: mock)")
    p_rec.add_argument("--since", help="submit time, ISO")

    sub.add_parser("audit")
    sub.add_parser("list")

    args = ap.parse_args(argv)
    path = Path(args.file).expanduser()
    rows = load(path)

    try:
        if args.cmd in ("add", "update") and args.resume_used:
            check_resume(args.resume_used)
        if args.cmd == "record-submit":
            row = record_submit(rows, {"company": args.company, "req_id": args.req_id, "role": args.role},
                                args.resume_used, args.read_back, args.link, args.date, args.receipt_id,
                                args.inbox, args.since)
            save(path, rows)
            print(json.dumps({"recorded": True, "receipt_found": bool(row["receipt_id"]), "row": row}))
            return 0
        if args.cmd == "audit":
            problems = audit(rows)
            print(json.dumps({"ok": not problems, "problems": problems}, indent=1))
            return 1 if problems else 0
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
