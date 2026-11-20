# Codex setup

This fork exposes all ten job-agent skills to Codex and provides a Codex setup path. Full browser execution, unattended runs and parallel workers are later migration milestones. Setup checks alone do not mean that an application run has passed.

## Open the repository

```bash
git clone https://github.com/jonathan-prabakar/job-agent.git
cd job-agent
codex
```

In the desktop app, open the cloned folder as the project instead. Codex reads `AGENTS.md` and discovers the relative skill-folder links under `.agents/skills/`. The original `skills/` folders remain the source of truth; keep scripts, references and assets together. Do not install a second copy of the same skills globally.

In Codex CLI, use `/skills` to check that all ten skills appear, then ask:

```text
$job-setup
```

In a client without that selector, ask: "Set up job-agent using the job-setup skill." A request to review or modify the repository should not start the wizard.

Official references: [skill discovery](https://learn.chatgpt.com/docs/build-skills) and [AGENTS.md](https://learn.chatgpt.com/docs/agent-configuration/agents-md).

## Prerequisites

- Node.js 20.19 or later, Python 3.9 or later, and Chrome 144 or later.
- `tectonic` and PyMuPDF for the resume build and mandatory upload gate. Check `tectonic --version` and `python3 -c "import fitz"`.
- On Windows, use `py -3` instead of `python3`. Windows and Linux remain community-supported.

Install commands are in [Getting started](getting-started.md). A missing PDF dependency blocks the resume gate; do not upload an unchecked PDF.

## Configure the browser

Choose the data workspace before registering the server: use `JOB_AGENT_HOME` when set, otherwise `~/.job-agent`. User profiles and resumes belong there, outside tracked source files. Resolve this to an absolute path and use that same path for browser file access. The Codex sandbox must also permit writes to the workspace; MCP file roots and Codex write permissions are separate checks.

First inspect `codex mcp list`. Reuse a matching configuration, and do not replace a server used by another project silently. The following is a template: replace `/absolute/path/to/job-agent-data` before running it.

```bash
codex mcp add job-agent-browser -- \
  npx -y chrome-devtools-mcp@1.10.1 \
  --autoConnect \
  --no-usage-statistics \
  --workspace=/absolute/path/to/job-agent-data
```

Open `chrome://inspect/#remote-debugging` in Chrome and turn on remote debugging. Reopen the Codex session if the tools have not loaded. Ask the agent to call `list_pages`, then click Chrome's **Allow remote debugging?** prompt yourself. A successful result proves attachment, not the complete application workflow. The first milestone does not install Claude or copy `~/.claude/agents/job-applier.md`.

For a separate Chrome profile, launch `skills/job-setup/scripts/launch_chrome.py` with `JOB_AGENT_HOME` set to the chosen workspace. Register the dedicated server instead:

```bash
codex mcp add job-agent-dedicated -- \
  npx -y chrome-devtools-mcp@1.10.1 \
  --browser-url=http://127.0.0.1:9333 \
  --no-usage-statistics \
  --workspace=/absolute/path/to/job-agent-data
```

Set `browser.mode: dedicated` in preferences and use only that server for browser work. Sign in once in the separate profile. Keep the existing package version pinned during migration.

Alternatively, put the stdio server's `command` and `args` in a `[mcp_servers.job-agent-browser]` table in a trusted project's `.codex/config.toml`. Generate machine-specific paths locally rather than checking them into this repository. See [Codex MCP configuration](https://learn.chatgpt.com/docs/extend/mcp).

## Check connectors and finish setup

Discover connectors in the active client. Verify Gmail with one read-only label-list or search call. If it is missing, connect a Gmail plugin or authenticated MCP server in that client. A desktop connection does not prove that a separate scheduled CLI process can access it. Do not use Claude's connector settings.

Start with the local CSV tracker. Only offer Sheets or Notion after verifying access to the selected backend. Missing Gmail must stay visible as an incomplete setup capability: the prior-application check fails closed and must not be disabled to force a pass.

Continue the setup wizard for the resume, preferences, standing answers and writing voice. Preserve `setup-progress.json` on reruns. Keep auto-submit off, credential mode off and scheduling disabled unless an applicable, validated workflow and the user's settings authorize them. This milestone does not configure unattended execution.

## Validation before a real run

Run the discovery checks from the repository root:

```bash
python3 -m unittest discover -s tests -p test_codex_discovery.py
```

The next migration milestone uses the [local mock ATS rig](../tests/e2e/README.md) to validate sequential browser execution, typing, resume uploads, read-back, parking and receipt tracking. After that passes, start with one real dry-run application that stops at Submit. Do not infer browser success from unit tests.
