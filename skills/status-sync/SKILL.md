---
name: status-sync
description: Update job-agent tracker statuses from new email (Gmail MCP by default, or the local mock inbox in the test rig). Reads recent mail for online assessment invites, interview invites, offers and rejections, matches each message to its tracker row by company and requisition ID, and updates the status without creating duplicates. Use when the user asks to sync application statuses or check for responses.
---

# status-sync

## Inputs

- Email, per `email.receipts` in preferences: the Gmail MCP (default, read only for this skill), or with `mock` the folder in `email.mock_inbox` (the e2e rig).
- `scripts/sync_status.py` from this skill's folder applies the rules below to a CSV tracker and prints a JSON plan.
- Tracker per the `tracker` skill. Last sync time in `<workspace>/state/status-sync.json` (`{"last_sync": "ISO time"}`); default to 14 days ago.

## Steps

1. Gmail: search with `in:anywhere after:<last_sync date>` plus terms such as `assessment OR "coding challenge" OR HackerRank OR CodeSignal OR interview OR "next steps" OR offer OR "unfortunately" OR "not moving forward" OR "other candidates"`.
   Write the messages you found to a JSON file as a list of `{id, from, subject, date, body}` (date as ISO time). Mock inbox: skip the search and pass `--inbox <email.mock_inbox>` instead of `--messages`.
2. Preview: `python3 scripts/sync_status.py --tracker <csv_path> --messages <file> --state <workspace>/state/status-sync.json`. It classifies, matches and applies steps 3 to 5, and lists skipped messages with a reason. Read the plan; if a classification is wrong, drop that message from the file and run it again. Then run the same command with `--apply`, which saves `last_sync` only when every update succeeded. For Notion or Sheets, apply the printed plan by hand with the same rules.
   The rules the script follows (and that you follow by hand for Notion or Sheets):
3. Classify each message: `Assessment`, `Interview`, `Offer`, `Rejected`, or ignore (newsletters, job alerts, receipts already stored).
4. Match to a row: req ID in the message first, then company plus role, then company alone only if the company has exactly one open row. When the match is ambiguous, list it for the user instead of guessing.
5. Update rules:
   - Never create a row from this skill. An unmatched message goes in the report.
   - Use the newest message per row. A later rejection on the same req overrides an older assessment invite, and a later interview overrides an older rejection only if it clearly refers to the same req.
   - Do not move `Offer` or `Withdrawn` to anything else without asking.
   - Add the message date and a short reason to `notes`, after what is already there. Never drop earlier notes: apply-fill keeps the path of the pre-submit read-back there.
6. Save the new `last_sync` only after all updates succeed.

## Report

Rows changed (company, role, old status, new status, message date), unmatched or ambiguous messages, and any deadline mentioned in an assessment or interview email.

Never reply to, send, delete, archive or label email.
