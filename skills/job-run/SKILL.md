---
name: job-run
description: Run the full job-agent loop. Takes the run lock, scans for new jobs, gates them, then starts one subagent per queued job (up to the per-run limit) to tailor a resume and fill the application in its own browser tab, has a separate writer draft written answers, re-verifies every form itself, syncs receipts and statuses into the tracker, and ends with a READY, ALERT or NOTHING READY line and a banner only when something needs the user. Also explains how to schedule it every N hours. Use when the user says run job-agent, apply to new jobs, or runs /job-agent:run.
---

# job-run

Python: commands below say `python3`. Use `python_cmd` from `profile/preferences.yaml` instead when it is set (setup writes `py -3` on Windows).

## Preconditions

- Workspace (`$JOB_AGENT_HOME` or `~/.job-agent/`) has `profile/preferences.yaml` and `profile/standing-answers.yaml`. If not, run `job-setup`.
- Browser reachable. A failed connect is not proof the connection is gone: with several connections attaching at once, chrome-devtools-mcp can answer "Could not connect to Chrome" or "Could not find DevToolsActivePort" for one of them while the others attach (seen in QA). On either error, wait about 10 seconds and repeat the same call, up to 3 tries in all, before you treat the browser as unreachable. `main` mode: Chrome is open with remote debugging enabled, and your browser MCP uses `--autoConnect`. If `browser.auto_allow` is true, run `python3 ../job-setup/scripts/auto_allow.py arm --label orchestrator` right before your first browser call. `dedicated` mode: start it with `python3 ../job-setup/scripts/launch_chrome.py`, and drive it with the `job-agent-dedicated` MCP server setup added (`--browser-url`), not the plugin's `--autoConnect` server.
- Write a run log to `state/runs/<run-id>.md` as you go, and one summary line per run to `state/run-log.md` (`scripts/run_state.py log`).
- Each run starts blank and knows only the files it reads. Read `profile/preferences.yaml`, `profile/standing-answers.yaml`, `profile/corrections.md` (rules the user taught earlier runs), `voice/profile.md` and `state/queue.json` before doing anything else.

## Guard (first, every run)

1. **Lock.** `python3 scripts/run_state.py lock --dir <workspace>/state/run.lock --stale-hours <schedule.lock_stale_hours or 3>`. Exit 3 means another run is active: end with one line saying so. A lock older than the limit is from a hung run; the script replaces it and says so, and you note it in the log. Release it with `run_state.py unlock` as your last action, including when you stop early.
2. **Preflight.** `python3 scripts/run_state.py preflight --log <workspace>/state/run-log.md` (macOS checks for a locked screen). Then make your first browser call. A locked screen, or a browser that does not attach, means `run_state.py blocked --log <workspace>/state/run-log.md --cause "<short cause>"` and stop. Never ask for a password. If it prints `"notify": true` (the second blocked run in a row), send its `banner` with `notify.py`; otherwise send nothing.

## Loop

1. **Scan** with `job-scan`.
2. **Gate** with `job-gate`. Show the queue and the cut report. In an interactive session with `auto_submit: false`, continue without waiting. With `auto_submit: true`, ask the user to confirm the queue first unless they started the run unattended on purpose.
   Then take this run's batch: `python3 ../job-gate/scripts/apply_queue.py --queue <workspace>/state/queue.json next --limit <browser.max_forms_per_run or 10>`. Only `QUEUED` entries come back: `FILLED` ones wait for the user, `WAIT-REFERRAL` ones wait for the referral, `NEEDS YOU` ones wait for the user, `DROPPED` ones never return. Entries past the limit stay queued for the next run. Before opening a posting, list pages and reuse a tab already open for that req.
3. **Fan out.** Every applier needs its OWN browser connection, so agents never share a selected tab.
   - Claude Code: if the `job-applier` subagent exists (`~/.claude/agents/job-applier.md`, installed by setup), start one per queue item in the background. It brings its own chrome-devtools MCP connection. If it does not exist, process the queue one job at a time yourself or with a single subagent; never run parallel fills over one shared MCP connection.
   - Other agents: give each parallel worker its own chrome-devtools MCP process (`--autoConnect`, or `--browser-url` in dedicated mode). If the runtime cannot do that, run jobs one after another.
   - Give each applier: the queue item, its `jd_path`, the workspace path, the path to `../job-setup/scripts/`, a unique output folder, and these rules: run `tailor-resume` then `apply-fill`; upload only a resume PDF whose gate passed (`resume_gate.py --verify <pdf>` prints `VERIFY: PASS`), and park the job with `Needs you: resume gate failed` otherwise; send every free-text answer through `your-voice` before pasting it; use `portal-auth` for sign-in walls within the user's settings; open its own tab with `new_page` and use only that page; never touch another tab; use only its own browser connection, retry a failed connect ("Could not connect to Chrome", "Could not find DevToolsActivePort") twice about 10 seconds apart, and if it still has none, return parked instead of using the orchestrator's; if `browser.auto_allow` is true, run `auto_allow.py arm --label <job_key>` right before its first browser call.
   - Each new connection raises a Chrome "Allow remote debugging?" prompt. Tell the user to expect one per applier, unless auto-allow is enabled.
   Keep concurrent fills at or below `browser.max_parallel_tabs` (default 3). Never run a shared tab-switching helper for several agents; each works only through its own page id.
   **Written answers with `written_answers: writer`.** Appliers leave every written box empty and report each question's exact text, limit and required flag. For each form, start one writer (the `your-voice` skill in its own subagent, or yourself when subagents are not available) with all of that form's questions together, the company, `jd_path`, the tailored resume and the master. It follows `../your-voice/references/written-answer-standard.md` and the user's approved answers in `voice/approved/`, and runs `writecheck.py crossform` across the form's answers. Paste the returned answers into the applier's tab with real input, in your own read-back pass (step 4).
   Watch long runs: an applier that has not reported after a reasonable time is checked by its tab, not waited on forever. A fix you find on one form (a wrong dropdown pattern, a field that autofill breaks) is applied to every other open form of the same kind in this run.
4. **Collect reports.** A `parked` report is a normal result: record it and keep going. If an applier crashes, returns nothing, or says it declined a step, treat that job as parked (`Needs you: <reason>`, or `Needs you: applier failed` when there is no reason), leave its tab alone, and continue with the rest of the queue. Never retry a parked job in the same run. Do not trust a subagent's "ready". Run `python3 ../tailor-resume/scripts/resume_gate.py --verify <pdf>` on each uploaded PDF yourself; a FAIL means the form is not ready. For each tab, find it by its URL with `list_pages` (page ids can be renumbered during a run, see `apply-fill` Tab discipline), take your own snapshot, confirm the snapshot URL is that job's, and re-read every live field: required errors, empty required fields, resume attached, consent boxes. Fix or flag.
   **Read-back, yourself, on the live tab.** Never relay a subagent's "verified": you answer for the form. Check, for every form:
   - every field, required and optional, by its label with its current value, against standing answers: look for blanks (demographics, pronouns, address country, optional cover letters and text boxes);
   - every dropdown shows the intended option (react-select: hit-test, then read back);
   - the resume: the attached file name and size match the tailored PDF on disk (`../apply-fill/scripts/upload_guard.py verify`), its gate passes (`resume_gate.py --verify`, or `upload_guard.py check` for a user's own gate), and its project order fits this role;
   - written answers: read each on the page, in full, as a skeptical hiring reviewer, against `../your-voice/references/written-answer-standard.md`; rewrite (through the writer) any that fails; no story repeats across the form;
   - the gates again with the full job description in hand: if the posting now fails, close only the tab you opened, set the queue entry to `DROPPED: <reason>`, and do not call it ready;
   - no error elements, the final control present and unclicked, no thank-you or confirmation URL.
   A form is ready only when nothing is left to fix. Set the queue entry to `FILLED` with the time, tab URL, posting date, pay and pay route, resume path, coverage, written-answer files and any GenAI flag. Anything only the user can fix is `NEEDS YOU: <what it asks for>`, never ready.
5. **Track.** Use the `tracker` skill, and `status-sync` for receipts and status mail (it reads `in:anywhere` at least two days back). For each receipt that matches a queue entry by req ID or exact title: record the submit (`record-submit`), then `apply_queue.py remove --receipt <message id>`. A receipt for a role this run did not fill is still recorded (`record-submit --not-filled`) and listed in the log. Run `tracker_csv.py reconcile` with the receipts you found when rows and email disagree. `Ready` and parked jobs: `add` or `update` the row, unless `tracker.rows_for_unsubmitted` is false (then they live only in the queue, and only sent applications get rows). Every job whose final control was pressed: one `tracker_csv.py record-submit` call with the absolute path of the PDF the applier uploaded (from its report; check the file exists), the read-back path, and the receipt (`--inbox <email.mock_inbox>` when `email.receipts: mock`; with Gmail, search per `tracker` and pass `--receipt-id`). Then run `tracker_csv.py audit`; it must exit 0 before you summarize. Fix each problem it lists; a receipt that never came is fine only as "no receipt yet".
6. **Corrections.** When the user corrects anything (a wrong answer, a gate call, a form habit), fix the open tab, apply the same fix to every other open form it touches, and append the rule to `profile/corrections.md` as `- YYYY-MM-DD: <rule> (why: <one line>)`, so every later run reads it. Writing corrections also go to `voice/profile.md` through the `your-voice` corrections loop.
7. **Summarize** for the user: counts per stage, each job with status and the final control label, missing-term questions from tailoring (one batch), drafted written answers with their inferred sentences to check (if the user edits one, run the `your-voice` corrections loop so the next answer learns from it), and essays left for them.
8. **Parked tabs.** End with one list of every parked job so the user can clear them in one sitting: company, role, reason (`Needs you: captcha` and similar), and the tab URL. These tabs stay open and filled; tell the user not to close them. After the user clears one, re-read that tab's live form (step 4) before treating it as ready. Parked-job notifications follow `notify.parked`: `each` (default: the parking skill sent one per job; also send one summary notification now with `scripts/notify.py` if anything was parked), `summary` (only that one summary), or `none` (the list in the run report is enough; parked forms are told at the user's next message, with no ping).
9. **Notify and finish.** Send a notification only for:
   - forms that became ready this run (`auto_submit: false`): one banner naming only those forms;
   - a new assessment, interview or offer from `status-sync`'s `alerts` (checked by req ID, still live, not already handled): one banner naming the company and the deadline if stated;
   - two blocked runs in a row (the guard above).
   Rejections, receipts, near misses, terms to confirm and parked forms send nothing extra; they go in the run report and the log. Build the lines with `python3 scripts/run_state.py banner --ready "<Company Role>"... --genai "<the same name for a GenAI-flagged form>" --alert "<Assessment from Company, due Nov 12>"`. Banners name forms only: no pay, counts, coverage or terms, no quotes or apostrophes, under 150 characters. Send each banner text with `notify.py`. Your final message starts with exactly those lines: `READY: <banner>` or `NOTHING READY`, then `ALERT: <banner>` per alert, then one counts line (cards scanned, passes, forms ready, receipts). Append the run summary to `state/run-log.md` (time, cards and window, passes, cuts by gate with near misses, forms filled and what the read-back fixed, `NEEDS YOU` items, terms to confirm, receipts logged, status changes with deadlines), then release the lock.

## Running every N hours

The interval is `schedule.every_hours` in preferences (default 3 when the schedule is enabled; 0 or missing means no schedule, so say so and offer to set one). Read it and use it as `N` below; the examples show N=3.

Claude Code:
- In a session: `/loop <N>h /job-agent:run` (for example `/loop 3h /job-agent:run`) repeats while the session is open.
- Scheduled tasks or cloud routines (`/schedule`) can start a run on a cron every `schedule.every_hours` hours. A browser-driving run needs this machine and its Chrome, so use a local scheduled task, not a cloud one. Add jitter (`schedule.jitter_minutes`, default 15) so runs do not all land on the hour, for example a cron at minute 15 of every third hour between 08:00 and 23:00: `15 8-23/3 * * *`.

Other agents, or plain cron, using a headless CLI:

```
# crontab -e: every schedule.every_hours (here 3) hours at minute 5
5 */3 * * * $HOME/.job-agent/run.sh >> $HOME/.job-agent/state/cron.log 2>&1
```

For jitter, start `run.sh` with a random sleep of up to `schedule.jitter_minutes`, for example `sleep $((RANDOM % 900))` for 15 minutes. The run lock keeps two runs from overlapping if one runs long.

with `run.sh` along the lines of:

```
#!/usr/bin/env bash
claude -p "/job-agent:run"
# or: codex exec "Run the job-run skill from job-agent"
```

A headless run cannot answer permission prompts. Pre-approve what the run uses, or it stops at the first prompt. Example for Claude Code (`~/.claude/settings.json`; adjust the Gmail, Notion or Sheets server names to the ones `/mcp` shows):

```json
{
  "permissions": {
    "allow": [
      "mcp__plugin_job-agent_job-agent-browser",
      "mcp__job-agent-browser-own",
      "mcp__job-agent-dedicated",
      "mcp__gmail",
      "Bash(python3 *keyword_coverage.py*)",
      "Bash(python3 *resume_check.py*)",
      "Bash(python3 *layout_check.py*)",
      "Bash(python3 *resume_gate.py*)",
      "Bash(python3 *md_to_tex.py*)",
      "Bash(tectonic *)",
      "Bash(python3 *tracker_csv.py*)",
      "Bash(python3 *sync_status.py*)",
      "Bash(python3 *auto_allow.py arm*)",
      "Bash(python3 *notify.py*)",
      "Bash(python3 *gate.py*)",
      "Bash(python3 *apply_queue.py*)",
      "Bash(python3 *jobright_meta.py*)",
      "Bash(python3 *run_state.py*)",
      "Bash(python3 *upload_guard.py*)",
      "Bash(python3 *writecheck.py*)",
      "Bash(python3 *portal_creds.py*)",
      "Bash(python3 *sms_code.py*)",
      "Read(~/.job-agent/**)",
      "Edit(~/.job-agent/**)",
      "Write(~/.job-agent/**)"
    ]
  }
}
```

On Windows, write `py -3` instead of `python3` in each `Bash(...)` line, or add both forms. Leave out the `portal_creds.py` and `sms_code.py` lines unless credential mode is on. Allow only what you use.

Unattended runs: the computer must stay on and awake. On a Mac, keep it plugged in and run `caffeinate -dimsu &` (or turn on "Prevent automatic sleeping" in System Settings > Battery > Options); a sleeping Mac skips runs with no error. In `main` mode every connection raises a Chrome prompt, so walk-away runs need the opt-in auto-allow helper (macOS only; Windows and Linux are experimental and have no helper). Without it, a run started while nobody is at the keyboard waits at the prompt and then fails that job. The `dedicated` mode never prompts. Keep `auto_submit: false` for unattended runs unless the user has read the README trade-off and set caps. A headless run that hits a CAPTCHA or another human-only step parks that job (tab left open, tracker row `Needs you: ...`, notification sent) and moves on; nothing waits for input.
