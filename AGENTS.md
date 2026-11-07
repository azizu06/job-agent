# job-agent: instructions for coding agents

This repo turns you into a job-application agent. If a user gave you this repo's link and said "set this up" (or similar), do all of it for them: install, setup, then offer a dry run.

## What to do

1. **Install the skills** for your agent:
   - Claude Code: `/plugin marketplace add azizu06/job-agent` then `/plugin install job-agent@job-agent`.
   - Other agents (community-supported, not tested end to end): `npx skills add azizu06/job-agent`, or clone the repo and read `skills/*/SKILL.md` directly.
   - If installed with npx skills add, skills live in .agents/skills/, and add the browser MCP yourself: `npx -y chrome-devtools-mcp@1.10.1 --autoConnect` (Codex: `codex mcp add job-agent-browser -- npx -y chrome-devtools-mcp@1.10.1 --autoConnect`). Also pass `--no-usage-statistics --workspace=$HOME/.job-agent` so it sends no usage data and can upload resumes from the workspace.
2. **Setup:** follow `skills/job-setup/SKILL.md`. It writes the user's profile into the workspace (`$JOB_AGENT_HOME`, default `~/.job-agent/`) and attaches to the user's own Chrome with chrome-devtools MCP `--autoConnect`.
3. **Run:** follow `skills/job-run/SKILL.md`, which calls the other skills in order.

Before step 1, check the prerequisites yourself: `node --version` (20.19 or later), `python3 --version` (3.9 or later; `py -3` on Windows), and Chrome 144 or later. If one is missing, give the user the install line for their OS from `docs/getting-started.md` instead of failing. Answer user questions from `docs/faq.md` and the rest of `docs/` first. Many users come from a short video and have never used a coding agent: explain each click only they can make (Chrome's remote debugging switch, the "Allow remote debugging?" prompt, parked tabs) in one plain sentence when it comes up.

## Skills

| Skill | Purpose |
| --- | --- |
| `skills/job-setup` | Interview the user, write preferences and standing answers, connect the browser |
| `skills/job-scan` | Read new postings from JobRight (or Indeed MCP) up to the saved checkpoint |
| `skills/job-gate` | Filter by preferences, dedupe against the tracker, write the queue |
| `skills/tailor-resume` | Build a truthful one-page copy from the master resume, with coverage before and after |
| `skills/your-voice` | Every written answer: facts only, two drafts, built-in humanize pass, optional voice profile, self-audit, `writecheck.py` |
| `skills/apply-fill` | Fill one application in its own tab and stop at Submit |
| `skills/job-run` | Run the loop, one subagent per job, then re-verify and track |
| `skills/tracker` | CSV, Notion or Sheets tracker plus Gmail receipts |
| `skills/status-sync` | Update statuses from assessment, interview, offer and rejection emails |
| `skills/portal-auth` | Sign in to the user's job-portal accounts with SSO or a browser-saved login; optional credential mode for the rest |

## Rules that always apply

- Stop at the final Submit unless the user set `auto_submit: true`; even then, follow every guardrail in `skills/apply-fill/SKILL.md`.
- Portal sign-in only through `skills/portal-auth`: Google, then Microsoft, then LinkedIn SSO, then a login the browser already saved, then park. Typed passwords, account creation, password resets and verification codes only in its optional credential mode (off by default), within the user's settings. Passwords live only in the OS keychain and never appear in chat or logs.
- If you decline or cannot do a step (many agents will not type passwords, create accounts or enter codes), park that job like a CAPTCHA: tab left open, `Needs you: <reason>`, notify, move on. Never retry it in a loop and never stop the run.
- Never solve or bypass a CAPTCHA or bot check. Park the tab (left open and filled), mark the row `Needs you: captcha`, notify the user, and move on. SSN and payment details always go to the user.
- The user clicks Chrome's "Allow remote debugging?" prompt, unless they enabled the opt-in `auto_allow.py` helper.
- Each parallel agent uses its own browser connection and its own tab.
- Work only in tabs you opened. In the default mode this is the user's real browser.
- Never invent resume facts or application answers.
- No LinkedIn or other social media automation. No private API scraping.
- User data lives only in the workspace, never in this repo's tracked files.

On Windows, use `py -3` wherever these docs say `python3`.

## Developing this repo

- Tests: `python3 -m unittest discover -s tests` (standard library only).
- Plugin check: `claude plugin validate .`
- Keep prose plain: no em dashes, no hype words.
- Docs: `README.md` is the product page, `docs/how-it-works.md` holds the detail, `docs/getting-started.md` is for first-time users, and `docs/faq.md`, `docs/troubleshooting.md` and `docs/your-voice.md` hold the FAQ, fixes and answer-writing detail. Keep facts in sync across them when a skill changes.
- README images: `assets/banner.png` and `assets/demo.gif`, built from `assets/src/`. The demo fills a live posting as the fictional applicant in `assets/src/demo-persona.json` and never submits; no real person's data may appear in any frame.
