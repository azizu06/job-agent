---
name: your-voice
description: Writes every free-text job-application answer ("why this company", "tell us about a project", short essays, cover letter boxes) from the user's real facts only. Drafts two angles and keeps the more specific one, runs the built-in humanizing layer (craft moves plus an AI-tell catalog), optionally rewrites in the user's own voice from their writing samples, rules and corrections, self-audits, and checks characters and length with writecheck.py. Also sets up the optional voice profile and records the user's corrections. Use from apply-fill and job-run for every written answer, during job-setup's voice step, or when the user edits or rejects an answer.
---

# your-voice

Python: commands below say `python3`. Use `python_cmd` from `profile/preferences.yaml` instead when it is set (setup writes `py -3` on Windows).

Every written answer goes through this skill before anything is typed into a form. Short factual boxes (URLs, dates, yes or no, location, salary) do not; apply-fill fills those from standing answers.

Layers, in order:

1. Facts-only draft from two angles; keep the more specific one.
2. Humanize pass, always on: `references/humanize.md`.
3. Voice layer, optional: the user's samples, rules and corrections in `voice/profile.md`.
4. Self-audit, then `scripts/writecheck.py`, then paste.

## Files

All in the workspace (`$JOB_AGENT_HOME` or `~/.job-agent/`):

| Path | What it is |
| --- | --- |
| `voice/samples/` | Optional. 2 to 5 things the user wrote themselves, one file each |
| `voice/profile.md` | Optional. How they write: sentence length, openers, connectives, words they use and avoid, their own rules, corrections. Template: `assets/profile.example.md`. Missing means the humanizing layer only |
| `voice/facts.md` | Extra facts the user gave for answers that are not in the resume (why a field interests them, a club, a class). Optional |
| `voice/approved/` | Answers the user approved or submitted, one file each, with the question at the top |

From this skill: `references/written-answer-standard.md` (what a strong answer says: a decision with its mechanism, research tied to the user's own work, length ranges, a cut list, the cross-form rules and the reviewer's test), `references/humanize.md` (craft moves and the AI-tell catalog), `scripts/writecheck.py` (character, length, pattern and cross-form check, stdlib only), `assets/profile.example.md`.

`voice/approved/` is the exemplar slot: answers the user reviewed and approved, or submitted. A fresh writer writes far better with a few of them in hand, so keep it filled (see Corrections loop). It holds only the user's own answers, never examples copied from anywhere else.

## Setup (called by job-setup, step `voice`)

1. Ask exactly: "Want answers to sound like you? Paste 2-5 things you've written, or add your own writing rules. Skip to use the humanizing layer only."
2. **Samples.** Only text they wrote without AI help: essays, cover letters, school applications, long emails or messages. Save each as `voice/samples/<n>.txt`. Measure them with `python3 scripts/writecheck.py stats <workspace>/voice/samples/*`. Write `voice/profile.md` from `assets/profile.example.md`, filling in what the numbers and a read of the samples show: median sentence length, contractions, dashes or exclamation marks, how sentences open, connectives, words and phrases they use often, words they never use. Set `Source:` to the sample count and date. Write rules about style only; copy no facts or sentences from the samples into the profile.
3. **Rules.** If they give writing rules ("never say passionate", "keep it under 100 words", "I use dashes"), write them under "Their rules" in `voice/profile.md`, starting from the template if there is no profile yet.
4. Show the profile and ask "Does this sound like you? Anything to change?" Apply their changes.
5. **Skip.** Write no profile. Answers use the humanizing layer only. Say they can add samples later by asking "learn my writing voice".
6. Create `voice/approved/` and an empty `voice/facts.md` if missing, in every case.

## Draft one answer

Inputs: the question text, its limit (`maxlength`, "N characters", "N words", or none), the company, the job description at `jd_path`, the tailored resume, the master resume, `profile/standing-answers.yaml`, and the files above.

Read `references/written-answer-standard.md` first, every time. When you draft for a whole form (the `writer` mode in `apply-fill`, where appliers leave essays empty and report each question's exact text, limit and required flag), take all of its questions together, plan which story carries which answer so none repeats, then draft each one with the steps below.

1. **Facts only.** List the facts you may use, each with its source: master resume, tailored resume, standing answers, `voice/facts.md`, and the job description (for what the company and role are). Nothing else. Never invent an employer, project, skill, tool, date, number, title, award or motive. If the question needs a fact you do not have (for example "why do you want to live in Austin"), do not make one up: draft from what you have and list the gap, or park as `Needs you: written answer` when no honest answer is possible.
2. **Depth from approved answers.** Read up to 3 files in `voice/approved/` closest to this question to see what the user chose to say and how much detail they like. Never copy a sentence from them verbatim, and never reuse an answer written for another company.
3. **Two drafts, two angles.** Each draft carries at least one decision with its mechanism (standard, point 1). Draft A from the user's side: lead with the one experience that best matches the posting, then tie it to the role. Draft B from the posting's side: lead with what the role needs, then show one real thing the user did that fits. Both first person, plain, under the limit, using the craft moves in Part 1 of `references/humanize.md`.
4. **Keep the more specific one.** Count the concrete, checkable facts per sentence (named project, tool, number, result) and the tells from Part 2. Keep the draft with more facts and fewer tells. You may move one better sentence over from the other draft.
5. **Humanize pass (always).** Apply `references/humanize.md` in full: strip every tell in Part 2, check the craft moves in Part 1, and respect "Do not over-correct". Keep every fact; this pass changes how it reads, never what it says.
6. **Voice layer (if `voice/profile.md` exists).** Rewrite to match it: sentence length, openers, connectives, contractions, words they use and avoid, their rules. Corrections and their rules win over everything else, including `humanize.md`.
7. **Self-audit.** Answer both questions in your report, naming specific lines:
   - What still reads as AI? Fix each line you name.
   - Which fact could the user not defend in an interview, or which sentence goes beyond a source? Cut it, or keep it modest and list it word for word under "inferred sentences".
8. **writecheck.** Save the answer to `<your output folder>/answers/<slug>.txt` and run `python3 scripts/writecheck.py check <file> --max-chars <limit>` (or `--max-words`). With no stated limit use `--max-words 150`. Add `--allow-dashes` and `--allow WORD` only when `voice/profile.md` says so. Fix every problem and run it again until it prints `CLEAN`. Use `--fix <out>` only for quotes, invisible characters and odd spaces.
9. **Across the form.** With two or more answers for one form, run `python3 scripts/writecheck.py crossform <answer files> --allow "<company>"` and fix every shared story until it prints `CLEAN`.
10. **Reviewer's test.** Read each answer as a skeptical hiring engineer (the test at the end of the standard). Rewrite any answer that fails it, then run steps 8 and 9 again.
11. **Return** the final answer, its character and word count, the source of each fact, the inferred sentences, the self-audit, and the last writecheck output (and the crossform output for a whole form). apply-fill types the answer only after this.

Never send a draft to a second model, a paraphrasing service or an "AI humanizer" website to reword it. The rewrite happens here, under the facts-only rule, so nothing new gets added and the user's text stays with them.

## Corrections loop

When the user edits an answer (in the form, in chat, or by saying "I would not say that"), or rejects one:

1. Compare their version with yours and name the rule behind the change in one line (for example "never says 'I am eager'", "puts the result first", "shorter: about 80 words").
2. Append it to the Corrections section of `voice/profile.md` (create the profile from `assets/profile.example.md` if it does not exist): `- YYYY-MM-DD: <rule> (was: "<your text>", now: "<their text>")`, with today's date. Keep each quote under 15 words.
3. If the rule changes a measured default (length, dashes, contractions), update that line too.
4. Apply it to every answer still waiting in this run.

When the user approves an answer, or it was submitted, save it to `voice/approved/<YYYY-MM-DD>-<company>-<question-slug>.md` with the question and limit at the top.

## Never

- Use a fact that is not in the listed sources.
- Copy sentences from samples or approved answers verbatim into a new answer.
- Put samples, profiles or answers in this repo; they live only in the workspace.
- Skip the humanize pass or writecheck, or type an answer that is not `CLEAN`.
