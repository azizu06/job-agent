# Troubleshooting

Common problems during runs and how to fix them.

| Problem | Fix |
| --- | --- |
| Chrome never shows "Allow remote debugging?" | Check Chrome is 144 or later and open. Turn the switch on at `chrome://inspect/#remote-debugging`, then restart Chrome |
| The agent opened a new, empty Chrome | The browser MCP is missing `--autoConnect`. Run setup again, or copy the line from [docs/how-it-works.md](how-it-works.md#browser) |
| "Allow" pops up for every job | Expected. Each job opens its own connection. Click Allow, or turn on auto-allow on a Mac |
| Resume upload fails with "not within any of the configured workspace roots" | You set a custom `JOB_AGENT_HOME`. The agent copies the PDF to a temp folder and retries. If it still fails, set `--workspace=` to your folder |
| Scan says "checkpoint not found" or reads old jobs | Your JobRight feed is not sorted by Most Recent. Sort it, then ask your agent to "recapture my JobRight feed" |
| Jobs run one at a time | The `job-applier` subagent is missing. Run setup again; it copies the file to `~/.claude/agents/` |
| A scheduled run stops at the first prompt | Headless runs need tools pre-approved. Copy the allow-list from [skills/job-run/SKILL.md](../skills/job-run/SKILL.md) |
| Auto-allow clicks nothing | Grant Accessibility to the Python path that `enable` printed, and set Chrome's language to English |
| No resume PDF, only a `.md` or `.tex` file | Install `tectonic` and PyMuPDF (`pip install pymupdf`). Without them the agent hands you the source file and cannot run the layout gate |
| A form shows "needs corrections" after filling | The portal ignored a field. The agent re-reads every field before it calls a form ready; if it flags one, fix it by hand |
| Most jobs park as `Needs you: sign-in` | Sign in to Google in that Chrome, and keep Sign in with Google allowed in setup. Workday needs one account per company |

First-time install problems (missing `node` or `python3`, JobRight sign-in) are in [getting-started.md](getting-started.md#if-something-goes-wrong).

Still stuck? Open an issue with what you ran, what you expected and the exact error text. Leave out your name, email and resume.
