# Voice profile

Template for the optional voice layer. Setup copies it to `<workspace>/voice/profile.md` when the user gives writing samples or rules, and fills it in from them. The defaults below are only placeholders until then. "Their rules" and the Corrections section win over everything above them and over `references/humanize.md`.

Source: <N samples, date> or <rules only, date>.

## Measured from samples

Filled from `writecheck.py stats` when samples exist. Defaults:

- Median sentence length: 14 words. Mix a few longer sentences with short plain ones.
- Contractions: use them where they read naturally ("I'm", "didn't").
- Dashes: none. Use periods, commas, "and", "so".
- Exclamation marks: none.

## How they open

- Start with the work or the fact, never with a feeling about applying.
- First person, active voice: "I built", "I led", "I fixed".

## Connectives they use

- "so", "because", "also", "but". Avoid "moreover", "furthermore", "additionally".

## Words they use

- (none yet)

## Words they avoid

- passionate, thrilled, excited to apply, leverage, synergy, innovative, cutting-edge, journey

## Allowed AI-list words

Words from `writecheck.py`'s AI list that this user really uses. Each is passed as `--allow WORD`.

- (none)

## Their rules

Rules the user stated in their own words.

- (none yet)

## Length

- No stated limit: 120 to 150 words.
- A stated limit: stay under 90 percent of it.

## Corrections

One line per correction, newest last: `- YYYY-MM-DD: <rule> (was: "<their deleted text>", now: "<their text>")`.

- (none yet)
