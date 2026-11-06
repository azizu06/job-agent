#!/usr/bin/env python3
"""auto-allow: OPT-IN helper that presses Chrome's "Allow remote debugging?"
prompt for the agent's own connections. OFF by default.

When an agent attaches to your main Chrome (chrome-devtools MCP
--autoConnect), Chrome asks "Allow remote debugging?" for every new
connection. Each agent opens its own connection, so a run can raise several
prompts. For walk-away runs this helper clicks them, but only while armed:

  1. Right before its own connect, each agent runs `auto_allow.py arm`.
     That opens a short window (default 15 s) for one prompt.
  2. One watcher process runs while any window is open. Each time a Chrome
     prompt appears it clicks Allow, logs the click, and closes the oldest
     open window. N arms allow at most N clicks.
  3. When no window is open, the watcher exits. Nothing runs between runs.

What turning it on means: the prompt does not say who is asking. Any local
program that requests a debugging connection while a window is open gets
approved too, and uses up that agent's window.

Platforms:
  macOS    System Events UI scripting through osascript. Grant Accessibility
           to the app that runs your agent (System Settings > Privacy &
           Security > Accessibility).
  Windows  not supported yet. An untested pywinauto backend exists; it runs
           only with JOB_AGENT_AUTO_ALLOW_WINDOWS=1 (`pip install pywinauto`).

The prompt is found by its English text, so Chrome must be in English.
  Linux    not supported; click Allow yourself or use the dedicated profile.

Commands:
  enable | disable          turn the helper on or off (setup asks you first)
  arm [--window S] [--label NAME]
  status
  watch                     internal: the watcher loop

Standard library only (plus pywinauto for the untested Windows backend).
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path

PROMPT_TEXT = "remote debugging"
BUTTON = "Allow"
STALE_LOCK_S = 5.0


def base_dir() -> Path:
    home = Path(os.environ.get("JOB_AGENT_HOME", Path.home() / ".job-agent")).expanduser()
    return home / "auto-allow"


def paths(base: Path) -> dict[str, Path]:
    return {
        "enabled": base / "ENABLED",
        "arms": base / "arms",
        "lock": base / "watcher.lock",
        "log": base.parent / "auto-allow.log",
    }


def log(base: Path, message: str) -> None:
    p = paths(base)["log"]
    p.parent.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with p.open("a", encoding="utf-8") as fh:
        fh.write(f"{stamp} {message}\n")


# ------------------------------------------------------------------ arms

def is_enabled(base: Path) -> bool:
    return paths(base)["enabled"].exists()


def arm(base: Path, window: float, label: str, now: float | None = None) -> Path:
    if not is_enabled(base):
        raise PermissionError("auto-allow is not enabled. Run `auto_allow.py enable` after reading the README.")
    now = time.time() if now is None else now
    arms = paths(base)["arms"]
    arms.mkdir(parents=True, exist_ok=True)
    safe = "".join(c for c in label if c.isalnum() or c in "-_")[:40] or "agent"
    f = arms / f"{now:.3f}-{safe}-{uuid.uuid4().hex[:6]}.arm"
    f.write_text(f"{now + window:.3f}\n", encoding="utf-8")
    log(base, f"armed {f.stem} for {window:g}s")
    return f


def open_arms(base: Path, now: float | None = None) -> list[Path]:
    """Unexpired arms, oldest first. Expired ones are removed and logged."""
    now = time.time() if now is None else now
    arms = paths(base)["arms"]
    if not arms.exists():
        return []
    live = []
    for f in sorted(arms.glob("*.arm")):
        try:
            expiry = float(f.read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            expiry = 0.0
        if expiry <= now:
            f.unlink(missing_ok=True)
            log(base, f"window closed without a prompt: {f.stem}")
        else:
            live.append(f)
    return live


def consume(base: Path, f: Path, what: str) -> None:
    f.unlink(missing_ok=True)
    log(base, f"clicked {BUTTON} ({what}); closed window {f.stem}")


# ------------------------------------------------------------------ watcher lock

def take_lock(base: Path, now: float | None = None) -> bool:
    lock = paths(base)["lock"]
    lock.parent.mkdir(parents=True, exist_ok=True)
    now = time.time() if now is None else now
    try:
        if now - lock.stat().st_mtime > STALE_LOCK_S:
            lock.unlink(missing_ok=True)
    except FileNotFoundError:
        pass
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return False
    os.write(fd, str(os.getpid()).encode())
    os.close(fd)
    return True


def heartbeat(base: Path) -> None:
    try:
        os.utime(paths(base)["lock"])
    except FileNotFoundError:
        pass


def release_lock(base: Path) -> None:
    paths(base)["lock"].unlink(missing_ok=True)


# ------------------------------------------------------------------ backends

MAC_SCRIPT = r'''
on findIn(elem, depth, buttonName, matchText)
	tell application "System Events"
		if depth > 6 then return missing value
		set foundText to false
		set foundButton to missing value
		try
			set kids to UI elements of elem
		on error
			return missing value
		end try
		repeat with k in kids
			try
				set r to role of k
				if r is "AXButton" and (name of k as text) is buttonName then set foundButton to k
				if r is "AXStaticText" then
					set v to ""
					try
						set v to (value of k as text)
					end try
					if v is "" then
						try
							set v to (name of k as text)
						end try
					end if
					if v contains matchText then set foundText to true
				end if
			end try
		end repeat
		if foundText and foundButton is not missing value then return foundButton
		repeat with k in kids
			try
				if role of k is not "AXWebArea" then
					set b to my findIn(k, depth + 1, buttonName, matchText)
					if b is not missing value then return b
				end if
			end try
		end repeat
		return missing value
	end tell
end findIn

on run argv
	set maxClicks to (item 1 of argv) as integer
	set buttonName to item 2 of argv
	set matchText to item 3 of argv
	set clicked to {}
	tell application "System Events"
		repeat with procName in {"Google Chrome", "Google Chrome Beta", "Google Chrome Canary", "Chromium"}
			if (count of clicked) >= maxClicks then exit repeat
			if exists process procName then
				tell process procName
					repeat with w in windows
						if (count of clicked) >= maxClicks then exit repeat
						set b to my findIn(w, 0, buttonName, matchText)
						if b is not missing value then
							click b
							set end of clicked to (procName as text)
						end if
					end repeat
				end tell
			end if
		end repeat
	end tell
	set AppleScript's text item delimiters to linefeed
	return clicked as text
end run
'''


def mac_click(max_clicks: int) -> list[str]:
    out = subprocess.run(
        ["osascript", "-", str(max_clicks), BUTTON, PROMPT_TEXT],
        input=MAC_SCRIPT, capture_output=True, text=True, timeout=20,
    )
    if out.returncode != 0:
        raise RuntimeError(out.stderr.strip() or "osascript failed")
    return [line for line in out.stdout.splitlines() if line.strip()]


def windows_click(max_clicks: int) -> list[str]:  # untested; opt-in only
    from pywinauto import Desktop  # type: ignore

    clicked: list[str] = []
    for win in Desktop(backend="uia").windows(class_name="Chrome_WidgetWin_1"):
        if len(clicked) >= max_clicks:
            break
        try:
            texts = [t.window_text() for t in win.descendants(control_type="Text")]
            if not any(PROMPT_TEXT in (t or "").lower() for t in texts):
                continue
            for button in win.descendants(control_type="Button"):
                if button.window_text() == BUTTON:
                    button.invoke()
                    clicked.append(win.window_text() or "Chrome")
                    break
        except Exception:  # a window can vanish mid-scan
            continue
    return clicked


def platform_backend():
    if sys.platform == "darwin":
        return mac_click
    if sys.platform == "win32" and os.environ.get("JOB_AGENT_AUTO_ALLOW_WINDOWS") == "1":
        return windows_click
    return None


# ------------------------------------------------------------------ watcher

def watch(base: Path, backend, sleep=time.sleep, clock=time.time, max_loops: int | None = None) -> int:
    """Click prompts while any arm is open. Returns the number of clicks."""
    # A watcher that is just exiting may still hold the lock; retry briefly so
    # a fresh arm is never left without a watcher.
    for _ in range(6):
        if take_lock(base, clock()):
            break
        sleep(0.5)
    else:
        return 0
    clicks = 0
    loops = 0
    try:
        while True:
            live = open_arms(base, clock())
            if not live:
                log(base, "no open windows; watcher stopped")
                return clicks
            try:
                hits = backend(len(live))
            except Exception as exc:  # report and keep the window open until it expires
                log(base, f"click attempt failed: {exc}")
                hits = []
            for what, f in zip(hits, live):
                consume(base, f, what)
                clicks += 1
            heartbeat(base)
            loops += 1
            if max_loops is not None and loops >= max_loops:
                return clicks
            sleep(0.5)
    finally:
        release_lock(base)


def spawn_watcher() -> None:
    cmd = [sys.executable, str(Path(__file__).resolve()), "watch"]
    kwargs: dict = {"stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    subprocess.Popen(cmd, **kwargs)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("enable")
    sub.add_parser("disable")
    p_arm = sub.add_parser("arm")
    p_arm.add_argument("--window", type=float, default=15.0)
    p_arm.add_argument("--label", default="agent")
    sub.add_parser("status")
    sub.add_parser("watch")
    args = ap.parse_args(argv)
    base = base_dir()
    p = paths(base)

    if args.cmd == "enable":
        if platform_backend() is None:
            print("auto-allow supports macOS only (Windows is not supported yet).", file=sys.stderr)
            return 1
        base.mkdir(parents=True, exist_ok=True)
        p["enabled"].write_text("on\n", encoding="utf-8")
        log(base, "enabled by user")
        print("auto-allow enabled. It only acts while an agent has armed it.")
        return 0
    if args.cmd == "disable":
        p["enabled"].unlink(missing_ok=True)
        for f in open_arms(base):
            f.unlink(missing_ok=True)
        log(base, "disabled by user")
        print("auto-allow disabled.")
        return 0
    if args.cmd == "status":
        live = open_arms(base)
        print(f"enabled: {is_enabled(base)}; open windows: {len(live)}; log: {p['log']}")
        return 0
    if args.cmd == "arm":
        if platform_backend() is None:
            print("auto-allow is not available on this platform; click Allow yourself.", file=sys.stderr)
            return 1
        try:
            arm(base, args.window, args.label)
        except PermissionError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        spawn_watcher()
        print(f"armed for {args.window:g}s")
        return 0
    if args.cmd == "watch":
        backend = platform_backend()
        if backend is None:
            return 1
        watch(base, backend)
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
