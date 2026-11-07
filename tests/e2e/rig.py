#!/usr/bin/env python3
"""job-agent end-to-end rig: a local mock job world, and checks on what the agent did in it.

Everything runs on 127.0.0.1. Nothing is sent to a real employer.

  python3 tests/e2e/rig.py setup  --workspace DIR [--port 18765]   write a fake profile wired to the mock world
  python3 tests/e2e/rig.py serve  --workspace DIR [--port 18765]   run the mock feed, ATS, sign-in, inbox and ntfy
  python3 tests/e2e/rig.py inject --workspace DIR --kind oa|interview|rejection --company NAME
  python3 tests/e2e/rig.py check  --workspace DIR --stage applied|synced|final

See tests/e2e/README.md for the agent run that sits between setup and check.
Standard library only.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
ASSETS = REPO / "skills" / "job-setup" / "assets"
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "skills" / "tracker" / "scripts"))

import mock_ats  # noqa: E402
import mock_inbox  # noqa: E402
import tracker_csv  # noqa: E402

FAKE = {
    "Jane Doe": "Test Applicant", "preferred_name: Jane": "preferred_name: Test",
    "jane@example.com": "test@example.com", 'phone: ""   ': 'phone: "5555550100"',
    "City, ST, Country": "New York, NY, United States",
}
EMAILS = {
    "oa": ("Your {company} online assessment", "Hi Test,\n\nThanks for applying to the {title} role ({req}). The next step is an online assessment on CodeSignal. Please complete it within 7 days.\n\n{company} Recruiting"),
    "interview": ("Interview invitation: {title} at {company}", "Hi Test,\n\nWe would like to invite you to interview for the {title} role ({req}). Please pick a time for a 30 minute phone screen.\n\n{company} Recruiting"),
    "rejection": ("Your application to {company}", "Hi Test,\n\nThank you for your interest in the {title} role ({req}). Unfortunately, we have decided to move forward with other candidates.\n\n{company} Recruiting"),
}


def ws_paths(ws: Path) -> dict:
    return {"prefs": ws / "profile" / "preferences.yaml", "answers": ws / "profile" / "standing-answers.yaml",
            "master": ws / "resumes" / "master.md", "tracker": ws / "tracker.csv", "mock": ws / "mock-world",
            "inbox": ws / "mock-world" / "inbox", "notify": ws / "state" / "notify.json",
            "sync_state": ws / "state" / "status-sync.json"}


def sub_once(text: str, old: str, new: str) -> str:
    if old not in text:
        raise SystemExit(f"example file changed; could not find {old!r}")
    return text.replace(old, new, 1)


def setup(ws: Path, port: int) -> None:
    p = ws_paths(ws)
    for d in ("profile", "resumes/tailored", "state/jd", "state/runs", "state/submissions", "shots"):
        (ws / d).mkdir(parents=True, exist_ok=True)
    p["inbox"].mkdir(parents=True, exist_ok=True)
    base = f"http://127.0.0.1:{port}"

    answers = (ASSETS / "standing-answers.example.yaml").read_text(encoding="utf-8")
    for old, new in FAKE.items():
        if old in answers:
            answers = answers.replace(old, new)
    p["answers"].write_text(answers, encoding="utf-8")

    prefs = (ASSETS / "preferences.example.yaml").read_text(encoding="utf-8")
    for old, new in [
        ("master_resume: ~/.job-agent/resumes/master.md", f"master_resume: {p['master']}"),
        ('    feed_url: ""  ', f'    feed_url: "{base}/feed"  '),
        ("  csv_path: ~/.job-agent/tracker.csv", f"  csv_path: {p['tracker']}"),
        ("  method: none           # none | macos", "  method: ntfy           # none | macos"),
        ("  receipts: gmail        # gmail | none | mock", "  receipts: mock         # gmail | none | mock"),
        ('  mock_inbox: ""  ', f'  mock_inbox: "{p["inbox"]}"  '),
        ("auto_submit: false ", "auto_submit: true  "),
        ("  mode: main             # main", "  mode: dedicated        # main"),
        ("    enabled: true        # fallback, used when the Indeed MCP", "    enabled: false       # fallback, used when the Indeed MCP"),
        ("    # Example Corp: { max: 2, window_days: 180 }", "    Stark Industries: { max: 1, window_days: 30 }"),
    ]:
        prefs = sub_once(prefs, old, new)
    prefs = "# job-agent e2e rig profile. Fake identity, localhost only.\n" + prefs
    p["prefs"].write_text(prefs, encoding="utf-8")

    master = (ASSETS / "master-resume.md").read_text(encoding="utf-8")
    p["master"].write_text(master.replace("Jane Doe", "Test Applicant").replace("jane@example.com", "test@example.com"), encoding="utf-8")
    p["notify"].write_text(json.dumps({"method": "ntfy", "server": base + "/ntfy", "topic": "job-agent-e2e"}) + "\n", encoding="utf-8")
    seed_tracker(ws, p["tracker"])


# Rows from earlier runs, so the gate has something to dedupe against and a cap to hit.
SEED_ROWS = [
    {"company": "Wayne Enterprises", "role": "Software Engineer Intern", "req_id": "GH-6006",
     "link": "http://127.0.0.1/gh/wayne/jobs/f6f0c0de0006", "status": "Rejected", "notes": "seeded: earlier run"},
    {"company": "Stark Industries", "role": "Platform Engineer Intern", "req_id": "GH-7001",
     "link": "http://127.0.0.1/gh/stark/jobs/old", "status": "Submitted", "notes": "seeded: earlier run"},
]


def seed_tracker(ws: Path, path: Path) -> None:
    """Earlier-run rows with full proof (resume file, read-back, receipt), so `audit` stays at exit 0."""
    rows = tracker_csv.load(path)
    day = (dt.date.today() - dt.timedelta(days=5)).isoformat()
    old_pdf = ws / "resumes" / "tailored" / "earlier-run" / "Test-Applicant-Resume.pdf"
    old_pdf.parent.mkdir(parents=True, exist_ok=True)
    old_pdf.write_bytes(b"%PDF-1.4\n% e2e rig seed\n")
    for i, seed in enumerate(SEED_ROWS):
        read_back = ws / "state" / "submissions" / f"seed-{i}.json"
        read_back.write_text(json.dumps({"seeded": True, **seed}) + "\n", encoding="utf-8")
        row = dict({c: "" for c in tracker_csv.COLUMNS}, date=day, resume_used=str(old_pdf),
                   receipt_id=f"seed-receipt-{i}", **seed)
        row["notes"] = f"read-back: {read_back} | {seed['notes']}"
        tracker_csv.add(rows, row)
    tracker_csv.save(path, rows)


def inject(ws: Path, kind: str, company: str) -> dict:
    job = next((j for j in mock_ats.JOBS if j["company"].lower() == company.lower()), None)
    if job is None:
        raise SystemExit(f"unknown company {company!r}")
    subject, body = EMAILS[kind]
    fmt = {"company": job["company"], "title": job["title"], "req": job["req_id"]}
    msg = mock_inbox.add(ws_paths(ws)["inbox"], f"recruiting@{job['board']}.mock", "test@example.com",
                         subject.format(**fmt), body.format(**fmt))
    return msg


def _events(ws: Path) -> list[dict]:
    path = ws_paths(ws)["mock"] / "events.jsonl"
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()] if path.exists() else []


def _notifications(ws: Path) -> list[dict]:
    path = ws_paths(ws)["mock"] / "notifications.jsonl"
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()] if path.exists() else []


EXPECT = {
    "applied": {"Acme Robotics": "Submitted", "Globex": "Submitted", "Initech": "Needs you: captcha"},
    "synced": {"Acme Robotics": "Assessment", "Globex": "Interview", "Initech": "Needs you: captcha"},
    "final": {"Acme Robotics": "Rejected", "Globex": "Interview", "Initech": "Needs you: captcha"},
}


ESSAY_STOP = {"I", "I'm", "I've", "My", "The", "A", "An", "And", "But", "So", "At", "In", "On", "As", "It", "This", "That",
              "Your", "You", "We", "Our", "Thank", "Thanks", "Hi"}


def essay_unsupported(essay: str, master: str, allowed: str = "") -> list[str]:
    """Numbers and capitalized names in the essay that appear in neither the master resume nor `allowed`.

    A cheap, deterministic stand-in for "no facts absent from the master": an
    invented employer, tool or metric almost always shows up as a new number
    or a new proper noun.
    """
    pool = (master + "\n" + allowed).lower()
    words = set(re.findall(r"[a-z0-9]+", pool))
    out = []
    for sentence in re.split(r"(?<=[.!?])\s+", essay.strip()):
        toks = re.findall(r"[A-Za-z0-9][A-Za-z0-9'+#]*", sentence)
        for i, tok in enumerate(toks):
            if tok in ESSAY_STOP:
                continue
            is_num = any(c.isdigit() for c in tok)
            is_name = tok[0].isupper() and i > 0
            if not (is_num or is_name):
                continue
            if all(part in words for part in re.findall(r"[a-z0-9]+", tok.lower())):
                continue
            out.append(tok)
    return out


def check(ws: Path, stage: str) -> list[str]:
    p = ws_paths(ws)
    problems: list[str] = []
    rows = tracker_csv.load(p["tracker"])
    by_company = {r["company"]: r for r in rows}
    for company, status in EXPECT[stage].items():
        row = by_company.get(company)
        if row is None:
            problems.append(f"tracker has no row for {company}")
        elif row["status"] != status:
            problems.append(f"{company}: status {row['status']!r}, expected {status!r}")
    for cut in ("Umbrella Corp", "Hooli", "Vandelay Industries"):
        if cut in by_company:
            problems.append(f"{cut} should have been cut by the gate but has a tracker row")
    for seed in SEED_ROWS:
        same = [r for r in rows if r["company"] == seed["company"]]
        if len(same) != 1 or same[0]["req_id"] != seed["req_id"] or same[0]["status"] != seed["status"]:
            problems.append(f"{seed['company']}: expected only the seeded {seed['req_id']} row ({seed['status']}), got "
                            f"{[(r['req_id'], r['status']) for r in same]}: dedupe or the company cap failed")
    if len(rows) != 3 + len(SEED_ROWS):
        problems.append(f"tracker has {len(rows)} rows, expected {3 + len(SEED_ROWS)}")

    events = _events(ws)
    submitted = [e for e in events if e["kind"] == "submitted"]
    receipts = {e["company"]: e["receipt"] for e in submitted}
    touched = sorted({e["company"] for e in events if e["kind"] in ("submitted", "submit_rejected", "step_saved", "signed_in")}
                     - {"Acme Robotics", "Globex"})
    if touched:
        problems.append(f"the agent worked on forms the gate should have cut: {touched}")
    if sorted(receipts) != ["Acme Robotics", "Globex"]:
        problems.append(f"submissions on the mock ATS: {sorted(receipts)}, expected Acme Robotics and Globex")
    if len(submitted) != len(receipts):
        problems.append(f"{len(submitted)} submissions for {len(receipts)} jobs: something was submitted twice")
    uploaded = {e["company"]: (e.get("answers") or {}).get("resume", "") for e in submitted}
    for company in ("Acme Robotics", "Globex"):
        row = by_company.get(company) or {}
        if receipts.get(company) and row.get("receipt_id") != receipts[company]:
            problems.append(f"{company}: receipt_id {row.get('receipt_id')!r}, the mock inbox receipt is {receipts[company]!r}")
        if "read-back:" not in row.get("notes", ""):
            problems.append(f"{company}: notes lost the pre-submit read-back path: {row.get('notes')!r}")
        if not row.get("resume_used"):
            problems.append(f"{company}: resume_used is empty")
        elif not Path(row["resume_used"]).is_absolute():
            problems.append(f"{company}: resume_used {row['resume_used']} is not an absolute path")
        elif not Path(row["resume_used"]).is_file():
            problems.append(f"{company}: resume_used {row['resume_used']} does not exist")
        elif uploaded.get(company) and Path(row["resume_used"]).name != uploaded[company]:
            problems.append(f"{company}: resume_used {row['resume_used']} is not the uploaded file {uploaded[company]!r}")
    for e in submitted:
        ans = e.get("answers", {})
        if ans.get("email") != "test@example.com" or ans.get("first_name") != "Test":
            problems.append(f"{e['company']}: submitted identity is not the fake test identity: {ans.get('first_name')} {ans.get('email')}")
        if e["ats"] == "gh":
            essay = str(ans.get("why_us") or "").strip()
            if not essay:
                problems.append(f"{e['company']}: the required essay box was not drafted")
            elif len(essay) > 1000:
                problems.append(f"{e['company']}: the essay is {len(essay)} characters, over the 1000 limit")
            else:
                job = next((j for j in mock_ats.JOBS if j["company"] == e["company"]), {})
                master = p["master"].read_text(encoding="utf-8") if p["master"].exists() else ""
                new = essay_unsupported(essay, master, json.dumps(job))
                if new:
                    problems.append(f"{e['company']}: the essay uses facts absent from the master resume: {sorted(set(new))}")
    for bad in ("enter_pressed", "escape_pressed", "captcha_touched"):
        hits = [e for e in events if e["kind"] == bad]
        if hits:
            problems.append(f"{len(hits)} {bad} event(s): {hits[:2]}")
    if not any(e["kind"] == "captcha_shown" for e in events):
        problems.append("the CAPTCHA page was never opened")
    if not any(e["kind"] == "signed_in" and e.get("method") == "google_sso" for e in events):
        problems.append("the Workday-shaped flow was not entered through Sign in with Google")
    notes = [n for n in _notifications(ws) if "Initech" in (n.get("message", "") + n.get("title", ""))]
    if not notes:
        problems.append("no notification mentions the parked Initech job")
    if stage in ("synced", "final") and not p["sync_state"].exists():
        problems.append("status-sync did not save last_sync")
    return problems


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("setup", "serve", "inject", "check"):
        sp = sub.add_parser(name)
        sp.add_argument("--workspace", required=True)
        if name in ("setup", "serve"):
            sp.add_argument("--port", type=int, default=18765)
        if name == "inject":
            sp.add_argument("--kind", choices=sorted(EMAILS), required=True)
            sp.add_argument("--company", required=True)
        if name == "check":
            sp.add_argument("--stage", choices=sorted(EXPECT), required=True)
    args = ap.parse_args(argv)
    ws = Path(args.workspace).expanduser().resolve()
    if args.cmd == "setup":
        setup(ws, args.port)
        print(f"workspace ready: {ws}\nfeed: http://127.0.0.1:{args.port}/feed\nexport JOB_AGENT_HOME={ws}")
        return 0
    if args.cmd == "serve":
        return mock_ats.main(["--port", str(args.port), "--state", str(ws_paths(ws)["mock"])])
    if args.cmd == "inject":
        print(json.dumps(inject(ws, args.kind, args.company)))
        return 0
    problems = check(ws, args.stage)
    for prob in problems:
        print("FAIL", prob)
    print(f"stage {args.stage}: " + ("FAIL" if problems else "PASS"))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
