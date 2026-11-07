#!/usr/bin/env python3
"""Layout gate for a rendered resume PDF built from the default template.

Reads the PDF that `tectonic` built from `skills/job-setup/assets/master-resume.tex`
(or from a tailored copy of it, or from `md_to_tex.py` output) and checks what the
eye sees on the page. Prints one `ok` or `BAD` line per check and ends with
`violations: N`. The resume is ready only at `violations: 0`.

  python3 layout_check.py tailored.pdf
  python3 layout_check.py tailored.pdf --min-fill 95
  python3 layout_check.py tailored.pdf --bullets-only   # quick pass while rewording bullets

Checks:
  1. Exactly one page.
  2. Bullets: at most 2 rendered lines, and every line (the last one too) at least
     --min-fill percent of the text width. No 3-line bullets, no half-empty last lines.
  3. No hanging or orphan line anywhere (a wrapped skills row counts) and no wrap
     line without a bullet.
  4. Skills rows are one line each, and the last skills line reaches the right edge.
  5. Full height: the gap under the last line is at most 43.3pt on the 792pt page.
  6. Uniform spacing: bullet pitch, heading to first bullet, entry to entry, section
     rule to first line, section-title gaps, heading line to line, skills pitch.
  7. Every project title is underlined, at one depth, the same distance above its first bullet.
  8. A pixel check of the real white space between heading ink and the first bullet.
  9. Header is the name plus one centered contact line, nothing outside the margins, left edges on the template columns,
     dates and locations on one right column, every entry row has its right side,
     full-width section rules, all four sections present.
 10. One font size per row type, bold skills labels, no overlapping lines.

The column positions below match the default template (0.5in side margins, 11pt
article, 0.15in entry indent). A template with other margins needs new numbers.

Dependency: PyMuPDF (`python3 -m pip install pymupdf`). The checks themselves are
plain Python over a small page model, so tests can build pages without a PDF.
Exit code 1 when any check fails, 2 when the PDF cannot be read.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from typing import Callable

TOL = 0.35  # pt: allowed spread inside one spacing kind
BULLET_GLYPH, BULLET_LEFT, ENTRY_LEFT, SECTION_LEFT = 61.5, 70.8, 46.8, 36.0
LEFT_LIMIT, RIGHT = 35.5, 576.0
MAX_BOTTOM_GAP = 43.3
SECTIONS = ("Education", "Experience", "Projects", "TechnicalSkills")


@dataclass
class Row:
    """One visual line: every span sharing a baseline (left text plus right-aligned dates)."""
    base: float
    parts: list[tuple[float, float, str]]  # (x0, x1, text), sorted left to right
    top: float
    bot: float
    size: float
    label_bold: bool = False  # first span on the line is bold (skills labels)
    kind: str = ""
    section: str | None = None

    @property
    def x0(self) -> float:
        return self.parts[0][0]

    @property
    def x1(self) -> float:
        return max(p[1] for p in self.parts)

    @property
    def text(self) -> str:
        return self.parts[0][2]


@dataclass
class Page:
    width: float
    height: float
    rows: list[Row]
    rules: list[tuple[float, float, float, float]] = field(default_factory=list)  # thin drawn lines (x0, y0, x1, y1)
    pages: int = 1
    white_above: Callable[[float], float] | None = None  # pt of white space above the ink line at y


def extract(pdf_path: str) -> Page:
    """Read page 1 of a PDF into a Page. Needs PyMuPDF."""
    try:
        import pymupdf
    except ImportError:  # older PyMuPDF releases
        import fitz as pymupdf  # type: ignore
    doc = pymupdf.open(pdf_path)
    p = doc[0]
    rows: dict[float, dict] = {}
    for b in p.get_text("dict")["blocks"]:
        for line in b.get("lines", []):
            spans = [s for s in line["spans"] if s["text"].strip()]
            if not spans:
                continue
            # The longest span sets the baseline: the bullet glyph sits off the text baseline.
            base = round(max(spans, key=lambda s: len(s["text"].strip()))["origin"][1], 1)
            key = next((k for k in rows if abs(k - base) < 0.6), base)
            r = rows.setdefault(key, {"parts": [], "spans": [], "size": 0.0})
            r["parts"].append((line["bbox"][0], line["bbox"][2], "".join(s["text"] for s in spans).strip(),
                               line["bbox"][1], line["bbox"][3]))
            r["spans"].extend(spans)
            r["size"] = max([r["size"]] + [s["size"] for s in spans])
    out = []
    for key in sorted(rows):
        r = rows[key]
        r["parts"].sort()
        first = min(r["spans"], key=lambda s: s["bbox"][0])
        out.append(Row(base=key, parts=[(a, b, t) for a, b, t, _, _ in r["parts"]],
                       top=min(x[3] for x in r["parts"]), bot=max(x[4] for x in r["parts"]),
                       size=r["size"], label_bold=bool(first["flags"] & 16)))
    rules = [(d["rect"].x0, d["rect"].y0, d["rect"].x1, d["rect"].y1)
             for d in p.get_drawings() if d["rect"].height < 2]
    zoom = 4
    pix = p.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), colorspace=pymupdf.csGRAY)
    width, samples = pix.width, pix.samples
    x_lo, x_hi = int(40 * zoom), min(int(580 * zoom), width)

    def ink(y: int) -> bool:
        return any(samples[y * width + x] < 160 for x in range(x_lo, x_hi, 2))

    def white_above(y_pt: float) -> float:
        # Start inside the lower line's ink, climb to its top edge, then measure the white run above it.
        y = int(y_pt * zoom)
        while y > 0 and ink(y):
            y -= 1
        start = y
        while y > 0 and not ink(y):
            y -= 1
        return round((start - y) / zoom, 2)

    return Page(width=p.rect.width, height=p.rect.height, rows=out, rules=rules, pages=len(doc),
                white_above=white_above)


def _box_white_above(page: Page) -> Callable[[float], float]:
    """White space above y from row boxes and drawn rules: the pixel check for pages built without a PDF."""
    boxes = sorted([(r.top, r.bot) for r in page.rows] + [(y0, y1) for _, y0, _, y1 in page.rules])

    def white_above(y_pt: float) -> float:
        here = next((b for b in boxes if b[0] <= y_pt <= b[1]), None)
        if here is None:
            return 0.0
        above = [b[1] for b in boxes if b[1] < here[0]]
        return round(here[0] - max(above), 2) if above else 0.0
    return white_above


def classify(rows: list[Row]) -> None:
    section = None
    for r in rows:
        t = r.text
        if t.replace(" ", "") in SECTIONS:
            r.kind, section = "section", t.replace(" ", "")
        elif section is None:
            r.kind = "header"
        elif t.startswith("•"):
            r.kind = "bullet"
        elif abs(r.x0 - BULLET_LEFT) < 2:
            r.kind = "wrap"
        elif section == "TechnicalSkills":
            r.kind = "skill" if ":" in t[:20] else "orphan"
        elif abs(r.x0 - ENTRY_LEFT) < 2:
            r.kind = "entry"
        else:
            r.kind = "orphan"
        r.section = section


def check(page: Page, min_fill: int = 95) -> list[tuple[bool, str]]:
    """Run every layout check. Returns (passed, message) pairs in report order."""
    res: list[tuple[bool, str]] = []

    def put(passed: bool, msg: str) -> None:
        res.append((passed, msg))

    if page.pages != 1:
        put(False, f"{page.pages} pages, need 1")
    rows = sorted(page.rows, key=lambda r: r.base)
    if not rows:
        put(False, "no text found on page 1")
        return res
    classify(rows)
    white_above = page.white_above or _box_white_above(page)
    width = RIGHT - BULLET_LEFT

    for r in rows:
        if r.kind == "orphan":
            put(False, f"hanging line in {r.section}: {r.text[:60]!r}")

    # Bullets: <= 2 lines, every line >= min_fill percent of the text width.
    bullets, cur = [], None
    for r in rows:
        if r.kind == "bullet":
            cur = [r]
            bullets.append(cur)
        elif r.kind == "wrap" and cur is not None:
            cur.append(r)
        elif r.kind == "wrap":
            put(False, f"wrap line with no bullet: {r.text[:60]!r}")
        else:
            cur = None
    for b in bullets:
        fills = [round(100 * (r.x1 - BULLET_LEFT) / width) for r in b]
        put(len(b) <= 2 and min(fills) >= min_fill, f"bullet {len(b)}L {fills} :: {b[0].text[2:60]}")

    # Skills: one line per row; the last row reaches the right edge.
    skills = [r for r in rows if r.section == "TechnicalSkills" and r.kind in ("skill", "orphan")]
    if skills:
        fill = round(100 * (skills[-1].x1 - ENTRY_LEFT) / (RIGHT - ENTRY_LEFT))
        put(fill >= min_fill, f"last skills row fill {fill}% :: {skills[-1].text[:40]}")

    gap = page.height - max(r.bot for r in rows)
    put(gap <= MAX_BOTTOM_GAP, f"bottom gap {gap:.1f}pt (max {MAX_BOTTOM_GAP})")

    # Spacing, baseline to baseline (or cap top to baseline) so glyph shapes cannot fake a difference.
    def uniform(name: str, vals: list[tuple[float, str]]) -> None:
        if not vals:
            return
        lo, hi = min(v for v, _ in vals), max(v for v, _ in vals)
        if hi - lo <= TOL:
            put(True, f"{name}: {lo:.1f}-{hi:.1f}pt across {len(vals)}")
        else:
            mid = sorted(v for v, _ in vals)[len(vals) // 2]
            odd = [w for v, w in vals if abs(v - mid) > TOL]
            put(False, f"{name}: {lo:.1f}-{hi:.1f}pt, off: {odd}")

    body = [r for r in rows if r.kind != "header"]
    cap = lambda r: r.base - 0.70 * r.size  # noqa: E731
    srules = [y0 for x0, y0, x1, y1 in page.rules if x1 - x0 > 500]
    unders = [(x0, y0, x1, y1) for x0, y0, x1, y1 in page.rules if abs(x0 - ENTRY_LEFT) < 2 and x1 - x0 < 200]
    steps: dict[str, list[tuple[float, str]]] = {k: [] for k in (
        "bullet line pitch", "experience heading to first bullet", "project heading to first bullet",
        "entry to entry", "section rule to first line", "last line to next section title",
        "heading line to line", "skills line pitch")}
    for a, b in zip(body, body[1:]):
        vis, w, ka, kb = round(cap(b) - a.base, 2), b.text[:28], a.kind, b.kind
        if ka in ("bullet", "wrap") and kb in ("bullet", "wrap"):
            steps["bullet line pitch"].append((round(b.base - a.base, 2), w))
        elif ka == "entry" and kb == "bullet":
            # Project titles are underlined: measure from the underline, the lowest ink of the heading.
            u = next((y1 for x0, y0, x1, y1 in unders if 0 < y0 - a.base < 6), None)
            key = "project heading to first bullet" if a.section == "Projects" else "experience heading to first bullet"
            steps[key].append((round(cap(b) - (u if u else a.base), 2), a.text[:28]))
        elif ka in ("bullet", "wrap") and kb == "entry":
            steps["entry to entry"].append((vis, w))
        elif ka == "entry" and kb == "entry" and a.section != "Projects":
            steps["heading line to line"].append((round(b.base - a.base, 2), w))
        elif kb == "section":
            steps["last line to next section title"].append((vis, w))
        elif ka == "skill" and kb in ("skill", "orphan"):
            steps["skills line pitch"].append((round(b.base - a.base, 2), w))
        if ka == "section":
            rule = next((y for y in srules if a.base < y < cap(b)), None)
            if rule is None:
                put(False, f"no rule under section {a.text}")
            else:
                steps["section rule to first line"].append((round(cap(b) - rule, 2), w))
    for k, v in steps.items():
        uniform(k, v)
    bp = [v for v, _ in steps["bullet line pitch"]]
    sp = [v for v, _ in steps["skills line pitch"]]
    if bp and sp:
        put(abs(sum(bp) / len(bp) - sum(sp) / len(sp)) <= TOL,
            f"bullet pitch {sum(bp) / len(bp):.2f} vs skills pitch {sum(sp) / len(sp):.2f}")

    # Project title underlines: one depth below the baseline, one gap to the first bullet.
    depth, clear = [], []
    for r in (r for r in rows if r.section == "Projects" and r.kind == "entry"):
        u = next((u for u in unders if 0 < u[1] - r.base < 6), None)
        if u is None:
            put(False, f"project title has no underline: {r.text[:30]}")
            continue
        depth.append((round(u[1] - r.base, 2), r.text[:20]))
        nxt = next((x for x in rows if x.base > r.base + 1), None)
        if nxt:
            clear.append((round(nxt.top - u[1], 2), r.text[:20]))
    uniform("project underline depth", depth)
    uniform("project underline to first bullet", clear)

    # Pixel check: real white space between heading ink and first-bullet ink (0.8pt for glyph shapes).
    px: dict[str, list[tuple[float, str]]] = {"pixel: heading to first bullet": [], "pixel: entry to entry": []}
    for a, b in zip(body, body[1:]):
        if a.kind == "entry" and b.kind == "bullet":
            px["pixel: heading to first bullet"].append((white_above(b.base - 2.5), a.text[:20]))
        if a.kind in ("bullet", "wrap") and b.kind == "entry":
            px["pixel: entry to entry"].append((white_above(b.base - 2.5), b.text[:20]))
    for k, v in px.items():
        if v:
            lo, hi = min(x for x, _ in v), max(x for x, _ in v)
            put(hi - lo <= 0.8, f"{k}: {lo:.1f}-{hi:.1f}pt :: {[(x, w[:12]) for x, w in v]}")

    # Whole-page structure. Header: the name line and one contact line.
    hdr = [r for r in rows if r.kind == "header"]
    put(len(hdr) <= 2, f"header lines: {len(hdr)} (name + one contact line)" if len(hdr) <= 2 else
        f"header wraps to {len(hdr)} lines; shorten the contact line to one line")
    for r in (r for r in rows if r.kind == "header"):
        c = (r.x0 + r.x1) / 2
        put(abs(c - page.width / 2) <= 1.5, f"header centered ({c:.1f} vs {page.width / 2:.1f}) :: {r.text[:30]}")
    for r in rows:
        if r.x1 > RIGHT + 0.6 or r.x0 < LEFT_LIMIT:
            put(False, f"outside margins x0={r.x0:.1f} x1={r.x1:.1f} :: {r.text[:40]}")
    cols = {"section": SECTION_LEFT, "entry": ENTRY_LEFT, "skill": ENTRY_LEFT, "bullet": BULLET_GLYPH, "wrap": BULLET_LEFT}
    for r in rows:
        if r.kind in cols and abs(r.x0 - cols[r.kind]) > 1.0:
            put(False, f"{r.kind} starts at x={r.x0:.1f}, expected {cols[r.kind]} :: {r.text[:40]}")
    rights = [(round(r.parts[-1][1], 1), r.parts[-1][2][:16]) for r in rows if r.kind == "entry" and len(r.parts) > 1]
    if rights:
        lo, hi = min(v for v, _ in rights), max(v for v, _ in rights)
        put(hi - lo <= 1.0, f"right column (dates/locations) aligned: {lo:.1f}-{hi:.1f}")
    for r in rows:
        if r.kind == "entry" and r.section in ("Education", "Experience") and len(r.parts) < 2:
            put(False, f"entry row missing its right-side date/location :: {r.text[:40]}")
    full = [(x0, x1) for x0, y0, x1, y1 in page.rules if x1 - x0 > 500]
    for x0, x1 in full:
        if abs(x0 - SECTION_LEFT) > 1 or abs(x1 - RIGHT) > 1:
            put(False, f"section rule not full width: {x0:.1f}-{x1:.1f}")
    nsec = sum(r.kind == "section" for r in rows)
    put(len(full) == nsec, f"section rules {len(full)} for {nsec} section titles")
    missing = sorted(set(SECTIONS) - {r.section for r in rows if r.kind == "section"})
    put(not missing, f"sections present: missing {missing}" if missing else "sections present: all 4")
    sizes: dict[str, set[float]] = {}
    for r in rows:
        sizes.setdefault(r.kind, set()).add(round(r.size, 1))
    for k in ("section", "bullet", "wrap", "skill"):
        if len(sizes.get(k, ())) > 1:
            put(False, f"{k} rows use mixed font sizes {sorted(sizes[k])}")
    for r in rows:
        if r.kind == "skill" and not r.label_bold:
            put(False, f"skills row label not bold :: {r.text[:30]}")
    for a, b in zip(rows, rows[1:]):
        if b.base - a.base < 0.75 * min(a.size, b.size):
            put(False, f"lines overlap: {a.text[:20]!r} / {b.text[:20]!r}")
    return res


def report(results: list[tuple[bool, str]]) -> int:
    for passed, msg in results:
        print(("ok   " if passed else "BAD  ") + msg)
    bad = sum(not p for p, _ in results)
    print("violations:", bad)
    return bad


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pdf")
    ap.add_argument("--min-fill", type=int, default=95, help="minimum percent of the text width per bullet line")
    ap.add_argument("--bullets-only", action="store_true",
                    help="quick pass while rewording: only the bullet line-count and fill checks")
    args = ap.parse_args(argv)
    try:
        page = extract(args.pdf)
    except ImportError:
        print("layout_check: PyMuPDF is missing. Install it with: python3 -m pip install pymupdf", file=sys.stderr)
        return 2
    except Exception as exc:  # unreadable or missing PDF
        print(f"layout_check: cannot read {args.pdf}: {exc}", file=sys.stderr)
        return 2
    results = check(page, args.min_fill)
    if args.bullets_only:
        results = [r for r in results if re.match(r"bullet \d+L |wrap line", r[1])]
    return 1 if report(results) else 0


if __name__ == "__main__":
    sys.exit(main())
