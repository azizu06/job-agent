---
name: portal-auth
description: Get the user into their own job-portal accounts during an application. Default flow - Sign in with Google, then Microsoft, then LinkedIn, using an account already signed in to their Chrome, then a login the browser already saved, then park the job for the user. An optional credential mode, off by default, adds typed keychain passwords, account creation, password resets and verification-code entry; many agents (including Claude) refuse those steps under their own safety rules, and when they do the job parks. Never solves a CAPTCHA. Use when apply-fill hits a sign-in, account or verification wall.
---

# portal-auth

Python: commands below say `python3`. Use `python_cmd` from `profile/preferences.yaml` instead when it is set (setup writes `py -3` on Windows).

Many portals require an account, and Workday makes a separate account per company. This skill gets the user into accounts they already have where it can, and parks the job for the user where it cannot. It does not promise to get past every sign-in wall; parking is a normal, expected result.

## Settings (from `profile/preferences.yaml`)

```yaml
portal_accounts:
  allow_sso: true            # Sign in with Google, Microsoft or LinkedIn, using an account already signed in to this Chrome
  allow_saved_login: true    # click Sign In when the browser itself autofilled a saved login
  email: ""                  # defaults to contact.email in standing answers
  credential_mode: false     # optional, off by default; see Credential mode
  # The keys below apply only when credential_mode is true.
  allow_sign_in: false       # type the email and paste a password stored in the OS keychain
  allow_create: false        # create new portal accounts for the user
  allow_password_reset: false
  email_code_minutes: 10     # how far back to look for an emailed code
  sms_codes: false           # macOS only: read SMS codes from Messages (needs Full Disk Access)
```

Setup asks once about each setting. A setting being true allows a step; it does not force you to do it.

## Default flow

Try these in this exact order. Skip a step whose setting is false, that the portal does not offer, or whose provider account is not signed in to this Chrome. Try each step at most once per job. If a step is tried and does not get you in, go to the next step.

1. **Sign in with Google** (`allow_sso`).
2. **Sign in with Microsoft** (`allow_sso`).
3. **Sign in with LinkedIn** (`allow_sso`). Use only the sign-in handoff: pick the account, read the consent screen, return to the portal. Never browse or act on linkedin.com beyond that.
4. **Browser-saved login** (`allow_saved_login`).
5. **Park the job** (see Parking) with `Needs you: sign-in`, or `Needs you: create account` when the portal says no account exists. If `credential_mode` is true, try Credential mode first and park only if it does not get you in.

### SSO (steps 1 to 3)

- Click the SSO button. In the account chooser, pick the account whose email matches `portal_accounts.email` (or `contact.email`). Never pick a different account, never add an account, never type a provider password. If the provider asks for a password or a code, park with `Needs you: sign-in`. If the chooser is ambiguous (no account matches exactly, or two look alike), park with `Needs you: pick account`.
- On the consent screen, read it. Click Continue or Allow only when it asks for basic profile and email for sign-in to this employer's portal (check the app name and the portal host). If it asks for anything more (Drive, Gmail, contacts, calendar, "manage" anything) or names an unrelated app, park the job with `Needs you: sso consent`.
- Confirm you landed back on the portal, signed in. If not, go to the next step.

### Browser-saved login (step 4)

Only when Chrome itself has already filled both the email and the password fields. Click Sign In. Never press Enter. Do not type, paste or read a password in this step. If the fields are empty, or the login is rejected, go to step 5.

## Credential mode (optional, off by default)

Many agents (including Claude) will refuse these steps under their own safety rules; when they do, the job parks for you.

Credential mode covers every step that handles a secret or makes an account: typing or pasting a stored password, creating a portal account, resetting a password, and entering an email or SMS verification code. It runs only when `credential_mode: true`, and each part also needs its own setting. Order, after the default flow:

1. **Keychain password** (`allow_sign_in`). If `portal_creds.py has <host>` succeeds, type the email from `portal_creds.py email <host>`, paste the password (see Passwords), click Sign In. Never press Enter.
2. **Create an account** (`allow_create`), only when no default step worked and there is no stored entry. Use the user's email and `portal_creds.py new <host> --email <email>` (add `--no-symbols` or `--length` if the page states rules); paste it into the password and confirm fields. Tick only the portal's own required account-terms box after reading it; leave marketing and data-sharing boxes unticked. Then verify the email (see Codes and links).
3. **Reset a password** (`allow_password_reset`) when the stored password fails: Forgot Password, submit the email, open the reset link from Gmail in the same tab, `portal_creds.py new <host> --email <email>`, paste into new and confirm fields, save, sign in.
4. **Verification codes** (see Codes and links), only as part of steps 1 to 3.

With `credential_mode: false`, do none of these. Park instead.

## When you decline or cannot do a step

Your own safety rules, or the user's tool settings, may stop you from typing passwords, creating accounts or entering codes, even with credential mode on. Some steps your tools cannot do. That is expected, and it is never an error.

- Park the job (see Parking) with a reason that names the step, for example `Needs you: sign-in`, `Needs you: create account`, `Needs you: password reset`, `Needs you: email code` or `Needs you: sms code`. Do not go on to later steps; they need the same kind of action.
- Do not retry the step. Do not ask the user to approve it in chat and then wait. Do not loop through the same sign-in page again. One attempt per step, then park.
- Do not stop the run, raise an error, or abandon the other jobs. Return the parked report and let `job-run` move on to the next job.
- Do not close or reload the tab. Leave it on the page where you stopped, with everything filled so far, so the user can finish the step by hand.

## Passwords (credential mode only)

- Stored only in the OS keychain through `scripts/portal_creds.py` (Python `keyring`: macOS Keychain, Windows Credential Manager). One entry per portal host, for example `acme.wd5.myworkdayjobs.com`. The index `state/portals.json` holds hosts and emails only.
- **Never print, log, echo or type a password into chat or a file.** Never pass it on a command line. To enter it: `python3 scripts/portal_creds.py copy <host>`, click the password field, paste with `press_key` (`Meta+V` on macOS, `Control+V` on Windows and Linux). The clipboard clears after 20 seconds. Verify only that the field is non-empty (an `evaluate_script` that returns the value's length).
- Never reuse one password across portals.

## Codes and links (credential mode only)

- **Email codes and links:** search Gmail with `in:anywhere newer_than:<email_code_minutes>m` from the portal's sender (or the company name). Use only the newest matching message. Open verification and reset links in the same tab. Type codes into the code field with real typing.
- **SMS codes (macOS, opt-in `sms_codes`):** run `python3 scripts/sms_code.py --minutes 5 --sender <company or short code>`. It reads `~/Library/Messages/chat.db` read-only, finds the newest incoming message with a code, and puts the code on the clipboard; paste it. Needs Full Disk Access for the app running the agent (System Settings > Privacy & Security > Full Disk Access) and Text Message Forwarding from the user's iPhone. Windows: Phone Link has no stable API, so SMS codes are parked for the human. Linux: park.
- **Authenticator-app codes, security keys, push approvals:** park.

## Parking (CAPTCHA, bot checks, declined steps and anything else for the human)

Never solve, bypass or work around a CAPTCHA or bot check, and never use a solving service. Parking is the same for every reason, including a step you declined or could not do:

1. Leave the tab open with everything filled so far. Do not reload or close it.
2. Set the queue entry to `NEEDS YOU: <what the page asks for>` (`../job-gate/scripts/apply_queue.py set`), and the tracker row to `Needs you: <reason>` unless `tracker.rows_for_unsubmitted` is false, for example `Needs you: captcha`, `Needs you: sign-in`, `Needs you: create account`, `Needs you: password reset`, `Needs you: email code`, `Needs you: sms code`, `Needs you: sso consent` or `Needs you: ssn or payment`.
3. If `notify.parked` is `each` (the default), send a notification: `python3 ../job-run/scripts/notify.py --title "job-agent: needs you" --message "<company> <role>: <reason>" --url <page url>`. With `summary` or `none`, send nothing here; `job-run` lists parked jobs at the end.
4. Return a report with the page id, URL and reason (what exactly the page asks for) so `job-run` lists it, and move on to the next form.

Always park: CAPTCHA or "verify you are human"; SMS codes the agent cannot read; authenticator or push 2FA; SSO consent beyond basic sign-in; any request for SSN, national ID, bank or payment details; a host that is not the employer's or its ATS; any step whose setting is false; any credential-mode step while `credential_mode` is false; and any step you decline or cannot do. A parked job is a normal result, not a failure: the run continues with the next job.
