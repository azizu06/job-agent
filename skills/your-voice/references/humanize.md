# Humanize: craft moves and AI tells

The humanizing layer of `your-voice`. It runs on every written answer, with or without a voice profile. Two halves: craft moves to apply while drafting, then the tell catalog to apply after. Stripping tells alone gives clean, flat text; the craft moves are what make it read like a person.

If the user has a voice profile (`voice/profile.md`), it wins over this file. When their own writing uses a pattern listed here, keep it in their answers.

## Part 1: Craft moves (while drafting)

Application answers are short and practical. Answer the question in the first sentence or two, give each paragraph one job, and prove claims with one or two specific facts. A story or a surprising ending is optional; a direct "why this role" question wants a direct answer.

1. **Answer first.** The first sentence answers the question that was asked. No warm-up.
   - Flat: "Throughout my academic career I have developed a strong interest in software."
   - Better: "I want this role because your team runs the payments backend I have been building toward for two years."
2. **Anchor in one concrete thing.** Open on a real project, moment or result from the sources, then widen out. Do not open with a claim about your character.
   - Flat: "I am passionate about building reliable software."
   - Better: "My scheduling app double-booked a room on its first day, so I wrote the tests it should have had."
3. **One idea per answer.** Pick the strongest single point and give it room. Three accomplishments in 150 words reads like a resume pasted into a box.
4. **Specific nouns beat categories.** "A Flask API with 40 endpoints" over "a backend project". "The robotics club's line-following robot" over "a team project". Every specific must come from the sources.
5. **Give it a turn when the question allows.** A before and after: something that broke and what changed, a plan that shifted after feedback. Tension makes a short answer memorable. Skip it for logistics questions.
6. **Vary sentence length on purpose.** A longer sentence that follows a line of thought, then a short plain one. A run of same-length medium sentences is the most common sign of machine prose.
7. **Say why it matters plainly.** "I worked nights through school, so flexible shift tools matter to me" beats "this deeply resonates with my core values". Only state a reason the sources support.
8. **End on a fact, not a summary.** Close on the last concrete thing or a small plain line. Never restate the prompt or announce excitement.
9. **Find the honest, slightly unexpected angle.** The obvious answer is the one every applicant writes. Look for a true framing others would not give. True first, unexpected second, never clever for its own sake.
10. **Read it back as a person.** Would the user say this sentence out loud to a friend? If it sounds like a press release or a cover letter template, rewrite it.

No flowery writing: no stacked metaphors and no imagery for its own sake. The craft is precision and restraint. A line that is creative but not true goes.

## Part 2: AI tells (after drafting)

Ordered by how often each shows up in application answers, most common first.

| Tell | Fix |
|---|---|
| **Throat-clearing opener.** "I am thrilled to apply", "As a passionate student", "I believe that" | Start with the content |
| **Company flattery with no fact.** "your innovative culture", "your mission resonates with me" | One specific thing about the company from the job description, tied to one thing the user did, or nothing |
| **AI vocabulary.** delve, foster, garner, landscape, pivotal, showcase, testament, underscore, crucial, vibrant, robust, seamless, leverage, tapestry, realm, multifaceted | Plain word, or cut |
| **Grandiose abstractions.** "drive impact", "make a difference", "leverage my skills" | What actually happened, plainly |
| **Contrastive negation.** "not just X", "more than just X", "it's not X, it's Y", "not only X but also Y" | State the positive idea once |
| **Rule of three.** "fast, scalable, and reliable" | One or two concrete things |
| **Selection narration.** "one project that stands out", "I'd like to highlight", "comes to mind", "let me walk you through" | Delete the sentence and open with the work |
| **Generic upbeat ending.** "I am excited for what lies ahead", "I look forward to contributing" | End on the last real fact |
| **Em and en dashes** | Period, comma, "and", "so". Checked by `writecheck.py` |
| **Significance inflation.** "a pivotal moment", "a defining experience" | Say what happened |
| **Restating the question.** "Why do I want to work at Acme? ..." | Answer it |
| **Copula avoidance.** "serves as", "stands as", "boasts", "features" | "is", "are", "has" |
| **Promotional adjectives.** cutting-edge, innovative, world-class, renowned | Neutral description, or cut |
| **Filler phrases.** "in order to", "due to the fact that", "it is important to note that" | "to", "because", or just say it |
| **Trailing -ing chains.** "..., reflecting my commitment to..., contributing to..." | Cut the chain |
| **Five-paragraph shape in 150 words.** Intro, three points, conclusion | One or two paragraphs that each say one thing |
| **Figurative stand-ins.** "wears many hats", "where the magic happens" | The literal fact the image stands for. Test: is the image literally true? |
| **Stock idioms.** "hit the ground running", "at the end of the day" | The literal statement |
| **Manufactured staccato.** Several short dramatic fragments in a row | One short sentence for emphasis is fine; a run of them is not |
| **Colon-led setup.** "Here's what draws me in:" | Say it in a sentence |
| **Excessive hedging.** "could potentially be argued" | "may", or commit to the claim |
| **Elegant variation.** Cycling synonyms so a word does not repeat | Repeat the clearer word |
| **False ranges.** "from X to Y" where X and Y are not ends of a real scale | List the things directly |
| **Aphorisms.** "X is the backbone of Y" | The concrete claim underneath |
| **Authority tropes.** "at its core", "what really matters is" | Make the actual claim |
| **Vague attribution.** "experts say", "studies show" | Name the source or drop the claim |
| **Curly quotes, invisible Unicode, odd spaces** | Straight quotes, plain spaces. Checked by `writecheck.py` |
| **Bullets, headings, bold or emojis in a text box** | Prose |
| **Title Case in a sentence** | Sentence case |
| **Chat residue.** "I hope this helps", "Great question", "as of my last update" | Cut |

## Do not over-correct

Normal human writing is not a tell. Do not flag these alone:

- Correct grammar, consistent style, plain but correct prose
- Common transitions ("Also", "So", "Because")
- One short emphatic sentence
- The user's own opinion stated as opinion
- Patterns the user's own writing shows they use

Look for clusters. One pattern alone usually means nothing; three in one paragraph means rewrite the paragraph. Over-editing produces clean, dead prose, which is its own tell.

## Signals to keep

If a draft has these, do not sand them off:

- Specific, hard-to-fake detail from the sources: a real project name, a real number, a real tool
- An admission that something did not fully work, and what the user changed
- A first-person choice the user can explain in an interview
- Varied sentence length: a longer sentence next to a short plain one
