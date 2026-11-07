import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "tracker" / "scripts" / "tracker_csv.py"
sys.path.insert(0, str(SCRIPT.parent))

import tracker_csv as tc  # noqa: E402


class KeyTests(unittest.TestCase):
    def test_company_suffix_and_case_ignored(self):
        a = tc.row_key({"company": "Acme, Inc.", "req_id": "R-123"})
        b = tc.row_key({"company": "acme", "req_id": "r123"})
        self.assertEqual(a, b)

    def test_different_req_same_company_is_distinct(self):
        a = tc.row_key({"company": "Acme", "req_id": "R1"})
        b = tc.row_key({"company": "Acme", "req_id": "R2"})
        self.assertNotEqual(a, b)

    def test_falls_back_to_role_without_req(self):
        a = tc.row_key({"company": "Acme", "role": "SWE Intern"})
        b = tc.row_key({"company": "Acme", "role": "Data Intern"})
        self.assertNotEqual(a, b)


class RowTests(unittest.TestCase):
    def test_add_dedupes(self):
        rows = []
        _, created = tc.add(rows, {"company": "Acme", "role": "SWE", "req_id": "R1"})
        self.assertTrue(created)
        _, created = tc.add(rows, {"company": "ACME Inc", "role": "SWE", "req_id": "r1"})
        self.assertFalse(created)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["status"], "Ready")

    def test_update_status_and_reject_bad_status(self):
        rows = []
        tc.add(rows, {"company": "Acme", "req_id": "R1"})
        row = tc.update(rows, "Acme", "R1", "", {"status": "Interview", "receipt_id": None})
        self.assertEqual(row["status"], "Interview")
        with self.assertRaises(ValueError):
            tc.update(rows, "Acme", "R1", "", {"status": "Maybe"})
        self.assertIsNone(tc.update(rows, "Other", "R1", "", {"status": "Offer"}))

    def test_needs_you_status(self):
        rows = []
        tc.add(rows, {"company": "Acme", "req_id": "R1"})
        self.assertEqual(tc.update(rows, "Acme", "R1", "", {"status": "Needs you: captcha"})["status"], "Needs you: captcha")
        with self.assertRaises(ValueError):
            tc.update(rows, "Acme", "R1", "", {"status": "Needs you: "})

    def test_count_filters(self):
        rows = []
        tc.add(rows, {"company": "Acme", "req_id": "R1", "status": "Submitted", "date": "2026-01-05"})
        tc.add(rows, {"company": "Acme", "req_id": "R2", "status": "Submitted", "date": "2026-01-06"})
        tc.add(rows, {"company": "Beta", "req_id": "B1", "status": "Ready", "date": "2026-01-06"})
        self.assertEqual(tc.count(rows, status="Submitted"), 2)
        self.assertEqual(tc.count(rows, date="2026-01-06"), 2)
        self.assertEqual(tc.count(rows, company="acme inc"), 2)
        self.assertEqual(tc.count(rows, company="Acme", since="2026-01-06"), 1)


class CliTests(unittest.TestCase):
    def run_cli(self, path, *args):
        return subprocess.run([sys.executable, str(SCRIPT), "--file", str(path), *args], capture_output=True, text=True)

    def test_round_trip(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "tracker.csv"
            out = self.run_cli(path, "add", "--company", "Acme", "--req-id", "R1", "--role", "SWE", "--status", "Submitted")
            self.assertTrue(json.loads(out.stdout)["created"])
            out = self.run_cli(path, "add", "--company", "Acme", "--req-id", "R1")
            self.assertFalse(json.loads(out.stdout)["created"])
            out = self.run_cli(path, "update", "--company", "Acme", "--req-id", "R1", "--receipt-id", "MSG-1")
            self.assertEqual(json.loads(out.stdout)["row"]["receipt_id"], "MSG-1")
            out = self.run_cli(path, "find", "--company", "Nope", "--req-id", "X")
            self.assertEqual(out.returncode, 2)
            out = self.run_cli(path, "count", "--status", "Submitted")
            self.assertEqual(out.stdout.strip(), "1")
            self.assertEqual(path.read_text().splitlines()[0], ",".join(tc.COLUMNS))


class RecordSubmitTests(unittest.TestCase):
    """Pass 4 regression: empty receipt_id and a relative, missing resume_used."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = Path(self.tmp.name)
        self.csv = self.d / "tracker.csv"
        self.pdf = self.d / "resumes" / "acme" / "Test_Applicant_Acme.pdf"
        self.pdf.parent.mkdir(parents=True)
        self.pdf.write_bytes(b"%PDF-1.4\n")
        self.inbox = self.d / "inbox"
        import mock_inbox
        self.msg = mock_inbox.add(self.inbox, "no-reply@acme.mock", "test@example.com",
                                  "Thank you for applying to Acme Robotics", "We have received your application for GH-1001.")

    def tearDown(self):
        self.tmp.cleanup()

    def cli(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT), "--file", str(self.csv), *args], capture_output=True, text=True)

    def rec(self, resume, *extra):
        return self.cli("record-submit", "--company", "Acme Robotics", "--req-id", "GH-1001", "--role", "SWE Intern",
                        "--resume-used", str(resume), "--read-back", str(self.d / "state/submissions/a1.json"), *extra)

    def test_receipt_comes_from_inbox(self):
        out = self.rec(self.pdf, "--inbox", str(self.inbox))
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        row = tc.load(self.csv)[0]
        self.assertEqual(row["receipt_id"], self.msg["id"])
        self.assertEqual(row["status"], "Submitted")
        self.assertEqual(row["resume_used"], str(self.pdf))
        self.assertTrue(row["notes"].startswith("read-back: "))
        self.assertEqual(self.cli("audit").returncode, 0)

    def test_existing_ready_row_is_upgraded_not_duplicated(self):
        self.cli("add", "--company", "Acme Robotics", "--req-id", "GH-1001", "--status", "Ready", "--notes", "filled")
        self.rec(self.pdf, "--inbox", str(self.inbox))
        rows = tc.load(self.csv)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["receipt_id"], self.msg["id"])
        self.assertIn("filled", rows[0]["notes"])

    def test_relative_resume_rejected(self):
        out = self.rec("resumes/acme/Test_Applicant_Acme.pdf", "--inbox", str(self.inbox))
        self.assertEqual(out.returncode, 1)
        self.assertIn("absolute", out.stdout)
        self.assertFalse(self.csv.exists())

    def test_missing_resume_rejected(self):
        out = self.rec(self.d / "nope.pdf")
        self.assertEqual(out.returncode, 1)
        self.assertIn("does not exist", out.stdout)
        out = self.cli("add", "--company", "X", "--resume-used", "rel.pdf")
        self.assertEqual(out.returncode, 1)

    def test_no_receipt_is_noted(self):
        out = self.rec(self.pdf)
        self.assertFalse(json.loads(out.stdout)["receipt_found"])
        self.assertIn("no receipt yet", tc.load(self.csv)[0]["notes"])
        self.assertEqual(self.cli("audit").returncode, 0)

    def test_audit_flags_pass4_rows(self):
        tc.save(self.csv, [{"company": "Acme Robotics", "req_id": "GH-1001", "status": "Rejected", "receipt_id": "",
                            "resume_used": "resumes/a1/resume.pdf", "notes": "read-back: x.json"}])
        out = self.cli("audit")
        self.assertEqual(out.returncode, 1)
        probs = json.loads(out.stdout)["problems"]
        self.assertTrue(any("receipt_id is empty" in p for p in probs))
        self.assertTrue(any("absolute" in p for p in probs))


class LoopAdditions(unittest.TestCase):
    def test_new_statuses_and_columns(self):
        rows = []
        tc.add(rows, {"company": "Acme", "req_id": "R1", "status": "Discovered", "pay": "$45/hr", "location": "New York, NY"})
        tc.update(rows, "Acme", "R1", "", {"status": "Ghosted"})
        self.assertEqual(rows[0]["status"], "Ghosted")
        self.assertEqual(rows[0]["pay"], "$45/hr")
        self.assertIn("applied_at", tc.COLUMNS)

    def test_receipt_for_a_role_the_loop_did_not_fill(self):
        rows = []
        row = tc.record_submit(rows, {"company": "Acme", "req_id": "R7", "role": "SWE Intern"}, "", "",
                               receipt_id="msg-7", not_filled=True)
        self.assertEqual(row["status"], "Submitted")
        self.assertIn(tc.NOT_FILLED, row["notes"])
        self.assertEqual(tc.audit(rows), [])
        with self.assertRaises(ValueError):
            tc.record_submit(rows, {"company": "Acme", "req_id": "R8"}, "", "", receipt_id="msg-8")

    def test_reconcile_finds_receipts_without_rows(self):
        rows = [{"company": "Acme", "req_id": "R1", "role": "x", "status": "Submitted", "receipt_id": ""}]
        res = tc.reconcile(rows, [{"company": "Acme", "req_id": "R1", "id": "m1"},
                                  {"company": "Acme", "req_id": "R2", "id": "m2"}])
        self.assertEqual([r["id"] for r in res["receipts_without_row"]], ["m2"])
        self.assertEqual(res["rows_missing_receipt"][0]["receipt"], "m1")


if __name__ == "__main__":
    unittest.main()
