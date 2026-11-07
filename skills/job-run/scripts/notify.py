#!/usr/bin/env python3
"""Send a job-agent notification (for example "a CAPTCHA needs you").

Channel settings live in <workspace>/state/notify.json, written by setup, so
no URL or topic has to appear on a command line:

  {"method": "macos"}
  {"method": "ntfy", "topic": "my-private-topic", "server": "https://ntfy.sh"}
  {"method": "slack", "webhook_url": "https://hooks.slack.com/services/..."}
  {"method": "none"}

An ntfy topic name works like a password: anyone who knows it can read it.
Pick a long random one. A Slack webhook URL can post to your channel; keep it
private.

Usage: notify.py --title TEXT --message TEXT [--url LINK] [--config PATH]
Standard library only.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path


def default_config() -> Path:
    home = Path(os.environ.get("JOB_AGENT_HOME", Path.home() / ".job-agent")).expanduser()
    return home / "state" / "notify.json"


def applescript_quote(text: str) -> str:
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def build_request(cfg: dict, title: str, message: str, url: str | None):
    """Return ("command", argv) or ("http", urllib Request) or ("none", None)."""
    method = cfg.get("method", "none")
    if method == "macos":
        body = message + (f"\n{url}" if url else "")
        script = f"display notification {applescript_quote(body)} with title {applescript_quote(title)}"
        return "command", ["osascript", "-e", script]
    if method == "ntfy":
        server = cfg.get("server", "https://ntfy.sh").rstrip("/")
        topic = cfg["topic"]
        headers = {"Title": title.encode("ascii", "replace").decode()}
        if url:
            headers["Click"] = url
        req = urllib.request.Request(f"{server}/{topic}", data=message.encode("utf-8"), headers=headers, method="POST")
        return "http", req
    if method == "slack":
        text = f"*{title}*\n{message}" + (f"\n{url}" if url else "")
        req = urllib.request.Request(
            cfg["webhook_url"], data=json.dumps({"text": text}).encode("utf-8"),
            headers={"Content-Type": "application/json"}, method="POST")
        return "http", req
    return "none", None


def unsupported_reason(cfg: dict, platform: str = sys.platform) -> str | None:
    """Why this method cannot work on this OS, or None when it can."""
    if cfg.get("method") == "macos" and platform != "darwin":
        return "method macos needs macOS; use ntfy or slack in state/notify.json"
    return None


def send(cfg: dict, title: str, message: str, url: str | None = None) -> bool:
    kind, payload = build_request(cfg, title, message, url)
    if kind == "command":
        return subprocess.run(payload, capture_output=True).returncode == 0
    if kind == "http":
        with urllib.request.urlopen(payload, timeout=10) as resp:
            return 200 <= resp.status < 300
    return False


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--title", required=True)
    ap.add_argument("--message", required=True)
    ap.add_argument("--url")
    ap.add_argument("--config", default=str(default_config()))
    args = ap.parse_args(argv)
    path = Path(args.config).expanduser()
    cfg = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"method": "none"}
    if cfg.get("method", "none") == "none":
        print("notifications are off (no state/notify.json)")
        return 0
    reason = unsupported_reason(cfg)
    if reason:
        print(f"notification failed: {reason}", file=sys.stderr)
        return 1
    try:
        ok = send(cfg, args.title, args.message, args.url)
    except Exception as exc:  # network or permission problems should not stop a run
        print(f"notification failed: {exc}", file=sys.stderr)
        return 1
    print("sent" if ok else "notification failed")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
