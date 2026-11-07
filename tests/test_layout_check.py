"""Layout gate checks on a page model of the default template.

The fixture is the real template PDF read by layout_check.extract, saved as JSON, so
these tests need no PDF library. Each failing case breaks one thing on that page.
"""

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills" / "tailor-resume" / "scripts"))

import layout_check as lc  # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "resume" / "template-page.json"
DATA = json.loads(FIXTURE.read_text(encoding="utf-8"))


def page(mutate=None) -> lc.Page:
    d = copy.deepcopy(DATA)
    if mutate:
        mutate(d)
    rows = [lc.Row(base=r["base"], parts=[tuple(p) for p in r["parts"]], top=r["top"], bot=r["bot"],
                   size=r["size"], label_bold=r["label_bold"]) for r in d["rows"]]
    return lc.Page(width=d["width"], height=d["height"], pages=d["pages"], rows=rows,
                   rules=[tuple(q) for q in d["rules"]])


def bad(p: lc.Page) -> list[str]:
    return [m for ok, m in lc.check(p) if not ok]


def find(d, start: str) -> int:
    return next(i for i, r in enumerate(d["rows"]) if r["parts"][0][2].startswith(start))


def shift(d, i: int, dy: float) -> None:
    """Move row i and everything below it down by dy (rules too)."""
    y = d["rows"][i]["top"]
    for r in d["rows"][i:]:
        r["base"] += dy
        r["top"] += dy
        r["bot"] += dy
    d["rules"] = [[x0, y0 + dy, x1, y1 + dy] if y0 >= y else [x0, y0, x1, y1] for x0, y0, x1, y1 in d["rules"]]


class TemplatePasses(unittest.TestCase):
    def test_template_page_is_clean(self):
        self.assertEqual(bad(page()), [])


class Fails(unittest.TestCase):
    def assertFlags(self, mutate, needle):
        problems = bad(page(mutate))
        self.assertTrue(any(needle in p for p in problems), f"{needle!r} not in {problems}")

    def test_two_pages(self):
        self.assertFlags(lambda d: d.update(pages=2), "2 pages, need 1")

    def test_half_empty_last_line(self):
        def m(d):
            i = find(d, "•Built")
            w = d["rows"][i + 1]["parts"][0]
            w[1] = 300.0  # the wrap line of bullet 1 now ends mid-page
        self.assertFlags(m, "bullet 2L")

    def test_short_one_line_bullet(self):
        def m(d):
            d["rows"][find(d, "•Moved")]["parts"][0][1] = 450.0
        self.assertFlags(m, "bullet 1L")

    def test_three_line_bullet(self):
        def m(d):
            i = find(d, "•Built")
            extra = copy.deepcopy(d["rows"][i + 1])
            shift(d, i + 2, 12.0)
            for k in ("base", "top", "bot"):
                extra[k] += 12.0
            d["rows"].insert(i + 2, extra)
        self.assertFlags(m, "bullet 3L")

    def test_wrap_without_bullet(self):
        def m(d):
            i = find(d, "•Built")
            d["rows"][i]["parts"][0][2] = "Built" + d["rows"][i]["parts"][0][2][2:]
            d["rows"][i]["parts"][0][0] = lc.BULLET_LEFT
        self.assertFlags(m, "wrap line with no bullet")

    def test_orphan_line(self):
        def m(d):
            d["rows"][find(d, "andfuel")]["parts"][0][0] = 120.0  # a stray line off every column
        self.assertFlags(m, "hanging line in Experience")

    def test_wrapped_skills_row(self):
        def m(d):
            last = d["rows"][-1]
            extra = copy.deepcopy(last)
            extra["parts"] = [[lc.ENTRY_LEFT, 200.0, "Grafana,Prometheus"]]
            for k in ("base", "top", "bot"):
                extra[k] += 11.95
            d["rows"].append(extra)
        self.assertFlags(m, "hanging line in TechnicalSkills")

    def test_last_skills_row_short(self):
        def m(d):
            d["rows"][-1]["parts"][-1][1] = 400.0
        self.assertFlags(m, "last skills row fill")

    def test_bottom_gap(self):
        def m(d):
            for r in d["rows"]:
                r["base"] -= 20
                r["top"] -= 20
                r["bot"] -= 20
            d["rules"] = [[a, b - 20, c, e - 20] for a, b, c, e in d["rules"]]
        self.assertFlags(m, "bottom gap")

    def test_uneven_bullet_pitch(self):
        self.assertFlags(lambda d: shift(d, find(d, "•Moved"), 1.5), "bullet line pitch")

    def test_uneven_entry_gap(self):
        self.assertFlags(lambda d: shift(d, find(d, "WebDeveloper"), 1.5), "entry to entry")

    def test_missing_project_underline(self):
        def m(d):
            base = d["rows"][find(d, "Shuttle")]["base"]
            d["rules"] = [q for q in d["rules"] if not (abs(q[0] - lc.ENTRY_LEFT) < 2 and 0 < q[1] - base < 6)]
        self.assertFlags(m, "project title has no underline: Shuttle")

    def test_header_off_center(self):
        def m(d):
            for p in d["rows"][0]["parts"]:
                p[0] += 20
                p[1] += 20
        self.assertFlags(m, "header centered")

    def test_header_wraps(self):
        def m(d):
            extra = copy.deepcopy(d["rows"][1])
            shift(d, 2, 12.0)
            for k in ("base", "top", "bot"):
                extra[k] += 12.0
            d["rows"].insert(2, extra)
        self.assertFlags(m, "header wraps to 3 lines")

    def test_text_past_right_margin(self):
        def m(d):
            d["rows"][find(d, "•Moved")]["parts"][-1][1] = 590.0
        self.assertFlags(m, "outside margins")

    def test_date_column_misaligned(self):
        def m(d):
            d["rows"][find(d, "SoftwareEngineering")]["parts"][-1][1] -= 8
        self.assertFlags(m, "right column (dates/locations) aligned")

    def test_entry_without_date(self):
        def m(d):
            r = d["rows"][find(d, "SoftwareEngineering")]
            r["parts"] = r["parts"][:1]
        self.assertFlags(m, "missing its right-side date")

    def test_missing_section(self):
        def m(d):
            i = find(d, "Projects")
            d["rows"][i]["parts"][0][2] = "Things"
        self.assertFlags(m, "sections present: missing ['Projects']")

    def test_mixed_bullet_font_size(self):
        def m(d):
            d["rows"][find(d, "•Moved")]["size"] = 10.95
        self.assertFlags(m, "bullet rows use mixed font sizes")

    def test_skills_label_not_bold(self):
        def m(d):
            d["rows"][-1]["label_bold"] = False
        self.assertFlags(m, "skills row label not bold")

    def test_box_pixel_check_flags_uneven_heading_gap(self):
        def m(d):
            i = find(d, "•Launched")
            d["rows"][i]["top"] += 1.5
        self.assertFlags(m, "pixel: heading to first bullet")


if __name__ == "__main__":
    unittest.main()
