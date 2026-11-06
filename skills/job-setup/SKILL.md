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

Script commands below say `python3`; on Windows use `py -3`.

1. **Existing files.** If `profile/preferences.yaml` exists, summarize it and ask what to change instead of starting over.
2. **Preferences.** Follow the keys and comments in `assets/preferences.example.yaml` in this skill's folder:
   - target roles and title words to exclude; seniority, and for internships the term (for example Summer 2027)
   - pay floor with units, and what to do when pay is missing (default: check the live posting)
   - locations, remote, relocation; sectors and interests (ranking only)
   - companies to skip, per-company caps and rolling windows; max posting age in days
   - tracker backend: csv (default), notion, or sheets, plus its URL
   - `auto_submit` (default false), `dry_run`, daily cap. Explain the README "Auto-submit" trade-off before they choose true.
   - `skip_if_genai_banned` (default true)
3. **Standing answers.** Follow `assets/standing-answers.example.yaml` in this skill's folder. EEO answers are optional; default each to "Decline to self-identify". Never guess; a blank means the agent asks later.
4. **Master resume.** Ask for its path (Markdown or LaTeX). If they only have a one-page resume, offer to start a master from `assets/master-resume.md` (LaTeX: `assets/master-resume.tex`) and ask for extra entries and alternate bullets. Record `master_resume`.
5. **Browser: attach to the user's main Chrome (default).** The agent uses the Chrome they already use, with their existing logins, so they do not sign in to JobRight or Gmail again. Portals that need a new sign-in may still park for them.
   - Needs Chrome 144 or later and Node.js (for `npx chrome-devtools-mcp`). Ask the user to open `chrome://inspect/#remote-debugging` and turn remote debugging on. That is a one-time switch.
   - The Claude Code plugin ships the `job-agent-browser` MCP server (chrome-devtools MCP with `--autoConnect --no-usage-statistics --workspace=${HOME}/.job-agent`). If the skills were installed with `npx skills add` (they live in `.agents/skills/`), add the browser MCP yourself: `npx -y chrome-devtools-mcp@1.10.1 --autoConnect --no-usage-statistics --workspace=<workspace>` (Codex: `codex mcp add job-agent-browser -- npx -y chrome-devtools-mcp@1.10.1 --autoConnect --no-usage-statistics --workspace=<workspace>`). Show the user the exact snippet for their agent. `--workspace` lets the browser server read the tailored resumes for upload.
   - Test it: call `list_pages`. Chrome shows "Allow remote debugging?". The user clicks Allow. Chrome asks again for every new connection, and each parallel applier opens its own connection, so a run raises one prompt per applier.
   - Claude Code parallel appliers: copy `assets/job-applier.md` from this skill's folder to `~/.claude/agents/job-applier.md` (in the copy, set `--workspace=` to the real workspace path when it is not `~/.job-agent`, so appliers can upload the tailored resumes; in dedicated mode, also swap `--autoConnect` for `--browser-url=http://127.0.0.1:<browser.port>`). That subagent starts its own chrome-devtools MCP connection, so appliers never share a selected tab. Tell the user you did it. If the file already exists and differs, show the difference and ask before replacing it.
   - Alternative for people who want the agent isolated from their main browser: `python3 scripts/launch_chrome.py` starts a separate profile with `--remote-debugging-port=9333 --user-data-dir=<workspace>/chrome-profile` (macOS, Linux, Windows). No prompts, but they sign in to JobRight, Gmail and job portals once in that window. Set `browser.mode: dedicated` and point the MCP at `--browser-url=http://127.0.0.1:9333` instead of `--autoConnect`.
6. **Walk-away runs: the auto-allow helper (recommended for unattended runs, off by default).** Offer it, explain it, and enable it only if the user says yes:
   - What it does: right before each agent's own connect, that agent arms a 15 second window. While any window is open, `scripts/auto_allow.py` presses Allow on Chrome's prompt, logs each click to `<workspace>/auto-allow.log`, and closes one window per click. With no open window it clicks nothing.
   - What it means: the prompt does not say who is asking, so any local program that connects to Chrome inside an open window is approved too.
   - macOS only. `enable` installs and loads a per-user LaunchAgent (`~/Library/LaunchAgents/io.github.azizu06.job-agent.auto-allow.plist`, RunAtLoad and KeepAlive) that does the clicking; `disable` unloads and removes it. Never run the clicker from the agent's own shell: System Events is unreachable from a sandboxed agent or hook (AppleScript error -10827). Grant Accessibility to the Python binary that `enable` prints, since that is what the LaunchAgent runs (System Settings > Privacy & Security > Accessibility, +, Cmd-Shift-G to paste the path). It finds Chrome's prompt by its English text, so Chrome must be in English. Windows: not supported yet. Linux: not available.
   - If yes: run `python3 scripts/auto_allow.py enable` and set `browser.auto_allow: true`.
7. **Portal accounts.** Ask each once and store under `portal_accounts`:
   - "Allow the agent to use Sign in with Google, Microsoft or LinkedIn on job portals, with an account already signed in to your Chrome?" Default yes. It tries Google, then Microsoft, then LinkedIn, picks only the user's own matching account, and only continues past consent screens that ask for basic profile and email.
   - May it click Sign In when Chrome itself autofills a saved login? (default yes) It never types or reads the password in this step.
   - Explain that anything else (no SSO, no saved login) parks the job for them: the tab stays open and they finish the sign-in by hand.
   - Offer the optional credential mode (default no). Say exactly: "Many agents (including Claude) will refuse these steps under their own safety rules; when they do, the job parks for you." It covers typing a password stored in the OS keychain (`allow_sign_in`), creating portal accounts with a generated password (`allow_create`; Workday creates one per company), resetting a forgotten password through the reset email (`allow_password_reset`), and entering emailed or (macOS) SMS codes (`sms_codes`). Only if they say yes, set `credential_mode: true` and ask about each of those four (each default no).
   - SMS codes (macOS only): explain that it reads `~/Library/Messages/chat.db` read-only for a code from the last 5 minutes, and needs Full Disk Access for the app running the agent (System Settings > Privacy & Security > Full Disk Access) plus Text Message Forwarding from their iPhone. On Windows say SMS codes come back to them (Phone Link has no stable API).
   If credential mode is on with sign-in, creation or reset, check `python3 -c "import keyring"`; if missing, ask before running `pip install keyring`. Explain that CAPTCHAs and bot checks are never solved: the agent parks that tab, filled and open, and tells them.
8. **Notifications for parked jobs.** Ask how to reach them when a tab needs them: macOS notification, an ntfy.sh topic (suggest a long random topic name, since anyone who knows it can read it), a Slack incoming webhook, or none. Write `<workspace>/state/notify.json` (shapes in `../job-run/scripts/notify.py`), set `notify.method` in preferences, and send a test with `notify.py --title "job-agent" --message "test"`.
9. **JobRight feed.** Ask the user to open JobRight, go to recommended jobs, sort by Most Recent, and paste that URL; save it as `sources.jobright.feed_url`.
10. **Optional connectors.** Check which MCPs exist and say what each enables: Gmail (receipts, account verification, status sync), Notion or Google Sheets (tracker), Indeed (fallback job source). Missing ones are fine.
11. **Write and confirm.** Write both YAML files, print a short summary (no secrets, no full contact details), and suggest `/job-agent:run dry-run` (other agents: "run the job-run skill in dry-run mode") for the first run.

## Never

- Store passwords, codes or API keys in any file. Passwords go only in the OS keychain through `portal-auth`.
- Enable `auto_allow` or credential mode without the user's explicit yes after the explanation above.
