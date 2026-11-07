#!/usr/bin/env python3
"""ALTERNATIVE browser mode: start a separate "job-agent" Chrome profile.

The default mode attaches to the user's main, signed-in Chrome with
chrome-devtools MCP --autoConnect. Use this launcher only if you want the
agent isolated from your main browser. You then sign in to job sites once in
this profile.

It starts Chrome with --remote-debugging-port and its own --user-data-dir
(Chrome 136+ ignores the port flag on the default profile). Chrome shows no
"Allow remote debugging?" prompt for a port it was started with. Point the
MCP at it with --browser-url=http://127.0.0.1:<port>.

Works on macOS, Linux and Windows. Standard library only.

Usage: launch_chrome.py [--port 9333] [--profile DIR] [--headless]

The default port is 9333, not 9222: Chrome's own remote-debugging switch
(chrome://inspect) usually serves the main profile on 9222. If something
already answers on the port, the launcher reuses it only when that browser
is the one this launcher started for this profile (a marker file in the
profile holds its port and process ID);
otherwise it stops, so the agent never drives the main browser by mistake.

Security: while this Chrome runs, any program on this computer can control it
through the port, including sites you are signed into in this profile. The
port listens on 127.0.0.1. Quit this Chrome when you are not using the agent.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path


def workspace() -> Path:
    return Path(os.environ.get("JOB_AGENT_HOME", Path.home() / ".job-agent")).expanduser()


def candidate_paths() -> list[str]:
    if sys.platform == "darwin":
        apps = [Path("/Applications"), Path.home() / "Applications"]
        names = ["Google Chrome", "Chromium"]
        return [str(a / f"{n}.app" / "Contents" / "MacOS" / n) for a in apps for n in names]
    if sys.platform == "win32":
        roots = [os.environ.get(k, "") for k in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA")]
        return [str(Path(r) / "Google" / "Chrome" / "Application" / "chrome.exe") for r in roots if r]
    found = [shutil.which(b) for b in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser")]
    return [f for f in found if f]


def find_chrome() -> str | None:
    if os.environ.get("CHROME_BIN"):
        return os.environ["CHROME_BIN"]
    for path in candidate_paths():
        if Path(path).exists():
            return path
    return None


MARKER = "job-agent-chrome.json"


def pid_alive(pid: int) -> bool:
    if sys.platform == "win32":
        out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True)
        return str(pid) in out.stdout
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def profile_owns_port(profile: Path, port: int) -> bool:
    """True when this launcher started the Chrome that serves the port, for this profile."""
    try:
        info = json.loads((profile / MARKER).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return info.get("port") == port and isinstance(info.get("pid"), int) and pid_alive(info["pid"])


def port_alive(port: int) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=1):
            return True
    except OSError:
        return False


def chrome_args(chrome: str, port: int, profile: Path, headless: bool) -> list[str]:
    """The Chrome command line. Headless runs (the test rig, CI) also skip the
    OS keychain, so they never raise a "Chrome Safe Storage" keychain prompt;
    the visible profile keeps the keychain so its saved logins stay encrypted."""
    cmd = [
        chrome,
        f"--remote-debugging-port={port}",
        f"--user-data-dir={profile}",
        "--no-first-run",
        "--no-default-browser-check",
    ]
    if headless:
        cmd += ["--headless=new", "--use-mock-keychain", "--password-store=basic"]
    return cmd


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=int(os.environ.get("JOB_AGENT_CHROME_PORT", 9333)))
    ap.add_argument("--profile", default=os.environ.get("JOB_AGENT_CHROME_PROFILE"))
    ap.add_argument("--headless", action="store_true")
    args = ap.parse_args(argv)

    home = workspace()
    profile = Path(args.profile).expanduser() if args.profile else home / "chrome-profile"
    flag = f"--browser-url=http://127.0.0.1:{args.port}"

    if port_alive(args.port):
        if profile_owns_port(profile, args.port):
            print(f"The job-agent Chrome profile is already up on port {args.port}.\nMCP flag: {flag}")
            return 0
        print(f"Another browser already answers on port {args.port} (it may be your main Chrome). "
              "Pick a free port with --port and set browser.port to match.", file=sys.stderr)
        return 1

    chrome = find_chrome()
    if not chrome:
        print("Chrome not found. Set CHROME_BIN to its path.", file=sys.stderr)
        return 1

    home.mkdir(parents=True, exist_ok=True)
    profile.mkdir(parents=True, exist_ok=True)
    cmd = chrome_args(chrome, args.port, profile, args.headless)

    log = open(home / "chrome.log", "ab")
    kwargs: dict = {"stdout": log, "stderr": log, "stdin": subprocess.DEVNULL}
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    proc = subprocess.Popen(cmd, **kwargs)
    (profile / MARKER).write_text(json.dumps({"port": args.port, "pid": proc.pid}), encoding="utf-8")

    for _ in range(30):
        if port_alive(args.port):
            print(f"job-agent Chrome profile is up.\nProfile: {profile}\nMCP flag: {flag}")
            return 0
        time.sleep(0.5)
    print(f"Chrome started but port {args.port} did not answer. See {home / 'chrome.log'}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
