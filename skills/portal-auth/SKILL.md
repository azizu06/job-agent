---
name: portal-auth
description: Get the user into their own job-portal accounts during an application. Prefers "Sign in with Google" (or Microsoft, LinkedIn) using the account already signed in to their Chrome, else signs in with keychain or browser-saved credentials, and, only if allowed in setup, creates accounts or resets passwords. Reads email codes through the Gmail MCP and, on macOS opt-in, SMS codes from Messages. Parks the tab for the human on any CAPTCHA. Use when apply-fill hits a sign-in, account or verification wall.
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

Setup asks once about each permission. If a setting is false, that path is skipped; if no path is left, park the job (see Parking).

## Order of attempts

1. **SSO first** (`allow_sso`). If the portal offers "Sign in with Google" (or Microsoft or LinkedIn) and the user has that account signed in to this Chrome:
   - Click the SSO button. In the account chooser, pick the account whose email matches `portal_accounts.email` (or `contact.email`). Never pick a different account, never add an account, never type a Google password.
   - On the consent screen, read it. Click Continue or Allow only when it asks for basic profile and email for sign-in to this employer's portal (check the app name and the portal host). If it asks for anything more (Drive, Gmail, contacts, calendar, "manage" anything) or names an unrelated app, stop and park the job.
   - Confirm you landed back on the portal, signed in.
2. **Saved credentials** (`allow_sign_in`). If the browser autofilled email and password, click Sign In. Else if `portal_creds.py has <host>` succeeds, type the email from `portal_creds.py email <host>`, paste the password (below), click Sign In. Never press Enter.
3. **Create an account** (`allow_create`), only when the portal offers no usable SSO and there is no stored entry. Use the user's email and `portal_creds.py new <host> --email <email>` (add `--no-symbols` or `--length` if the page states rules); paste it into the password and confirm fields. Tick only the portal's own required account-terms box after reading it; leave marketing and data-sharing boxes unticked. Then verify the email (see Codes and links).
4. **Reset a password** (`allow_password_reset`) when the stored or saved password fails: Forgot Password, submit the email, open the reset link from Gmail in the same tab, `portal_creds.py new <host> --email <email>`, paste into new and confirm fields, save, sign in.

## Passwords

- Stored only in the OS keychain through `scripts/portal_creds.py` (Python `keyring`: macOS Keychain, Windows Credential Manager). One entry per portal host, for example `acme.wd5.myworkdayjobs.com`. The index `state/portals.json` holds hosts and emails only.
- **Never print, log, echo or type a password into chat or a file.** Never pass it on a command line. To enter it: `python3 scripts/portal_creds.py copy <host>`, click the password field, paste with `press_key` (`Meta+V` on macOS, `Control+V` on Windows and Linux). The clipboard clears after 20 seconds. Verify only that the field is non-empty (an `evaluate_script` that returns the value's length).
- Never reuse one password across portals.

## Codes and links

- **Email codes and links:** search Gmail with `in:anywhere newer_than:<email_code_minutes>m` from the portal's sender (or the company name). Use only the newest matching message. Open verification and reset links in the same tab. Type codes into the code field with real typing.
- **SMS codes (macOS, opt-in `sms_codes`):** run `python3 scripts/sms_code.py --minutes 5 --sender <company or short code>`. It reads `~/Library/Messages/chat.db` read-only, finds the newest incoming message with a code, and puts the code on the clipboard; paste it. Needs Full Disk Access for the app running the agent (System Settings > Privacy & Security > Full Disk Access) and Text Message Forwarding from the user's iPhone. Windows: Phone Link has no stable API, so SMS codes are parked for the human. Linux: park.
- **Authenticator-app codes, security keys, push approvals:** park.

## Parking (CAPTCHA, bot checks and anything else for the human)

Never solve, bypass or work around a CAPTCHA or bot check, and never use a solving service. Instead:

1. Leave the tab open with everything filled so far. Do not reload or close it.
2. Set the tracker row to `Needs you: captcha` (or `Needs you: sms code`, `Needs you: sso consent`, `Needs you: ssn or payment`, `Needs you: sign-in`).
3. Send a notification: `python3 ../job-run/scripts/notify.py --title "job-agent: needs you" --message "<company> <role>: <reason>" --url <page url>`.
4. Return a report with the page id, URL and reason so `job-run` lists it, and move on.

Always park: CAPTCHA or "verify you are human"; SMS codes the agent cannot read; authenticator or push 2FA; SSO consent beyond basic sign-in; any request for SSN, national ID, bank or payment details; a host that is not the employer's or its ATS; and any step whose setting is false.
