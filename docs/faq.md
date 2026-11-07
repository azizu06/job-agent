# FAQ

Short answers to the questions people ask first. Detail lives in [how-it-works.md](how-it-works.md).

## What is JobRight?

[JobRight](https://jobright.ai) is a job board that builds a feed of postings matched to your profile. job-agent reads that feed in your own signed-in Chrome, newest first, and stops at the last job it saw. A free account is enough. If you do not want JobRight, the agent can use the Indeed MCP connector instead.

## Is it free?

job-agent is free and MIT licensed. JobRight's free account works. The cost is your coding agent: a Claude, ChatGPT or Cursor subscription, or API usage. See the next question.

## What does it cost in tokens?

Each job runs in its own agent session that reads the page, tailors a resume and fills the form, so cost scales with how many jobs you run and how long each form is. On a Claude Pro or Max plan it counts toward your plan's usage limit, not a separate bill. To see your real number, do a dry run on a few jobs and check your usage before you schedule it.

## Does it work on Windows? Linux?

job-agent is built for Claude Code on macOS, and CI runs the test suite on macOS and Ubuntu. Windows and Linux are next on the [roadmap](../README.md#roadmap). The auto-allow helper for walk-away runs and reading SMS codes use macOS features.

## Will I get banned?

It can happen. Automation may break a site's terms, and a site may limit or close your account. The agent lowers the risk: it works in your normal Chrome, reads slowly, uses no private APIs, never touches LinkedIn, never solves CAPTCHAs, and caps how many roles it applies to per company. Many companies also limit how many roles you can apply to, so the caps protect your candidacy too.

## Can it apply through LinkedIn Easy Apply?

No. It does not automate LinkedIn or any social site. It applies on the employer's own portal (Greenhouse, Workday, Lever, Ashby and others). It can use the "Sign in with LinkedIn" button on a portal, if you allow it, but it never browses linkedin.com.

## What if I have no resume?

Setup can start one with you from the [master resume template](../skills/job-setup/assets/master-resume.md). You list your school, jobs, projects and skills, and the agent shapes them into entries. Every number and tool must be something you really did; the agent never adds facts of its own.

## Will it lie on my resume or answers?

No. It only rewords and selects from your master resume and your standing answers. A checker fails any tailored resume that contains a number not found in the master, and a layout gate checks the rendered PDF (one full page, every line filled, even spacing) before it is uploaded. Written answers are drafted from the same sources by the `your-voice` skill, and any sentence it had to infer is listed for you to check. Set `written_answers: leave` to write them yourself.

## Will my answers sound like ChatGPT wrote them?

That is what the `your-voice` skill is for. Each answer goes through a built-in humanizing layer that removes common AI giveaways, then, if you gave samples or rules, a rewrite in your voice, then a character and length check. It learns from every edit you make. It still only uses facts from your resume, so read each answer before you submit, and set `written_answers: leave` if you would rather write them yourself. See [Answers in your voice](your-voice.md).

## Does it submit on its own?

Not unless you turn on `auto_submit`. Auto-submit when you turn it on: it presses the final button itself, within your daily and per-company caps, and still stops at CAPTCHAs, sign-in walls and unanswered required questions. It is off by default, so a first run fills everything, stops at the final button for your review, and the tracker row says `Ready`.

## What happens at a CAPTCHA or a sign-in page?

It tries Sign in with Google, Microsoft or LinkedIn with an account already in your Chrome, then a login Chrome already saved. If none works, or it sees a CAPTCHA, it parks the job: the tab stays open and filled, and you get a notification. At the end of the run you get one list of parked tabs to clear in one sitting.

## Where does my data go?

Your profile, resumes, tracker and run logs live in `~/.job-agent/` on your computer. Passwords, if you turn on the optional credential mode, live only in your OS keychain. Nothing personal goes into this repo. Your agent's model provider sees what the agent reads, as with any agent task.

## Does my computer have to stay on?

Yes. The agent drives the Chrome on your computer, so runs need it on, awake and signed in. A cloud agent cannot reach your Chrome. On a Mac, walk-away runs also need the auto-allow helper.

## Does it only do internships?

No. Set `seniority` to internship, new-grad, junior, mid or senior, set your pay floor per hour or per year, and list the titles you want. The examples use internships because the author is a student.

## Can I stop or undo it?

Stop your agent at any time; filled tabs stay open. A submitted application cannot be pulled back by the agent, which is why auto-submit is off by default. To turn helpers off, ask your agent "turn off auto-allow".

## Which coding agents does it work with?

Claude Code, including parallel appliers, one per job. Codex, Cursor and other agents that read skills can load them too and run one job at a time; first-class support for them is on the [roadmap](../README.md#roadmap).
