#!/usr/bin/env python3
"""Mock job feed, mock ATS forms, mock sign-in, mock inbox and mock ntfy, all on localhost.

The job-agent end-to-end rig. Nothing here talks to a real employer. Standard
library only.

  python3 tests/e2e/mock_ats.py --port 18765 --state <dir>

Pages
  /feed                         JobRight-like card list, sorted "Most Recent"
  /jobs/info/<id>               aggregator posting page with the "Original Job Post" link
  /gh/<board>/jobs/<id>         Greenhouse-shaped posting and one-page form
  /wd/<tenant>/job/<id>         Workday-shaped posting; Apply leads to sign-in and 3 steps
  /mock-google/o/oauth2         mocked "Sign in with Google" chooser and consent
  /ntfy/<topic>                 POST target for notify.py (method ntfy, local server)
  /_events                      JSON log of what happened (submissions, Enter, Escape, ...)

State written under --state
  inbox/<id>.json               receipts the portals "email" on submit (the mock inbox)
  events.jsonl                  every event, one JSON object per line
  notifications.jsonl           every notification posted to /ntfy/<topic>
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import re
import secrets
import sys
import threading
import urllib.parse
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

TEST_ACCOUNT = "test@example.com"

JOBS = [
    {
        "id": "a1f0c0de0001", "company": "Acme Robotics", "title": "Software Engineer Intern",
        "location": "New York, NY", "work_model": "Hybrid", "pay": "$40/hr", "term": "Summer 2027",
        "req_id": "GH-1001", "ats": "gh", "board": "acmerobotics", "posted_minutes": 12,
        "skills": "Python, Docker, AWS, CI/CD with GitHub Actions, Linux and REST APIs",
    },
    {
        "id": "b2f0c0de0002", "company": "Globex", "title": "Backend Engineer Intern",
        "location": "Remote (US)", "work_model": "Remote", "pay": "$45/hr", "term": "Summer 2027",
        "req_id": "WD-2002", "ats": "wd", "board": "globex", "posted_minutes": 25,
        "skills": "Python, PostgreSQL, Redis, REST APIs and Docker",
    },
    {
        "id": "c3f0c0de0003", "company": "Initech", "title": "Software Engineer Intern",
        "location": "New York, NY", "work_model": "Onsite", "pay": "$38/hr", "term": "Summer 2027",
        "req_id": "GH-3003", "ats": "gh", "board": "initech", "posted_minutes": 40, "captcha": True,
        "skills": "TypeScript, React, Node.js and SQL",
    },
    {
        "id": "d4f0c0de0004", "company": "Umbrella Corp", "title": "Senior Software Engineer",
        "location": "New York, NY", "work_model": "Onsite", "pay": "$90/hr", "term": "",
        "req_id": "GH-4004", "ats": "gh", "board": "umbrella", "posted_minutes": 55,
        "skills": "Java, Kubernetes and Kafka",
    },
    {
        "id": "e5f0c0de0005", "company": "Hooli", "title": "Software Engineer Intern",
        "location": "San Francisco, CA", "work_model": "Onsite", "pay": "$50/hr", "term": "Summer 2027",
        "req_id": "GH-5005", "ats": "gh", "board": "hooli", "posted_minutes": 70,
        "skills": "Go, gRPC and Kubernetes",
    },
    # Gate cases that need the tracker or the link, not the card: a req already
    # in the tracker (dedupe), a company at its cap, and a LinkedIn-only post.
    {
        "id": "f6f0c0de0006", "company": "Wayne Enterprises", "title": "Software Engineer Intern",
        "location": "New York, NY", "work_model": "Hybrid", "pay": "$42/hr", "term": "Summer 2027",
        "req_id": "GH-6006", "ats": "gh", "board": "wayne", "posted_minutes": 80,
        "skills": "Python, Flask and PostgreSQL",
    },
    {
        "id": "a7f0c0de0007", "company": "Stark Industries", "title": "Backend Engineer Intern",
        "location": "Remote (US)", "work_model": "Remote", "pay": "$44/hr", "term": "Summer 2027",
        "req_id": "GH-7007", "ats": "gh", "board": "stark", "posted_minutes": 90,
        "skills": "Python, Docker and AWS",
    },
    {
        "id": "b8f0c0de0008", "company": "Vandelay Industries", "title": "Software Engineer Intern",
        "location": "New York, NY", "work_model": "Onsite", "pay": "$41/hr", "term": "Summer 2027",
        "req_id": "LI-8008", "ats": "linkedin", "board": "vandelay", "posted_minutes": 100,
        "skills": "Python and SQL",
    },
]
LINKEDIN_JOB_URL = "https://www.linkedin.com/jobs/view/4000000008/"
BY_ID = {j["id"]: j for j in JOBS}

DEGREES = ["Associate's Degree", "Bachelor of Arts (BA)", "Bachelor of Science (BS)", "Master of Science (MS)", "Doctor of Philosophy (PhD)"]
YES_NO = ["Yes", "No"]
HEARD = ["Company careers page", "Job board", "Referral", "University career fair"]


def apply_path(job: dict) -> str:
    if job["ats"] == "linkedin":
        return LINKEDIN_JOB_URL
    if job["ats"] == "gh":
        return f"/gh/{job['board']}/jobs/{job['id']}"
    return f"/wd/{job['board']}/job/{job['id']}"


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


class State:
    def __init__(self, root: Path):
        self.root = root
        (root / "inbox").mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()
        self.sessions: dict[str, dict] = {}

    def event(self, kind: str, **data) -> None:
        rec = {"at": now_iso(), "kind": kind, **data}
        with self.lock, (self.root / "events.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec) + "\n")

    def events(self) -> list[dict]:
        path = self.root / "events.jsonl"
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def mail(self, sender: str, to: str, subject: str, body: str) -> str:
        mid = "mock-" + secrets.token_hex(6)
        msg = {"id": mid, "from": sender, "to": to, "subject": subject, "date": dt.datetime.now(dt.timezone.utc).isoformat(), "body": body}
        (self.root / "inbox" / f"{mid}.json").write_text(json.dumps(msg, indent=1), encoding="utf-8")
        return mid

    def notify(self, topic: str, title: str, body: str, click: str) -> None:
        rec = {"at": now_iso(), "topic": topic, "title": title, "message": body, "click": click}
        with self.lock, (self.root / "notifications.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec) + "\n")


# ---------------------------------------------------------------- page parts

CSS = """
body{font-family:-apple-system,Segoe UI,sans-serif;max-width:760px;margin:24px auto;padding:0 16px;color:#111;background:#fff}
.card{display:block;border:1px solid #ddd;border-radius:8px;padding:12px;margin:10px 0;color:inherit;text-decoration:none}
.field{margin:14px 0}.field label{display:block;font-weight:600;margin-bottom:4px}
input[type=text],input[type=email],input[type=tel],input[type=password],textarea{width:100%;padding:8px;border:1px solid #bbb;border-radius:6px;box-sizing:border-box}
.select{position:relative}.select__control{border:1px solid #bbb;border-radius:6px;padding:8px;cursor:text}
.select__single-value{color:#111}.select__placeholder{color:#888}
.select__menu{position:absolute;left:0;right:0;background:#fff;border:1px solid #bbb;z-index:5}
.select__option{padding:6px 8px;cursor:pointer}.select__option:hover{background:#eef}
.error{color:#b00020;font-size:13px}.banner{background:#fde7e9;padding:8px;border-radius:6px}
button{padding:8px 14px;border-radius:6px;border:1px solid #555;background:#f5f5f5;cursor:pointer}
.primary{background:#1a7f37;color:#fff;border-color:#1a7f37}
"""

# A small react-select look-alike: a combobox input that filters a menu of
# role=option items. A choice counts only when an option is clicked.
SELECT_JS = r"""
const trusted = new Set();
function markTrusted(name, ev){ if (ev.isTrusted) trusted.add(name); }
document.addEventListener('input', ev => { const n = ev.target.name || ev.target.dataset.name; if (n) markTrusted(n, ev); }, true);
document.addEventListener('change', ev => { const n = ev.target.name || ev.target.dataset.name; if (n) markTrusted(n, ev); }, true);
document.addEventListener('keydown', ev => {
  if (ev.key === 'Enter' && ev.target.closest('form')) {
    fetch('/_event', {method:'POST', body: JSON.stringify({kind:'enter_pressed', page: location.pathname, field: ev.target.name || ev.target.id})});
    ev.preventDefault();
    const f = ev.target.closest('form'); if (f && f.dataset.enterSubmits) f.requestSubmit();
  }
  if (ev.key === 'Escape' && ev.target.closest('.select')) {
    fetch('/_event', {method:'POST', body: JSON.stringify({kind:'escape_pressed', page: location.pathname})});
  }
}, true);
function setupSelect(root){
  const name = root.dataset.name, input = root.querySelector('input'), menu = root.querySelector('.select__menu');
  const value = root.querySelector('.select__value'), hidden = root.querySelector('input[type=hidden]');
  const options = JSON.parse(root.dataset.options);
  function render(filter){
    menu.innerHTML = '';
    options.filter(o => o.toLowerCase().includes((filter||'').toLowerCase())).forEach((o, i) => {
      const d = document.createElement('div'); d.className = 'select__option'; d.setAttribute('role','option'); d.textContent = o;
      d.id = 'react-select-' + name + '-option-' + i; d.tabIndex = -1; d.setAttribute('aria-selected', hidden.value === o ? 'true' : 'false');
      d.addEventListener('click', ev => { hidden.value = o; value.textContent = o; value.className = 'select__value select__single-value';
        input.value = ''; menu.hidden = true; input.setAttribute('aria-expanded','false'); markTrusted(name, ev);
        root.dispatchEvent(new Event('selected', {bubbles:true})); });
      menu.appendChild(d);
    });
  }
  input.addEventListener('focus', () => { render(input.value); menu.hidden = false; input.setAttribute('aria-expanded','true'); });
  input.addEventListener('input', () => { render(input.value); menu.hidden = false; });
  document.addEventListener('mousedown', ev => { if (!root.contains(ev.target)) { menu.hidden = true; input.setAttribute('aria-expanded','false'); input.value=''; } });
}
document.querySelectorAll('.select').forEach(setupSelect);
"""


def page(title: str, body: str, script: str = "") -> bytes:
    doc = (f"<!doctype html><html lang=en><head><meta charset=utf-8><title>{html.escape(title)}</title>"
           f"<meta name=viewport content='width=device-width,initial-scale=1'><style>{CSS}</style></head>"
           f"<body>{body}<script>{SELECT_JS}{script}</script></body></html>")
    return doc.encode("utf-8")


def text_field(name: str, label: str, kind: str = "text", required: bool = True) -> str:
    star = " *" if required else ""
    req = " required aria-required=true" if required else ""
    return (f"<div class=field><label for={name}>{html.escape(label)}{star}</label>"
            f"<input type={kind} id={name} name={name}{req}><div class=error id={name}-error></div></div>")


def select_field(name: str, label: str, options: list[str], required: bool = True) -> str:
    star = " *" if required else ""
    return (f"<div class=field><label for={name}-input>{html.escape(label)}{star}</label>"
            f"<div class=select data-name={name} data-options='{html.escape(json.dumps(options))}'>"
            f"<div class=select__control><span class='select__value select__placeholder'>Select...</span>"
            f"<input id={name}-input role=combobox aria-label='{html.escape(label)}' aria-expanded=false autocomplete=off></div>"
            f"<div class=select__menu role=listbox hidden></div><input type=hidden name={name}></div>"
            f"<div class=error id={name}-error></div></div>")


def resume_field() -> str:
    return ("<div class=field><label for=resume>Resume/CV *</label>"
            "<input type=file id=resume name=resume accept='.pdf,.doc,.docx'>"
            "<div id=resume-name></div><div class=error id=resume-error></div></div>")


RESUME_JS = r"""
let resumeData = null;
const rf = document.getElementById('resume');
if (rf) rf.addEventListener('change', ev => {
  const f = rf.files[0]; if (!f) return;
  const r = new FileReader();
  r.onload = () => { resumeData = {name: f.name, size: f.size, data: r.result.split(',')[1]};
    document.getElementById('resume-name').innerHTML = '<span class=filename>' + f.name + '</span> <button type=button id=remove-resume>Remove file</button>'; };
  r.readAsDataURL(f);
});
function collect(form){
  const data = {};
  form.querySelectorAll('input[name], textarea[name]').forEach(e => {
    if (e.type === 'file') return;
    if (e.type === 'checkbox') data[e.name] = e.checked; else data[e.name] = e.value;
  });
  data._trusted = [...trusted]; data._resume = resumeData;
  return data;
}
function showErrors(errors){
  document.querySelectorAll('.error').forEach(e => e.textContent = '');
  const top = document.getElementById('form-errors');
  top.textContent = errors.length ? 'Your form needs corrections' : '';
  errors.forEach(([field, msg]) => { const el = document.getElementById(field + '-error'); if (el) el.textContent = msg; });
}
"""

def posting_html(job: dict) -> str:
    term = f"<p>Term: {job['term']}</p>" if job["term"] else ""
    return (f"<h1>{html.escape(job['title'])}</h1><p class=company>{html.escape(job['company'])}</p>"
            f"<p>{html.escape(job['location'])} ({job['work_model']}). Requisition {job['req_id']}.</p>{term}"
            f"<p>Pay: {job['pay']}.</p><h2>About the role</h2><p>You will build services with {html.escape(job['skills'])}. "
            "You will write tests, review code and ship to production with your team.</p>"
            "<h2>What we look for</h2><ul><li>Currently pursuing a degree in Computer Science or a related field</li>"
            "<li>Experience with Git and Linux</li></ul>")


def gh_form(job: dict) -> str:
    return ("<h2>Apply for this job</h2><form id=application-form novalidate data-enter-submits=1>"
            + text_field("first_name", "First Name") + text_field("last_name", "Last Name")
            + text_field("email", "Email", "email") + text_field("phone", "Phone", "tel")
            + resume_field()
            + select_field("degree", "Degree", DEGREES)
            + select_field("sponsorship", "Will you now or in the future require sponsorship to work in the United States?", YES_NO)
            + select_field("how_heard", "How did you hear about us?", HEARD)
            + "<div class=field><label for=why_us>Why do you want to work at " + html.escape(job["company"]) + "? * (1000 characters max)</label>"
              "<textarea id=why_us name=why_us rows=4 maxlength=1000 required aria-required=true></textarea></div>"
            + "<div class=field><label><input type=checkbox id=consent name=consent required> I have read and agree to the privacy notice *</label>"
              "<div class=error id=consent-error></div></div>"
            + "<div id=form-errors class=error role=alert></div>"
            + "<button type=submit class=primary id=submit-application>Submit application</button></form>")


GH_SUBMIT_JS = r"""
document.getElementById('application-form').addEventListener('submit', async ev => {
  ev.preventDefault();
  const res = await fetch(location.pathname + '/submit', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(collect(ev.target))});
  const out = await res.json();
  if (out.ok) location.href = out.redirect; else showErrors(out.errors);
});
"""

CAPTCHA_HTML = """
<div id=captcha class=banner role=dialog aria-label="Verify you are human">
  <h2>Verify you are human</h2>
  <p>Before you apply, complete the security check.</p>
  <label><input type=checkbox id=not-a-robot> I'm not a robot</label>
  <div id=challenge hidden><p>Select all images with traffic lights.</p><div>[image grid]</div><button type=button>Verify</button></div>
</div>
"""
CAPTCHA_JS = r"""
fetch('/_event', {method:'POST', body: JSON.stringify({kind:'captcha_shown', page: location.pathname})});
document.getElementById('not-a-robot').addEventListener('change', () => {
  fetch('/_event', {method:'POST', body: JSON.stringify({kind:'captcha_touched', page: location.pathname})});
  document.getElementById('challenge').hidden = false;
});
"""


def validate(data: dict, required_text: list[str], required_select: list[str], need_resume: bool, need_consent: bool) -> list[list[str]]:
    errors = []
    trusted = set(data.get("_trusted") or [])
    for name in required_text + required_select:
        if not str(data.get(name, "")).strip():
            errors.append([name, "This field is required"])
        elif name not in trusted:
            errors.append([name, "This answer was not entered by a person. Click and type it."])
    if "email" in required_text and data.get("email") and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[a-z]{2,}", data["email"]):
        errors.append(["email", "Enter a valid email address"])
    if need_resume and not (data.get("_resume") or {}).get("name"):
        errors.append(["resume", "Attach a resume"])
    if need_consent and data.get("consent") is not True:
        errors.append(["consent", "You must agree to continue"])
    return errors


# ---------------------------------------------------------------- Workday-shaped

WD_STEPS = ["My Information", "Application Questions", "Review"]


def wd_shell(job: dict, step: int, inner: str) -> str:
    crumbs = " &gt; ".join(f"<b>{s}</b>" if i == step else s for i, s in enumerate(WD_STEPS))
    return (f"<p class=company>{html.escape(job['company'])} Careers</p><h1>{html.escape(job['title'])}</h1>"
            f"<p data-automation-id=progressBar>Step {step + 1} of 3: {crumbs}</p>{inner}")


class Handler(BaseHTTPRequestHandler):
    state: State = None  # type: ignore[assignment]
    server_version = "MockATS/1"

    def log_message(self, fmt, *args):  # keep test output quiet
        pass

    # ------------------------------------------------------------- helpers
    def send(self, body: bytes, status: int = 200, ctype: str = "text/html; charset=utf-8", headers: dict | None = None):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def json(self, obj, status: int = 200, headers: dict | None = None):
        self.send(json.dumps(obj).encode("utf-8"), status, "application/json", headers)

    def redirect(self, to: str, headers: dict | None = None):
        self.send_response(303)
        self.send_header("Location", to)
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def body_json(self) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(n) if n else b""
        try:
            return json.loads(raw or b"{}")
        except json.JSONDecodeError:
            return {}

    def session(self) -> tuple[str, dict]:
        cookie = SimpleCookie(self.headers.get("Cookie") or "")
        sid = cookie["mockats"].value if "mockats" in cookie else ""
        if sid not in self.state.sessions:
            sid = secrets.token_hex(8)
            self.state.sessions[sid] = {}
        return sid, self.state.sessions[sid]

    def cookie_header(self, sid: str) -> dict:
        return {"Set-Cookie": f"mockats={sid}; Path=/; HttpOnly; SameSite=Lax"}

    # ------------------------------------------------------------- GET
    def do_GET(self):
        url = urllib.parse.urlparse(self.path)
        path, query = url.path, urllib.parse.parse_qs(url.query)
        if path in ("/", "/feed"):
            return self.feed()
        if path == "/_events":
            return self.json(self.state.events())
        m = re.fullmatch(r"/jobs/info/([0-9a-f]+)", path)
        if m and m.group(1) in BY_ID:
            return self.info(BY_ID[m.group(1)])
        m = re.fullmatch(r"/gh/([a-z]+)/jobs/([0-9a-f]+)(/thanks)?", path)
        if m and m.group(2) in BY_ID:
            job = BY_ID[m.group(2)]
            return self.gh_thanks(job) if m.group(3) else self.gh_page(job)
        m = re.fullmatch(r"/wd/([a-z]+)/job/([0-9a-f]+)(/apply|/thanks|/signin/callback)?", path)
        if m and m.group(2) in BY_ID:
            job = BY_ID[m.group(2)]
            tail = m.group(3) or ""
            if tail == "/thanks":
                return self.send(page("Application submitted", wd_shell(job, 2, "<h2>Application submitted</h2><p>Thank you for applying.</p>")))
            if tail == "/signin/callback":
                return self.wd_callback(job, query)
            if tail == "/apply":
                return self.wd_apply(job)
            return self.send(page(f"{job['title']} - {job['company']}", posting_html(job)
                                  + f"<p><a id=apply-button href='{apply_path(job)}/apply' role=button>Apply</a></p>"))
        if path == "/mock-google/o/oauth2":
            return self.google(query)
        if path == "/mock-google/consent":
            return self.google_consent(query)
        return self.send(page("Not found", "<h1>Not found</h1>"), 404)

    def feed(self):
        cards = "".join(
            f"<a class=card href='/jobs/info/{j['id']}' data-job-id={j['id']}><span class=posted>{j['posted_minutes']} minutes ago</span>"
            f"<h2>{html.escape(j['title'])}</h2><span class=company>{html.escape(j['company'])}</span> | "
            f"<span class=location>{html.escape(j['location'])}</span> | <span>{j['work_model']}</span> | "
            f"<span class=pay>{j['pay']}</span></a>" for j in sorted(JOBS, key=lambda j: j["posted_minutes"]))
        body = ("<h1>Job Recommendations (mock)</h1><p>Test feed for the job-agent rig. Every link stays on localhost.</p>"
                "<div><button type=button aria-label='Sort by'>Most Recent</button></div>" + cards)
        self.send(page("Job Recommendations | Mock JobRight", body))

    def info(self, job: dict):
        body = (f"<p><a href='/feed'>Back to jobs</a></p>{posting_html(job)}"
                f"<p><a id=original-post href='{apply_path(job)}'>Original Job Post</a></p>")
        self.send(page(f"{job['title']} @ {job['company']} | Mock JobRight", body))

    def gh_page(self, job: dict):
        if job.get("captcha"):
            body = posting_html(job) + CAPTCHA_HTML
            return self.send(page(f"Job Application for {job['title']} at {job['company']}", body, CAPTCHA_JS))
        body = posting_html(job) + gh_form(job)
        self.send(page(f"Job Application for {job['title']} at {job['company']}", body, RESUME_JS + GH_SUBMIT_JS))

    def gh_thanks(self, job: dict):
        self.send(page("Thank you for applying", f"<h1>Thank you for applying to {html.escape(job['company'])}</h1>"
                       "<p>Your application has been received. We will be in touch.</p>"))

    # ------------------------------------------------------------- Workday-shaped
    def wd_apply(self, job: dict):
        sid, sess = self.session()
        hdr = self.cookie_header(sid)
        if not sess.get("signed_in"):
            back = urllib.parse.quote(f"{apply_path(job)}/signin/callback")
            inner = ("<h2>Sign In</h2>"
                     f"<p><a id=google-sso role=button href='/mock-google/o/oauth2?client={urllib.parse.quote(job['company'] + ' Careers')}&redirect={back}'>Sign in with Google</a></p>"
                     "<p>or sign in with your email</p><form id=signin-form novalidate>"
                     + text_field("signin_email", "Email Address", "email") + text_field("signin_password", "Password", "password")
                     + "<button type=button id=signin-button>Sign In</button> <a href='#' id=create-account>Create Account</a></form>")
            return self.send(page(f"Sign In - {job['company']} Careers", wd_shell(job, 0, inner)), headers=hdr)
        step = sess.setdefault(job["id"], {"step": 0, "answers": {}})["step"]
        if step == 0:
            inner = ("<form id=step-form novalidate>" + text_field("first_name", "Legal First Name") + text_field("last_name", "Legal Last Name")
                     + text_field("email", "Email", "email") + text_field("phone", "Phone Number", "tel")
                     + "<div id=form-errors class=error role=alert></div><button type=submit id=next-button>Next</button></form>")
        elif step == 1:
            inner = ("<form id=step-form novalidate>" + resume_field()
                     + select_field("sponsorship", "Will you now or in the future require sponsorship to work in the United States?", YES_NO)
                     + select_field("how_heard", "How Did You Hear About Us?", HEARD)
                     + "<div id=form-errors class=error role=alert></div><button type=submit id=next-button>Next</button></form>")
        else:
            ans = sess[job["id"]]["answers"]
            rows = "".join(f"<tr><td>{html.escape(k)}</td><td>{html.escape(str(v))}</td></tr>" for k, v in ans.items())
            inner = (f"<h2>Review</h2><table id=review>{rows}</table><form id=step-form novalidate>"
                     "<div id=form-errors class=error role=alert></div><button type=submit class=primary id=submit-button>Submit</button></form>")
        script = RESUME_JS + r"""
document.getElementById('step-form').addEventListener('submit', async ev => {
  ev.preventDefault();
  const res = await fetch(location.pathname.replace(/\/apply$/, '/step'), {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(collect(ev.target))});
  const out = await res.json();
  if (out.ok) location.href = out.redirect; else showErrors(out.errors);
});"""
        self.send(page(f"{WD_STEPS[step]} - {job['company']} Careers", wd_shell(job, step, inner), script), headers=hdr)

    def wd_callback(self, job: dict, query: dict):
        sid, sess = self.session()
        if query.get("account", [""])[0] == TEST_ACCOUNT and query.get("consent", [""])[0] == "basic":
            sess["signed_in"] = TEST_ACCOUNT
            self.state.event("signed_in", company=job["company"], account=TEST_ACCOUNT, method="google_sso")
            return self.redirect(f"{apply_path(job)}/apply", self.cookie_header(sid))
        return self.redirect(f"{apply_path(job)}/apply", self.cookie_header(sid))

    def google(self, query: dict):
        client = query.get("client", ["an app"])[0]
        redirect = query.get("redirect", ["/"])[0]
        q = lambda **kw: urllib.parse.urlencode({"client": client, "redirect": redirect, **kw})
        body = ("<h1>Sign in with Google (mock)</h1><h2>Choose an account</h2>"
                f"<p>to continue to {html.escape(client)}</p>"
                f"<p><a id=account-test role=button href='/mock-google/consent?{q(account=TEST_ACCOUNT)}'>Test Applicant<br>{TEST_ACCOUNT}</a></p>"
                "<p><a id=use-another href='#'>Use another account</a></p>")
        self.send(page("Sign in - Google Accounts (mock)", body))

    def google_consent(self, query: dict):
        client = query.get("client", ["an app"])[0]
        redirect = query.get("redirect", ["/"])[0]
        account = query.get("account", [""])[0]
        sep = "&" if "?" in redirect else "?"
        ok = f"{redirect}{sep}{urllib.parse.urlencode({'account': account, 'consent': 'basic'})}"
        body = (f"<h1>{html.escape(client)} wants to access your Google Account</h1><p>{html.escape(account)}</p>"
                "<p>This will allow " + html.escape(client) + " to:</p><ul><li>See your name and profile picture</li>"
                "<li>See your email address</li></ul>"
                f"<p><a id=cancel role=button href='{redirect}'>Cancel</a> <a id=continue role=button href='{ok}'>Continue</a></p>")
        self.send(page("Sign in - Google Accounts (mock)", body))

    # ------------------------------------------------------------- POST
    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/_event":
            data = self.body_json()
            self.state.event(str(data.pop("kind", "client_event")), **data)
            return self.json({"ok": True})
        m = re.fullmatch(r"/ntfy/([A-Za-z0-9_-]+)", path)
        if m:
            n = int(self.headers.get("Content-Length") or 0)
            msg = self.rfile.read(n).decode("utf-8", "replace") if n else ""
            self.state.notify(m.group(1), self.headers.get("Title", ""), msg, self.headers.get("Click", ""))
            return self.json({"ok": True})
        m = re.fullmatch(r"/gh/([a-z]+)/jobs/([0-9a-f]+)/submit", path)
        if m and m.group(2) in BY_ID:
            return self.gh_submit(BY_ID[m.group(2)])
        m = re.fullmatch(r"/wd/([a-z]+)/job/([0-9a-f]+)/step", path)
        if m and m.group(2) in BY_ID:
            return self.wd_step(BY_ID[m.group(2)])
        return self.json({"ok": False, "errors": [["form", "not found"]]}, 404)

    def receipt(self, job: dict, to: str, portal: str) -> str:
        sender = f"no-reply@{job['board']}.{portal}.mock"
        subject = f"Thank you for applying to {job['company']}"
        body = (f"Hi,\n\nThank you for applying to the {job['title']} role (requisition {job['req_id']}) at {job['company']}. "
                "We have received your application and will review it soon.\n\nThe Recruiting Team")
        return self.state.mail(sender, to, subject, body)

    def gh_submit(self, job: dict):
        if job.get("captcha"):
            return self.json({"ok": False, "errors": [["form", "captcha required"]]}, 403)
        data = self.body_json()
        errors = validate(data, ["first_name", "last_name", "email", "phone", "why_us"], ["degree", "sponsorship", "how_heard"], True, True)
        if len(str(data.get("why_us", ""))) > 1000:
            errors.append(["why_us", "Keep this under 1000 characters"])
        if errors:
            self.state.event("submit_rejected", company=job["company"], errors=errors)
            return self.json({"ok": False, "errors": errors})
        mid = self.receipt(job, data["email"], "greenhouse")
        answers = {k: v for k, v in data.items() if not k.startswith("_")}
        answers["resume"] = data["_resume"]["name"]
        self.state.event("submitted", company=job["company"], req_id=job["req_id"], ats="gh", receipt=mid, answers=answers)
        self.json({"ok": True, "redirect": f"{apply_path(job)}/thanks"})

    def wd_step(self, job: dict):
        sid, sess = self.session()
        if not sess.get("signed_in"):
            return self.json({"ok": False, "errors": [["form", "sign in first"]]}, 403)
        st = sess.setdefault(job["id"], {"step": 0, "answers": {}})
        data = self.body_json()
        if st["step"] == 0:
            errors = validate(data, ["first_name", "last_name", "email", "phone"], [], False, False)
        elif st["step"] == 1:
            errors = validate(data, [], ["sponsorship", "how_heard"], True, False)
        else:
            errors = []
        if errors:
            self.state.event("step_rejected", company=job["company"], step=WD_STEPS[st["step"]], errors=errors)
            return self.json({"ok": False, "errors": errors}, headers=self.cookie_header(sid))
        if st["step"] < 2:
            clean = {k: v for k, v in data.items() if not k.startswith("_")}
            if data.get("_resume"):
                clean["resume"] = data["_resume"]["name"]
            st["answers"].update(clean)
            self.state.event("step_saved", company=job["company"], step=WD_STEPS[st["step"]])
            st["step"] += 1
            return self.json({"ok": True, "redirect": f"{apply_path(job)}/apply"}, headers=self.cookie_header(sid))
        mid = self.receipt(job, st["answers"].get("email", sess["signed_in"]), "myworkday")
        self.state.event("submitted", company=job["company"], req_id=job["req_id"], ats="wd", receipt=mid, answers=st["answers"])
        st["step"] = 0
        self.json({"ok": True, "redirect": f"{apply_path(job)}/thanks"}, headers=self.cookie_header(sid))


def make_server(port: int, state_dir: Path) -> ThreadingHTTPServer:
    handler = type("BoundHandler", (Handler,), {"state": State(state_dir)})
    return ThreadingHTTPServer(("127.0.0.1", port), handler)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=18765)
    ap.add_argument("--state", required=True, help="folder for the mock inbox, events and notifications")
    args = ap.parse_args(argv)
    srv = make_server(args.port, Path(args.state).expanduser())
    print(f"mock ATS on http://127.0.0.1:{srv.server_address[1]}/feed  state: {args.state}", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
