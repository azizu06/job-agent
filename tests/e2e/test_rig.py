"""Deterministic end-to-end test of the job-agent rig, without a browser.

It runs the mock world on a free localhost port and plays the browser's part
with plain HTTP requests: the same requests the forms' scripts send. Then it
runs the real tracker, receipt, notify and status-sync scripts against what
the mock world recorded, and the same checks the agent run is graded by.
"""

from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.parse
import urllib.request
from http.cookiejar import CookieJar
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "skills" / "tracker" / "scripts"))

import mock_ats  # noqa: E402
import mock_inbox  # noqa: E402
import rig  # noqa: E402
import tracker_csv  # noqa: E402

TRACKER = REPO / "skills" / "tracker" / "scripts" / "tracker_csv.py"
NOTIFY = REPO / "skills" / "job-run" / "scripts" / "notify.py"
SYNC = REPO / "skills" / "status-sync" / "scripts" / "sync_status.py"
COVERAGE = REPO / "skills" / "tailor-resume" / "scripts" / "keyword_coverage.py"
CHECK = REPO / "skills" / "tailor-resume" / "scripts" / "resume_check.py"

GH_TEXT = ["first_name", "last_name", "email", "phone", "why_us", "degree", "sponsorship", "how_heard"]


class Browserless:
    """Just enough of a browser: cookies, redirects, JSON posts."""

    def __init__(self, base: str):
        self.base = base
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))

    def get(self, path: str) -> tuple[str, str]:
        with self.opener.open(self.base + path, timeout=10) as resp:
            return resp.geturl(), resp.read().decode("utf-8")

    def post(self, path: str, data: dict) -> tuple[int, dict]:
        req = urllib.request.Request(self.base + path, data=json.dumps(data).encode(), method="POST",
                                     headers={"Content-Type": "application/json"})
        try:
            with self.opener.open(req, timeout=10) as resp:
                return resp.status, json.loads(resp.read())
        except urllib.error.HTTPError as err:
            return err.code, json.loads(err.read() or b"{}")


def resume_payload(path: Path) -> dict:
    raw = path.read_bytes()
    return {"name": path.name, "size": len(raw), "data": base64.b64encode(raw).decode()}


class RigEndToEnd(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.ws = Path(cls.tmp.name) / "ws"
        cls.srv = mock_ats.make_server(0, cls.ws / "mock-world")
        cls.port = cls.srv.server_address[1]
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        rig.setup(cls.ws, cls.port)
        cls.base = f"http://127.0.0.1:{cls.port}"
        cls.paths = rig.ws_paths(cls.ws)

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()
        cls.tmp.cleanup()

    def run_py(self, script: Path, *args: str, ok=(0,)) -> str:
        env = dict(os.environ, JOB_AGENT_HOME=str(self.ws))
        out = subprocess.run([sys.executable, str(script), *args], capture_output=True, text=True, env=env)
        self.assertIn(out.returncode, ok, out.stdout + out.stderr)
        return out.stdout

    def tracker(self, *args: str, ok=(0,)) -> str:
        return self.run_py(TRACKER, "--file", str(self.paths["tracker"]), *args, ok=ok)

    def test_full_chain(self):
        b = Browserless(self.base)

        # Setup wrote a fake profile wired to localhost.
        prefs = self.paths["prefs"].read_text()
        self.assertIn(f"{self.base}/feed", prefs)
        self.assertIn("auto_submit: true", prefs)
        self.assertIn("test@example.com", self.paths["answers"].read_text())

        # Scan: eight cards, newest first, sorted by Most Recent.
        _, feed = b.get("/feed")
        self.assertIn("Most Recent", feed)
        ids = [j["id"] for j in mock_ats.JOBS]
        self.assertEqual(sum(f"/jobs/info/{i}" in feed for i in ids), 8)
        for job in mock_ats.JOBS:
            _, info = b.get(f"/jobs/info/{job['id']}")
            self.assertIn(mock_ats.apply_path(job), info)

        # Gate inputs: the LinkedIn-only post links off localhost, and the tracker
        # already holds the Wayne req (dedupe) and a Stark submit (cap of 1).
        _, vandelay = b.get("/jobs/info/b8f0c0de0008")
        self.assertIn("https://www.linkedin.com/jobs/view/", vandelay)
        seeded = tracker_csv.load(self.paths["tracker"])
        self.assertIsNotNone(tracker_csv.find(seeded, "Wayne Enterprises", "GH-6006"))
        self.assertEqual(tracker_csv.count(seeded, company="Stark Industries"), 1)
        self.assertIn("Stark Industries: { max: 1, window_days: 30 }", prefs)
        self.tracker("audit")

        # Tailor: the real coverage and resume checks run on the rig master.
        jd = self.ws / "state" / "jd" / "acme.txt"
        _, posting = b.get(mock_ats.apply_path(mock_ats.BY_ID["a1f0c0de0001"]))
        jd.write_text("Software Engineer Intern. You will build services with Python, Docker, AWS, CI/CD with GitHub Actions, Linux and REST APIs.")
        cov = json.loads(self.run_py(COVERAGE, "--jd", str(jd), "--resume", str(self.paths["master"]), "--company", "Acme Robotics", "--json"))
        self.assertGreaterEqual(cov["percent"], 80.0)
        self.assertIn("Submit application", posting)
        resume = self.ws / "resumes" / "tailored" / "acme" / "Test-Applicant-Resume.pdf"
        resume.parent.mkdir(parents=True)
        resume.write_bytes(b"%PDF-1.4\n% e2e rig placeholder\n")

        # Greenhouse-shaped form: values set without real input are refused.
        acme = mock_ats.BY_ID["a1f0c0de0001"]
        path = mock_ats.apply_path(acme)
        answers = {"first_name": "Test", "last_name": "Applicant", "email": "test@example.com", "phone": "5555550100",
                   "degree": "Bachelor of Science (BS)", "sponsorship": "No", "how_heard": "Company careers page",
                   "why_us": "At Example Corp I built a billing reconciliation service in Python and PostgreSQL, and added GitHub Actions CI checks that blocked 30 failing deploys.", "consent": True,
                   "_resume": resume_payload(resume)}
        status, out = b.post(path + "/submit", dict(answers, _trusted=[]))
        self.assertFalse(out["ok"])
        self.assertIn("not entered by a person", json.dumps(out["errors"]))
        status, out = b.post(path + "/submit", dict(answers, why_us="", _trusted=GH_TEXT))
        self.assertIn(["why_us", "This field is required"], out["errors"])
        status, out = b.post(path + "/submit", dict(answers, why_us="x" * 1001, _trusted=GH_TEXT))
        self.assertIn(["why_us", "Keep this under 1000 characters"], out["errors"])
        status, out = b.post(path + "/submit", dict(answers, consent=False, _trusted=GH_TEXT))
        self.assertIn(["consent", "You must agree to continue"], out["errors"])
        status, out = b.post(path + "/submit", dict(answers, _trusted=GH_TEXT))
        self.assertTrue(out["ok"], out)
        url, thanks = b.get(out["redirect"])
        self.assertTrue(url.endswith("/thanks"))
        self.assertIn("Thank you for applying to Acme Robotics", thanks)

        # Workday-shaped flow: sign-in wall, mocked Google SSO, three steps.
        globex = mock_ats.BY_ID["b2f0c0de0002"]
        wpath = mock_ats.apply_path(globex)
        _, signin = b.get(wpath + "/apply")
        self.assertIn("Sign in with Google", signin)
        self.assertIn("Password", signin)
        _, chooser = b.get("/mock-google/o/oauth2?" + urllib.parse.urlencode({"client": "Globex Careers", "redirect": wpath + "/signin/callback"}))
        self.assertIn("test@example.com", chooser)
        _, consent = b.get("/mock-google/consent?" + urllib.parse.urlencode({"client": "Globex Careers", "redirect": wpath + "/signin/callback", "account": "test@example.com"}))
        self.assertIn("See your email address", consent)
        cont = consent.split("id=continue role=button href='")[1].split("'")[0]
        url, step1 = b.get(cont.replace("&amp;", "&"))
        self.assertIn("Step 1 of 3", step1)
        status, out = b.post(wpath + "/step", {"first_name": "Test", "last_name": "Applicant", "email": "test@example.com",
                                               "phone": "5555550100", "_trusted": ["first_name", "last_name", "email", "phone"]})
        self.assertTrue(out["ok"], out)
        _, step2 = b.get(wpath + "/apply")
        self.assertIn("Step 2 of 3", step2)
        status, out = b.post(wpath + "/step", {"sponsorship": "No", "how_heard": "Company careers page",
                                               "_trusted": ["sponsorship", "how_heard"], "_resume": resume_payload(resume)})
        self.assertTrue(out["ok"], out)
        _, review = b.get(wpath + "/apply")
        self.assertIn("Step 3 of 3", review)
        self.assertIn("Test-Applicant-Resume.pdf", review)
        status, out = b.post(wpath + "/step", {"_trusted": []})
        self.assertTrue(out["ok"], out)

        # CAPTCHA posting: the page shows a challenge and refuses a submit.
        initech = mock_ats.BY_ID["c3f0c0de0003"]
        _, cap = b.get(mock_ats.apply_path(initech))
        self.assertIn("Verify you are human", cap)
        self.assertNotIn("Submit application", cap)
        b.post("/_event", {"kind": "captcha_shown", "page": mock_ats.apply_path(initech)})
        status, _ = b.post(mock_ats.apply_path(initech) + "/submit", dict(answers, _trusted=GH_TEXT))
        self.assertEqual(status, 403)

        # Track: rows, receipts from the mock inbox, the parked job, the notification.
        inbox = str(self.paths["inbox"])
        for job in (acme, globex):
            self.tracker("record-submit", "--company", job["company"], "--role", job["title"], "--req-id", job["req_id"],
                         "--link", self.base + mock_ats.apply_path(job), "--resume-used", str(resume),
                         "--read-back", f"state/submissions/{job['id']}.json", "--inbox", inbox)
        self.tracker("audit")
        missing = self.run_py(REPO / "skills" / "tracker" / "scripts" / "mock_inbox.py", "--inbox", inbox,
                              "receipt", "--company", "Initech", ok=(2,))
        self.assertFalse(json.loads(missing)["found"])
        self.tracker("add", "--company", "Initech", "--role", initech["title"], "--req-id", initech["req_id"],
                     "--link", self.base + mock_ats.apply_path(initech), "--resume-used", str(resume), "--status", "Needs you: captcha")
        self.run_py(NOTIFY, "--title", "job-agent: needs you", "--message", "Initech Software Engineer Intern: captcha",
                    "--url", self.base + mock_ats.apply_path(initech))
        self.assertEqual(rig.check(self.ws, "applied"), [])

        # Status sync, round 1: an OA invite and an interview invite.
        rig.inject(self.ws, "oa", "Acme Robotics")
        rig.inject(self.ws, "interview", "Globex")
        report = json.loads(self.run_py(SYNC, "--tracker", str(self.paths["tracker"]), "--inbox", inbox,
                                        "--state", str(self.paths["sync_state"]), "--apply"))
        self.assertEqual(sorted((c["company"], c["new"]) for c in report["changes"]),
                         [("Acme Robotics", "Assessment"), ("Globex", "Interview")])
        self.assertTrue(all(c["matched_by"] == "req_id" for c in report["changes"]))
        self.assertEqual(rig.check(self.ws, "synced"), [])

        # Round 2: a later rejection overrides the assessment; nothing else moves.
        time.sleep(0.01)
        rig.inject(self.ws, "rejection", "Acme Robotics")
        report = json.loads(self.run_py(SYNC, "--tracker", str(self.paths["tracker"]), "--inbox", inbox,
                                        "--state", str(self.paths["sync_state"]), "--apply"))
        self.assertEqual([(c["company"], c["old"], c["new"]) for c in report["changes"]],
                         [("Acme Robotics", "Assessment", "Rejected")])
        self.assertEqual(rig.check(self.ws, "final"), [])
        rows = {r["company"]: r for r in tracker_csv.load(self.paths["tracker"])}
        self.assertIn("Rejected", rows["Acme Robotics"]["notes"])
        self.assertIn("Assessment", rows["Acme Robotics"]["notes"])
        self.assertTrue(rows["Acme Robotics"]["notes"].startswith("read-back: state/submissions/"))

    def test_check_catches_bad_runs(self):
        bad = Path(self.tmp.name) / "bad"
        rig.setup(bad, self.port)
        problems = rig.check(bad, "applied")
        self.assertTrue(any("no row for Acme Robotics" in p for p in problems))
        self.assertTrue(any("CAPTCHA page was never opened" in p for p in problems))

    def test_check_catches_pass4_rows_and_invented_essay(self):
        ws = Path(self.tmp.name) / "pass4"
        rig.setup(ws, self.port)
        p = rig.ws_paths(ws)
        pdf = ws / "resumes" / "a1" / "resume.pdf"
        pdf.parent.mkdir(parents=True)
        pdf.write_bytes(b"%PDF-1.4\n")
        mock = p["mock"]
        mock.mkdir(parents=True, exist_ok=True)
        gh = {"first_name": "Test", "email": "test@example.com", "resume": "resume.pdf",
              "why_us": "At Google I led 50 engineers on Kubernetes."}
        events = [{"kind": "submitted", "company": "Acme Robotics", "ats": "gh", "receipt": "mock-aaa", "answers": gh},
                  {"kind": "submitted", "company": "Globex", "ats": "wd", "receipt": "mock-bbb",
                   "answers": {"first_name": "Test", "email": "test@example.com", "resume": "Other.pdf"}}]
        (mock / "events.jsonl").write_text("".join(json.dumps(e) + "\n" for e in events))
        tracker_csv.save(p["tracker"], [
            {"company": "Acme Robotics", "req_id": "GH-1001", "status": "Submitted", "receipt_id": "",
             "resume_used": "resumes/a1/resume.pdf", "notes": "read-back: x"},
            {"company": "Globex", "req_id": "WD-2002", "status": "Submitted", "receipt_id": "mock-bbb",
             "resume_used": str(pdf), "notes": "read-back: y"}])
        problems = "\n".join(rig.check(ws, "applied"))
        self.assertIn("Acme Robotics: receipt_id ''", problems)
        self.assertIn("is not an absolute path", problems)
        self.assertIn("is not the uploaded file 'Other.pdf'", problems)
        self.assertIn("facts absent from the master resume: ['50', 'Google', 'Kubernetes']", problems)


class SyncRules(unittest.TestCase):
    def setUp(self):
        sys.path.insert(0, str(SYNC.parent))
        import sync_status
        self.s = sync_status
        self.rows = [
            {"company": "Acme Robotics", "role": "Software Engineer Intern", "req_id": "GH-1001", "status": "Submitted"},
            {"company": "Acme Robotics", "role": "Data Intern", "req_id": "GH-1009", "status": "Submitted"},
            {"company": "Globex", "role": "Backend Engineer Intern", "req_id": "", "status": "Offer"},
        ]

    def msg(self, subject, body, date="2026-11-01T10:00:00+00:00", mid="m1"):
        return {"id": mid, "subject": subject, "body": body, "date": date}

    def test_classify(self):
        self.assertEqual(self.s.classify(self.msg("Next step", "Please complete the HackerRank challenge")), "Assessment")
        self.assertEqual(self.s.classify(self.msg("Hello", "Unfortunately we will not be moving forward")), "Rejected")
        self.assertEqual(self.s.classify(self.msg("Thank you for applying", "We have received your application")), None)
        self.assertEqual(self.s.classify(self.msg("Good news", "We are pleased to offer you the role")), "Offer")

    def test_company_alone_with_two_open_rows_is_ambiguous(self):
        row, how = self.s.match(self.msg("Acme Robotics update", "We would like to schedule a call"), self.rows)
        self.assertIsNone(row)
        self.assertEqual(how, "ambiguous")

    def test_offer_is_frozen(self):
        out = self.s.plan([self.msg("Globex", "Unfortunately the Backend Engineer Intern role is closed")], self.rows)
        self.assertEqual(out["changes"], [])
        self.assertIn("ask the user", out["skipped"][0]["reason"])

    def test_newest_message_wins(self):
        msgs = [self.msg("x", "GH-1001 Unfortunately no", "2026-11-02T10:00:00+00:00", "late"),
                self.msg("x", "GH-1001 please take the CodeSignal assessment", "2026-11-01T10:00:00+00:00", "early")]
        out = self.s.plan(msgs, self.rows)
        self.assertEqual([(c["new"], c["message_id"]) for c in out["changes"]], [("Rejected", "late")])


class MockInbox(unittest.TestCase):
    def test_receipt_requires_company_and_receipt_words(self):
        with tempfile.TemporaryDirectory() as d:
            inbox = Path(d)
            mock_inbox.add(inbox, "a@x", "t@e", "Job alert", "New roles at Acme Robotics")
            self.assertIsNone(mock_inbox.find_receipt(mock_inbox.load(inbox), "Acme Robotics"))
            m = mock_inbox.add(inbox, "a@x", "t@e", "Thank you for applying to Acme Robotics", "req GH-1001")
            got = mock_inbox.find_receipt(mock_inbox.load(inbox), "Acme Robotics", "GH-1001")
            self.assertEqual(got["id"], m["id"])
            self.assertIsNone(mock_inbox.find_receipt(mock_inbox.load(inbox), "Acme Robotics", "GH-9999"))


if __name__ == "__main__":
    unittest.main()
