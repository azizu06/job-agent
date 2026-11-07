# Written-answer standard

Read this, and the user's approved answers in `voice/approved/`, before drafting or reviewing any written answer. The approved answers show the depth the user accepts. Match their depth; never reuse their sentences on another form unless the same fact fits.

The humanize pass (`humanize.md`) controls how an answer reads. This file controls what it says.

## What a good answer has

1. **A decision only this person could describe.** Each long answer carries at least one story with its mechanism: what was at stake or broke, what they decided or changed and why, and what happened. Include real pushback or a tradeoff when the sources have one.
   - Strong: "I made the retry job skip any order already marked paid, because charging someone twice is worse than a late email."
   - Strong: "A teammate pointed out that the cache served stale prices after a sale ended. I kept the cache for product pages and read prices from the database at checkout."
   - Weak: "the data pipeline that keeps improving our results." It names a thing and shows no decision.
2. **Research serves the story.** At most one company fact per paragraph, tied to the user's own work in the same sentence or the next. The reader never has to build the bridge. A statistic with a wish attached is not evidence.
3. **Cover letters.** Say who the user is and what they do in the first lines, then two stories with mechanism, each mapped to the posting's own words, then one concrete closing line. Never end on a statistic, and never spend a whole story on one vague line.
4. **Technology lists.** Plain sentences grouped by what each tool was used for, not a keyword string.
5. **Every answer stands alone** and uses different evidence from the other answers on that form.

## Length

Write to depth, then stop. Long answers run about 150 to 250 words, cover letters about 200 to 250, and "a few bullets" about 50 to 80 words per bullet. A field cap is a ceiling; short is not a goal in itself. In review, cut filler, repetition and unsupported claims first. When an answer runs over these ranges, keep the single best mechanism and drop the second story instead of squeezing both. Never cut a mechanism just to reach a lower count.

## Cut or rewrite on sight

- Figurative or wish endings ("I want that work to end with a person getting home").
- Forced parallels: two things that are not the same problem, claimed as the same. Claims about how the company's own system works that the user cannot defend. A company blog post presented as the user's own comparison.
- Lines that talk the user down ("as an intern I would have no say over..."), and closers that define a virtue ("is what empathy means to me").
- Credit for a result the source does not tie to the change named. State what the source states.
- Overclaims about scale or fit (a local tool described as running "at that volume").
- Tools outside the user's confirmed skills, feedback they did not report, counts with a stale date, and velocity numbers.
- Family, hardship and personal-background stories, unless the question asks about background or the user has cleared that use in `voice/facts.md`.
- A story with the link missing: two facts side by side with no stated connection.
- Anything that makes the user look less finished ("still learning X") in a cover letter or a "why us" answer.

## Across one form

- No story, project or metric carries two answers. Run `python3 scripts/writecheck.py crossform <every answer file for the form> --allow "<company>"`; it must print `CLEAN`.
- Each answer answers its exact question, and stands alone if read without the others.
- Every fact traces to a file: the master resume, the tailored resume, standing answers, `voice/facts.md`, or the job description. List each sentence that goes beyond a source word for word under "inferred sentences", check it against the source, and remove it if the source does not support it.
- Optional boxes get a real answer unless the user set `optional_sections: skip`.

## The test in review

For each answer: would a senior engineer learn one decision here that only this person could describe, and is its connection to this company stated outright? If not, rewrite it. Then run `writecheck.py check` and require `CLEAN`.

## Testing a change to this standard (optional)

To tell whether a change to these rules makes answers better, compare blind:

1. Pick a few real forms the user already answered. Hold their approved answers out of the writer's inputs.
2. Draft each answer twice, once under the old rules and once under the new ones, from the same facts.
3. Shuffle each pair into A and B and store the key in a file the judge cannot read.
4. Give a fresh agent, with no part of this conversation, the questions, the job descriptions and the unlabeled pairs, and ask it to pick the stronger answer of each pair as a skeptical hiring engineer and say why.
5. Unblind, count, then trace every fact in the winning answers back to a source file. A win built on an invented fact is a loss.
