# job-agent

Skills that turn your coding agent (Claude Code, Codex, Cursor and others) into a job-application agent.

1. **Find** new postings in your job feed.
2. **Tailor** a one-page resume for each one from your master resume, without inventing anything.
3. **Fill** the application in your own Chrome, then **track** it and its email replies.

By default it stops at the final Submit button. You review and click it.

## Install

Pick one. All three use this same repo.

**1. Paste the link (quickest, any agent).** Send your agent this:

```
https://github.com/azizu06/job-agent  set this up
```

It reads [`AGENTS.md`](AGENTS.md), installs the skills, and runs setup with you.

**2. Claude Code plugin.**

```
/plugin marketplace add azizu06/job-agent
/plugin install job-agent@job-agent
/job-agent:setup
```

**3. Skills CLI** (Codex, Cursor and [many other agents](https://github.com/vercel-labs/skills); it asks which agents to install into).

```
npx skills add azizu06/job-agent
```

Then ask your agent to "run the job-setup skill".

## Setup is one command

`/job-agent:setup` (or "run the job-setup skill") does everything in one pass:

- asks what jobs you want and your standard application answers, and records your master resume
- attaches to the Chrome you already use, so you never sign in to anything again
- checks which MCPs you have (Gmail, Notion, Sheets, Indeed) and what each adds
- offers the optional auto-allow helper for walk-away runs
- asks whether the agent may use Sign in with Google on job portals, sign in with saved passwords, create or reset portal accounts, and (macOS) read SMS codes
- sets up a notification (macOS, ntfy.sh or Slack) for jobs that need you

Then:

```
/job-agent:run dry-run     # fills forms, never presses Submit
/job-agent:run
```

## How it works

| Step | Skill | What it does |
| --- | --- | --- |
| Setup | `job-setup` | Writes your preferences and standing answers, attaches to Chrome |
| Scan | `job-scan` | Reads your JobRight "Most Recent" feed down to the last card it saw. Falls back to the Indeed MCP connector |
| Gate | `job-gate` | Filters by title, term, pay floor, location and posting age. Skips jobs already in your tracker |
| Tailor | `tailor-resume` | Copies your master, picks the best entries and bullets, reports keyword coverage before and after, asks you about missing terms |
| Fill | `apply-fill` | Fills the form in its own tab with real clicks and typing, uploads the resume, checks every field |
| Sign in | `portal-auth` | Tries Sign in with Google, then Microsoft, then LinkedIn, then saved passwords; creates or resets accounts only if you allowed it; reads email and (macOS) SMS codes. Parks the job if the agent declines or cannot do a step |
| Run | `job-run` | Runs the loop, one applier per job, each with its own browser connection, then re-checks every form |
| Track | `tracker` | Local CSV by default, or Notion or Google Sheets. Finds the receipt email after a submit |
| Sync | `status-sync` | Reads new email for assessments, interviews, offers and rejections and updates each row |

Your data stays in `~/.job-agent/` (or `$JOB_AGENT_HOME`): profile, resumes, tracker and state. Passwords live only in your OS keychain. Nothing personal goes in this repo.

### The master resume

Keep one long master resume with everything you have done and several alternate bullets per entry. Each job gets a new copy built from it. The agent never adds a metric, tool or experience that is not in the master, and it lists the job's keywords you still lack so you decide. Start from [`templates/master-resume.md`](templates/master-resume.md) (a LaTeX version is in `templates/`). The checks are plain Python with no dependencies:

```
python3 skills/tailor-resume/scripts/keyword_coverage.py --jd jd.txt --resume tailored.md --before master.md
python3 skills/tailor-resume/scripts/resume_check.py --master master.md --resume tailored.md
```

## Browser

**Default: your own Chrome.** The agent works in the Chrome you already use, with your existing logins, through [chrome-devtools MCP](https://github.com/ChromeDevTools/chrome-devtools-mcp) and its `--autoConnect` option.

1. Use Chrome 144 or later. Open `chrome://inspect/#remote-debugging` once and turn remote debugging on.
2. When the agent connects, Chrome asks "Allow remote debugging?". Click Allow.

Chrome asks every time a new debugging connection starts. Each applier opens its own connection so agents never get in each other's way, which means one prompt per applier. During a session Chrome shows a banner that it is being controlled by automated software. The Claude Code plugin sets up the MCP for you (chrome-devtools-mcp 1.10.1, the version this repo was tested with); for other agents, add `npx -y chrome-devtools-mcp@1.10.1 --autoConnect`. For parallel appliers in Claude Code, setup copies [`templates/claude-agents/job-applier.md`](templates/claude-agents/job-applier.md) to `~/.claude/agents/` (plugins cannot give a subagent its own MCP connection). Without it, jobs run one at a time.

**Optional, off by default: auto-allow.** For runs with nobody at the keyboard, [`auto_allow.py`](skills/job-setup/scripts/auto_allow.py) presses Allow for the agent.

- It only acts while armed. Each agent arms a 15 second window right before its own connect. While any window is open, the helper clicks each Chrome prompt that appears, logs the click to `~/.job-agent/auto-allow.log`, and closes one window per click. When no window is open it is not running.
- What it does: it approves the agent's own connections.
- What turning it on means: Chrome's prompt does not say who is asking, so any other program on your computer that connects to Chrome while a window is open is approved too.
- macOS: grant Accessibility to the app that runs your agent (System Settings > Privacy & Security > Accessibility). Windows: **beta, untested**, needs `pip install pywinauto`. Linux: not available; click Allow yourself or use a separate profile.
- Turn it on with `python3 skills/job-setup/scripts/auto_allow.py enable`, off with `disable`.

**Alternative: a separate profile.** If you want the agent isolated from your main browser, `python3 skills/job-setup/scripts/launch_chrome.py` starts Chrome with its own profile (`--remote-debugging-port=9222 --user-data-dir=~/.job-agent/chrome-profile`) on macOS, Linux or Windows. Point the MCP at it with `--browser-url=http://127.0.0.1:9222` and set `browser.mode: dedicated`. There are no prompts, but you sign in to your job sites once in that window. While it runs, any program on your computer can control that profile through the port.

## Safety

The agent will never:

- solve or get around a CAPTCHA or bot check. It parks that job instead: the tab stays open and filled, the tracker row says `Needs you: captcha`, you get a notification, and the run moves on. The run ends with a list of parked tabs so you clear them in one sitting.
- stall or crash on a step it will not or cannot do. Some agents refuse to type passwords, create accounts or enter codes under their own policies. The agent parks that job the same way (`Needs you: sign-in`, `Needs you: create account` and so on), does not retry it, and moves on.
- enter an SSN or payment details, or approve an authenticator or push 2FA request.
- use Sign in with Google, create a portal account or reset a password unless you allowed it in setup. With Google it picks only your own matching account and continues only past consent screens that ask for basic profile and email. Generated passwords go to your OS keychain and never appear in chat or logs.
- press Enter or Escape inside a form, or reload a filled tab. It answers fields with real clicks and typing.
- write answers to essay questions. It leaves them empty and lists them for you.
- touch a browser tab it did not open.
- automate LinkedIn or any social media site.

Verification codes: emailed codes are read through the Gmail MCP (newest message from that sender, within a few minutes). On macOS, if you opt in, SMS codes are read from the Messages database (`~/Library/Messages/chat.db`, read-only, last 5 minutes), which needs Full Disk Access for the app running your agent (System Settings > Privacy & Security > Full Disk Access) and Text Message Forwarding from your iPhone. On Windows, SMS codes come to you, because Phone Link has no stable API.

Before it calls a form ready, it re-reads the live form for errors. Some portals record your application before the last step; on unfamiliar multi-step forms it stops after step 1 and checks your email after each step.

### Auto-submit

`auto_submit: false` is the default: the agent fills everything and stops at the final button. You read the form and click Submit.

Setting `auto_submit: true` lets it press the final button. Even then it never submits past a CAPTCHA, a sign-in wall, an unanswered required question, or a posting that bans AI tools. It respects a daily cap and a per-company cap, and logs a full read-back of every answer to your tracker before it clicks. `dry_run: true` fills and reads back without ever clicking.

The trade-off: auto-submit saves you the review step, but a wrong answer, a bad upload or a misread dropdown goes to the employer with your name on it, and you cannot take it back. Many companies also limit how many roles you can apply to. Start with `dry_run`, then `auto_submit: false`, and turn on auto-submit only after you trust the fills on the portals you use.

## Your responsibility

- **Job site terms.** Automating a website may break its terms of service, and a site may limit or close your account. You are responsible for how you use this tool on JobRight, Indeed, employer portals and any other site. The agent reads slowly in your own signed-in browser and uses no private APIs, which lowers the load on a site but does not make automation allowed.
- **Employer AI policies.** Some employers ask applicants not to use AI tools when applying. The agent looks for that language, skips those postings by default and tells you. Read each posting yourself before you submit.
- **What you submit.** You are responsible for everything sent in your name. Check each application.

## Requirements

- A coding agent that supports skills or can read Markdown instructions.
- Google Chrome 144 or later, Node.js (for `npx chrome-devtools-mcp`), and Python 3.9 or later.
- Optional: `pip install keyring` (portal passwords), `pip install pywinauto` (auto-allow on Windows).
- Optional MCPs: Gmail (receipts, account verification, status sync), Notion or Google Sheets (tracker), Indeed (fallback job source).
- Optional for rendering resumes: `pandoc` or `tectonic`, and `pdftoppm`.

## Scheduling

Run it every few hours with `/loop 4h /job-agent:run` in Claude Code, a local scheduled task, or cron with a headless CLI such as `claude -p` or `codex exec`. Walk-away runs on your main Chrome need auto-allow; the separate profile needs nothing. Headless runs need their tools pre-approved; the example allow-list is in [`skills/job-run/SKILL.md`](skills/job-run/SKILL.md).

## Development

```
python3 -m unittest discover -s tests
claude plugin validate .
```

## License

MIT. By Aziz Umarov ([@azizu06](https://github.com/azizu06)).
