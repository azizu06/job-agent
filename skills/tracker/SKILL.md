---
name: tracker
description: Record job applications for job-agent in a pluggable tracker (local CSV by default, or a Notion database or Google Sheet through their MCPs) with columns company, role, req ID, link, date, resume used, status, receipt ID. After a submit, finds the confirmation email through the Gmail MCP and stores the receipt. Use when adding, updating, or checking application records.
---

# tracker

## Columns and statuses

Columns: `company, role, req_id, link, date, resume_used, status, receipt_id, notes`.

Statuses: `Ready` (filled, waiting for the user to submit), `Submitted`, `Assessment`, `Interview`, `Offer`, `Rejected`, `Withdrawn`.

A row is unique by company plus requisition ID. Without a req ID, company plus role. Never dedupe on company alone.

## Backends (`tracker.backend` in preferences)

**csv (default).** Use `scripts/tracker_csv.py` from this skill's folder; it handles dedupe, atomic writes and counts:

```
python3 scripts/tracker_csv.py --file <csv_path> add --company "Acme" --role "SWE Intern" --req-id R123 --link <url> --resume-used <pdf> --status Ready
python3 scripts/tracker_csv.py --file <csv_path> update --company "Acme" --req-id R123 --status Submitted --receipt-id <id>
python3 scripts/tracker_csv.py --file <csv_path> find --company "Acme" --req-id R123
python3 scripts/tracker_csv.py --file <csv_path> count --status Submitted --date today
python3 scripts/tracker_csv.py --file <csv_path> count --company "Acme" --since 2026-01-01
```

**notion.** Needs the Notion MCP and `tracker.notion_database_url`. If the database does not exist, offer to create one with the columns above (`status` as a select with the statuses above). Before adding, query the database for the same company and req ID; update that page instead of creating a duplicate.

**sheets.** Needs a Google Sheets MCP and `tracker.sheets_url`. Header row is the column list. Read the sheet, match company plus req ID, then update that row or append.

For Notion and Sheets, keep the same dedupe and status rules as the CSV script.

## Receipt after submit

With the Gmail MCP:
1. Search with `in:anywhere` so Promotions and Spam are included, from the submit time onward, for the company name, the role, or the req ID (for example `in:anywhere after:<date> ("<company>" OR "<req_id>") (application OR applying OR received)`).
2. Pick the message that confirms this application. Store its message ID (or the portal's confirmation number from the body) as `receipt_id`.
3. No receipt after a reasonable wait: leave `receipt_id` empty and note "no receipt yet". Some portals never send one.

Never send, delete or label email from this skill.
