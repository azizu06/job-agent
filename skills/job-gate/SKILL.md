---
name: job-gate
description: Filter job-agent scan results against the user's preferences.yaml (title fit, term, pay floor, location, posting age, skip list, caps) and dedupe against the tracker by company plus requisition ID. Writes the apply queue and a cut report. Use after job-scan, or when the user asks which scanned jobs are worth applying to.
---

# job-gate

## Inputs

- Workspace `$JOB_AGENT_HOME` or `~/.job-agent/`: `profile/preferences.yaml`, the newest `state/scan-*.json` (or one the user names), `state/first-seen.json`, and the tracker.
- Tracker: CSV through `../tracker/scripts/tracker_csv.py --file <csv_path> find|count`, or the Notion or Sheets backend described in the `tracker` skill.

## Gate, in order (each default is configurable in preferences)

1. **Title first.** Keep when the title matches a `target_roles` entry or a close synonym; cut when it contains an `exclude_title_words` entry. Judge role type from the title before reading anything else.
2. **Read the full posting**, not the card preview. Open the employer's live posting (the ATS page the aggregator links to) in its own tab (background, one page id). Pull: requisition ID, term or start date, pay range, location and remote policy, and any statement asking applicants not to use generative AI. Aggregator pages are not enough: JobRight tags skills like "AI Tools" that are not a policy, and its pages list the user's network contacts. Save only the employer's job description text to `state/jd/`, never the aggregator page.
3. **Term.** For internships the stated term must match `term`. A posting with no term is a near miss, not a cut.
4. **Pay.** Compare the midpoint of the posted range with `pay_floor` in the same units. Convert with 2080 work hours a year: hourly = yearly / 2080, and monthly pay is yearly / 12 (so hourly = monthly x 12 / 2080). If the live posting has no pay either, keep the job as a near miss with reason `pay not posted`. Missing pay on an aggregator card is not a cut until the live posting is checked; follow `missing_pay`.
5. **Location.** Must match `locations`, or be remote when `remote_ok`. `relocate_ok` only answers relocation questions on forms; it does not widen this gate.
6. **Age.** Days since `first_seen` must be at most `max_posting_age_days`.
7. **Skip list.** Cut companies in `companies_to_skip`.
8. **GenAI policy.** If the posting asks applicants not to use AI tools and `skip_if_genai_banned` is true, cut it with reason `genai_policy` and list it for the user. Never auto-fill those.
9. **Dedupe.** Key is company plus requisition ID (never company alone). With no req ID, use company plus normalized title plus link. Cut if the tracker already has the key in any status. A later Rejected on the same req overrides an older Assessment.
10. **Caps.** Count tracker rows for the company within its window (`per_company` override or `per_company_default`; `window_days` means rolling, `--since` on the CSV script). When a capped portal has several sibling reqs, rank them by fit and ask the user to confirm the pick before queueing.

Near misses are not queued. List each one in the report so the user can add it.

## Output

- `state/queue.json`: list of `{job_key, company, title, req_id, link, apply_url, ats_guess, fit_notes, jd_path}`. Save each full job description to `state/jd/<job_key>.txt` and set `jd_path`.
- Report every run: how many scanned, the time window covered, cuts grouped by reason with counts, near misses (one line each with the reason), and the final queue.
