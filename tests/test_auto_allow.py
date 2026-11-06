import plistlib
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills" / "job-setup" / "scripts"))

import auto_allow as aa  # noqa: E402


class Clock:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t

    def sleep(self, s):
        self.t += s


class AutoAllowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name) / "auto-allow"

    def tearDown(self):
        self.tmp.cleanup()

    def enable(self):
        self.base.mkdir(parents=True, exist_ok=True)
        aa.paths(self.base)["enabled"].write_text("on")

    def test_arm_refused_when_disabled(self):
        with self.assertRaises(PermissionError):
            aa.arm(self.base, 15, "a")

    def test_arms_expire(self):
        self.enable()
        aa.arm(self.base, 15, "a", now=1000)
        self.assertEqual(len(aa.open_arms(self.base, now=1010)), 1)
        self.assertEqual(aa.open_arms(self.base, now=1016), [])

    def test_each_click_consumes_one_arm_oldest_first(self):
        self.enable()
        first = aa.arm(self.base, 15, "first", now=1000)
        aa.arm(self.base, 15, "second", now=1001)
        clock = Clock(1002)
        calls = []

        def backend(max_clicks):
            calls.append(max_clicks)
            return ["Google Chrome"] if len(calls) == 1 else []

        clicks = aa.watch(self.base, backend, sleep=clock.sleep, clock=clock, max_loops=2)
        self.assertEqual(clicks, 1)
        self.assertEqual(calls, [2, 1])  # never asks for more clicks than open windows
        live = aa.open_arms(self.base, now=clock())
        self.assertEqual(len(live), 1)
        self.assertFalse(first.exists())
        log = aa.paths(self.base)["log"].read_text()
        self.assertIn("clicked Allow (Google Chrome)", log)

    def test_watcher_stops_when_no_window_open(self):
        self.enable()
        aa.arm(self.base, 1, "a", now=1000)
        clock = Clock(1000)
        clicks = aa.watch(self.base, lambda n: [], sleep=clock.sleep, clock=clock)
        self.assertEqual(clicks, 0)
        self.assertFalse(aa.paths(self.base)["lock"].exists())
        self.assertIn("watcher stopped", aa.paths(self.base)["log"].read_text())

    def test_backend_errors_are_logged_not_raised(self):
        self.enable()
        aa.arm(self.base, 1, "a", now=1000)
        clock = Clock(1000)

        def broken(n):
            raise RuntimeError("not allowed assistive access")

        self.assertEqual(aa.watch(self.base, broken, sleep=clock.sleep, clock=clock), 0)
        self.assertIn("not allowed assistive access", aa.paths(self.base)["log"].read_text())

    def test_single_watcher_lock(self):
        self.base.mkdir(parents=True)
        self.assertTrue(aa.take_lock(self.base))
        self.assertFalse(aa.take_lock(self.base))
        aa.release_lock(self.base)
        self.assertTrue(aa.take_lock(self.base))


if __name__ == "__main__":
    unittest.main()


class LaunchAgentTests(unittest.TestCase):
    def test_plist_runs_daemon_at_load_and_keeps_alive(self):
        base = Path("/Users/x/.job-agent/auto-allow")
        d = plistlib.loads(aa.launch_agent_plist(base, "/usr/bin/python3", Path("/r/auto_allow.py")))
        self.assertEqual(d["Label"], aa.LAUNCH_LABEL)
        self.assertTrue(d["Label"].endswith(".job-agent.auto-allow"))
        self.assertEqual(d["ProgramArguments"], ["/usr/bin/python3", "/r/auto_allow.py", "daemon"])
        self.assertTrue(d["RunAtLoad"])
        self.assertTrue(d["KeepAlive"])
        self.assertEqual(d["EnvironmentVariables"]["JOB_AGENT_HOME"], "/Users/x/.job-agent")

    def test_plist_path_is_per_user(self):
        p = aa.launch_agent_path(Path("/Users/x"))
        self.assertEqual(p, Path(f"/Users/x/Library/LaunchAgents/{aa.LAUNCH_LABEL}.plist"))

    def test_install_and_remove_use_launchctl_and_file(self):
        calls = []

        class R:
            returncode = 0
            stdout = stderr = ""

        def fake(*args):
            calls.append(args)
            return R()

        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "ws" / "auto-allow"
            plist = Path(tmp) / "LaunchAgents" / "a.plist"
            aa.install_launch_agent(base, plist, launchctl=fake)
            self.assertTrue(plist.exists())
            self.assertEqual(calls[-1][0], "bootstrap")
            aa.remove_launch_agent(plist, launchctl=fake)
            self.assertFalse(plist.exists())
            self.assertEqual(calls[-1][0], "bootout")

    def test_daemon_clicks_only_while_armed(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "auto-allow"
            base.mkdir()
            aa.paths(base)["enabled"].write_text("on")
            hits = []
            backend = lambda n: hits.append(n) or ["Google Chrome"]
            self.assertEqual(aa.daemon(base, backend, sleep=lambda s: None, max_loops=2), 0)
            self.assertEqual(hits, [])
            aa.arm(base, 15, "t")
            self.assertEqual(aa.daemon(base, backend, sleep=lambda s: None, max_loops=3), 1)
