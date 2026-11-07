---
name: tailor-resume
description: Build a one-page tailored resume for one job from the user's master resume, choosing the best-matching entries and alternate bullets and working in job-description keywords truthfully. Reports keyword coverage before and after and lists missing terms for the user to decide. Never invents metrics, tools, or experience. Use when the user asks to tailor a resume to a job, or as part of job-run.
---

# tailor-resume

Python: commands below say `python3`. Use `python_cmd` from `profile/preferences.yaml` instead when it is set (setup writes `py -3` on Windows).

## The model

The master resume (path in `preferences.yaml` as `master_resume`) holds everything the user has done, with alternate bullets under each entry. A tailored resume is a new copy built from it for one posting. The master is never edited during tailoring. Layout and rules: `../job-setup/assets/master-resume.md` (next to this skill's folder).

## Hard rules

- Never add a metric, tool, employer, title, date or experience that is not in the master. Rewording is fine; new facts are not.
- Coverage counts only terms the user can truthfully claim.
- Every job gets its own copy in a unique folder: `<workspace>/resumes/tailored/<company>-<role>-<req or date>-<short random id>/`. Parallel runs must never share a folder.
- Never put AI-tool usage in bullets unless the master has it.

## Steps

1. Save the full job description to a text file if it is not already (`state/jd/<job_key>.txt`).
2. Baseline: run `python3 scripts/keyword_coverage.py --jd <jd> --resume <master> --company "<company>" --json` from this skill's folder. `--company` drops words built from the employer's name (AcmeLabs, TeamAcme). If the posting has tool names the extractor misses, write a terms file (`term | alias`) and pass `--also`. If it still lists words that are not skills (a street, a product name), say so in the report instead of chasing them.
3. Pick entries: never use a master bullet that still ends in `<!-- confirm -->` (setup drafted it and the user has not confirmed it); ask the user about it instead. Rank by direct match to the posting, then strength of result, then recency. Keep the cap of bullets per entry (default 3). Swap in alternates from the master to cover more terms. Mirror the posting's spelling ("CI/CD", "JavaScript") when the master supports the claim.
4. Skills rows: rebuild from the master's Skills bank around the posting's required and preferred terms. Each row must fit on one line.
5. Write the copy (same format as the master: Markdown or LaTeX).
6. Score again with `--before <master>` (same `--company`) to get the before and after report.
7. Run `python3 scripts/resume_check.py --master <master> --resume <copy>` (Markdown masters). It fails on: too many bullets per entry, likely 3-line bullets, any number not found in the master, repeated opening verbs, and a first project bullet that does not say what the project is. Fix every failure.
8. Render to PDF. LaTeX: `tectonic copy.tex`. Markdown: `pandoc copy.md -o copy.pdf --pdf-engine=tectonic` (or `--pdf-engine=xelatex`); pandoc alone cannot make a PDF, so a Markdown master needs both pandoc and a LaTeX engine. If pandoc is missing or fails to run, use `python3 scripts/md_to_tex.py copy.md` then `tectonic copy.tex`; it needs only tectonic. Then render page 1 to PNG with `pdftoppm -png -r 80 copy.pdf page` (from poppler; if your `pdftoppm` has no `-png`, use `pdftopng -r 80 copy.pdf page` or `sips -s format png copy.pdf --out page.png` on a Mac) and look at it. Check: exactly one page, no bullet over 2 lines, no orphan line holding one or two words, each skills row on one line. If a tool is missing, say so and hand the user the source file.
9. **Missing terms.** List every JD term still missing with one line on what it means. Ask the user about all of them in one batch. For each one the user confirms, add it to the master's "Confirmed terms" section (with where they used it) and rebuild. Do not ask about the same term twice.

## Report

- Copy path and PDF path
- Coverage: master vs tailored, with matched and still-missing lists
- Before and after of every changed bullet and skills row
- `resume_check.py` verdict and what you saw in the PNG
- Questions about missing terms, in one list
