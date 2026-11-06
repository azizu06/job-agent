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


if __name__ == "__main__":
    unittest.main()
