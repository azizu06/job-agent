"""The rig's gate cases through gate.py, plus the loop's gate rules on rig-shaped postings.

Same rig profile and seeded tracker as test_rig.py. The mock world's eight
jobs must gate exactly as tests/e2e/README.md says; the extra postings cover a
repost, a fail-closed prior-application check, a pending referral and a GenAI
restriction.
"""

from __future__ import annotations

import datetime as dt
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "skills" / "job-gate" / "scripts"))
sys.path.insert(0, str(REPO / "skills" / "tracker" / "scripts"))

import apply_queue  # noqa: E402
import gate  # noqa: E402
import mock_ats  # noqa: E402
import prefs_yaml  # noqa: E402
import rig  # noqa: E402
import tracker_csv  # noqa: E402

NOW = dt.datetime.now(dt.timezone.utc)
CLEAR = {"gmail": "clear", "tracker": "clear"}


def scan_item(job: dict, base: str) -> dict:
    url = mock_ats.apply_path(job)
    return {"job_key": job["id"], "company": job["company"], "title": job["title"], "location": job["location"],
            "work_mode": job["work_model"].lower(), "pay_text": job["pay"], "term_text": job["term"],
            "req_id": job["req_id"], "apply_url": url if url.startswith("http") else base + url,
            "first_seen": (NOW - dt.timedelta(minutes=job["posted_minutes"])).isoformat(), "prior_check": dict(CLEAR)}


class RigGate(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.ws = Path(cls.tmp.name) / "ws"
        rig.setup(cls.ws, 18999)
        p = rig.ws_paths(cls.ws)
        cls.prefs = prefs_yaml.load(p["prefs"])
        cls.rows = tracker_csv.load(p["tracker"])
        cls.base = "http://127.0.0.1:18999"

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def run_gate(self, items):
        return gate.run(items, self.prefs, self.rows, apply_queue.empty(), NOW)

    def test_mock_world_gates_as_documented(self):
        res = self.run_gate([scan_item(j, self.base) for j in mock_ats.JOBS])
        self.assertEqual(sorted(e["company"] for e in res["passes"]), ["Acme Robotics", "Globex", "Initech"])
        self.assertEqual(res["role_cut_count"], 1)  # Umbrella Corp, Senior title
        self.assertEqual([(e["company"], e["gate"]) for e in res["near_misses"]], [("Hooli", "location")])
        self.assertEqual([e["company"] for e in res["already_applied"]], ["Wayne Enterprises"])
        self.assertEqual([e["company"] for e in res["dropped"]], ["Stark Industries"])
        self.assertIn("cap: 1 of 1 used in 30 days", res["dropped"][0]["why"])
        self.assertEqual([e["company"] for e in res["cuts"]["linkedin_only"]], ["Vandelay Industries"])

    def acme(self, **kw):
        item = scan_item(mock_ats.BY_ID["a1f0c0de0001"], self.base)
        item.update(req_id="GH-1099", job_key="acme-1099")
        item.update(kw)
        return item

    def test_repost(self):
        res = self.run_gate([self.acme(employer_published=(NOW - dt.timedelta(days=38)).isoformat(),
                                       employer_date_source="Greenhouse first_published")])
        self.assertEqual(res["passes"], [])
        self.assertIn("REPOST: Greenhouse first_published", res["cuts"]["repost"][0]["why"])

    def test_prior_check_fails_closed(self):
        res = self.run_gate([self.acme(prior_check={"gmail": "error", "tracker": "clear"})])
        self.assertEqual(res["passes"], [])
        self.assertEqual(len(res["prior_check_failed"]), 1)
        self.assertIn("could not run", gate.report(res))

    def test_wait_referral(self):
        res = self.run_gate([self.acme(referral={"state": "pending", "name": "Test Friend"})])
        self.assertEqual(res["passes"][0]["state"], apply_queue.WAIT_REFERRAL)
        self.assertIn("WAIT-REFERRAL", gate.report(res))

    def test_genai_flag(self):
        res = self.run_gate([self.acme(genai_restricted=True, genai_quote="Please do not use generative AI")])
        self.assertEqual(res["passes"][0]["flags"], ["GenAI rule in posting"])
        self.assertIn("GenAI rule in posting", gate.report(res))


if __name__ == "__main__":
    unittest.main()
