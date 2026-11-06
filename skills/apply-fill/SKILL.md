---
name: apply-fill
description: Fill one job application in the user's Chrome through a browser MCP, using the user's standing answers and a tailored resume, and stop at the final Submit by default. Encodes safe form rules (no Enter, no Escape, real clicks and typing, verify every field, no reloads) and an opt-in guarded auto-submit. Use when the user asks to fill or apply to a job, or as part of job-run.
---

# apply-fill

Read `references/ats-gotchas.md` before touching a Workday, Greenhouse, Lever, Phenom, Ashby or iCIMS form.

## Inputs

- One queue item (`apply_url`, `company`, `req_id`, `job_key`), the tailored resume PDF path, `profile/standing-answers.yaml` and `profile/preferences.yaml` from the workspace (`$JOB_AGENT_HOME` or `~/.job-agent/`).
- Your own browser MCP connection: chrome-devtools MCP with `--autoConnect` (the user's main Chrome) or `--browser-url=http://127.0.0.1:9333` (dedicated profile). In main mode this is the user's real browser: touch nothing but your own tab.

## Tab discipline

- Open the application once with `new_page` (background). Note your tab's page id from the result or `list_pages`. Pass it as `pageId` on every tool that takes one (chrome-devtools-mcp 1.10.1 requires it on click, fill, type_text, press_key, take_snapshot, upload_file and evaluate_script). Never select, close or navigate a tab you did not open.
- Page ids are numbered per MCP connection. Two appliers can both have a page 5 that are different tabs; never pass a page id from one connection to another.
- One writer per tab. When several agents run, each needs its own browser MCP connection with an explicit target (`--autoConnect` or `--browser-url`), or the MCP may launch a throwaway browser. Never share one tab-switching helper or one MCP connection across parallel agents.
- Background tabs can drop input. If typed values do not register, enable focus emulation on your page (CDP `Emulation.setFocusEmulationEnabled` with `enabled: true`) before filling.
- Before every write, confirm the page URL still belongs to this job.

## Hard rules

1. **Never press Enter or Return in a form.** It can submit. Commit dropdown choices by clicking the option. Never set `submitKey` on `type_text`. The one exception is listed in the gotchas file (Workday searchable prompts).
2. **Never press Escape inside a dropdown.** Close it by clicking a neutral area.
3. **Never reload a tab that has been filled.**
4. **Real interaction for every field.** Click the field, then type (`click` then `type_text`, or `fill` on plain inputs). For radios, checkboxes and consent boxes, click the visible control. Do not set `.value` or `.checked` from JavaScript: Lever and Ashby can keep Submit dead or show "needs corrections" for JS-set fields. After each field, read the value back and fix mismatches.
5. **Upload the resume through the file input** with `upload_file`. chrome-devtools-mcp only reads and writes files inside its allowed folders (the agent's project folders, folders passed with `--workspace`, and the OS temp folder). The plugin passes `--workspace=${HOME}/.job-agent`. If the upload says the path "is not within any of the configured workspace roots" (for example a custom `JOB_AGENT_HOME`), copy the PDF, keeping its filename, into a new folder under the OS temp folder (`python3 -c "import tempfile; print(tempfile.gettempdir())"`), upload it from there, and delete that folder after the job. Save screenshots the same way. If the upload still fails, fall back in order: CDP `DOM.setFileInputFiles` on the input node, then a base64 `File` assigned through `DataTransfer` and a dispatched `change` event. Confirm the attached filename or size is shown.
6. **After every click or step,** check that the URL is not a thanks, confirmation or "application received" page.
7. **Unknown multi-step ATS:** some (Phenom and similar) record the application before the final step. On an unfamiliar flow, stop after step 1, report the step count, and after each Next search email for a receipt before claiming "not submitted".
8. **Sign-in, account and verification walls** go to the `portal-auth` skill. Its default flow tries Sign in with Google, then Microsoft, then LinkedIn (with an account already signed in to this Chrome), then a login the browser already saved, then parks the job. Typed passwords, account creation, resets and code entry happen only in its optional credential mode (off by default); many agents (including Claude) will refuse those steps under their own safety rules, and when they do, the job parks. If `portal-auth` returns parked, this job is parked: stop work on it (rule 10).
9. **CAPTCHA or bot check: park, never solve.** Leave the tab open and filled, set the tracker row to `Needs you: captcha`, send a notification with `../job-run/scripts/notify.py`, report the page id and URL, and stop work on this job so the run moves on. Park the same way for anything else only the human can do (SSN or payment requests, codes the agent cannot read, consent beyond basic sign-in).
10. **A step you decline or cannot do: park it the same way.** Some agents will not type passwords, create accounts or enter verification codes, because of their own policies or the user's tool settings, and some tools cannot do a step (an upload, a widget that ignores input). That is expected. Park exactly as for a CAPTCHA: keep the tab open and filled, set the tracker row to `Needs you: <reason>` (for example `Needs you: sign-in`, `Needs you: create account`, `Needs you: email code`, `Needs you: resume upload`), notify, report, and stop work on this job. Try the step once; never retry it in a loop, never wait in chat for approval, and never stop or fail the whole run. A parked job is a normal result.
11. **Essay and free-text questions** ("why us", "tell us about a project"): leave empty and report the exact question, limit, and whether it is required. Short factual boxes (URLs, dates, yes or no, location) you fill from standing answers.
12. **Salary boxes:** use the posted number (or midpoint, per `pay_expectation`) and report where it came from.
13. **Never invent answers.** A blank standing answer means stop and ask. Do not write motives or metrics for the user.
14. **Before calling a form ready,** take a fresh snapshot and check: no required-field error text, every required radio group has a choice, every required consent box is checked, the resume shows as attached, conditional fields that appeared after earlier answers are filled.

## Submit

Default (`auto_submit: false`): stop when only the final control remains. Report its exact label. Treat every control labelled Submit, Apply, Send, Finish, or a Next on a flow known to record early, as final. Add a tracker row with status `Ready`.

Opt-in (`auto_submit: true`), all guardrails still apply:
- `dry_run: true` means fill and read back, never press the final control.
- Daily cap: `tracker_csv.py count --status Submitted --date today` must be below `caps.daily_submit_cap`.
- Per-company cap: count for the company within its window must be below the cap.
- Never submit on a page with a CAPTCHA (park it instead), a sign-in wall, a GenAI ban, an empty required essay, or any unresolved error.
- Pre-submit read-back: snapshot the form, write every question and answer to `state/submissions/<job_key>.json`, and put its path in the tracker `notes` as exactly `read-back: <path>` (that prefix, with the hyphen; status-sync and the checks look for it).
- Then click the final control once. Confirm by URL change and an email receipt (see `tracker`), not by on-page "thank you" text alone.

## Report

Status (`ready`, `submitted`, `parked: <reason>`, or `blocked: <reason>`; a step you declined or could not do is `parked`, never an error), page id and URL, every field set (question and answer, and which answers you derived from the master resume or education dates rather than read from standing answers), resume attached (filename), essays left empty (text and limits), required fields left empty and why, blockers, the exact label of the final control and whether it was pressed, and a screenshot path. Browser extensions (Simplify, JobRight and similar) draw panels over the page that can show the user's real name and resume; crop screenshots to the form before you share them.
