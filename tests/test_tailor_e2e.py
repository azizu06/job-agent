"""End to end: tailor the Jordan Lee master to a sample posting, build the PDF, pass the gate.

Needs `tectonic` on PATH and PyMuPDF (`python3 -m pip install pymupdf`); skipped without them.
Set REFRESH_FIXTURES=1 to rewrite tests/fixtures/resume/template-page.json from the
freshly built template PDF (do it after any change to master-resume.tex).
"""

import contextlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "tailor-resume" / "scripts"
ASSETS = ROOT / "skills" / "job-setup" / "assets"
sys.path.insert(0, str(SCRIPTS))

import layout_check  # noqa: E402
import md_to_tex  # noqa: E402
import resume_check  # noqa: E402
import resume_gate  # noqa: E402

try:
    import pymupdf  # noqa: F401
    HAVE_PYMUPDF = True
except ImportError:
    HAVE_PYMUPDF = False

JD = """Northwind Logistics - Software Engineering Intern, Platform

You will build backend services in Python and TypeScript that move freight data between
our carriers and customers. You will design REST APIs, store data in PostgreSQL and Redis,
package services with Docker and run them on AWS. We ship through CI/CD with GitHub Actions
and run everything on Linux. Our dashboards are built with React and Next.js.

Nice to have: Kafka, Terraform.
We value ownership, curiosity and collaboration.
"""
NOT_CLAIMABLE = "# culture words, never coverage terms\nownership\ncuriosity\ncollaboration\n"


def build(tex: Path) -> Path:
    out = subprocess.run(["tectonic", "-X", "compile", tex.name], cwd=tex.parent, capture_output=True, text=True)
    if out.returncode != 0:
        raise AssertionError(out.stdout + out.stderr)
    return tex.with_suffix(".pdf")


def tailor(master: str) -> str:
    """What the tailor-resume steps do for this posting, done by hand so the test is deterministic:
    swap in the Docker/AWS alternate, re-rank projects by match, drop unused alternates."""
    body = re.sub(r"\\iffalse\b.*?\\fi\b\n?", "", master.split("\\begin{document}", 1)[1], flags=re.S)
    tex = master.split("\\begin{document}", 1)[0] + "\\begin{document}" + body
    alt = re.search(r"\\resumeItem\{Containerized[^\n]*\}", master).group(0)
    tex = re.sub(r"\\resumeItem\{Blocked[^\n]*\}", lambda _: alt, tex, count=1)
    projects = re.findall(r"(        \\resumeProjectHeading\n.*?\\resumeItemListEnd\n)", tex, flags=re.S)
    by_name = {re.search(r"\}\{(\w+)\}", p).group(1): p for p in projects}
    order = ["Shuttle", "FloodWatch", "Ledgerline", "StudyBuddy"]  # match to the posting, then strength
    start = tex.index(projects[0])
    end = tex.index(projects[-1]) + len(projects[-1])
    between = "\n".join(by_name[n] for n in order)
    return tex[:start] + between + tex[end:]


@unittest.skipUnless(shutil.which("tectonic") and HAVE_PYMUPDF, "needs tectonic and PyMuPDF")
class TailorEndToEnd(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def gate(self, pdf: Path, resume: Path, master: Path) -> None:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = resume_gate.main(["--pdf", str(pdf), "--resume", str(resume), "--master", str(master),
                                   "--out", str(self.dir / (pdf.stem + "-gate"))])
        self.assertEqual(rc, 0, f"gate failed for {pdf.name}:\n" + buf.getvalue())
        for name in ("full-110dpi.png", "top-half-220dpi.png", "bottom-half-220dpi.png"):
            self.assertTrue((self.dir / (pdf.stem + "-gate") / name).stat().st_size > 10_000)
        self.assertTrue(resume_gate.verify(pdf)[0])

    def test_template_passes_the_gate(self):
        master = self.dir / "master-resume.tex"
        shutil.copy(ASSETS / "master-resume.tex", master)
        pdf = build(master)
        self.gate(pdf, master, master)
        if os.environ.get("REFRESH_FIXTURES"):
            p = layout_check.extract(str(pdf))
            r = lambda v: round(v, 2)  # noqa: E731
            data = {"_note": "Page model of skills/job-setup/assets/master-resume.tex built by tectonic. "
                             "Refresh: REFRESH_FIXTURES=1 python3 -m unittest tests.test_tailor_e2e",
                    "width": p.width, "height": p.height, "pages": p.pages,
                    "rows": [{"base": x.base, "parts": [[r(a), r(b), t] for a, b, t in x.parts], "top": r(x.top),
                              "bot": r(x.bot), "size": r(x.size), "label_bold": x.label_bold} for x in p.rows],
                    "rules": [[r(v) for v in q] for q in p.rules]}
            (ROOT / "tests" / "fixtures" / "resume" / "template-page.json").write_text(
                json.dumps(data, indent=0) + "\n", encoding="utf-8")

    def test_markdown_master_renders_in_the_template_and_passes(self):
        md = self.dir / "master.md"
        shutil.copy(ASSETS / "master-resume.md", md)
        tex = self.dir / "master-md.tex"
        tex.write_text(md_to_tex.convert(md.read_text(encoding="utf-8")), encoding="utf-8")
        self.gate(build(tex), md, md)

    def test_tailor_to_a_posting_and_pass_the_gate(self):
        master = self.dir / "master-resume.tex"
        shutil.copy(ASSETS / "master-resume.tex", master)
        copy = self.dir / "Northwind-Platform" / "Jordan-Lee-Resume.tex"
        copy.parent.mkdir()
        copy.write_text(tailor(master.read_text(encoding="utf-8")), encoding="utf-8")
        jd = self.dir / "jd.txt"
        jd.write_text(JD, encoding="utf-8")
        excl = self.dir / "not-claimable.txt"
        excl.write_text(NOT_CLAIMABLE, encoding="utf-8")

        out = subprocess.run([sys.executable, str(SCRIPTS / "keyword_coverage.py"), "--jd", str(jd), "--resume",
                              str(copy), "--before", str(master), "--company", "Northwind", "--exclude", str(excl),
                              "--json", "--min", "95"], capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        report = json.loads(out.stdout)
        self.assertGreaterEqual(report["after"]["percent"], 95.0)
        self.assertGreaterEqual(report["after"]["percent"], report["before"]["percent"])
        self.assertIn("docker", [t.lower() for t in report["after"]["matched"]])

        text = copy.read_text(encoding="utf-8")
        self.assertNotIn("\\iffalse", text.split("\\begin{document}")[1])
        self.assertEqual(resume_check.run_checks(master.read_text(encoding="utf-8"), text), [])
        order = [e["title"] for e in resume_check.parse_entries(text) if e["kind"] == "project"]
        self.assertEqual(order[0], "Shuttle")
        self.gate(build(copy), copy, master)


if __name__ == "__main__":
    unittest.main()
