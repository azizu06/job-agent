<p align="center">
  <img src="assets/banner.png" alt="job-agent: your coding agent finds jobs, tailors your resume and fills the application. You click Submit." width="100%">
</p>

<p align="center">
  <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-E8590C"></a>
  <a href="https://github.com/azizu06/job-agent/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/azizu06/job-agent/actions/workflows/ci.yml/badge.svg"></a>
  <img alt="Platforms: macOS, Windows, Linux" src="https://img.shields.io/badge/platforms-macOS%20%7C%20Windows%20%7C%20Linux-0F1115">
  <img alt="Works with Claude Code, Codex, Cursor" src="https://img.shields.io/badge/agents-Claude%20Code%20%7C%20Codex%20%7C%20Cursor-0F1115">
</p>

<p align="center">
  <a href="#install">Install</a> ·
  <a href="#quickstart">Quickstart</a> ·
  <a href="#what-runs-on-its-own">What you do once</a> ·
  <a href="#safety">Safety</a> ·
  <a href="#troubleshooting">Troubleshooting</a> ·
  <a href="#faq">FAQ</a>
</p>

job-agent is a set of skills for your coding agent. It finds new postings, builds a one-page resume for each one from your master resume, and fills the application in your own Chrome. It never invents a fact, and by default it stops at the final Submit button so you can check the form and click it yourself.

<p align="center">
  <img src="assets/demo.gif" alt="The agent fills a test application on the localhost mock rig: it reads the feed, checks the posting, types each field, uploads the resume, picks dropdown answers, drafts the essay, ticks the consent box and stops at Submit." width="760">
  <br>
  <sub>A real run on the built-in test rig. Every page is on localhost and every value is fake.</sub>
</p>

## How it works

```mermaid
flowchart LR
    A([Setup wizard<br>once]) --> B[Scan<br>JobRight feed]
    B --> C{Filter<br>your rules}
    C -- cut --> X[Cut report]
    C -- keep --> D[Tailor<br>resume per job]
    D --> E[Fill<br>one agent per job]
    E --> F{Auto-submit<br>on?}
    F -- no --> G[Stops at Submit<br>you click it]
    F -- yes --> H[Submits within<br>your caps]
    E -. CAPTCHA or sign-in .-> P[Parked tab<br>you finish it]
    G --> T[(Tracker<br>CSV, Notion, Sheets)]
    H --> T
    T --> S[Email sync<br>receipts and replies]
    S -. every few hours .-> B

    classDef accent fill:#E8590C,stroke:#E8590C,color:#fff
    classDef ink fill:#0F1115,stroke:#0F1115,color:#fff
    class E,D accent
    class G,P ink
```

## You need

- [ ] A coding agent: [Claude Code](https://claude.com/claude-code), Codex, Cursor or [another agent that reads skills](https://github.com/vercel-labs/skills)
- [ ] Google Chrome 144 or later (stable). Not Edge, Brave or Arc
- [ ] Node.js 20.19 or later
- [ ] Python 3.9 or later
- [ ] A free [JobRight](https://jobright.ai) account. Setup walks you through it
- [ ] A resume, any format. Setup turns it into a master resume
- [ ] Optional: `pandoc`, `tectonic` and `poppler` to build the resume PDF

New to some of these? [docs/getting-started.md](docs/getting-started.md) installs each one on macOS, Windows and Linux.

## Install

Pick one route.

| Route | Best for | Run this |
| --- | --- | --- |
| **Claude Code plugin** | Claude Code users. Sets up the browser for you | `/plugin marketplace add azizu06/job-agent`<br>`/plugin install job-agent@job-agent` |
| **Skills CLI** | Codex, Cursor and other agents | `npx skills add azizu06/job-agent` |
| **Paste the link** | Any agent. It installs and runs setup with you | `https://github.com/azizu06/job-agent set this up` |

The Skills CLI and paste routes also need the browser MCP added to your agent. Setup prints the exact line for your agent.

## Quickstart

1. **Install** with one of the routes above. In Claude Code, run `/reload-plugins` after.
2. **Turn on Chrome remote debugging.** Open `chrome://inspect/#remote-debugging` and switch it on. You do this once.
3. **Run setup:** `/job-agent:setup`. About 10 questions and 10 minutes. It writes nothing until you say yes. In other agents, say "set up job-agent".
4. **Try a dry run:** `/job-agent:run dry-run`. It scans, tailors and fills, and never presses Submit. When Chrome asks "Allow remote debugging?", click Allow.

When the dry run looks right, use `/job-agent:run`. To repeat it every 4 hours, use `/loop 4h /job-agent:run`.

## Pick a tracker

Every application gets a row: company, role, requisition ID, link, date, resume used, status and receipt.

| Tracker | You need | Pick it if |
| --- | --- | --- |
| **CSV** (default) | Nothing | You want it to work now. Opens in Excel, Numbers or Google Sheets |
| **Notion** | The Notion MCP connector | You already plan in Notion. Setup can create the database |
| **Google Sheets** | A Google Sheets MCP connector | You want a live sheet you can share or open on your phone |

Add the Gmail MCP to any of them and the agent finds receipt emails, then moves rows to Assessment, Interview, Offer or Rejected as replies arrive.

## What runs on its own

| You do once | It does every run | You still do sometimes |
| --- | --- | --- |
| Install the plugin or skills | Reads new postings in your JobRight feed | Clear parked tabs: CAPTCHAs, new sign-ins, codes |
| Turn on Chrome remote debugging | Filters them by title, term, pay, location and age | Answer missing-keyword questions, once per term |
| Mac only, for walk-away runs: grant Accessibility to the auto-allow helper | Builds a tailored resume for each job | Click Submit, unless you turned on auto-submit |
| Create a free JobRight account and sort it by Most Recent | Fills each form in its own tab | Keep the computer on and awake during runs |
| Give it your resume | Records every job in your tracker | |
| Answer the setup wizard | Finds receipts and status emails | |
| Sign in to optional connectors: Gmail, Notion, Sheets | Notifies you when a tab needs you | |

## Safety

The agent never solves a CAPTCHA, never enters an SSN or payment details, and never touches a tab it did not open. It does not automate LinkedIn or any social site. When it hits a step only you can do, it parks the job: the tab stays open and filled, the tracker row says `Needs you: <reason>`, you get a notification, and the run moves on.

**Auto-submit is off by default.** Turn it on only after you trust the fills on your portals. Even then it stops at CAPTCHAs, sign-in walls, unanswered required questions and postings that ban AI tools, and it keeps to a daily cap and a per-company cap. A wrong answer sent with your name on it cannot be taken back.

**Terms of service.** Automating a website may break its terms, and a site may limit or close your account. The agent reads slowly in your own browser and uses no private APIs, which lowers the load but does not make automation allowed. You are responsible for how you use it.

**Employer AI policies.** Some employers ask applicants not to use AI tools. The agent looks for that language, skips those postings by default and tells you. Read each posting before you submit.

Full rules: [docs/how-it-works.md](docs/how-it-works.md#safety-rules).

## Troubleshooting

| Problem | Fix |
| --- | --- |
| Chrome never shows "Allow remote debugging?" | Check Chrome is 144 or later and open. Turn the switch on at `chrome://inspect/#remote-debugging`, then restart Chrome |
| The agent opened a new, empty Chrome | The browser MCP is missing `--autoConnect`. Run setup again, or copy the line from [docs/how-it-works.md](docs/how-it-works.md#browser) |
| "Allow" pops up for every job | Expected. Each job opens its own connection. Click Allow, or turn on auto-allow on a Mac |
| Resume upload fails with "not within any of the configured workspace roots" | You set a custom `JOB_AGENT_HOME`. The agent copies the PDF to a temp folder and retries. If it still fails, set `--workspace=` to your folder |
| Scan says "checkpoint not found" or reads old jobs | Your JobRight feed is not sorted by Most Recent. Sort it, then ask your agent to "recapture my JobRight feed" |
| Jobs run one at a time | The `job-applier` subagent is missing. Run setup again; it copies the file to `~/.claude/agents/` |
| A scheduled run stops at the first prompt | Headless runs need tools pre-approved. Copy the allow-list from [skills/job-run/SKILL.md](skills/job-run/SKILL.md) |
| Auto-allow clicks nothing | Grant Accessibility to the Python path that `enable` printed, and set Chrome's language to English |
| `python3` is not found on Windows | Use `py -3` wherever the docs say `python3` |
| No resume PDF, only a `.md` or `.tex` file | Install `pandoc`, `tectonic` and `poppler`. Without them the agent hands you the source file |
| A form shows "needs corrections" after filling | The portal ignored a field. The agent re-reads every field before it calls a form ready; if it flags one, fix it by hand |
| Most jobs park as `Needs you: sign-in` | Sign in to Google in that Chrome, and keep Sign in with Google allowed in setup. Workday needs one account per company |

More in [docs/getting-started.md](docs/getting-started.md#if-something-goes-wrong).

## FAQ

<details>
<summary><b>What is JobRight?</b></summary>

[JobRight](https://jobright.ai) is a job board that builds a feed of postings matched to your profile. job-agent reads that feed in your own signed-in Chrome, newest first, and stops at the last job it saw. A free account is enough. If you do not want JobRight, the agent can use the Indeed MCP connector instead.
</details>

<details>
<summary><b>Is it free?</b></summary>

job-agent is free and MIT licensed. JobRight's free account works. The cost is your coding agent: a Claude, ChatGPT or Cursor subscription, or API usage. See the next question.
</details>

<details>
<summary><b>What does it cost in tokens?</b></summary>

Each job runs in its own agent session that reads page snapshots, tailors a resume and fills the form, so cost grows with the number of jobs and the length of each form. One measured run on the test rig with Claude Sonnet: 5 postings, 3 forms filled, about 11 million mostly cached input tokens and 29,000 output tokens, about $2.80 at API list prices. Real portals have longer pages, so expect more per job. On a Claude Pro or Max plan this counts toward your usage limit instead of a bill. Start with a dry run on a few jobs and check your usage before you schedule it.
</details>

<details>
<summary><b>Does it work on Windows? Linux?</b></summary>

Yes, the main loop works on macOS, Windows and Linux, and CI runs the tests on all three. Use `py -3` where the docs say `python3`. Two extras are macOS only: the auto-allow helper for walk-away runs and reading SMS codes. On Windows and Linux you click Chrome's Allow prompt yourself, or use the separate Chrome profile, which never asks.
</details>

<details>
<summary><b>Will I get banned?</b></summary>

It can happen. Automation may break a site's terms, and a site may limit or close your account. The agent lowers the risk: it works in your normal Chrome, reads slowly, uses no private APIs, never touches LinkedIn, never solves CAPTCHAs, and caps how many roles it applies to per company. Many companies also limit how many roles you can apply to, so the caps protect your candidacy too.
</details>

<details>
<summary><b>Can it apply through LinkedIn Easy Apply?</b></summary>

No. It does not automate LinkedIn or any social site. It applies on the employer's own portal (Greenhouse, Workday, Lever, Ashby and others). It can use the "Sign in with LinkedIn" button on a portal, if you allow it, but it never browses linkedin.com.
</details>

<details>
<summary><b>What if I have no resume?</b></summary>

Setup can start one with you from the [master resume template](skills/job-setup/assets/master-resume.md). You list your school, jobs, projects and skills, and the agent shapes them into entries. Every number and tool must be something you really did; the agent never adds facts of its own.
</details>

<details>
<summary><b>Will it lie on my resume or answers?</b></summary>

No. It only rewords and selects from your master resume and your standing answers. A checker fails any tailored resume that contains a number not found in the master. Written answers are drafted from the same sources, and any sentence it had to infer is listed for you to check. Set `written_answers: leave` to write them yourself.
</details>

<details>
<summary><b>Does it submit on its own?</b></summary>

Not unless you turn on `auto_submit`. By default it fills everything and stops at the final button, and the tracker row says `Ready`. You open the tab, read the form and click Submit.
</details>

<details>
<summary><b>What happens at a CAPTCHA or a sign-in page?</b></summary>

It tries Sign in with Google, Microsoft or LinkedIn with an account already in your Chrome, then a login Chrome already saved. If none works, or it sees a CAPTCHA, it parks the job: the tab stays open and filled, and you get a notification. At the end of the run you get one list of parked tabs to clear in one sitting.
</details>

<details>
<summary><b>Where does my data go?</b></summary>

Your profile, resumes, tracker and run logs live in `~/.job-agent/` on your computer. Passwords, if you turn on the optional credential mode, live only in your OS keychain. Nothing personal goes into this repo. Your agent's model provider sees what the agent reads, as with any agent task.
</details>

<details>
<summary><b>Does my computer have to stay on?</b></summary>

Yes. The agent drives the Chrome on your computer, so runs need it on, awake and signed in. A cloud agent cannot reach your Chrome. On a Mac, walk-away runs also need the auto-allow helper.
</details>

<details>
<summary><b>Does it only do internships?</b></summary>

No. Set `seniority` to internship, new-grad, junior, mid or senior, set your pay floor per hour or per year, and list the titles you want. The examples use internships because the author is a student.
</details>

<details>
<summary><b>Can I stop or undo it?</b></summary>

Stop your agent at any time; filled tabs stay open. A submitted application cannot be pulled back by the agent, which is why auto-submit is off by default. To turn helpers off, ask your agent "turn off auto-allow".
</details>

<details>
<summary><b>Which coding agents does it work with?</b></summary>

Claude Code gets the smoothest setup, including parallel appliers. Codex, Cursor and any agent that reads skills or Markdown instructions work too, with one job at a time unless your agent can give each worker its own browser connection. Some agents refuse to type passwords or enter codes; those jobs park for you instead of failing.
</details>

More detail: [docs/how-it-works.md](docs/how-it-works.md). Development and the test rig: [tests/e2e/README.md](tests/e2e/README.md).

---

<p align="center">
  <b>If job-agent saves you an evening of copy-pasting, star the repo.</b><br>
  It helps other students find it. Issues and pull requests are welcome.
  <br><br>
  <a href="https://github.com/azizu06/job-agent"><img alt="Star on GitHub" src="https://img.shields.io/github/stars/azizu06/job-agent?style=social"></a>
  <br><br>
  <sub>MIT. By Aziz Umarov (<a href="https://github.com/azizu06">@azizu06</a>).</sub>
</p>
