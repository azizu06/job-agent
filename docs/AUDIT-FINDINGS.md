# Audit findings for the integrator

A beginner-viewer audit of the repo, done while rewriting the README (branch `w3-readme`). The README and docs now answer each question below. The items listed here need changes in `skills/`, `commands/` or `tests/`, which this branch does not touch.

Severity: **high** means a beginner hits it on a normal first run; **medium** means a common case breaks or a doc claim depends on it; **low** means polish.

## Questions a viewer would DM, and where they are answered

| Question | Answered in |
| --- | --- |
| What is JobRight? Do I need to pay for it? | README FAQ, docs/getting-started.md step 3 |
| Is it free? | README FAQ |
| What does it cost in tokens? | README FAQ (one measured rig run; see finding 1) |
| Does it work on Windows? Linux? | README FAQ, docs/getting-started.md |
| Will I get banned? | README FAQ and Safety |
| Can it use LinkedIn Easy Apply? | README FAQ |
| What if I have no resume? | README FAQ (see finding 2) |
| Will it lie on my resume? | README FAQ |
| Does it submit on its own? | README Safety and FAQ |
| What happens at a CAPTCHA or sign-in page? | README FAQ, docs/how-it-works.md |
| Where does my data go? | README FAQ, docs/how-it-works.md "Your data" |
| Does my computer need to stay on? | README "What runs on its own" and FAQ |
| Only internships? | README FAQ |
| Which agents does it work with? | README FAQ |
| How do I install Node, Python, Chrome? | docs/getting-started.md |
| Which clicks do I have to make myself? | README table, docs/getting-started.md |

## Findings

Status after integration: fixed 2, 3, 4, 5, 6, 9, 10, 12 (12 by a `python_cmd` preference and a note at the top of each skill). Open: 1 (needs a real dry run), 7, 8, 11.

### 1. No measured token or cost numbers for real portals (medium)

The only data point is the rig run (`p2run`): Claude Sonnet, 5 postings, 3 forms filled, about 10.8M cache-read input tokens, 0.5M cache-write, 28.5k output, $2.78 at list price. The README quotes it with a caveat. Real Workday and Greenhouse pages produce far larger snapshots.

- Measure one real dry run on 3 to 5 live postings and replace the README number.
- Suggest `job-run` step 6 (Summarize) report the run's token use or cost when the agent exposes it, so users see it per run.

### 2. Setup has no path for a user with no resume (high)

`skills/job-setup/SKILL.md` step 4 covers "a path" or "only a one-page resume". A student with no resume at all, the most likely DM, has no branch. The README FAQ now says setup can start one from the template.

- Add a branch to step 4: interview the user (school, jobs, projects, clubs, skills), draft `resumes/master.md` from `assets/master-resume.md`, and mark every bullet for the user to confirm before any tailoring. Keep the no-invented-facts rule explicit.

### 3. `pandoc` alone cannot make a PDF (medium)

`skills/tailor-resume/SKILL.md` step 8 says "for example `pandoc` for Markdown". `pandoc file.md -o file.pdf` needs a LaTeX engine; without one it fails. The rig run reported "`pandoc` and `pdftoppm` fail on this machine" and fell back to `tectonic`. The old README listed "`pandoc` or `tectonic`" as if either were enough.

- In step 8, name the command: `pandoc in.md -o out.pdf --pdf-engine=tectonic` (or `xelatex`), and say both tools are needed for Markdown masters. The new docs tell users to install pandoc, tectonic and poppler together.

### 4. macOS notification offered on every OS (medium)

`skills/job-run/scripts/notify.py` method `macos` shells out to `osascript`. `skills/job-setup/SKILL.md` step 8 offers "macOS notification" without an OS check, so a Windows or Linux user can pick it and every parked-job notification fails.

- Offer `macos` only on macOS. Consider a Windows toast (PowerShell `New-BurntToastNotification` is not built in; ntfy is the safe cross-platform default).

### 5. JobRight cards that link only to LinkedIn are undefined (medium)

`job-gate` step 2 opens "the employer's live posting (the ATS page the aggregator links to)". Some aggregator cards link to a LinkedIn job. The hard rule bans LinkedIn automation, but neither `job-gate` nor `apply-fill` says what to do.

- In `job-gate`, if the only apply link is on linkedin.com (or another social site), cut it with reason `linkedin_only` and list it for the user, or search the company's careers page for the same req ID. Never open the LinkedIn posting.

### 6. Setup and scan disagree on changing the JobRight sort (low)

`job-setup` step 9 says "select it yourself if the sort control shows another option". `job-scan` step 2 says "do not change the user's sort setting". Both are defensible, but a reader cannot tell which wins.

- Make scan's rule explicit: setup may set Most Recent once with the user present; scans never change it.

### 7. Cover letter uploads are not covered (medium)

`apply-fill` covers the resume file input and free-text essays. Many Greenhouse and Lever forms have a separate cover letter upload or "Enter manually" box. Only `ats-gotchas.md` mentions it, for button scoping. Users will ask "does it write cover letters?".

- Add a rule: an optional cover letter field stays empty unless `written_answers: draft` and the user opts in with a new `cover_letter: draft | leave` setting; a required one is drafted under rule 11 or parks as `Needs you: cover letter`.

### 8. No command for status sync (low)

`commands/` has only `setup` and `run`. Status sync runs only when the user asks in prose. A `/job-agent:sync` command (and mention in `job-run` scheduling) would make "check my replies" one step.

### 9. Keeping the computer awake is not in the skills (low)

Scheduled runs fail silently if the Mac sleeps. `job-run` "Running every N hours" could mention `caffeinate -i` on macOS, and Windows power settings, and setup could ask when the user enables scheduling.

### 10. `${HOME}` inside the user-level agent file is unverified (medium)

`skills/job-setup/assets/job-applier.md` passes `--workspace=${HOME}/.job-agent` in `mcpServers` args. The plugin's `plugin.json` gets variable expansion; it is not confirmed that Claude Code expands `${HOME}` in a user agent's frontmatter. If it does not, uploads fail with "not within any of the configured workspace roots" for every parallel applier.

- Have setup write the absolute workspace path into the copy (step 5 already says to when the workspace is not `~/.job-agent`; make it unconditional), or add a rig test.

### 11. Beginners do not know how to add the Gmail, Notion or Sheets connectors (low)

Setup "checks which MCPs exist". For a missing one it says what it enables but not how to add it. In Claude Code these are claude.ai connectors or `claude mcp add`; in Codex and Cursor they differ.

- Have step 10 print the add command or settings path for the user's agent, or link a short doc.

### 12. Windows `python3` substitution relies on the agent (low)

Every SKILL.md says `python3` with a one-line note to use `py -3` on Windows. Agents miss notes. The headless allow-list in `job-run` already calls this out.

- Consider a tiny launcher note at the top of each skill's Steps, or have setup record `python_cmd` in preferences and have skills use it.

## Not changed on purpose

- `skills/job-run/SKILL.md` still holds the headless allow-list. The README links to it instead of copying it.
- The e2e rig README already documents the demo world; the new demo GIF is built from it (sources in `assets/src/`).
