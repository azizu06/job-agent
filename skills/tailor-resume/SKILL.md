---
name: tailor-resume
description: Build a one-page tailored resume for one job from the user's master resume, in the default LaTeX layout, choosing the best-matching entries and alternate bullets and working in job-description keywords truthfully. Holds every content, framing and layout rule, and the gate (content check, PDF layout check, three PNGs) that must pass before any upload. Reports keyword coverage before and after, writes a review file and an interview-defense sheet, and asks about every missing term. Never invents metrics, tools, or experience. Use when the user asks to tailor a resume to a job, build or rebuild any resume PDF, or as part of job-run.
---

# tailor-resume

Python: commands below say `python3`. Use `python_cmd` from `profile/preferences.yaml` instead when it is set (setup writes `py -3` on Windows). Scripts live in this skill's `scripts/` folder.

Tools: `tectonic` builds the PDF. PyMuPDF (`python3 -m pip install pymupdf`) runs the layout check and renders the PNGs. Everything else is standard-library Python. pandoc is not needed.

## The model

- The master resume (`master_resume` in `preferences.yaml`) holds everything the user has done. Its printed page is the user's **general resume**: the current best bullets, one page, passing the gate. Alternates (extra bullets, entries, projects and skills rows) live in `\iffalse ... \fi` blocks (LaTeX) or `<!-- alt --> ... <!-- /alt -->` blocks (Markdown), so they never print.
- The default layout is `../job-setup/assets/master-resume.tex`. A Markdown master renders in the same layout through `scripts/md_to_tex.py`. An older Jake's-template `.tex` converts with `python3 scripts/apply_uniform.py file.tex`.
- A tailored copy is a new file built for one posting. Tailoring never edits the master.

## Files for each job

Every job gets its own folder: `<workspace>/resumes/tailored/<company>-<role>-<req or date>-<short random id>/`. Parallel runs never share a folder.

- `<First>-<Last>-Resume.tex` (or `.md` plus the generated `.tex`) and the built `.pdf`
- `gate/` with the three PNGs, and `<name>.pdf.gate.json`, the gate receipt
- `<workspace>/reviews/<job_key>.md`: the review file (see Report)
- `<workspace>/interview-prep/<job_key>-defense.md`: the defense sheet

## Copies

1. Start each job from the best existing copy: score the master and every copy in `resumes/tailored/` against this posting with `keyword_coverage.py`, and copy the highest scorer into the new folder. Use the master when nothing beats it. Never tailor an old copy in place.
2. Never edit a copy that was already submitted. Its folder is a record of what the employer has.
3. A change the user asks for on their general resume goes into the master's printed page in the same pass. Rebuild the master PDF and run the gate on it. Report it as "general (master) updated".
4. An older copy that breaks a current rule (a 4th bullet, a short line) gets fixed before it is reused.
5. A fix the user asks for on one copy is a rule for the whole batch: find the same pattern in the other copies of this run, fix them, and name them in the report.

## Content rules

Truth
- Never add a metric, tool, employer, title, date or experience that is not in the master. Rewording is fine; new facts are not. Every number must trace to the master (`resume_check.py` fails any that do not).
- Put a metric in every bullet where the master has real evidence for one. Write both ends of a change with units: "from 15 minutes to under 2", never "15 to 2".
- Never use a master bullet that still ends in `<!-- confirm -->`; ask the user about it.
- Never weaken or delete a claim the user approved in the master. Reword it only to add posting terms.

Selection and order
- Re-rank the projects on every build: direct match to the posting first, then strength of result, then recency. Order bullets inside each entry the same way, headline result first. Decide this yourself.
- When space runs out, drop the entry least relevant to the role. Never shrink the template.
- Hard cap: 3 bullets per entry. Raise coverage by swapping in alternates, rewording and reshaping Skills rows, never by adding a 4th bullet. A lower coverage number (still at the target) beats an inflated entry.
- Each opening verb at most twice on the page.

What bullets say
- The first bullet of every project says what the project IS in plain words, as a short "<noun> that <does what>" phrase in its first 60%: "a web app that shows live arrival times for campus shuttles". Detail and metrics follow in the same bullet. A tailored rewrite that drops the identity phrase fails.
- A bullet about a hackathon win names the hackathon and its host school next to the award and the project count: "winning Best Civic Hack of 180 projects at Lakeside University's LakeHacks". Never drop the name or the count to save space; cut filler instead.
- Name the real artifact: the concrete model, tool, format or technique, then the outcome and its number.
- No wording that makes real work sound fake: mock, synthetic, simulated, sandbox, testnet, fake, dummy, toy, demo, proof of concept, prototype, test data, seeded, hard-coded, staged. Write the real mechanism instead. Allowed: "software-in-the-loop simulation" and "staged rollout/release/deploy".
- No bullet whose point is using AI coding tools (Claude Code, Codex, Copilot, Cursor). Those go in a Skills row, and a posting's mention of them counts as covered there.

Skills rows
- Niche terms go in bullets. Commonly searched keywords (languages, frameworks, AWS, Docker, CI/CD, PostgreSQL, React) go in Skills.
- Rebuild the rows around the posting's required and preferred terms. Mirror its spelling ("CI/CD", "JavaScript") when the master supports the claim. Give Skills slots to keywords not already on the page (`resume_check.py` warns with SKILLDUP).
- Keep one-word labels. A tailored copy may add one posting-shaped row (for example `Concepts`) for concept keywords the posting lists. Every row fits on one line, and the last row reaches the right edge.
- When a line needs a word to reach the edge, pick the strongest truthful posting term yourself and report the choice. Do not ask.

Framing
- Impressive but defensible: bullets can be bold and high-level, as long as the core claim is real and the user can defend it in an interview. Never rewrite an approved bullet into a hedged, literal one.
- Use the most impressive sourced form of each number: rates and multipliers over small absolute counts.
- Every new or changed bullet gets a one-line interview defense in the defense sheet, never in the bullet. Caveats (scale, time limits, team contributions) live only in the defense sheet, phrased neutrally.

## Coverage

- Count only terms the user can truthfully claim. Tools the user never used, and culture or values words ("ownership", "curiosity"), leave the denominator: list them in a terms file and pass `--exclude`.
- Target: at least 95% of claimable terms, 100% whenever every claimable term fits.
- Report general vs tailored: the master's printed page (`--before <master>`) against the copy, with the delta.
- Never drop a missing term silently. Give each one a one-line plain meaning and ask the user about all of them in one batch. A confirmed term goes into the master the same turn (the matching Skills row, or the "Confirmed terms" section with where they used it), then rebuild. Never ask about the same term twice.

## Steps

1. Save the full job description to `state/jd/<job_key>.txt` if it is not there yet.
2. Baseline: `python3 scripts/keyword_coverage.py --jd <jd> --resume <master> --company "<company>" --json`. `--company` drops words built from the employer's name. If the posting has tool names the extractor misses, write a terms file (`term | alias`) and pass `--also`. Words that are not skills (a street, a product name) go in the `--exclude` file and the report.
3. Pick the starting copy (Copies, step 1) and write the new copy in its folder.
4. Choose entries and bullets by the Content rules: re-rank projects, swap alternates in, reword toward the posting, rebuild the Skills rows. Drop `\iffalse` blocks you do not use.
5. Score again with `--before <master> --exclude <file> --min 95`.
6. Content check while you edit: `python3 scripts/resume_check.py --master <master> --resume <copy>`. It fails on: unconfirmed bullets, more than 3 bullets, likely 3-line bullets, numbers not in the master, an opening verb used 3+ times, a project first bullet without its identity phrase, a hackathon win without host school and count, not-real wording, AI-tool bullets, and a LaTeX project heading that is not `\projtitle{url}{name}`. Fix every failure. Read the warnings (NOMETRIC, SKILLDUP) and act on them when the master has the evidence.
7. Build the PDF. LaTeX: `tectonic -X compile <copy>.tex`. Markdown: `python3 scripts/md_to_tex.py copy.md -o copy.tex`, then tectonic. While rewording for line fill, `python3 scripts/layout_check.py <copy>.pdf --bullets-only` is the quick loop.
8. **Gate (mandatory before any upload or send):**
   `python3 scripts/resume_gate.py --pdf <copy>.pdf --resume <copy>.tex --master <master>`
   It runs the content check and `layout_check.py` on the PDF, renders `full-110dpi.png`, `top-half-220dpi.png` and `bottom-half-220dpi.png` into `gate/`, and on a pass writes the receipt `<copy>.pdf.gate.json`. It must print `content violations: 0`, `violations: 0` and `VERDICT: PASS`. The layout check holds:
   - one page, filled to full height (bottom gap at most 43.3pt)
   - every bullet at most 2 rendered lines, every line (the last one too) at least 95% of the text width; no half-empty last lines
   - no orphan or hanging line anywhere (a wrapped Skills row counts), no wrap line without a bullet; every Skills row on one line, the last reaching the right edge
   - uniform spacing: bullet pitch, heading to first bullet, entry to entry, section gaps, project underline depth, plus a pixel check of the white space under each heading
   - header centered on one contact line, nothing outside the margins, every row on its template column, dates and locations on one right column, all four sections (Education, Experience, Projects, Technical Skills), one font size per row type, bold Skills labels
   Fix a failure by cutting filler, adding true detail, or changing a shared length in the template (`\sectionabove`, `\entrygap`, ...). Never add per-entry spacing and never change the template's fonts or margins. Rebuild and run the gate again.
9. **Visual review, every time.** Read all three PNGs yourself before calling the resume ready. Look for a lone word on a line, uneven underlines or gaps, cramped or ragged lines, anything the numbers might miss. A PDF rebuilt after the gate needs the gate again; `python3 scripts/resume_gate.py --verify <pdf>` fails when the PDF changed since its receipt.
10. Write the review file and the defense sheet (below), then ask about missing terms (Coverage). For each confirmed term, update the master and rebuild from step 4.

In the scheduled loop, do not wait for answers: write the questions into the review file's "Terms to confirm" list and the run summary, and the user answers them later.

## Report

The review file `<workspace>/reviews/<job_key>.md` holds, and the report repeats:
- Copy path, PDF path (absolute, clickable) and which copy it started from
- Coverage: general (master) X% vs tailored Y% (matched/total, delta), the matched and still-missing lists, and the excluded terms with why
- Added terms: JD term, the exact phrase on the page, and where (bullet, Skills row)
- Before and after of every changed bullet and Skills row
- Final project order with a one-line reason per position, even when unchanged
- Judgment calls: fill words chosen, alternates swapped, entries dropped
- Self-review, one pass/fail line each, with the bullet that best shows it: impressive but defensible framing; each project's first bullet says what it is (quote it); hackathon wins named with host school and count; no not-real wording; coverage at target
- Gate output (`content violations: 0`, `violations: 0`, `VERDICT: PASS`) and what you saw in the three PNGs
- Terms to confirm: every missing or excluded term with its one-line meaning

The defense sheet `<workspace>/interview-prep/<job_key>-defense.md` has, for each new or changed bullet: the bullet, a plain-language interview defense (what was built, how, where the number comes from), and any caveat.
