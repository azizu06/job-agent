# Getting started

This page is for you if you have never set up a coding agent or a browser MCP. job-agent is built for Claude Code on macOS. The page covers what to install, what each one-time click is for, and what your first run looks like.

- [1. Install the tools](#1-install-the-tools)
- [2. Install a coding agent](#2-install-a-coding-agent)
- [3. Make a JobRight account](#3-make-a-jobright-account)
- [4. Install job-agent and run setup](#4-install-job-agent-and-run-setup)
- [5. Your first run](#5-your-first-run)
- [If something goes wrong](#if-something-goes-wrong)

## 1. Install the tools

You need Chrome, Node.js and Python. The PDF tools are optional: without them the agent hands you the resume source file to export yourself.

| Tool | macOS (Homebrew) | Windows (winget) | Linux (Debian, Ubuntu) |
| --- | --- | --- | --- |
| Chrome 144+ | [google.com/chrome](https://www.google.com/chrome/) | `winget install Google.Chrome` | [google.com/chrome](https://www.google.com/chrome/) |
| Node.js 20.19+ | `brew install node` | `winget install OpenJS.NodeJS.LTS` | Use [nvm](https://github.com/nvm-sh/nvm); distro packages are often too old |
| Python 3.9+ | `brew install python` | `winget install Python.Python.3.12` | `sudo apt install python3` |
| PDF tools (optional) | `brew install pandoc tectonic poppler` | `winget install JohnMacFarlane.Pandoc`, then [tectonic](https://tectonic-typesetting.github.io) and poppler | `sudo apt install pandoc poppler-utils`, then [tectonic](https://tectonic-typesetting.github.io) |

Check them:

```
node --version
python3 --version
```

On Windows, Python runs as `py -3`. Wherever these docs say `python3`, type `py -3` instead.

Use Chrome itself, on the stable channel. Edge, Brave and Arc are built on Chrome but do not have the setting job-agent needs.

## 2. Install a coding agent

job-agent is a set of instructions for a coding agent, so you need one:

- [Claude Code](https://claude.com/claude-code): job-agent is built for it. The plugin wires up the browser for you and runs several applications at once.
- Codex, Cursor or [another agent that reads skills](https://github.com/vercel-labs/skills) can load the skills and run one job at a time. Full support is on the [roadmap](../README.md#coming-next).

The agent's subscription or API usage is the real cost of job-agent. See the token question in the [README FAQ](../README.md#faq).

## 3. Make a JobRight account

[JobRight](https://jobright.ai) builds a feed of postings matched to you. The agent reads that feed. Setup checks whether you are signed in and, if not, asks you to:

1. Create a free account at [jobright.ai](https://jobright.ai). Sign in with Google works.
2. Finish the job preferences it asks for: roles, locations, experience level, job type.
3. Open **Jobs** in the left menu.
4. Sort the list by **Most Recent**.

Do this in the Chrome you will use with job-agent, so the agent finds you already signed in. The agent never creates the account or types your password.

## 4. Install job-agent and run setup

Install with one route from the [README](../README.md#install). Then:

1. Open `chrome://inspect/#remote-debugging` in Chrome and switch remote debugging on. This lets the agent drive Chrome. You do it once.
2. Run setup. In Claude Code: `/job-agent:setup`. In other agents: "set up job-agent".

Setup asks one topic at a time and offers a default for each. Have these ready:

- the job titles you want, your pay floor and your locations
- your contact details, links, work authorization and school dates
- your resume file, or the facts to start one from the template

It asks before it writes any file, and before it turns on any optional helper.

### The clicks only you can make

| Click | Why | How often |
| --- | --- | --- |
| Chrome remote debugging switch | Lets the agent connect to your Chrome | Once |
| "Allow remote debugging?" | Chrome asks for every new agent connection | Each connection, unless auto-allow is on |
| Accessibility for the auto-allow helper (Mac, optional) | Lets the helper press Allow for you | Once |
| Sign in to Gmail, Notion or Sheets connectors (optional) | Receipts, status emails, a shared tracker | Once per connector |
| Parked tabs | CAPTCHAs, new portal accounts, codes | When the run lists them |

## 5. Your first run

Start with a dry run. In Claude Code: `/job-agent:run dry-run`. Elsewhere: "run the job-run skill in dry-run mode".

What you will see:

1. **Scan.** It opens your JobRight feed in a new tab and reads the newest cards.
2. **Filter.** It prints a cut report: how many jobs it kept and why it cut the rest.
3. **Tailor.** For each kept job it builds a resume copy and lists keywords you do not have yet. Answer those once; it remembers your answers.
4. **Fill.** Chrome asks "Allow remote debugging?" once per job. Click Allow. Each form fills in its own tab.
5. **Summary.** Every job with its status, the drafted written answers to check, and a list of parked tabs.

A dry run never presses Submit. Read a few filled forms. When they look right, run it for real; it still stops at Submit until you turn on auto-submit.

Your tracker is at `~/.job-agent/tracker.csv` unless you picked Notion or Sheets.

## If something goes wrong

| Problem | Fix |
| --- | --- |
| `node` or `python3` is not found | Close and reopen your terminal after installing. On Windows, use `py -3` |
| Chrome never asks "Allow remote debugging?" | Update Chrome to 144 or later, turn the switch on at `chrome://inspect/#remote-debugging`, and restart Chrome |
| A new, empty Chrome window opened | The browser MCP is missing `--autoConnect`. See [how-it-works.md](how-it-works.md#browser) |
| Setup says you are signed out of JobRight | Sign in at [jobright.ai](https://jobright.ai) in the same Chrome, then tell setup "done" |
| The scan reads the same jobs every time | Your feed is sorted by Recommended. Sort by Most Recent and run setup again |
| Every job parks as `Needs you: sign-in` | Sign in to your Google account in that Chrome. Workday needs one account per company, which you create once |
| The run stopped and asked for permission | Approve the tool, or pre-approve them for scheduled runs. The list is in [skills/job-run/SKILL.md](../skills/job-run/SKILL.md) |
| Your agent refused to type a password | Expected. Some agents refuse. The job parks; finish it in the open tab |

Still stuck? Open an issue with what you ran, what you expected and the exact error text. Leave out your name, email and resume.
