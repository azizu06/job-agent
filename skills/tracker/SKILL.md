---
name: tracker
description: Record job applications for job-agent in a pluggable tracker (local CSV by default, or a Notion database or Google Sheet through their MCPs) with columns company, role, req ID, link, date, resume used, status, receipt ID. After a submit, finds the confirmation email through the Gmail MCP and stores the receipt. Use when adding, updating, or checking application records.
---

# tracker

Python: commands below say `python3`. Use `python_cmd` from `profile/preferences.yaml` instead when it is set (setup writes `py -3` on Windows).

## Columns and statuses

Columns: `company, role, req_id, link, date, resume_used, status, receipt_id, notes, applied_at, pay, location`. For submitted jobs, `notes` starts with `read-back: <path to state/submissions/<job_key>.json>`; add later notes after it with ` | `. `receipt_id` is the confirmation email's message ID (or the portal's confirmation number), which is the proof the submission went through. `resume_used` is the real path of the uploaded file, never a placeholder such as "per queue".

Statuses: `Discovered` (optional: tracked before it is filled), `Ready` (filled, waiting for the user to submit), `Submitted`, `Assessment`, `Interview`, `Offer`, `Rejected`, `Ghosted` (sent, no reply after a long wait; the user sets it), `Withdrawn`, and `Needs you: <reason>` for a parked job.

Unsubmitted jobs: with `tracker.rows_for_unsubmitted: true` (default) filled and parked jobs get `Ready` and `Needs you` rows. With `false`, only sent applications get rows: filled and parked forms stay in `state/queue.json` (`FILLED`, `NEEDS YOU`) until a receipt arrives, which keeps the tracker to what employers actually received.

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

**notion.** Needs the Notion MCP and `tracker.notion_database_url`. If the database does not exist, offer to create one with the columns above (`status` as a select with the statuses above). Search before create: query the database for the same company and req ID, and update that page instead of creating a duplicate. Notion gotchas:
- To change the `status` select's options, use `notion-update-data-source` with `statements` (for example `ALTER COLUMN "status" SET SELECT('Submitted':green, 'Rejected':red, ...)`). Its `properties` and `schema` arguments are silently ignored.
- Several Notion and Gmail connector tools publish empty argument schemas, and a wrong argument name returns a generic error that looks like a dead server. Read the tool's error text (it often names the allowed values), or call a no-argument tool on the same server, before deciding the connector is down.
- Confirm a scoped search works by searching a value you know is present before trusting an empty result.

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

A receipt for a role the loop did not fill (the user applied by hand, or through an extension) is still logged: `record-submit --not-filled --receipt-id <id>` writes the row and flags it in `notes`; no resume or read-back is required for it. List it in the run log. When email and the tracker disagree, write the receipts you found to a JSON list (`company, req_id, role, id, date`) and run `tracker_csv.py reconcile --receipts <file>`: it lists receipts with no row and rows missing their receipt. Match on req ID: a receipt for another req at the same company is a different application.

Never send, delete or label email from this skill.
