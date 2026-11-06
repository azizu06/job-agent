---
name: job-setup
description: One-command setup for job-agent. Interviews the user, writes profile/preferences.yaml and profile/standing-answers.yaml in the job-agent workspace, records the master resume, attaches the agent to the user's own signed-in Chrome, checks the MCPs, and offers the optional auto-allow helper and portal-account settings. Use when the user says set up job-agent or "set this up" about this repo, runs /job-agent:setup, or when another job-agent skill finds no profile.
---

# job-setup

One pass, start to finish. Ask one topic at a time in plain language, offer the example value as the default, and write files only after the user confirms. Do every step you can yourself; ask the user only for choices and for clicks only they can make.

## Workspace

All user data lives in the workspace: `$JOB_AGENT_HOME` if set, else `~/.job-agent/` (on Windows `%USERPROFILE%\.job-agent\`). Create it if missing:

```
<workspace>/
  profile/preferences.yaml       # this wizard writes it
  profile/standing-answers.yaml  # this wizard writes it
  resumes/master.md              # or the user's own path
  resumes/tailored/<run-id>/     # one folder per tailored copy
  state/                         # checkpoint, scans, queue, run logs, portals.json
  tracker.csv                    # default tracker
  auto-allow/, auto-allow.log    # only if the helper is enabled
  chrome-profile/                # only in dedicated browser mode
```

Never write user data into the plugin or skill folder. If `JOB_AGENT_HOME` points at a clone of this repo, its `.gitignore` already excludes these paths.

## Steps

1. **Existing files.** If `profile/preferences.yaml` exists, summarize it and ask what to change instead of starting over.
2. **Preferences.** Follow the keys and comments in `profile/preferences.example.yaml` (repo root; reproduce the same keys if the file is not at hand):
   - target roles and title words to exclude; seniority, and for internships the term (for example Summer 2027)
   - pay floor with units, and what to do when pay is missing (default: check the live posting)
   - locations, remote, relocation; sectors and interests (ranking only)
   - companies to skip, per-company caps and rolling windows; max posting age in days
   - tracker backend: csv (default), notion, or sheets, plus its URL
   - `auto_submit` (default false), `dry_run`, daily cap. Explain the README "Auto-submit" trade-off before they choose true.
   - `skip_if_genai_banned` (default true)
3. **Standing answers.** Follow `profile/standing-answers.example.yaml`. EEO answers are optional; default each to "Decline to self-identify". Never guess; a blank means the agent asks later.
4. **Master resume.** Ask for its path (Markdown or LaTeX). If they only have a one-page resume, offer to start a master from `templates/master-resume.md` and ask for extra entries and alternate bullets. Record `master_resume`.
5. **Browser: attach to the user's main Chrome (default).** The agent uses the Chrome they already use, with their existing logins, so they never sign in again.
   - Needs Chrome 144 or later and Node.js (for `npx chrome-devtools-mcp`). Ask the user to open `chrome://inspect/#remote-debugging` and turn remote debugging on. That is a one-time switch.
   - The Claude Code plugin ships the `job-agent-browser` MCP server (chrome-devtools MCP with `--autoConnect`). For other agents, add chrome-devtools MCP with `--autoConnect` to their MCP config, and show the user the exact snippet for their agent.
   - Test it: call `list_pages`. Chrome shows "Allow remote debugging?". The user clicks Allow. Chrome asks again for every new connection, and each parallel applier opens its own connection, so a run raises one prompt per applier.
   - Claude Code parallel appliers: copy `templates/claude-agents/job-applier.md` to `~/.claude/agents/job-applier.md` (in dedicated mode, swap `--autoConnect` for `--browser-url=http://127.0.0.1:9222` in the copy). That subagent starts its own chrome-devtools MCP connection, so appliers never share a selected tab. Tell the user you did it. If the file already exists and differs, show the difference and ask before replacing it.
   - Alternative for people who want the agent isolated from their main browser: `python3 scripts/launch_chrome.py` starts a separate profile with `--remote-debugging-port=9222 --user-data-dir=<workspace>/chrome-profile` (macOS, Linux, Windows). No prompts, but they sign in to JobRight, Gmail and job portals once in that window. Set `browser.mode: dedicated` and point the MCP at `--browser-url=http://127.0.0.1:9222` instead of `--autoConnect`.
6. **Walk-away runs: the auto-allow helper (recommended for unattended runs, off by default).** Offer it, explain it, and enable it only if the user says yes:
   - What it does: right before each agent's own connect, that agent arms a 15 second window. While any window is open, `scripts/auto_allow.py` presses Allow on Chrome's prompt, logs each click to `<workspace>/auto-allow.log`, and closes one window per click. With no open window it is not running.
   - What it means: the prompt does not say who is asking, so any local program that connects to Chrome inside an open window is approved too.
   - macOS: grant Accessibility to the app that runs the agent (System Settings > Privacy & Security > Accessibility). Windows: beta and untested, needs `pip install pywinauto`. Linux: not available.
   - If yes: run `python3 scripts/auto_allow.py enable` and set `browser.auto_allow: true`.
7. **Portal accounts.** Ask each once and store under `portal_accounts`:
   - "Allow the agent to use Sign in with Google (or Microsoft, LinkedIn) on job portals, with the account already signed in to your Chrome?" Default yes if the user agrees. It only picks the user's own matching account and only continues past consent screens that ask for basic profile and email.
   - May it sign in with credentials saved in the OS keychain or the browser? (default yes)
   - May it create portal accounts for the user (Workday creates one per company) with their email and a generated password stored in the OS keychain? (default no)
   - May it reset a forgotten portal password through the reset email? (default no)
   - macOS only: may it read SMS verification codes from Messages? Explain that it reads `~/Library/Messages/chat.db` read-only for a code from the last 5 minutes, and needs Full Disk Access for the app running the agent (System Settings > Privacy & Security > Full Disk Access) plus Text Message Forwarding from their iPhone. Default no. On Windows say SMS codes come back to them (Phone Link has no stable API).
   If account creation or reset is yes, check `python3 -c "import keyring"`; if missing, ask before running `pip install keyring`. Explain that CAPTCHAs and bot checks are never solved: the agent parks that tab, filled and open, and tells them.
8. **Notifications for parked jobs.** Ask how to reach them when a tab needs them: macOS notification, an ntfy.sh topic (suggest a long random topic name, since anyone who knows it can read it), a Slack incoming webhook, or none. Write `<workspace>/state/notify.json` (shapes in `../job-run/scripts/notify.py`), set `notify.method` in preferences, and send a test with `notify.py --title "job-agent" --message "test"`.
9. **JobRight feed.** Ask the user to open JobRight, go to recommended jobs, sort by Most Recent, and paste that URL; save it as `sources.jobright.feed_url`.
10. **Optional connectors.** Check which MCPs exist and say what each enables: Gmail (receipts, account verification, status sync), Notion or Google Sheets (tracker), Indeed (fallback job source). Missing ones are fine.
11. **Write and confirm.** Write both YAML files, print a short summary (no secrets, no full contact details), and suggest `/job-agent:run dry-run` (other agents: "run the job-run skill in dry-run mode") for the first run.

## Never

- Store passwords, codes or API keys in any file. Passwords go only in the OS keychain through `portal-auth`.
- Enable `auto_allow` or portal account creation without the user's explicit yes after the explanation above.
