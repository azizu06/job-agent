import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills" / "job-setup" / "scripts"))

import launch_chrome as lc  # noqa: E402


class ProfileOwnsPortTests(unittest.TestCase):
    def test_marker_must_match_port_and_a_live_process(self):
        with tempfile.TemporaryDirectory() as d:
            profile = Path(d)
            self.assertFalse(lc.profile_owns_port(profile, 9333))
            (profile / lc.MARKER).write_text(json.dumps({"port": 9333, "pid": os.getpid()}))
            self.assertTrue(lc.profile_owns_port(profile, 9333))
            self.assertFalse(lc.profile_owns_port(profile, 9222))
            (profile / lc.MARKER).write_text(json.dumps({"port": 9333, "pid": 2 ** 22 + 12345}))
            self.assertFalse(lc.profile_owns_port(profile, 9333))

    def test_headless_never_uses_the_os_keychain(self):
        cmd = lc.chrome_args("chrome", 9333, Path("/p"), headless=True)
        for flag in ("--headless=new", "--use-mock-keychain", "--password-store=basic", "--no-first-run",
                     "--no-default-browser-check", "--remote-debugging-port=9333", "--user-data-dir=/p"):
            self.assertIn(flag, cmd)
        visible = lc.chrome_args("chrome", 9333, Path("/p"), headless=False)
        self.assertNotIn("--use-mock-keychain", visible)

    def test_default_port_is_not_the_main_chrome_port(self):
        import inspect
        self.assertIn("9333", inspect.getsource(lc.main))


if __name__ == "__main__":
    unittest.main()
