"""job-scan JobRight helpers: ObjectId first-seen, __NEXT_DATA__, the 24h checkpoint window."""

import datetime as dt
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills" / "job-scan" / "scripts"))

import jobright_meta as jm  # noqa: E402

UTC = dt.timezone.utc
NOW = dt.datetime(2026, 11, 6, 18, 0, tzinfo=UTC)


class FirstSeen(unittest.TestCase):
    def test_objectid_time(self):
        t = dt.datetime(2026, 8, 5, 12, 0, tzinfo=UTC)
        self.assertEqual(jm.first_seen(f"{int(t.timestamp()):08x}abcdef0123456789"), t)
        self.assertIsNone(jm.first_seen("8072713"))
        self.assertIsNone(jm.first_seen(""))


class NextData(unittest.TestCase):
    def test_reads_publish_time_and_original_url(self):
        blob = {"props": {"pageProps": {"job": {"publishTime": "2026-11-06 14:05:00",
                                                "originalUrl": "https://boards.example.com/acme/jobs/123?gh_src=x&a=b"}}}}
        html = f'<html><script id="__NEXT_DATA__" type="application/json">{json.dumps(blob)}</script></html>'
        got = jm.next_data(html)
        self.assertEqual(got["publish_time"], "2026-11-06 14:05:00")
        self.assertEqual(got["original_url"], "https://boards.example.com/acme/jobs/123?gh_src=x&a=b")

    def test_regex_fallback_and_missing(self):
        html = '<script id="__NEXT_DATA__">{"publishTime":"2026-11-06 01:00:00","originalUrl":"https:\\/\\/x.example\\/j?a=1\\u0026b=2"'
        html += "</script>"
        got = jm.next_data(html)
        self.assertEqual(got["original_url"], "https://x.example/j?a=1&b=2")
        self.assertEqual(jm.next_data("<html></html>"), {"publish_time": "", "original_url": ""})


class Window(unittest.TestCase):
    def test_fresh_checkpoint_stops_at_its_id(self):
        cp = {"job_key": "abc", "publish_time": "2026-11-06 12:00:00"}
        w = jm.window(cp, NOW)
        self.assertEqual((w["stop_at"], w["full_window"]), ("abc", False))
        new, reached = jm.cut_at_checkpoint(["n1", "n2", "n1", "abc", "old"], w["stop_at"])
        self.assertEqual((new, reached), (["n1", "n2"], True))

    def test_old_or_missing_checkpoint_scans_full_24h(self):
        w = jm.window({"job_key": "abc", "publish_time": "2026-11-04 12:00:00"}, NOW)
        self.assertTrue(w["full_window"])
        self.assertIsNone(w["stop_at"])
        self.assertIn("older than 24h", w["reason"])
        self.assertTrue(jm.window(None, NOW)["full_window"])
        self.assertEqual(jm.window(None, NOW)["since"], "2026-11-05T18:00:00+00:00")

    def test_save_and_load(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "state" / "jobright-checkpoint.json"
            jm.save_checkpoint(path, "top", "2026-11-06 17:00:00", "SWE Intern", "Acme", now=NOW)
            cp = jm.load_checkpoint(path)
            self.assertEqual(cp["job_key"], "top")
            self.assertFalse(jm.window(cp, NOW)["full_window"])
            path.write_text("not json")
            self.assertIsNone(jm.load_checkpoint(path))


if __name__ == "__main__":
    unittest.main()
