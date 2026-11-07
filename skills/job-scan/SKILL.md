---
name: job-scan
description: Collect new job postings for job-agent. Reads the user's JobRight "Most Recent" recommendations feed in their own signed-in Chrome through a browser MCP, stops at the saved checkpoint card, and falls back to the Indeed MCP connector. Writes a scan file to the workspace. Use when the user asks to find or scan new jobs, or as step 1 of job-run.
---

# job-scan

## Inputs

- Workspace: `$JOB_AGENT_HOME` or `~/.job-agent/`. Read `profile/preferences.yaml` (run `job-setup` first if missing).
- Checkpoint: `state/jobright-checkpoint.json`, shaped `{"job_key": "...", "title": "...", "company": "...", "seen_at": "ISO time"}`.
- First-seen log: `state/first-seen.json`, a map of job key to the ISO date the agent first saw it.

## Output

`state/scan-<YYYYMMDD-HHMM>.json`: a list of objects with `company, title, location, pay_text, posted_text, first_seen, link, source, job_key, req_id (if shown), apply_url (if shown)`. Also print a one-line summary: cards read, new cards, source, and whether the checkpoint was reached.

## JobRight (default source)

1. Use your browser MCP connection (`--autoConnect` to the main Chrome, or `--browser-url` in dedicated mode). Open `sources.jobright.feed_url` in a new tab with `new_page`; keep its page id and pass it on every call. Never touch other tabs.
2. Check the feed's sort control. The checkpoint only works on a feed sorted by Most Recent. If it shows anything else (JobRight's default is "Recommended"), do not change the user's sort setting (only setup sets Most Recent, once, with the user present; scans never change it); read the cards anyway, tell the user to save a Most Recent URL as `sources.jobright.feed_url`, and do not move the checkpoint this run.
3. Read cards top-down with `take_snapshot`. The list is virtualized: a snapshot holds only the cards near the viewport, and cards above drop out as you scroll. Record every card's key as you go and dedupe. For each card, build `job_key` from the card's job link (its ID or URL path). Fall back to `company|title|location` only when no link exists.
4. Stop when you reach the checkpoint card. If the checkpoint is not found, keep scrolling until cards are older than `max_posting_age_days` or a hard limit of 200 cards, then report "checkpoint not found".
5. Scroll slowly, one screen at a time, with a short pause. This is the user's signed-in session: no private API calls, no bulk requests, no parallel tabs on JobRight.
6. Record `first_seen` for each new key in `state/first-seen.json`. Freshness is judged from first-seen, because "Past 24 hours" style filters miss reposts.
7. **Move the checkpoint only after a complete scan of a Most Recent feed.** Set it to the top card of this scan. If the scan was cut short (error, sign-in wall, CAPTCHA), leave the old checkpoint so the next run rereads.
8. If JobRight shows a sign-in page or CAPTCHA, stop and tell the user. Do not type credentials or solve it.

## Indeed (fallback)

When JobRight is disabled, empty, or blocked, and an Indeed MCP connector is available, call `search_jobs` for each query in `sources.indeed.queries` with the user's locations, then `get_job_details` for each result. Map fields into the same output shape with `source: "indeed"`. If neither source works, report that and stop.

## Never

- Scrape LinkedIn, social media sites, or stories.
- Use undocumented APIs or tokens pulled from the page.
- Apply or click Apply buttons during a scan.
