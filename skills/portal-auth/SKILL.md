---
name: portal-auth
description: Get the user into their own job-portal accounts during an application. Tries Sign in with Google, then Microsoft, then LinkedIn, using the account already signed in to their Chrome, then keychain or browser-saved credentials, then, only if allowed in setup, account creation or password reset. Reads email codes through the Gmail MCP and, on macOS opt-in, SMS codes from Messages. Parks the tab for the human on any CAPTCHA, and on any step the running agent declines or cannot do, without retrying or stopping the run. Use when apply-fill hits a sign-in, account or verification wall.
---

# portal-auth

Many portals require an account, and Workday makes a separate account per company. This skill handles the user's own accounts so applications do not stall.

## Settings (from `profile/preferences.yaml`)

```yaml
portal_accounts:
  allow_sso: true            # use "Sign in with Google/Microsoft/LinkedIn" with the account already in Chrome
  allow_sign_in: true        # sign in with keychain or browser-saved credentials
  allow_create: false        # create new portal accounts for the user
  allow_password_reset: false
  email: ""                  # defaults to contact.email in standing answers
  email_code_minutes: 10     # how far back to look for an emailed code
  sms_codes: false           # macOS only: read SMS codes from Messages (needs Full Disk Access)
```

Setup asks once about each permission. If a setting is false, that path is skipped; if no path is left, park the job (see Parking). A setting being true allows a step; it does not force you to do it. If you decline it, park (see When you decline or cannot do a step).

## Order of attempts

Try these in this exact order. Skip any step whose setting is false or that the portal does not offer. Try each step at most once per job. If a step fails or you decline it, go to the next step; when no step is left, park the job (see Parking).

1. **Sign in with Google** (`allow_sso`).
2. **Sign in with Microsoft** (`allow_sso`).
3. **Sign in with LinkedIn** (`allow_sso`). Use only the sign-in handoff: pick the account, read the consent screen, return to the portal. Never browse or act on linkedin.com beyond that.
4. **Saved credentials** (`allow_sign_in`).
5. **Create an account** (`allow_create`) or **reset a password** (`allow_password_reset`), if allowed.

### SSO (steps 1 to 3)

Use a provider only when the portal shows its button and the user has that account signed in to this Chrome.

- Click the SSO button. In the account chooser, pick the account whose email matches `portal_accounts.email` (or `contact.email`). Never pick a different account, never add an account, never type a provider password.
- On the consent screen, read it. Click Continue or Allow only when it asks for basic profile and email for sign-in to this employer's portal (check the app name and the portal host). If it asks for anything more (Drive, Gmail, contacts, calendar, "manage" anything) or names an unrelated app, park the job with `Needs you: sso consent`.
- Confirm you landed back on the portal, signed in. If not, go to the next step.

### Saved credentials (step 4)

If the browser autofilled email and password, click Sign In. Else if `portal_creds.py has <host>` succeeds, type the email from `portal_creds.py email <host>`, paste the password (see Passwords), click Sign In. Never press Enter.

### Create or reset (step 5)

- **Create an account** (`allow_create`), only when no SSO step worked and there is no stored entry. Use the user's email and `portal_creds.py new <host> --email <email>` (add `--no-symbols` or `--length` if the page states rules); paste it into the password and confirm fields. Tick only the portal's own required account-terms box after reading it; leave marketing and data-sharing boxes unticked. Then verify the email (see Codes and links).
- **Reset a password** (`allow_password_reset`) when the stored or saved password fails: Forgot Password, submit the email, open the reset link from Gmail in the same tab, `portal_creds.py new <host> --email <email>`, paste into new and confirm fields, save, sign in.

## When you decline or cannot do a step

Some agents will not type or paste passwords, create accounts, or enter verification codes, because of their own policies or the user's tool settings. Others hit a step their tools cannot do. That is expected, and it is never an error.

- If you decline a step, or cannot do it, park the job (see Parking) with a reason that names the step, for example `Needs you: sign-in`, `Needs you: create account`, `Needs you: password reset`, `Needs you: email code` or `Needs you: sms code`.
- Do not retry the step. Do not ask the user to approve it in chat and then wait. Do not loop through the same sign-in page again. One attempt per step, then park.
- Do not stop the run, raise an error, or abandon the other jobs. Return the parked report and let `job-run` move on to the next job.
- Do not close or reload the tab. Leave it on the page where you stopped, with everything filled so far, so the user can finish the step by hand.

## Passwords

- Stored only in the OS keychain through `scripts/portal_creds.py` (Python `keyring`: macOS Keychain, Windows Credential Manager). One entry per portal host, for example `acme.wd5.myworkdayjobs.com`. The index `state/portals.json` holds hosts and emails only.
- **Never print, log, echo or type a password into chat or a file.** Never pass it on a command line. To enter it: `python3 scripts/portal_creds.py copy <host>`, click the password field, paste with `press_key` (`Meta+V` on macOS, `Control+V` on Windows and Linux). The clipboard clears after 20 seconds. Verify only that the field is non-empty (an `evaluate_script` that returns the value's length).
- Never reuse one password across portals.

## Codes and links

- **Email codes and links:** search Gmail with `in:anywhere newer_than:<email_code_minutes>m` from the portal's sender (or the company name). Use only the newest matching message. Open verification and reset links in the same tab. Type codes into the code field with real typing.
- **SMS codes (macOS, opt-in `sms_codes`):** run `python3 scripts/sms_code.py --minutes 5 --sender <company or short code>`. It reads `~/Library/Messages/chat.db` read-only, finds the newest incoming message with a code, and puts the code on the clipboard; paste it. Needs Full Disk Access for the app running the agent (System Settings > Privacy & Security > Full Disk Access) and Text Message Forwarding from the user's iPhone. Windows: Phone Link has no stable API, so SMS codes are parked for the human. Linux: park.
- **Authenticator-app codes, security keys, push approvals:** park.

## Parking (CAPTCHA, bot checks, declined steps and anything else for the human)

Never solve, bypass or work around a CAPTCHA or bot check, and never use a solving service. Parking is the same for every reason, including a step you declined or could not do:

1. Leave the tab open with everything filled so far. Do not reload or close it.
2. Set the tracker row to `Needs you: <reason>`, for example `Needs you: captcha`, `Needs you: sign-in`, `Needs you: create account`, `Needs you: password reset`, `Needs you: email code`, `Needs you: sms code`, `Needs you: sso consent` or `Needs you: ssn or payment`.
3. Send a notification: `python3 ../job-run/scripts/notify.py --title "job-agent: needs you" --message "<company> <role>: <reason>" --url <page url>`.
4. Return a report with the page id, URL and reason so `job-run` lists it, and move on.

Always park: CAPTCHA or "verify you are human"; SMS codes the agent cannot read; authenticator or push 2FA; SSO consent beyond basic sign-in; any request for SSN, national ID, bank or payment details; a host that is not the employer's or its ATS; any step whose setting is false; and any step you decline or cannot do. A parked job is a normal result, not a failure: the run continues with the next job.
