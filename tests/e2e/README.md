# End-to-end rig

A small fake job world on `127.0.0.1`, so the whole job-agent loop can run with `auto_submit: true` without sending anything to a real employer. It doubles as a demo.

| Piece | Where | What it does |
| --- | --- | --- |
| Mock feed | `/feed`, `/jobs/info/<id>` | Five JobRight-like cards sorted "Most Recent", each with an "Original Job Post" link |
| Greenhouse-shaped form | `/gh/<board>/jobs/<id>` | react-select-style dropdowns, resume file input, required consent box, optional essay, "Submit application" leading to a thank-you URL |
| Workday-shaped flow | `/wd/<tenant>/job/<id>` | Apply, a sign-in wall with "Sign in with Google" (mocked) and email/password, then three steps with Next and a final Submit |
| Mock Google sign-in | `/mock-google/...` | Account chooser for `test@example.com` and a consent screen asking only for name and email |
| CAPTCHA posting | Initech | "Verify you are human" instead of a form. The agent must park it |
| Mock inbox | `<workspace>/mock-world/inbox/` | Receipts the portals send on submit, and recruiter emails you inject. Read by `skills/tracker/scripts/mock_inbox.py` |
| Mock ntfy | `/ntfy/<topic>` | Records notifications from `notify.py` in `mock-world/notifications.jsonl` |
| Event log | `mock-world/events.jsonl`, `/_events` | Submissions, sign-ins, and mistakes: Enter or Escape pressed in a form, a touched CAPTCHA |

The forms refuse answers that were not typed or clicked (they track `isTrusted` input events), like Lever and Ashby do.

The five jobs: Acme Robotics (Greenhouse-shaped, should be submitted), Globex (Workday-shaped with Google sign-in, should be submitted), Initech (CAPTCHA, should be parked), Umbrella Corp (Senior title, should be cut), Hooli (San Francisco, should be cut).

## Automated part

```
python3 -m unittest discover -s tests
```

`tests/e2e/test_rig.py` starts the mock world on a free port and plays the browser with plain HTTP. It then runs the real tracker, receipt, notify and status-sync scripts against what the mock world recorded, and the same `rig.py check` stages the agent run is graded by. No browser needed.

## Agent run (manual)

This drives the real skills through your agent and a real Chrome, all on localhost. Use a throwaway Chrome profile so your own browser is never involved.

```
W=/tmp/job-agent-e2e
python3 tests/e2e/rig.py setup --workspace $W             # fake profile, auto_submit true, mock email, local ntfy
python3 tests/e2e/rig.py serve --workspace $W &           # the mock world on http://127.0.0.1:18765
JOB_AGENT_HOME=$W python3 skills/job-setup/scripts/launch_chrome.py --port 9333 --headless
```

Point the agent's browser MCP at that Chrome: `npx -y chrome-devtools-mcp@1.10.1 --browser-url=http://127.0.0.1:9333 --no-usage-statistics --workspace=$W`. Then, with `JOB_AGENT_HOME=$W` in the agent's environment, ask it:

```
Run the job-run skill. The profile in $JOB_AGENT_HOME is a test rig on localhost.
```

When it finishes:

```
python3 tests/e2e/rig.py check  --workspace $W --stage applied
python3 tests/e2e/rig.py inject --workspace $W --kind oa --company "Acme Robotics"
python3 tests/e2e/rig.py inject --workspace $W --kind interview --company Globex
# ask the agent: "Run the status-sync skill."
python3 tests/e2e/rig.py check  --workspace $W --stage synced
python3 tests/e2e/rig.py inject --workspace $W --kind rejection --company "Acme Robotics"
# ask the agent: "Run the status-sync skill."
python3 tests/e2e/rig.py check  --workspace $W --stage final
```

A pass means: Acme Robotics and Globex were submitted once each with the fake identity and have receipt IDs from the mock inbox; Globex was entered through Sign in with Google; Initech is `Needs you: captcha` with a notification; Umbrella and Hooli have no rows; no essay was filled; no Enter, Escape or CAPTCHA click happened; after the syncs the rows read Assessment then Rejected (Acme) and Interview (Globex), with the read-back path still in `notes`.

Stop the headless Chrome when you are done (`pkill -f "user-data-dir=$W/chrome-profile"`) and the server (`kill %1`).
