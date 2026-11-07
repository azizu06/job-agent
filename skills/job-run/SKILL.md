---
name: job-run
description: Run the full job-agent loop. Scans for new jobs, gates them, then starts one subagent per queued job to tailor a resume and fill the application in its own browser tab, collects their reports, re-verifies each form, and updates the tracker. Also explains how to schedule it every N hours. Use when the user says run job-agent, apply to new jobs, or runs /job-agent:run.
---

# job-run

Python: commands below say `python3`. Use `python_cmd` from `profile/preferences.yaml` instead when it is set (setup writes `py -3` on Windows).

## Preconditions

- Workspace (`$JOB_AGENT_HOME` or `~/.job-agent/`) has `profile/preferences.yaml` and `profile/standing-answers.yaml`. If not, run `job-setup`.
- Browser reachable. `main` mode: Chrome is open with remote debugging enabled, and your browser MCP uses `--autoConnect`. If `browser.auto_allow` is true, run `python3 ../job-setup/scripts/auto_allow.py arm --label orchestrator` right before your first browser call. `dedicated` mode: start it with `python3 ../job-setup/scripts/launch_chrome.py`, and drive it with the `job-agent-dedicated` MCP server setup added (`--browser-url`), not the plugin's `--autoConnect` server.
- Write a run log to `state/runs/<run-id>.md` as you go.

## Loop

1. **Scan** with `job-scan`.
2. **Gate** with `job-gate`. Show the queue and the cut report. In an interactive session with `auto_submit: false`, continue without waiting. With `auto_submit: true`, ask the user to confirm the queue first unless they started the run unattended on purpose.
3. **Fan out.** Every applier needs its OWN browser connection, so agents never share a selected tab.
   - Claude Code: if the `job-applier` subagent exists (`~/.claude/agents/job-applier.md`, installed by setup), start one per queue item in the background. It brings its own chrome-devtools MCP connection. If it does not exist, process the queue one job at a time yourself or with a single subagent; never run parallel fills over one shared MCP connection.
   - Other agents: give each parallel worker its own chrome-devtools MCP process (`--autoConnect`, or `--browser-url` in dedicated mode). If the runtime cannot do that, run jobs one after another.
   - Give each applier: the queue item, its `jd_path`, the workspace path, the path to `../job-setup/scripts/`, a unique output folder, and these rules: run `tailor-resume` then `apply-fill`; upload only a resume PDF whose gate passed (`resume_gate.py --verify <pdf>` prints `VERIFY: PASS`), and park the job with `Needs you: resume gate failed` otherwise; send every free-text answer through `your-voice` before pasting it; use `portal-auth` for sign-in walls within the user's settings; open its own tab with `new_page` and use only that page; never touch another tab; use only its own browser connection, and if it has none, return parked instead of using the orchestrator's; if `browser.auto_allow` is true, run `auto_allow.py arm --label <job_key>` right before its first browser call.
   - Each new connection raises a Chrome "Allow remote debugging?" prompt. Tell the user to expect one per applier, unless auto-allow is enabled.
   Keep concurrent fills at or below `browser.max_parallel_tabs` (default 3). Never run a shared tab-switching helper for several agents; each works only through its own page id.
4. **Collect reports.** A `parked` report is a normal result: record it and keep going. If an applier crashes, returns nothing, or says it declined a step, treat that job as parked (`Needs you: <reason>`, or `Needs you: applier failed` when there is no reason), leave its tab alone, and continue with the rest of the queue. Never retry a parked job in the same run. Do not trust a subagent's "ready". Run `python3 ../tailor-resume/scripts/resume_gate.py --verify <pdf>` on each uploaded PDF yourself; a FAIL means the form is not ready. For each tab, find it by its URL with `list_pages` (page ids can be renumbered during a run, see `apply-fill` Tab discipline), take your own snapshot, confirm the snapshot URL is that job's, and re-read every live field: required errors, empty required fields, resume attached, consent boxes. Fix or flag.
5. **Track.** Use the `tracker` skill. `Ready` and parked jobs: `add` or `update` the row. Every job whose final control was pressed: one `tracker_csv.py record-submit` call with the absolute path of the PDF the applier uploaded (from its report; check the file exists), the read-back path, and the receipt (`--inbox <email.mock_inbox>` when `email.receipts: mock`; with Gmail, search per `tracker` and pass `--receipt-id`). Then run `tracker_csv.py audit`; it must exit 0 before you summarize. Fix each problem it lists; a receipt that never came is fine only as "no receipt yet".
6. **Summarize** for the user: counts per stage, each job with status and the final control label, missing-term questions from tailoring (one batch), drafted written answers with their inferred sentences to check (if the user edits one, run the `your-voice` corrections loop so the next answer learns from it), and essays left for them.
7. **Parked tabs.** End with one list of every parked job so the user can clear them in one sitting: company, role, reason (`Needs you: captcha` and similar), and the tab URL. These tabs stay open and filled; tell the user not to close them. After the user clears one, re-read that tab's live form (step 4) before treating it as ready. If anything was parked, send one summary notification with `scripts/notify.py`.

## Running every N hours

The interval is `schedule.every_hours` in preferences (default 3 when the schedule is enabled; 0 or missing means no schedule, so say so and offer to set one). Read it and use it as `N` below; the examples show N=3.

Claude Code:
- In a session: `/loop <N>h /job-agent:run` (for example `/loop 3h /job-agent:run`) repeats while the session is open.
- Scheduled tasks or cloud routines (`/schedule`) can start a run on a cron every `schedule.every_hours` hours. A browser-driving run needs this machine and its Chrome, so use a local scheduled task, not a cloud one.

Other agents, or plain cron, using a headless CLI:

```
# crontab -e: every schedule.every_hours (here 3) hours at minute 5
5 */3 * * * $HOME/.job-agent/run.sh >> $HOME/.job-agent/state/cron.log 2>&1
```

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
