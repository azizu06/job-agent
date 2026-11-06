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

    def test_default_port_is_not_the_main_chrome_port(self):
        import inspect
        self.assertIn("9333", inspect.getsource(lc.main))


if __name__ == "__main__":
    unittest.main()
