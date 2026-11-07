"""job-gate rules: freshness, pay routes, role fit, caps and siblings, prior check, referrals, GenAI, events."""

import datetime as dt
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
GATE_DIR = REPO / "skills" / "job-gate" / "scripts"
sys.path.insert(0, str(GATE_DIR))
sys.path.insert(0, str(REPO / "skills" / "tracker" / "scripts"))

import apply_queue  # noqa: E402
import gate  # noqa: E402
import prefs_yaml  # noqa: E402

NOW = dt.datetime(2026, 11, 6, 18, 0, tzinfo=dt.timezone.utc)
CLEAR = {"gmail": "clear", "tracker": "clear"}


def oid(when: dt.datetime) -> str:
    """A JobRight-style ObjectId whose first 8 hex characters are `when`."""
    return f"{int(when.timestamp()):08x}" + "0" * 16


def prefs(**over):
    p = prefs_yaml.load(REPO / "skills" / "job-setup" / "assets" / "preferences.example.yaml")
    p["freshness"]["first_seen_hours"] = 24
    for k, v in over.items():
        p[k] = v
    return p


def job(**kw):
    base = {"company": "Acme", "title": "Software Engineer Intern", "location": "New York, NY", "work_mode": "hybrid",
            "term_text": "Summer 2027", "pay_text": "$45/hr", "req_id": "R1", "link": "https://acme.example/jobs/R1",
            "id": oid(NOW - dt.timedelta(hours=3)), "prior_check": dict(CLEAR)}
    base.update(kw)
    return base


class Pay(unittest.TestCase):
    def test_midpoint_and_units(self):
        self.assertEqual(gate.hourly_midpoint("$40 - $50/hr"), 45)
        self.assertAlmostEqual(gate.hourly_midpoint("$104,000 - $124,800 a year"), 55.0)
        self.assertAlmostEqual(gate.hourly_midpoint("$8,000/mo"), 8000 * 12 / 2080)
        self.assertIsNone(gate.hourly_midpoint("Competitive"))

    def test_routes(self):
        p = prefs(pay_floor={"amount": 40, "unit": "hour", "missing_pay": "check_live", "lookup": "levels_fyi",
                             "step_up_route": True},
                  prestige={"tiers": {"A": ["Bigco"]}, "step_up_tiers": ["A"]})
        r = gate.gate_one(job(pay_text="$35/hr"), p, NOW)
        self.assertEqual((r["decision"], r["gate"]), ("near", "pay"))
        r = gate.gate_one(job(company="Bigco", pay_text="$35/hr"), p, NOW)
        self.assertEqual(r["decision"], "pass")
        self.assertIn("step up", r["entry"]["pay_route"])
        r = gate.gate_one(job(pay_text="", levels_hourly=48, levels_note="2026, 9 entries"), p, NOW)
        self.assertEqual(r["decision"], "pass")
        self.assertIn("levels.fyi $48/hr (2026, 9 entries)", r["entry"]["pay_route"])
        r = gate.gate_one(job(pay_text="", levels_hourly=30), p, NOW)
        self.assertEqual((r["decision"], r["gate"]), ("near", "pay"))
        self.assertIn("levels.fyi $30/hr is under $40/hr", r["why"])


class Freshness(unittest.TestCase):
    def test_repost_by_objectid_first_seen(self):
        r = gate.gate_one(job(id=oid(NOW - dt.timedelta(days=40)), publish_time="2026-11-06 15:00:00"), prefs(), NOW)
        self.assertEqual((r["decision"], r["gate"]), ("cut", "repost"))
        self.assertIn("first seen Sep 27", r["why"])

    def test_repost_by_employer_publish_date(self):
        r = gate.gate_one(job(employer_published="2026-09-29T12:00:00Z", employer_date_source="Ashby publishedAt"),
                          prefs(), NOW)
        self.assertEqual((r["decision"], r["gate"]), ("cut", "repost"))
        self.assertIn("Ashby publishedAt published Sep 29", r["why"])

    def test_fresh_passes_and_exempt_source(self):
        self.assertEqual(gate.gate_one(job(employer_published="2026-11-05T12:00:00Z"), prefs(), NOW)["decision"], "pass")
        p = prefs()
        p["freshness"]["exempt_sources"] = ["newsletter"]
        old = job(id="", first_seen="2026-11-02T00:00:00Z", source="newsletter")
        self.assertEqual(gate.gate_one(old, p, NOW)["decision"], "pass")


class RoleFit(unittest.TestCase):
    def test_title_decides(self):
        p = prefs()
        self.assertEqual(gate.gate_one(job(title="Senior Software Engineer"), p, NOW)["decision"], "role_cut")
        self.assertEqual(gate.gate_one(job(title="Security Analyst Intern"), p, NOW)["decision"], "role_cut")
        # a cut word on a title that says Software Engineer stays in
        self.assertEqual(gate.gate_one(job(title="Software Engineer Intern, Security"), p, NOW)["decision"], "pass")
        r = gate.gate_one(job(title="Platform Engineer Intern"), p, NOW)
        self.assertEqual((r["decision"], r["entry"].get("fit_tier")), ("pass", "tailored"))

    def test_term_and_remote_brand(self):
        p = prefs()
        self.assertEqual(gate.gate_one(job(term_text="Fall 2026"), p, NOW)["gate"], "term")
        self.assertEqual(gate.gate_one(job(term_text=""), p, NOW)["gate"], "term")
        self.assertEqual(gate.gate_one(job(term_text=""), prefs(term_missing="pass"), NOW)["decision"], "pass")
        p = prefs(work_mode={"remote_requires_prestige": True}, prestige={"tiers": {"A": ["Bigco"]}})
        self.assertEqual(gate.gate_one(job(work_mode="remote", location="Remote (US)"), p, NOW)["gate"], "work_mode")
        self.assertEqual(gate.gate_one(job(company="Bigco", work_mode="remote", location="Remote (US)"), p, NOW)["decision"], "pass")


class TitleShapes(unittest.TestCase):
    """Title shapes seen on the live JobRight feed (QA pass 3)."""

    def test_engineering_intern_is_a_software_engineer_role(self):
        p = prefs()
        r = gate.gate_one(job(title="Software Engineering Intern"), p, NOW)
        self.assertEqual(r["decision"], "pass")
        r = gate.gate_one(job(title="Software Engineering Intern", location="San Francisco, CA"), p, NOW)
        self.assertEqual((r["decision"], r["gate"]), ("near", "location"))
        self.assertEqual(gate.gate_one(job(title="Software Engineerx Intern"), p, NOW)["decision"], "role_cut")

    def test_term_stated_in_the_title(self):
        p = prefs()
        r = gate.gate_one(job(title="Software Engineer Intern, Autonomy [Summer 2027]", term_text=""), p, NOW)
        self.assertEqual(r["decision"], "pass")
        r = gate.gate_one(job(title="Software Engineering Intern - Summer '27", term_text=""), p, NOW)
        self.assertEqual(r["decision"], "pass")
        r = gate.gate_one(job(title="Internship, Software Engineer (Winter/Spring 2027)", term_text=""), p, NOW)
        self.assertEqual((r["decision"], r["gate"]), ("near", "term"))
        self.assertIn("Winter/Spring 2027", r["why"])
        r = gate.gate_one(job(title="Software Engineer Intern", term_text=""), p, NOW)
        self.assertEqual((r["gate"], r["why"]), ("term", "no term stated"))


class PriorCheckFailsClosed(unittest.TestCase):
    def test_missing_or_errored_check_is_not_a_pass(self):
        p = prefs()
        self.assertEqual(gate.gate_one(job(prior_check=None), p, NOW)["decision"], "prior_failed")
        r = gate.gate_one(job(prior_check={"gmail": "error", "tracker": "clear"}), p, NOW)
        self.assertEqual(r["decision"], "prior_failed")
        self.assertIn("gmail check could not run", r["why"])
        p["prior_check"]["sources"] = ["gmail", "tracker", "simplify"]
        self.assertEqual(gate.gate_one(job(), p, NOW)["decision"], "prior_failed")

    def test_found_is_already_applied(self):
        r = gate.gate_one(job(prior_check={"gmail": "clear", "tracker": "clear", "simplify": "found",
                                           "note": "Simplify banner: applied Jul 24"}), prefs(), NOW)
        self.assertEqual(r["decision"], "applied")
        self.assertIn("simplify", r["why"])


class ReferralsGenAIEvents(unittest.TestCase):
    def test_wait_referral(self):
        r = gate.gate_one(job(referral={"state": "pending", "name": "A. Friend"}), prefs(), NOW)
        self.assertEqual((r["decision"], r["entry"]["state"]), ("pass", apply_queue.WAIT_REFERRAL))
        r = gate.gate_one(job(referral={"state": "contact", "name": "A. Friend", "email": "a@x"}), prefs(), NOW)
        self.assertEqual(r["entry"]["state"], apply_queue.QUEUED)
        self.assertEqual(r["entry"]["referral"]["state"], "contact")

    def test_genai_flag_default_and_skip(self):
        r = gate.gate_one(job(genai_restricted=True, genai_quote="Do not use AI tools"), prefs(), NOW)
        self.assertEqual(r["decision"], "pass")
        self.assertIn("GenAI rule in posting", r["entry"]["flags"])
        r = gate.gate_one(job(genai_restricted=True), prefs(genai_restriction="skip"), NOW)
        self.assertEqual((r["decision"], r["gate"]), ("cut", "genai_policy"))
        legacy = prefs()
        legacy.pop("genai_restriction")
        legacy["skip_if_genai_banned"] = True
        self.assertEqual(gate.genai_mode(legacy), "skip")

    def test_events_are_passes_never_submitted(self):
        r = gate.gate_one(job(kind="event", title="Info session RSVP", event_date="2026-11-20T18:00:00Z"), prefs(), NOW)
        self.assertEqual(r["decision"], "pass")
        self.assertTrue(r["entry"]["never_submit"])
        r = gate.gate_one(job(kind="event", title="Info session", event_date="2026-11-01T18:00:00Z"), prefs(), NOW)
        self.assertEqual((r["decision"], r["gate"]), ("cut", "event_over"))


class CapsSiblingsDedupe(unittest.TestCase):
    def test_best_two_siblings_then_drop(self):
        jobs = [job(req_id=f"R{i}", title="Software Engineer Intern", fit=i) for i in range(1, 5)]
        res = gate.run(jobs, prefs(), [], apply_queue.empty(), NOW)
        self.assertEqual([e["req_id"] for e in res["passes"]], ["R4", "R3"])
        self.assertEqual(len(res["dropped"]), 2)
        self.assertIn("only the best 2", res["dropped"][0]["why"])

    def test_rolling_cap_counts_recent_rows(self):
        p = prefs()
        p["caps"]["per_company"] = {"Acme": {"max": 1, "window_days": 30}}
        rows = [{"company": "Acme", "req_id": "OLD", "role": "x", "date": "2026-11-01", "status": "Submitted"}]
        res = gate.run([job()], p, rows, apply_queue.empty(), NOW)
        self.assertEqual(res["passes"], [])
        self.assertIn("cap: 1 of 1 used in 30 days", res["dropped"][0]["why"])
        rows[0]["date"] = "2026-09-01"
        self.assertEqual(len(gate.run([job()], p, rows, apply_queue.empty(), NOW)["passes"]), 1)

    def test_dedupe_by_req_not_company(self):
        rows = [{"company": "Acme Inc", "req_id": "R9", "role": "x", "date": "2026-11-01", "status": "Submitted"}]
        res = gate.run([job(req_id="R9"), job(req_id="R1")], prefs(), rows, apply_queue.empty(), NOW)
        self.assertEqual([e["req_id"] for e in res["passes"]], ["R1"])
        self.assertIn("tracker row R9", res["already_applied"][0]["why"])

    def test_report_has_three_groups_and_times(self):
        jobs = [job(publish_time="2026-11-06 15:00:00"), job(req_id="R2", pay_text="$20/hr"),
                job(req_id="R3", prior_check={"gmail": "found", "tracker": "clear", "note": "receipt Oct 2"}),
                job(title="Marketing Analyst")]
        text = gate.report(gate.run(jobs, prefs(), [], apply_queue.empty(), NOW), "last 24h")
        for part in ("Scanned 4 postings, window last 24h", "1. Passes", "2. Already applied", "3. Near misses",
                     "1 obvious role cuts", "2026-11-06 15:00:00", "posted midpoint $20/hr is under $30/hr"):
            self.assertIn(part, text)


class Queue(unittest.TestCase):
    def test_states_receipts_and_dropped_never_readded(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "queue.json"
            q = apply_queue.load(path)
            apply_queue.add(q, {"company": "Acme", "title": "SWE Intern", "req_id": "R1"})
            apply_queue.add(q, {"company": "Acme", "title": "SWE Intern", "req_id": "R2", "state": "DROPPED: sibling"})
            _, created = apply_queue.add(q, {"company": "Acme Inc.", "title": "Other", "req_id": "r-2"})
            self.assertFalse(created)
            with self.assertRaises(ValueError):
                apply_queue.remove(q, {"company": "Acme", "req_id": "R1"}, "")
            apply_queue.set_state(q, {"company": "Acme", "req_id": "R1"}, "FILLED")
            self.assertEqual(apply_queue.next_batch(q, 10), [])
            with self.assertRaises(ValueError):
                apply_queue.set_state(q, {"company": "Acme", "req_id": "R1"}, "NEEDS YOU")
            apply_queue.remove(q, {"company": "Acme", "req_id": "R1"}, "msg-123")
            apply_queue.save(path, q)
            q = apply_queue.load(path)
            self.assertEqual([e["req_id"] for e in q["entries"]], ["R2"])
            self.assertEqual(q["removed"][0]["receipt"], "msg-123")

    def test_next_limit_and_old_list_shape(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "queue.json"
            path.write_text(json.dumps([{"company": f"C{i}", "title": "SWE", "req_id": str(i)} for i in range(12)]))
            q = apply_queue.load(path)
            self.assertEqual(len(apply_queue.next_batch(q, 10)), 10)

    def test_cli_writes_queue(self):
        with tempfile.TemporaryDirectory() as d:
            scan = Path(d) / "scan.json"
            scan.write_text(json.dumps({"window": "24h", "items": [job(), job(req_id="R2", referral={"state": "pending"})]}))
            qp = Path(d) / "queue.json"
            out = subprocess.run([sys.executable, str(GATE_DIR / "gate.py"), "--prefs",
                                  str(REPO / "skills" / "job-setup" / "assets" / "preferences.example.yaml"),
                                  "--scan", str(scan), "--queue", str(qp), "--now", NOW.isoformat(), "--write-queue"],
                                 capture_output=True, text=True)
            self.assertEqual(out.returncode, 0, out.stderr)
            states = {e["req_id"]: e["state"] for e in apply_queue.load(qp)["entries"]}
            self.assertEqual(states, {"R1": "QUEUED", "R2": "WAIT-REFERRAL"})


class PrefsYaml(unittest.TestCase):
    def test_reads_inline_maps_and_lists(self):
        d = prefs_yaml.loads("a:\n  b: { max: 2, window_days: 180 }\n  c: [x, 'y z']\nlist:\n  - name: n\n    kind: gmail\n  - plain\n"
                             "q: \"has # hash\"  # comment\n")
        self.assertEqual(d["a"]["b"], {"max": 2, "window_days": 180})
        self.assertEqual(d["a"]["c"], ["x", "y z"])
        self.assertEqual(d["list"], [{"name": "n", "kind": "gmail"}, "plain"])
        self.assertEqual(d["q"], "has # hash")

    def test_example_files_parse(self):
        p = prefs_yaml.load(REPO / "skills" / "job-setup" / "assets" / "preferences.example.yaml")
        self.assertIs(p["auto_submit"], False)
        self.assertEqual(p["genai_restriction"], "flag")
        self.assertEqual(p["browser"]["max_forms_per_run"], 10)
        self.assertEqual(p["schedule"]["every_hours"], 0)
        a = prefs_yaml.load(REPO / "skills" / "job-setup" / "assets" / "standing-answers.example.yaml")
        self.assertEqual(a["education"][0]["degree"], "Bachelor of Science")
        self.assertEqual(a["date_fields_day"], "01")


if __name__ == "__main__":
    unittest.main()
