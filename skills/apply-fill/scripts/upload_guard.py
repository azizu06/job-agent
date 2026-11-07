#!/usr/bin/env python3
"""Gate-before-upload guard and upload checks for apply-fill. Standard library only.

  upload_guard.py stamp  --pdf /abs/resume.pdf --out <stamp.json> -- <gate command...>
        runs the resume gate; on exit 0 writes a stamp holding the PDF's sha256
  upload_guard.py check  --pdf /abs/resume.pdf --stamp <stamp.json>
        exit 0 only if the stamp passed for this exact file (same bytes)
  upload_guard.py js     --pdf /abs/resume.pdf [--selector 'input[type=file]']
        prints an evaluate_script function that attaches the PDF through
        DataTransfer (the fallback when upload_file is refused) and returns
        the attached name and size
  upload_guard.py verify --pdf /abs/resume.pdf --shown-name NAME [--shown-size "84 KB"]
        exit 0 when the name and size the page shows match the file on disk

Never upload a resume that has no passing stamp. The tracker records the
same absolute path. Any edit to the PDF after the gate changes its sha256, so
the stamp no longer matches and the gate has to run again.
"""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_pdf(path: Path) -> None:
    if not path.is_absolute():
        raise ValueError(f"use the absolute path of the PDF, got {path}")
    if not path.is_file():
        raise ValueError(f"{path} does not exist")
    if path.read_bytes()[:5] != b"%PDF-":
        raise ValueError(f"{path} is not a PDF")


def stamp(pdf: Path, out: Path, command: list[str]) -> dict:
    check_pdf(pdf)
    if not command:
        raise ValueError("give the gate command after --")
    proc = subprocess.run(command, capture_output=True, text=True)
    res = {"pdf": str(pdf), "sha256": sha256(pdf), "size": pdf.stat().st_size,
           "verdict": "PASS" if proc.returncode == 0 else "FAIL", "command": command,
           "at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
           "output_tail": (proc.stdout + proc.stderr)[-2000:]}
    if res["verdict"] == "PASS":
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(res, indent=1) + "\n", encoding="utf-8")
    return res


def check(pdf: Path, stamp_path: Path) -> tuple[bool, str]:
    check_pdf(pdf)
    try:
        st = json.loads(stamp_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False, f"no gate stamp at {stamp_path}: run the gate first"
    if st.get("verdict") != "PASS":
        return False, "the gate did not pass"
    if st.get("sha256") != sha256(pdf):
        return False, "the PDF changed after the gate ran (or the stamp is for another file): run the gate again"
    return True, "gate passed for this exact file"


def datatransfer_js(pdf: Path, selector: str = "input[type=file]") -> str:
    check_pdf(pdf)
    b64 = base64.b64encode(pdf.read_bytes()).decode()
    return ("() => { const bin = atob(%s); const arr = new Uint8Array(bin.length);"
            " for (let i = 0; i < bin.length; i++) arr[i] = bin.charCodeAt(i);"
            " const file = new File([arr], %s, {type: 'application/pdf'});"
            " const input = document.querySelector(%s); if (!input) return {error: 'no file input'};"
            " const dt = new DataTransfer(); dt.items.add(file); input.files = dt.files;"
            " input.dispatchEvent(new Event('input', {bubbles: true}));"
            " input.dispatchEvent(new Event('change', {bubbles: true}));"
            " return {name: input.files[0] && input.files[0].name, size: input.files[0] && input.files[0].size, expected: %d}; }"
            % (json.dumps(b64), json.dumps(pdf.name), json.dumps(selector), pdf.stat().st_size))


_SIZE = re.compile(r"([\d.,]+)\s*(B|bytes?|KB|kB|KiB|MB|MiB)?", re.I)


def parse_size(text: str) -> list[tuple[float, float]] | None:
    """Candidate (bytes, tolerance) pairs for text such as '84 KB', '0.1 MB' or '86016'.

    Pages print KB and MB in base 1000 or 1024 and round them, so both bases
    are candidates and the tolerance is half the last printed digit.
    """
    m = _SIZE.search(text or "")
    if not m:
        return None
    digits = m.group(1).replace(",", "")
    num = float(digits)
    unit = (m.group(2) or "B").lower()
    half = 0.5 * 10 ** -(len(digits.split(".")[1]) if "." in digits else 0)
    if unit.startswith("b"):
        return [(num, 0.0)]
    power = 2 if unit.startswith("m") else 1
    bases = (1024,) if unit.endswith("ib") else (1000, 1024)
    return [(num * b ** power, half * b ** power) for b in bases]


def verify(pdf: Path, shown_name: str, shown_size: str = "") -> tuple[bool, list[str]]:
    check_pdf(pdf)
    problems = []
    if shown_name.strip() != pdf.name:
        problems.append(f"page shows {shown_name!r}, the file is {pdf.name!r}")
    if shown_size:
        parsed = parse_size(shown_size)
        actual = pdf.stat().st_size
        if parsed is None:
            problems.append(f"could not read the size {shown_size!r}")
        elif not any(abs(value - actual) <= tol for value, tol in parsed):
            problems.append(f"page shows {shown_size}, the file is {actual} bytes")
    return not problems, problems


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    command: list[str] = []
    if "--" in argv:
        i = argv.index("--")
        argv, command = argv[:i], argv[i + 1:]
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("stamp", "check", "js", "verify"):
        p = sub.add_parser(name)
        p.add_argument("--pdf", required=True)
        if name == "stamp":
            p.add_argument("--out", required=True)
        if name == "check":
            p.add_argument("--stamp", required=True)
        if name == "js":
            p.add_argument("--selector", default="input[type=file]")
        if name == "verify":
            p.add_argument("--shown-name", required=True)
            p.add_argument("--shown-size", default="")
    args = ap.parse_args(argv)
    pdf = Path(args.pdf).expanduser()
    try:
        if args.cmd == "stamp":
            res = stamp(pdf, Path(args.out).expanduser(), command)
            print(json.dumps({k: res[k] for k in ("pdf", "sha256", "verdict")}))
            return 0 if res["verdict"] == "PASS" else 1
        if args.cmd == "check":
            ok, why = check(pdf, Path(args.stamp).expanduser())
            print(json.dumps({"ok": ok, "why": why}))
            return 0 if ok else 1
        if args.cmd == "js":
            print(datatransfer_js(pdf, args.selector))
            return 0
        ok, problems = verify(pdf, args.shown_name, args.shown_size)
        print(json.dumps({"ok": ok, "problems": problems}))
        return 0 if ok else 1
    except ValueError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        return 1


if __name__ == "__main__":
    sys.exit(main())
