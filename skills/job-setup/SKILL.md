---
name: job-setup
description: Guided, resumable setup for job-agent for first-time users. Explains each step, interviews the user, writes profile/preferences.yaml and profile/standing-answers.yaml in the job-agent workspace, records the master resume, attaches the agent to the user's own signed-in Chrome, checks the MCPs, and offers the optional auto-allow helper and portal-account settings. Use when the user says set up job-agent or "set this up" about this repo, runs /job-agent:setup, or when another job-agent skill finds no profile.
---

# job-setup

Python: commands below say `python3`. Use `python_cmd` from `profile/preferences.yaml` instead when it is set (setup writes `py -3` on Windows).

Guided setup for someone who has never seen this project. They must finish without asking the creator anything. Plain words, short sentences. For every step: say in one sentence WHY it matters, then give exact clicks, then check it worked yourself. Ask one thing at a time. Offer the safe default. Write files only after the user confirms.

Do everything you can yourself. Ask the user only for choices and for clicks only they can make.

## Opening (always show first)

Say this, adjusted to the steps still open:

> Setup takes about 10 minutes. We will: (1) connect me to your Chrome, (2) connect Gmail and pick a tracker, (3) link JobRight, (4) add your resume, (5) set your rules and teach me how you write, (6) run a practice application that stops before Submit.
>
> Have ready: Google Chrome 144 or later, Node.js installed, your resume (PDF, Word, or your LinkedIn profile text; no resume is fine too), optionally 2 to 5 things you wrote yourself (essays, cover letters, long emails), a Gmail account, and a free JobRight account (we make one if needed). Optional: a Notion or Google account for the tracker.

Ask: "Ready?" Then go.

## Assumed setup: Claude Code on a Mac

These steps are written for **Claude Code on macOS**, the fully tested path. Check once at the start (`uname -s` prints `Darwin` on a Mac). On a Mac with Claude Code, follow the steps as written and never read out the steps for other systems.

Not on a Mac, or not Claude Code? Say once: "You are not on Claude Code on a Mac, so a few steps work differently. Support for your setup is community-tested." Then use the section **Not on Mac or not using Claude Code?** at the end of this file wherever a step marks `(other setups: see end)`.

## Workspace and progress

All user data lives in the workspace: `$JOB_AGENT_HOME` if set, else `~/.job-agent/` (on Windows `%USERPROFILE%\.job-agent\`). Create it if missing:

```
<workspace>/
  profile/preferences.yaml       # this wizard writes it
  profile/standing-answers.yaml  # this wizard writes it
  resumes/master.md              # or the user's own path
  resumes/tailored/<run-id>/     # one folder per tailored copy
  state/                         # checkpoint, scans, queue, run logs, portals.json
  voice/samples/, voice/profile.md, voice/facts.md, voice/approved/   # your-voice skill
  tracker.csv                    # default tracker
  auto-allow/, auto-allow.log    # only if the helper is enabled
  chrome-profile/                # only in dedicated browser mode
```

Never write user data into the plugin or skill folder. If `JOB_AGENT_HOME` points at a clone of this repo, its `.gitignore` already excludes these paths.

Progress file: `<workspace>/state/setup-progress.json`, like `{"done": ["chrome", "connectors"]}`. After each step passes its check, add its id. On a re-run, read it, print a checklist with done steps ticked, say "Skipping what is already done", and resume at the first open step. If the user asks to redo a step, remove its id. Step ids: `chrome`, `autoallow`, `connectors`, `tracker`, `jobright`, `resume`, `preferences`, `answers`, `voice`, `permissions`, `notify`, `dryrun`.

## Steps

1. **Existing files.** If `profile/preferences.yaml` exists, summarize it and ask what to change instead of starting over.

2. **Chrome connection** (id `chrome`).
   - Why: I work inside the Chrome you already use, so your logins carry over and you never re-enter passwords.
   - Click path: open Chrome, paste `chrome://inspect/#remote-debugging` into the address bar, turn on the remote debugging toggle. One time only. Needs Chrome 144 or later and Node.js (for `npx chrome-devtools-mcp`).
   - The Claude Code plugin ships the `job-agent-browser` MCP server (chrome-devtools MCP with `--autoConnect --no-usage-statistics --workspace=${HOME}/.job-agent`). `--workspace` lets the browser server read tailored resumes for upload. (other setups: see end)
   - Test it: call `list_pages`. Chrome shows "Allow remote debugging?". Tell them: click **Allow**. Chrome asks again for every new connection, and each parallel applier connects separately, so a run can raise one prompt per applier.
   - Parallel appliers: copy `assets/job-applier.md` from this skill's folder to `~/.claude/agents/job-applier.md`. In the copy, always replace `${HOME}/.job-agent` in `--workspace=` with the absolute workspace path (for example `/Users/sam/.job-agent`), because variables in a user agent's frontmatter may not be expanded. In dedicated mode swap `--autoConnect` for `--browser-url=http://127.0.0.1:<browser.port>`. Tell the user you did it. If the file exists and differs, show the difference and ask before replacing it.
   - Alternative, isolated from the main browser: `python3 scripts/launch_chrome.py` starts a separate profile with `--remote-debugging-port=9333 --user-data-dir=<workspace>/chrome-profile`. No prompts, but they sign in to JobRight, Gmail and portals once in that window. Set `browser.mode: dedicated` and use `--browser-url=http://127.0.0.1:9333` instead of `--autoConnect`.

3. **Hands-free Allow clicks** (id `autoallow`, macOS only, default no).
   - Why: without it you click Allow each time the agent connects.
   - Ask yes/no: "Let a small helper click Allow for the agent? Consequence: any local program that connects to Chrome in the same few seconds is approved too. Default: no."
   - If yes: run `python3 scripts/auto_allow.py enable`, set `browser.auto_allow: true`. Accessibility click path: System Settings > Privacy & Security > Accessibility > the **+** button > press Cmd-Shift-G > paste the Python path that `enable` printed > Open > switch it on. Chrome must be in English.
   - How it works: right before each agent's own connect, that agent arms a 15 second window. While any window is open, `scripts/auto_allow.py` presses Allow, logs each click to `<workspace>/auto-allow.log`, and closes one window per click. With no open window it clicks nothing. `enable` installs a per-user LaunchAgent (`~/Library/LaunchAgents/io.github.azizu06.job-agent.auto-allow.plist`); `disable` removes it. Never run the clicker from the agent's own shell (System Events is unreachable from a sandbox, AppleScript error -10827). (other setups: see end)

4. **Gmail and connectors** (id `connectors`).
   - Why: Gmail lets me find confirmation emails and verification codes.
   - Check which MCP connectors exist. If Gmail is missing: "Open claude.ai, go to Settings > Connectors, find **Gmail**, click Connect, choose your Google account, click Allow. Then run `/mcp` here and check Gmail shows as connected." Re-check after they say done. (other setups: see end)
   - Notion and Sheets connectors are handled in the tracker step. Indeed is an optional fallback job source. Missing optional ones are fine.

5. **Tracker** (id `tracker`).
   - Why: a list of everything applied to, so you see status at a glance.
   - Show this menu, default 1:
     1. **CSV**: zero setup, a local file. Not shareable.
     2. **Google Sheets**: easy to share and filter. Needs the Google Sheets connector.
     3. **Notion**: the nicest board view. Needs the Notion connector.
   - Columns for all: `company, role, req_id, link, date, resume_used, status, receipt_id, notes` (statuses are in the tracker skill).
   - CSV: create `<workspace>/tracker.csv` with that header row. Set `tracker.backend: csv`.
   - Sheets: if the connector is missing, click path: Connectors > Google Sheets > Connect > Allow. Create a sheet named "Job applications" with that header row. Save its URL to `tracker.sheets_url`, set `backend: sheets`.
   - Notion: if the connector is missing, click path: Connectors > Notion > Connect > choose a workspace > pick a page to share. Create a database "Job applications": `company` as title, `status` as select (tracker skill statuses), `date` as date, `link` as URL, the other columns as text. Save its URL to `tracker.notion_database_url`, set `backend: notion`. Offer a Board view grouped by `status`.
   - Check: confirm the file, sheet or database exists and has the columns.

6. **JobRight feed** (id `jobright`). Capture the URL yourself; never ask the user to paste it.
   - Why: JobRight is the main source of new postings.
   - With your browser MCP, open `https://jobright.ai/jobs/recommend` in a new tab with `new_page` (or reuse a JobRight tab the user has open, read-only). Take a snapshot.
   - Signed in: job cards or a profile avatar show, and the URL stays under `/jobs`. Signed out: redirect to a landing or sign-in page, or "Sign in", "Log in", "Sign up" with no job cards.
   - If signed out, give these steps and wait until they say done:
     1. Go to https://jobright.ai and click Join Now. Make a free account (Sign in with Google works).
     2. Answer the job preference questions: roles, locations, experience level, job type.
     3. Open **Jobs** in the menu.
     4. Sort the list by **Most Recent**.
     Labels may differ slightly; pick the closest one. Then snapshot again. Never create the account or type credentials for them.
   - Once signed in, select Most Recent yourself if another sort shows, read the tab URL, save it as `sources.jobright.feed_url`, and confirm the snapshot lists job cards. Tell the user the URL.
   - Dedicated-profile mode: do this in that profile's window.

7. **Master resume** (id `resume`).
   - Why: every application is a trimmed copy of one master file. I never invent facts, so the master must hold the full truth.
   - Ask what they have: (a) a PDF or Word file, (b) pasted LinkedIn profile text (About, Experience, Education, Skills, Projects), (c) a Markdown or LaTeX master, or (d) nothing.
   - (a) and (b): read the file or text and convert it to the `assets/master-resume.md` layout (`##` sections, `###` entries, `- ` bullets). Show it and ask what is missing.
   - (c): record the path.
   - (d) **No resume at all**, or thin input. This is common for students, so never stop here. Say: "No problem. I will build one with you from questions, about 10 minutes. I only write down what you tell me." Then ask one block at a time and fill `assets/master-resume.md`:
     1. Header: name, email, phone (optional), city, links (GitHub, portfolio, LinkedIn URL).
     2. Education: school, degree, major, expected graduation, GPA only if they want it, relevant courses.
     3. Each job, internship or part-time role, including non-tech work (title, place, dates, what you did, tools, numbers you can defend).
     4. Each project, class project or hackathon (one line "A <thing> that <does what> for <whom>", stack, result, link).
     5. Clubs, volunteering, awards.
     6. Skills: only tools they have used, and where.
     Turn each answer into bullets in their words. Mark every bullet you wrote with a trailing `<!-- confirm -->`, then show the whole draft and ask them to confirm or fix each marked bullet. Remove the mark only when they confirm it. After each entry ask "any other way to say this?" and store answers as alternates in `<!-- alt -->` blocks. Never add a metric, tool, employer, date or title they did not state; if a section is empty, leave it out rather than fill it. `tailor-resume` refuses to use a bullet that still carries `<!-- confirm -->`.
   - Save to `<workspace>/resumes/master.md`, set `master_resume` and `resume_format`. LaTeX users start from `assets/master-resume.tex`.

8. **Preferences** (id `preferences`). Follow `assets/preferences.example.yaml`:
   - target roles and title words to exclude; seniority, and the term for internships (for example Summer 2027)
   - pay floor with units, and what to do when pay is missing (default: check the live posting)
   - locations, remote, relocation; sectors and interests (ranking only)
   - companies to skip, per-company caps; max posting age in days
   - `skip_if_genai_banned` (default true)
   - `python_cmd: python3` (write it yourself; Windows: `py -3`)

9. **Standing answers** (id `answers`). Why: forms ask the same questions every time. Follow `assets/standing-answers.example.yaml`. EEO answers are optional; default each to "Decline to self-identify". Never guess; blank means the agent asks later.

10. **Your writing voice** (id `voice`, optional). Why: written answers ("why this company", "tell us about a project") should not read like a chatbot. Every answer already goes through the built-in humanizing layer; this step adds the user's own voice on top. Follow the "Setup" section of `../your-voice/SKILL.md`, which asks: "Want answers to sound like you? Paste 2-5 things you've written, or add your own writing rules. Skip to use the humanizing layer only." Save to `<workspace>/voice/`.

11. **Permissions** (id `permissions`). Ask each as yes/no, say its consequence in one line, show the safe default, write the answer to preferences.
    - **Sign in with Google, Microsoft or LinkedIn on job portals** (`portal_accounts.allow_sso`, default yes). Consequence: uses an account already signed in to your Chrome; only continues past basic profile and email consent screens.
    - **Click Sign In when Chrome autofills a saved login** (`allow_saved_login`, default yes). Consequence: I never read or type the password. Anything else parks the job and you finish by hand.
    - **Credential mode** (`credential_mode`, default no). Consequence: I may type a keychain password, create portal accounts with a generated password, reset a forgotten password by email, and enter emailed or SMS codes. Say exactly: "Many agents (including Claude) will refuse these steps under their own safety rules; when they do, the job parks for you." Only on yes, ask each of `allow_sign_in`, `allow_create`, `allow_password_reset`, `sms_codes` (each default no).
    - **SMS codes** (macOS, only if credential mode is on, default no). Consequence: reads `~/Library/Messages/chat.db` read-only for a code from the last 5 minutes. Click path: System Settings > Privacy & Security > Full Disk Access > add the app running the agent; on iPhone: Settings > Messages > Text Message Forwarding > your Mac. On Windows, codes come back to you.
    - If credential mode needs it, check `python3 -c "import keyring"`; if missing, ask before `pip install keyring`.
    - **auto_submit** (default **no**). Consequence: yes means the agent presses Submit itself, up to the daily cap; no means it fills every form and stops for you to review and press Submit. Explain the README "Auto-submit" trade-off. Also set `dry_run` and `caps.daily_submit_cap`.
    - **Schedule** (default no). Consequence: the agent scans and applies while you are away, within your caps. If yes, default **every 3 hours**; accept another interval. Save `schedule.every_hours`. Walk-away runs need the Mac awake: tell them to keep it plugged in and offer `caffeinate -dimsu &` (stops sleep until they quit it or restart), or System Settings > Battery > Options > "Prevent automatic sleeping on power adapter when the display is off". Scheduled runs use a local Claude Code scheduled task (see `job-run`), never a cloud one, because the run needs this Mac's Chrome.
    - CAPTCHAs and bot checks are never solved: the agent parks that tab, filled and open, and tells you.

12. **Notifications** (id `notify`). Why: so you hear when a tab needs you. Offer, default 1: (1) a macOS notification on this Mac, (2) an ntfy.sh topic to get alerts on your phone (suggest a long random name, since anyone who knows it can read it), (3) a Slack incoming webhook, (4) none. (other setups: see end) Write `<workspace>/state/notify.json` (shapes in `../job-run/scripts/notify.py`), set `notify.method`, and send a test with `notify.py --title "job-agent" --message "test"`.

13. **Practice run** (id `dryrun`). Why: proves everything works before it matters.
    - Write both YAML files first and print a short summary (no secrets). Pick one real posting from the JobRight feed that matches the preferences. Run the job-run skill in dry-run mode on that one posting: tailor the resume, open the application, fill every field, stop at Submit without pressing it. Show the filled form and the tailored resume path. If something parks or fails, fix it or give the exact click needed.

14. **Summary screen.** Print:
    - A checklist of what is set up (Chrome, auto-allow on or off, Gmail, tracker type and location, JobRight feed URL, master resume path, voice (profile from N samples or rules, or humanizing layer only), auto_submit, schedule, notifications), each ticked or "not set".
    - How to start: `/job-agent:run dry-run` for another practice, `/job-agent:run` for a real run (other agents: "run the job-run skill").
    - If a schedule is enabled: "Say 'start the schedule' and I will run every <N> hours. Say 'stop the schedule' to end it." Do not start it without a yes.
    - "Run `/job-agent:setup` again any time; finished steps are skipped."

## Not on Mac or not using Claude Code?

Community-supported. The skills work in other agents and on other systems, with these differences. Use only the lines that apply.

- **Other agents** (Codex, Cursor, others via `npx skills add azizu06/job-agent`, skills in `.agents/skills/`): add the browser MCP yourself: `npx -y chrome-devtools-mcp@1.10.1 --autoConnect --no-usage-statistics --workspace=<absolute workspace>`. Codex: `codex mcp add job-agent-browser -- npx -y chrome-devtools-mcp@1.10.1 --autoConnect --no-usage-statistics --workspace=<absolute workspace>`. Show the exact snippet for their agent. Skip the `job-applier` copy; jobs run one at a time unless the agent can give each worker its own browser MCP process. Connectors (Gmail, Notion, Sheets) are added in that agent's own MCP settings; point the user there.
- **Windows** (experimental): `python_cmd: py -3`. No auto-allow helper: the user clicks Allow, or uses dedicated mode (`launch_chrome.py`), which never prompts. Notifications: ntfy or Slack, never `macos`. Keep the PC awake in Settings > System > Power. Schedules: Task Scheduler running the agent's headless CLI (see `job-run`).
- **Linux**: no auto-allow helper and no SMS codes; same notification and schedule notes as Windows (cron instead of Task Scheduler).

## Never

- Store passwords, codes or API keys in any file. Passwords go only in the OS keychain through `portal-auth`.
- Enable `auto_allow`, credential mode, `auto_submit` or the schedule without the user's explicit yes after the explanation above.
- Press Submit during the practice run.
