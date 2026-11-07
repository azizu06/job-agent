# Answers in your voice

Every written answer ("Why this company?", "Tell us about a project") goes through the `your-voice` skill before it is typed:

1. **Facts only, two angles.** It drafts from your master resume, standing answers and the job description, nothing else. It writes two drafts from different angles and keeps the more specific one.
2. **A built-in humanizing layer, always on.** It strips the common giveaways of AI writing (filler openers, "not just X but Y", stock words like "leverage", dashes) and applies plain craft moves: answer first, one idea, specific nouns, varied sentences.
3. **Your voice, if you want it.** Setup asks: "Want answers to sound like you? Paste 2-5 things you've written, or add your own writing rules. Skip to use the humanizing layer only." From your samples it learns your sentence length, openers and the words you use and avoid.
4. **Checks.** It audits itself (what still reads as AI, which fact you could not defend in an interview), then `writecheck.py` catches dashes, curly quotes, hidden Unicode characters and the form's length limit.

When you edit an answer, it saves the change as a rule in your voice profile, so the next answer starts closer to how you write. Answers you approve are kept as examples, never copied word for word. Nothing is sent to a second model or a paraphrasing website. Your samples stay in `~/.job-agent/voice/` on your computer.

Set `written_answers: leave` in your preferences to write every answer yourself. The skill itself is [`skills/your-voice/SKILL.md`](../skills/your-voice/SKILL.md).
