import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills" / "job-run" / "scripts"))

import notify as nt  # noqa: E402


class NotifyTests(unittest.TestCase):
    def test_macos_escapes_quotes(self):
        kind, argv = nt.build_request({"method": "macos"}, 'Say "hi"', "line", None)
        self.assertEqual(kind, "command")
        self.assertIn('\\"hi\\"', argv[2])

    def test_ntfy_request(self):
        kind, req = nt.build_request({"method": "ntfy", "topic": "abc123"}, "CAPTCHA", "Acme needs you", "https://example.com")
        self.assertEqual(kind, "http")
        self.assertEqual(req.full_url, "https://ntfy.sh/abc123")
        self.assertEqual(req.get_header("Click"), "https://example.com")
        self.assertEqual(req.data, b"Acme needs you")

    def test_slack_request(self):
        kind, req = nt.build_request({"method": "slack", "webhook_url": "https://hooks.example.com/x"}, "T", "M", None)
        self.assertEqual(json.loads(req.data)["text"], "*T*\nM")

    def test_macos_only_on_darwin(self):
        self.assertIsNone(nt.unsupported_reason({"method": "macos"}, "darwin"))
        self.assertIn("macOS", nt.unsupported_reason({"method": "macos"}, "linux"))
        self.assertIsNone(nt.unsupported_reason({"method": "ntfy"}, "win32"))

    def test_none(self):
        self.assertEqual(nt.build_request({}, "T", "M", None), ("none", None))


if __name__ == "__main__":
    unittest.main()
