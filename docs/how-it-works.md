# How job-agent works

The README is the short version. This page has the detail: each skill, the browser modes, sign-in, safety rules, auto-submit, scheduling and trackers. See also [your-voice.md](your-voice.md), [troubleshooting.md](troubleshooting.md) and [faq.md](faq.md).

- [The skills](#the-skills)
- [Your data](#your-data)
- [The master resume](#the-master-resume)
- [Browser](#browser)
- [Safety rules](#safety-rules)
- [Portal sign-in](#portal-sign-in)
- [Auto-submit](#auto-submit)
- [Scheduling](#scheduling)
- [Trackers](#trackers)
- [Optional connectors](#optional-connectors)
- [Development](#development)

## The skills

| Step | Skill | What it does |
| --- | --- | --- |
| Setup | `job-setup` | Writes your preferences and standing answers, records your master resume, attaches to Chrome, captures your JobRight feed |
| Scan | `job-scan` | Reads your JobRight "Most Recent" feed down to the last card it saw. Falls back to the Indeed MCP connector |
| Gate | `job-gate` | Filters by title and role fit, term, pay floor, location, freshness (it cuts reposts by first-seen and the employer's own posting date) and caps. Checks that you have not applied to that req already and stops the job if that check cannot run. Keeps the best one or two roles per company and holds jobs waiting on a referral |
| Tailor | `tailor-resume` | Copies your master, picks the best entries and bullets, reports keyword coverage before and after, asks you about missing terms |
| Fill | `apply-fill` | Fills the form in its own tab with real clicks and typing, uploads the resume, checks every field |
| Sign in | `portal-auth` | Tries Sign in with Google, then Microsoft, then LinkedIn, then a login Chrome already saved. Otherwise it parks the job for you |
| Run | `job-run` | Runs the loop, one applier per job, each with its own browser connection, then re-checks every form |
| Track | `tracker` | Local CSV by default, or Notion or Google Sheets. Finds the receipt email after a submit |
| Sync | `status-sync` | Reads new email for assessments, interviews, offers and rejections and updates each row |

What setup asks about:

- what jobs you want, and your standard application answers
- your master resume
- attaching to the Chrome you already use, so it starts with the logins you already have
- which MCPs you have (Gmail, Notion, Sheets, Indeed) and what each adds
- the optional auto-allow helper for walk-away runs
- whether the agent may use Sign in with Google, Microsoft or LinkedIn on job portals (default yes) and click Sign In on logins Chrome already saved, and the optional credential mode (off by default)
- a notification channel (macOS, ntfy.sh or Slack) for jobs that need you

## Your data

Everything personal lives in `~/.job-agent/`, or in `$JOB_AGENT_HOME` if you set it:

| Path | What it holds |
| --- | --- |
| `profile/preferences.yaml` | Roles, pay floor, locations, caps, tracker, auto-submit |
| `profile/standing-answers.yaml` | Contact details, links, work authorization, education, EEO answers |
| `resumes/master.md` | Your master resume (or the path you chose) |
| `resumes/tailored/` | One folder per tailored copy |
| `state/` | Scan files, the feed checkpoint, the queue, run logs, read-backs |
| `tracker.csv` | The default tracker |

Passwords, if you turn on credential mode, live only in your OS keychain. Nothing personal goes into this repo, and the repo's `.gitignore` excludes these paths in case your workspace points at a clone.

## The master resume

Keep one long master resume with everything you have done and several alternate bullets per entry. Each job gets a new copy built from it. The agent never adds a metric, tool or experience that is not in the master, and it lists the job's keywords you still lack so you decide.

Start from [`skills/job-setup/assets/master-resume.tex`](../skills/job-setup/assets/master-resume.tex), the default one-page layout, or its Markdown twin [`master-resume.md`](../skills/job-setup/assets/master-resume.md), which renders in the same layout. Both hold a sample resume for you to replace. Alternates sit in `\iffalse ... \fi` or `<!-- alt -->` blocks and never print. The content checks are plain Python; the PDF layout gate needs `tectonic` and PyMuPDF. From a clone of this repo:

```
python3 skills/tailor-resume/scripts/keyword_coverage.py --jd jd.txt --resume tailored.tex --before master.tex --min 95
python3 skills/tailor-resume/scripts/resume_check.py --master master.tex --resume tailored.tex
tectonic -X compile tailored.tex
python3 skills/tailor-resume/scripts/resume_gate.py --pdf tailored.pdf --resume tailored.tex --master master.tex
```

The gate prints `VERDICT: PASS` only when the content check and the layout check (one page filled to full height, bullets at most 2 lines with every line at least 95% full, no orphan lines, uniform spacing) are clean. It renders three PNGs to look at, and writes a receipt that `resume_gate.py --verify` checks before any upload.

## Browser

**Default: your own Chrome.** The agent works in the Chrome you already use, with your existing logins, through [chrome-devtools MCP](https://github.com/ChromeDevTools/chrome-devtools-mcp) and its `--autoConnect` option.

1. Use Chrome 144 or later. Open `chrome://inspect/#remote-debugging` once and turn remote debugging on.
2. When the agent connects, Chrome asks "Allow remote debugging?". Click Allow.

Chrome asks every time a new debugging connection starts. Each applier opens its own connection so agents never get in each other's way, which means one prompt per applier. During a session Chrome shows a banner that it is being controlled by automated software.

The Claude Code plugin sets up the MCP for you (chrome-devtools-mcp 1.10.1). For other agents, add:

```
npx -y chrome-devtools-mcp@1.10.1 --autoConnect --no-usage-statistics --workspace=$HOME/.job-agent
```

Codex:

```
codex mcp add job-agent-browser -- npx -y chrome-devtools-mcp@1.10.1 --autoConnect --no-usage-statistics --workspace=$HOME/.job-agent
```

`--no-usage-statistics` turns off the MCP's usage reporting to Google. The `--workspace` folder is where the browser server may read files, so it can upload your tailored resumes; use your `JOB_AGENT_HOME` if you set one.

For parallel appliers in Claude Code, setup copies [`skills/job-setup/assets/job-applier.md`](../skills/job-setup/assets/job-applier.md) to `~/.claude/agents/`. Plugins cannot give a subagent its own MCP connection, so the copy in your user folder does it. Without it, jobs run one at a time.

### Auto-allow (optional, off by default, macOS only)

For runs with nobody at the keyboard, [`auto_allow.py`](../skills/job-setup/scripts/auto_allow.py) presses Allow for the agent.

- It only acts while armed. Each agent arms a 15 second window right before its own connect. While any window is open, the helper clicks each Chrome prompt that appears, logs the click to `~/.job-agent/auto-allow.log`, and closes one window per click. When no window is open it clicks nothing.
- What turning it on means: Chrome's prompt does not say who is asking, so any other program on your computer that connects to Chrome while a window is open is approved too.
- Turning it on installs a per-user LaunchAgent (`~/Library/LaunchAgents/io.github.azizu06.job-agent.auto-allow.plist`). Turning it off unloads and removes it.
- Grant Accessibility to the Python binary the enable step prints: System Settings > Privacy & Security > Accessibility, press +, then Cmd-Shift-G to paste the path.
- It finds Chrome's prompt by its English text, so Chrome must be in English.
- The helper is a macOS feature. On other systems, click Allow yourself or use a separate profile.

To turn it on, ask your agent "turn on auto-allow". To turn it off, "turn off auto-allow".

### A separate profile (alternative)

If you want the agent isolated from your main browser, ask your agent to "start the job-agent Chrome profile". It starts Chrome with its own profile (`--remote-debugging-port=9333 --user-data-dir=~/.job-agent/chrome-profile`) on macOS, Linux or Windows. On Linux with a snap or flatpak Chrome, set `CHROME_BIN` to the Chrome command first. Point the MCP at it with `--browser-url=http://127.0.0.1:9333` and set `browser.mode: dedicated`.

There are no prompts, but you sign in to JobRight, Gmail and your job sites once in that window. While it runs, any program on your computer can control that profile through the port.

## Safety rules

The agent will never:

- solve or get around a CAPTCHA or bot check. It parks that job instead: the tab stays open and filled, the tracker row says `Needs you: captcha`, you get a notification, and the run moves on. The run ends with a list of parked tabs so you clear them in one sitting.
- stall or crash on a step it will not or cannot do. Some agents refuse to type passwords, create accounts or enter codes under their own policies. The agent parks that job the same way (`Needs you: sign-in`, `Needs you: create account` and so on), does not retry it, and moves on.
- enter an SSN or payment details, or approve an authenticator or push 2FA request.
- use Sign in with Google, Microsoft or LinkedIn unless you allowed it in setup. It picks only your own matching account and continues only past consent screens that ask for basic profile and email.
- press Enter or Escape inside a form, or reload a filled tab. It answers fields with real clicks and typing.
- invent facts in written answers. It drafts essay and free-text answers only from your resume, standing answers and the job description, lists any inferred sentence for you to check, and flags postings with a rule about AI-written answers so you decide (`genai_restriction: skip` skips them). Set `written_answers: writer` to have a separate writer draft every answer on a form together, or `leave` to leave them empty for you.
- touch a browser tab it did not open.
- automate LinkedIn or any social media site.

Before it calls a form ready, it re-reads the live form for errors. Some portals record your application before the last step; on unfamiliar multi-step forms it stops after step 1 and checks your email after each step.

**Terms of service.** Automating a website may break its terms, and a site may limit or close your account. The agent reads slowly in your own browser and uses no private APIs, which lowers the load but does not make automation allowed. You are responsible for how you use it.

**Employer AI policies.** Some employers ask applicants not to use AI tools. The agent reads each full posting for that language, fills those forms as usual, flags them in its report and its ready notification, and never auto-submits them, so you decide. Set `genai_restriction: skip` to skip them instead. Read each posting before you submit.

## Portal sign-in

By default the agent signs in to job portals only with an account already signed in to your Chrome (Google, then Microsoft, then LinkedIn) or a login Chrome already saved. If neither works, it parks the job: the tab stays open and you finish the sign-in.

**Optional credential mode, off by default.** It lets the agent type passwords from your OS keychain, create portal accounts, reset passwords and enter verification codes. Many agents (including Claude) will refuse these steps under their own safety rules; when they do, the job parks for you. Generated passwords go to your OS keychain and never appear in chat or logs. It needs `pip install keyring`.

Verification codes in credential mode:

- Emailed codes are read through the Gmail MCP: the newest message from that sender, within a few minutes.
- macOS, if you opt in: SMS codes are read from the Messages database (`~/Library/Messages/chat.db`, read-only, last 5 minutes). This needs Full Disk Access for the app running your agent (System Settings > Privacy & Security > Full Disk Access) and Text Message Forwarding from your iPhone.
- Windows and Linux: SMS codes come to you.

## Auto-submit

`auto_submit: false` is the default: the agent fills everything and stops at the final button. You review the form, then submit it, or turn on auto-submit once you trust the fills.

Setting `auto_submit: true` lets it press the final button. Even then it never submits past a CAPTCHA, a sign-in wall, an unanswered required question, a posting with a rule about AI tools, or an event RSVP. It respects a daily cap and a per-company cap, and logs a full read-back of every answer to your tracker before it clicks. `dry_run: true` fills and reads back without ever clicking.

The trade-off: auto-submit saves you the review step, but a wrong answer, a bad upload or a misread dropdown goes to the employer with your name on it, and you cannot take it back. Many companies also limit how many roles you can apply to. Start with `dry_run`, then `auto_submit: false`, and turn on auto-submit only after you trust the fills on the portals you use.

## Scheduling

- Claude Code, in a session: `/loop 4h /job-agent:run` repeats while the session is open.
- A local scheduled task, or cron with a headless CLI such as `claude -p` or `codex exec`. A cloud routine cannot reach your Chrome.

Each run takes a lock, so two runs never overlap; a lock older than 3 hours is from a hung run and is replaced. A run fills at most `browser.max_forms_per_run` forms (default 10) and leaves the rest queued. A locked screen or a browser that does not attach logs `BLOCKED` and stops; two blocked runs in a row send you a notification. Each run ends with `READY: <forms>`, `ALERT: <assessment, interview or offer>` or `NOTHING READY`, and a notification goes out only for the first two.

Walk-away runs on your main Chrome need auto-allow; the separate profile needs nothing. Headless runs need their tools pre-approved; the example allow-list is in [`skills/job-run/SKILL.md`](../skills/job-run/SKILL.md). Keep the computer on and awake while runs are due.

## Trackers

Every application gets a row: company, role, requisition ID, link, date, resume used, status and receipt.

| Tracker | You need | Pick it if |
| --- | --- | --- |
| **CSV** (default) | Nothing | You want it to work now. Opens in Excel, Numbers or Google Sheets |
| **Notion** | The Notion MCP connector | You already plan in Notion. Setup can create the database |
| **Google Sheets** | A Google Sheets MCP connector | You want a live sheet you can share or open on your phone |

Add the Gmail MCP to any of them and the agent finds receipt emails, then moves rows to Assessment, Interview, Offer or Rejected as replies arrive.

## Optional connectors

| Connector | What it adds |
| --- | --- |
| Gmail | Receipt emails, account verification, status sync |
| Notion | Tracker as a Notion database |
| Google Sheets | Tracker as a sheet |
| Indeed | A second job source when JobRight is off, empty or blocked |

Other requirements: `pip install keyring` for credential-mode passwords. On Linux, the clipboard helpers need `wl-copy` (Wayland) or `xclip`.

## Development

```
python3 -m unittest discover -s tests
claude plugin validate .
```

The suite includes end-to-end tests that run the full loop, from feed to tracker, against local Greenhouse and Workday forms, Google sign-in, a CAPTCHA page and an inbox. See [`tests/e2e/README.md`](../tests/e2e/README.md).

The README demo is a screen recording of a real run: Claude Code in the terminal beside Chrome, from the JobRight feed to a filled application, stopped at Submit.
