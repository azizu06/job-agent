#!/usr/bin/env python3
"""Resume gate: content check + PDF layout check + three PNGs for the visual review.

A tailored PDF is uploaded only after this gate prints `VERDICT: PASS` and someone has
looked at all three PNGs. On a pass it writes a receipt next to the PDF
(`<name>.pdf.gate.json`, holding the PDF's SHA-256); `--verify` checks that receipt, so
an uploader can refuse a PDF that was never gated or was rebuilt after the gate.

  python3 resume_gate.py --pdf copy.pdf --resume copy.tex --master master.tex
  python3 resume_gate.py --verify copy.pdf          # exit 0 only for a passed, unchanged PDF

Renders into `--out` (default: a `gate/` folder next to the PDF):
  full-110dpi.png, top-half-220dpi.png, bottom-half-220dpi.png

Dependency: PyMuPDF (`python3 -m pip install pymupdf`), for the layout check and the renders.
Exit codes: 0 pass, 1 violations, 2 missing input or dependency.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import layout_check  # noqa: E402
import resume_check  # noqa: E402


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def receipt_path(pdf: Path) -> Path:
    return pdf.with_name(pdf.name + ".gate.json")


def write_receipt(pdf: Path, resume: Path, pngs: list[Path]) -> Path:
    out = receipt_path(pdf)
    out.write_text(json.dumps({"verdict": "PASS", "pdf": str(pdf.resolve()), "sha256": sha256(pdf),
                               "source": str(resume.resolve()), "pngs": [str(p) for p in pngs],
                               "at": dt.datetime.now().isoformat(timespec="seconds")}, indent=2) + "\n",
                   encoding="utf-8")
    return out


def verify(pdf: Path) -> tuple[bool, str]:
    """True when the PDF has a PASS receipt whose hash matches the file on disk now."""
    if not pdf.is_file():
        return False, f"no such PDF: {pdf}"
    rec = receipt_path(pdf)
    if not rec.is_file():
        return False, f"no gate receipt ({rec.name}); run resume_gate.py on this PDF first"
    try:
        data = json.loads(rec.read_text(encoding="utf-8"))
    except ValueError:
        return False, f"unreadable gate receipt {rec}"
    if data.get("verdict") != "PASS":
        return False, "gate verdict is not PASS"
    if data.get("sha256") != sha256(pdf):
        return False, "the PDF changed after the gate passed; run the gate again"
    return True, f"gate PASS at {data.get('at')}"


def render(pdf: Path, out: Path) -> list[Path]:
    try:
        import pymupdf
    except ImportError:
        import fitz as pymupdf  # type: ignore
    out.mkdir(parents=True, exist_ok=True)
    page = pymupdf.open(str(pdf))[0]
    r = page.rect
    shots = {"full-110dpi.png": (110, None),
             "top-half-220dpi.png": (220, pymupdf.Rect(0, 0, r.width, r.height / 2 + 20)),
             "bottom-half-220dpi.png": (220, pymupdf.Rect(0, r.height / 2 - 20, r.width, r.height))}
    paths = []
    for name, (dpi, clip) in shots.items():
        pix = page.get_pixmap(dpi=dpi, clip=clip) if clip else page.get_pixmap(dpi=dpi)
        pix.save(str(out / name))
        paths.append(out / name)
    return paths


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pdf", help="rendered resume PDF")
    ap.add_argument("--resume", help="the .tex or .md source of that PDF")
    ap.add_argument("--master", help="the master resume (numbers must trace to it)")
    ap.add_argument("--out", help="folder for the PNGs (default: <pdf folder>/gate)")
    ap.add_argument("--min-fill", type=int, default=95)
    ap.add_argument("--verify", metavar="PDF", help="only check the receipt of an already gated PDF")
    args = ap.parse_args(argv)

    if args.verify:
        ok, msg = verify(Path(args.verify))
        print(("VERIFY: PASS " if ok else "VERIFY: FAIL ") + msg)
        return 0 if ok else 1
    if not (args.pdf and args.resume and args.master):
        ap.error("--pdf, --resume and --master are required (or use --verify PDF)")
    pdf, resume, master = Path(args.pdf), Path(args.resume), Path(args.master)
    for p in (pdf, resume, master):
        if not p.is_file():
            print(f"resume_gate: no such file: {p}", file=sys.stderr)
            return 2
    receipt_path(pdf).unlink(missing_ok=True)

    print(f"== content check: {resume}")
    warnings: list[str] = []
    problems = resume_check.run_checks(master.read_text(encoding="utf-8"), resume.read_text(encoding="utf-8"),
                                       warnings=warnings)
    for line in resume_check.summary(resume.read_text(encoding="utf-8")):
        print(line)
    for w in warnings:
        print("warn " + w)
    for p in problems:
        print("BAD  " + p)
    print(f"content violations: {len(problems)}")

    print(f"== layout check: {pdf}")
    try:
        layout_bad = layout_check.report(layout_check.check(layout_check.extract(str(pdf)), args.min_fill))
        pngs = render(pdf, Path(args.out) if args.out else pdf.parent / "gate")
    except ImportError:
        print("resume_gate: PyMuPDF is missing. Install it with: python3 -m pip install pymupdf", file=sys.stderr)
        return 2

    print("== renders (Read all three before calling the resume ready)")
    for p in pngs:
        print(p)
    if problems or layout_bad:
        print("VERDICT: FAIL. Fix wording or a shared length in the template, rebuild, run the gate again.")
        return 1
    rec = write_receipt(pdf, resume, pngs)
    print(f"receipt: {rec}")
    print("VERDICT: PASS (content + layout clean). Now look at the three PNGs before any upload.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
