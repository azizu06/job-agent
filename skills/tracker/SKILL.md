---
name: tracker
description: Record job applications for job-agent in a pluggable tracker (local CSV by default, or a Notion database or Google Sheet through their MCPs) with columns company, role, req ID, link, date, resume used, status, receipt ID. After a submit, finds the confirmation email through the Gmail MCP and stores the receipt. Use when adding, updating, or checking application records.
---

# tracker

## Columns and statuses

Columns: `company, role, req_id, link, date, resume_used, status, receipt_id, notes`. For submitted jobs, `notes` starts with `read-back: <path to state/submissions/<job_key>.json>`; add later notes after it with ` | `.

Statuses: `Ready` (filled, waiting for the user to submit), `Submitted`, `Assessment`, `Interview`, `Offer`, `Rejected`, `Withdrawn`, and `Needs you: <reason>` for a parked job.

A row is unique by company plus requisition ID. Without a req ID, company plus role. Never dedupe on company alone.

## Backends (`tracker.backend` in preferences)

**csv (default).** Use `scripts/tracker_csv.py` from this skill's folder; it handles dedupe, atomic writes and counts:

```
python3 scripts/tracker_csv.py --file <csv_path> add --company "Acme" --role "SWE Intern" --req-id R123 --link <url> --resume-used <pdf> --status Ready
python3 scripts/tracker_csv.py --file <csv_path> update --company "Acme" --req-id R123 --status Submitted --receipt-id <id>
python3 scripts/tracker_csv.py --file <csv_path> record-submit --company "Acme" --role "SWE Intern" --req-id R123 --link <url> --resume-used /abs/path/uploaded.pdf --read-back /abs/state/submissions/<job_key>.json [--inbox <email.mock_inbox> --since <submit time> | --receipt-id <gmail id>]
python3 scripts/tracker_csv.py --file <csv_path> audit   # exit 1 lists sent rows missing receipt, resume file or read-back
python3 scripts/tracker_csv.py --file <csv_path> find --company "Acme" --req-id R123   # exit 2 means not found
python3 scripts/tracker_csv.py --file <csv_path> count --status Submitted --date today
python3 scripts/tracker_csv.py --file <csv_path> count --company "Acme" --since 2026-01-01
```

**notion.** Needs the Notion MCP and `tracker.notion_database_url`. If the database does not exist, offer to create one with the columns above (`status` as a select with the statuses above). Before adding, query the database for the same company and req ID; update that page instead of creating a duplicate.

**sheets.** Needs a Google Sheets MCP and `tracker.sheets_url`. Header row is the column list. Read the sheet, match company plus req ID, then update that row or append.

For Notion and Sheets, keep the same dedupe and status rules as the CSV script.

`resume_used` is always the absolute path of the exact PDF that was uploaded, and that file must exist. The script rejects relative or missing paths. Never write a path relative to the workspace.

## Receipt after submit

Every pressed final control is recorded with ONE `record-submit` call, never with `add` plus a later `update`. It sets `Submitted`, the read-back note, the absolute resume path, and the receipt. After the last submit of a run, `audit` must exit 0.

The email source is `email.receipts` in preferences: `gmail` (the default, through the Gmail MCP), `none`, or `mock` (the local test rig only).

With `mock`, pass `--inbox <email.mock_inbox> --since <submit time>` to `record-submit`; it finds the confirming message itself and stores its `id` as `receipt_id`. If the receipt was not there yet, the output says `"receipt_found": false`: wait a few seconds and run the same `record-submit` again. To inspect the inbox by hand: `python3 scripts/mock_inbox.py --inbox <email.mock_inbox> receipt --company "<company>" --req-id <req>` (exit 2 means none).

With the Gmail MCP:
1. Search with `in:anywhere` so Promotions and Spam are included, from the submit time onward, for the company name, the role, or the req ID (for example `in:anywhere after:<date> ("<company>" OR "<req_id>") (application OR applying OR received)`).
2. Pick the message that confirms this application. Pass its message ID (or the portal's confirmation number from the body) to `record-submit --receipt-id`.
3. No receipt after a reasonable wait: run `record-submit` without a receipt; it notes "no receipt yet". Some portals never send one.

Never send, delete or label email from this skill.
