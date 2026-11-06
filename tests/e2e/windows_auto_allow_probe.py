#!/usr/bin/env python3
"""CI probe (windows-latest only): does Chrome show "Allow remote debugging?"
on a hosted runner, and does the Windows auto_allow backend press it?

Prints a VERDICT line and the evidence. Exit 0 when a click was logged,
1 otherwise. Not part of the unit suite.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
AA = REPO / "skills" / "job-setup" / "scripts" / "auto_allow.py"
CHROME = Path(os.environ.get("PROGRAMFILES", r"C:\Program Files")) / "Google" / "Chrome" / "Application" / "chrome.exe"


def windows_snapshot() -> list[str]:
    try:
        from pywinauto import Desktop  # type: ignore
        return [w.window_text() for w in Desktop(backend="uia").windows()]
    except Exception as exc:  # noqa: BLE001
        return [f"pywinauto failed: {exc}"]


def mcp_list_pages(timeout: float = 40.0) -> str:
    """Start chrome-devtools MCP with --autoConnect and call list_pages once."""
    proc = subprocess.Popen(
        "npx -y chrome-devtools-mcp@1.10.1 --autoConnect --no-usage-statistics",
        shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    msgs = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "probe", "version": "0"}}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "list_pages", "arguments": {}}},
    ]
    try:
        out, err = proc.communicate("".join(json.dumps(m) + "\n" for m in msgs), timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        out, err = proc.communicate()
    return (out or "")[-1500:] + "\nSTDERR:\n" + (err or "")[-1500:]


def main() -> int:
    if sys.platform != "win32":
        print("VERDICT: skipped (not Windows)")
        return 0
    if not CHROME.exists():
        print(f"VERDICT: no Chrome at {CHROME}")
        return 1
    home = Path(os.environ.get("JOB_AGENT_HOME") or tempfile.mkdtemp())
    home.mkdir(parents=True, exist_ok=True)
    # Default user-data-dir, so --autoConnect can find it. Remote debugging for
    # autoConnect is normally switched on by the user at chrome://inspect.
    chrome = subprocess.Popen([str(CHROME), "--no-first-run", "--no-default-browser-check", "chrome://inspect/#remote-debugging"])
    time.sleep(8)
    print("windows after launch:", windows_snapshot())
    env = dict(os.environ, JOB_AGENT_HOME=str(home))
    subprocess.run([sys.executable, str(AA), "enable"], env=env, check=False)
    subprocess.run([sys.executable, str(AA), "arm", "--window", "40", "--label", "ci"], env=env, check=False)
    print("MCP:", mcp_list_pages())
    print("windows after connect:", windows_snapshot())
    log = home / "auto-allow.log"
    text = log.read_text(encoding="utf-8") if log.exists() else ""
    print("auto-allow.log:\n" + text)
    chrome.kill()
    if "clicked Allow" in text:
        print("VERDICT: prompt shown and pressed by the Windows backend")
        return 0
    print("VERDICT: no click logged (see windows list and MCP output for why)")
    return 1


if __name__ == "__main__":
    sys.exit(main())
