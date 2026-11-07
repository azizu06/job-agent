"""job-run guard: lock with staleness, BLOCKED twice rule, final READY/ALERT/NOTHING READY lines."""

import datetime as dt
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills" / "job-run" / "scripts"))

import run_state as rs  # noqa: E402

UTC = dt.timezone.utc
T0 = dt.datetime(2026, 11, 6, 8, 15, tzinfo=UTC)


class Lock(unittest.TestCase):
    def test_fresh_lock_blocks_stale_lock_is_replaced(self):
        with tempfile.TemporaryDirectory() as d:
            lock = Path(d) / "state" / "run.lock"
            self.assertTrue(rs.take_lock(lock, 3, T0)["locked"])
            busy = rs.take_lock(lock, 3, T0 + dt.timedelta(hours=1))
            self.assertFalse(busy["locked"])
            later = rs.take_lock(lock, 3, T0 + dt.timedelta(hours=4))
            self.assertTrue(later["locked"] and later["replaced_stale"])
            self.assertIn("last run hung", later["reason"])
            rs.release_lock(lock)
            self.assertFalse(lock.exists())


class Blocked(unittest.TestCase):
    def test_only_two_in_a_row_notify(self):
        with tempfile.TemporaryDirectory() as d:
            log = Path(d) / "run-log.md"
            self.assertFalse(rs.record_blocked(log, "screen locked", T0)["notify"])
            second = rs.record_blocked(log, "Chrome did not attach", T0 + dt.timedelta(hours=3))
            self.assertTrue(second["notify"])
            self.assertEqual(second["banner"], "Job loop blocked: Chrome did not attach")
            rs.append(log, "run ok: 40 cards, 1 ready", T0 + dt.timedelta(hours=6))
            self.assertFalse(rs.record_blocked(log, "screen locked", T0 + dt.timedelta(hours=9))["notify"])

    def test_ioreg_parse(self):
        self.assertTrue(rs.screen_locked_from_ioreg('| "IOConsoleUsers" = ({"CGSSessionScreenIsLocked"=Yes,"kCGSSessionOnConsoleKey"=Yes})'))
        self.assertFalse(rs.screen_locked_from_ioreg('{"kCGSSessionOnConsoleKey"=Yes}'))


class Banner(unittest.TestCase):
    def test_ready_alert_nothing(self):
        self.assertEqual(rs.final_lines([]), ["NOTHING READY"])
        self.assertEqual(rs.final_lines(["Acme SWE Intern"]), ["READY: Acme SWE Intern ready to review and submit"])
        lines = rs.final_lines(["Acme", "Globex", "Initech"], genai=["Globex"], alerts=["Assessment from Hooli, due Nov 12"])
        self.assertEqual(lines[0], "READY: 3 ready to review and submit: Acme, Globex GenAI rule in posting, Initech")
        self.assertEqual(lines[1], "ALERT: Assessment from Hooli, due Nov 12")

    def test_banner_is_short_and_has_no_quotes(self):
        line = rs.final_lines([f"Company{i}'s \"Role\"" for i in range(20)])[0]
        self.assertLess(len(line[len("READY: "):]), 150)
        self.assertNotIn("'", line)
        self.assertNotIn('"', line)


if __name__ == "__main__":
    unittest.main()
