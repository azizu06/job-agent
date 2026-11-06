#!/usr/bin/env python3
"""Job-portal credentials in the OS keychain, for the portal-auth skill.

Passwords live only in the OS credential store through the `keyring` package
(macOS Keychain, Windows Credential Manager, Secret Service on Linux). They
are never written to files, never printed, and never passed on the command
line. The agent moves a password into a form by copying it to the clipboard
(`copy`) and pasting into the focused field, so it never enters the chat or
logs. The clipboard is cleared after a few seconds.

A non-secret index at <workspace>/state/portals.json records which domains
have an entry, the email used, and dates.

Commands:
  has DOMAIN                     exit 0 if an entry exists
  email DOMAIN                   print the stored email (not secret)
  new DOMAIN --email E [--length 20] [--no-symbols]
                                 generate a strong password, store it, print nothing secret
  copy DOMAIN [--clear-after 20] put the password on the clipboard, clear it later
  list                           print the index

Install: pip install keyring
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import secrets
import shutil
import string
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

SERVICE_PREFIX = "job-agent:"
SYMBOLS = "!#%+-=?@_"


def workspace() -> Path:
    return Path(os.environ.get("JOB_AGENT_HOME", Path.home() / ".job-agent")).expanduser()


def index_path() -> Path:
    return workspace() / "state" / "portals.json"


def normalize_domain(value: str) -> str:
    """Accept a URL or a host. Workday tenants keep their full host."""
    host = urlparse(value).hostname if "://" in value else value.split("/")[0]
    host = (host or "").lower().strip(".")
    if host.startswith("www."):
        host = host[4:]
    if not host or " " in host:
        raise ValueError(f"not a domain: {value!r}")
    return host


def generate_password(length: int = 20, symbols: bool = True) -> str:
    """At least one lower, upper, digit (and symbol) for portal rules."""
    if length < 12:
        raise ValueError("length must be at least 12")
    pools = [string.ascii_lowercase, string.ascii_uppercase, string.digits]
    if symbols:
        pools.append(SYMBOLS)
    alphabet = "".join(pools)
    while True:
        pw = "".join(secrets.choice(alphabet) for _ in range(length))
        if all(any(c in pool for c in pw) for pool in pools):
            return pw


def _keyring():
    try:
        import keyring  # type: ignore
    except ImportError:
        print("The keyring package is required: pip install keyring", file=sys.stderr)
        raise SystemExit(3)
    return keyring


def load_index() -> dict:
    p = index_path()
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def save_index(data: dict) -> None:
    p = index_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(p)


def store(domain: str, email: str, password: str, kr=None) -> None:
    kr = kr or _keyring()
    kr.set_password(SERVICE_PREFIX + domain, email, password)
    data = load_index()
    entry = data.get(domain, {"created": dt.date.today().isoformat()})
    entry.update({"email": email, "updated": dt.date.today().isoformat()})
    data[domain] = entry
    save_index(data)


def lookup(domain: str, kr=None) -> tuple[str, str] | None:
    kr = kr or _keyring()
    email = load_index().get(domain, {}).get("email")
    if not email:
        return None
    pw = kr.get_password(SERVICE_PREFIX + domain, email)
    return (email, pw) if pw else None


def clipboard_commands() -> tuple[list[str], list[str]] | None:
    """(copy command reading stdin, clear command) for this OS."""
    if sys.platform == "darwin":
        return ["pbcopy"], ["pbcopy"]
    if sys.platform == "win32":
        ps = ["powershell", "-NoProfile", "-Command"]
        return ps + ["$input | Set-Clipboard"], ps + ["Set-Clipboard -Value ' '"]
    for tool, args in (("wl-copy", []), ("xclip", ["-selection", "clipboard"]), ("xsel", ["--clipboard", "--input"])):
        if shutil.which(tool):
            return [tool, *args], [tool, *args]
    return None


def copy_to_clipboard(secret: str, clear_after: int) -> None:
    cmds = clipboard_commands()
    if cmds is None:
        raise RuntimeError("no clipboard tool found (pbcopy, Set-Clipboard, wl-copy, xclip or xsel)")
    copy, clear = cmds
    subprocess.run(copy, input=secret, text=True, check=True)
    # Clear later in a detached process so the agent is not blocked.
    sleeper = [sys.executable, "-c", f"import time,subprocess;time.sleep({int(clear_after)});"
               f"subprocess.run({clear!r},input='',text=True)"]
    kwargs: dict = {"stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.DETACHED_PROCESS
    else:
        kwargs["start_new_session"] = True
    subprocess.Popen(sleeper, **kwargs)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("has", "email"):
        sub.add_parser(name).add_argument("domain")
    p_new = sub.add_parser("new")
    p_new.add_argument("domain")
    p_new.add_argument("--email", required=True)
    p_new.add_argument("--length", type=int, default=20)
    p_new.add_argument("--no-symbols", action="store_true")
    p_copy = sub.add_parser("copy")
    p_copy.add_argument("domain")
    p_copy.add_argument("--clear-after", type=int, default=20)
    sub.add_parser("list")
    args = ap.parse_args(argv)

    if args.cmd == "list":
        print(json.dumps(load_index(), indent=2, sort_keys=True))
        return 0

    domain = normalize_domain(args.domain)
    if args.cmd == "has":
        return 0 if lookup(domain) else 1
    if args.cmd == "email":
        found = lookup(domain)
        if not found:
            return 1
        print(found[0])
        return 0
    if args.cmd == "new":
        store(domain, args.email, generate_password(args.length, not args.no_symbols))
        print(f"stored a new password for {domain} (not shown)")
        return 0
    if args.cmd == "copy":
        found = lookup(domain)
        if not found:
            print(f"no entry for {domain}", file=sys.stderr)
            return 1
        copy_to_clipboard(found[1], args.clear_after)
        print(f"password for {domain} is on the clipboard for {args.clear_after}s; paste it into the focused field")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
