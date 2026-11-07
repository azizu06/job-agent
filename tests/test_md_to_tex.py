import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills" / "tailor-resume" / "scripts"))

import md_to_tex  # noqa: E402
import resume_check  # noqa: E402

ASSETS = ROOT / "skills" / "job-setup" / "assets"

MD = """## Header
Test Applicant | 555-0100 | test@example.com | github.com/example

## Experience
### Software Engineer Intern | May 2026 -- Aug. 2026
Example Corp | Orlando, FL
- Cut invoice mismatches by **40%** with Python & SQL
<!-- alt -->
- An alternate that must not ship
<!-- /alt -->

## Projects
### [Trailmap](https://example.com/trailmap) | TypeScript, React
- A hiking app that plans routes for C# fans

## Technical Skills
- Languages: C#, Python

## Confirmed terms
- Kafka: used at Example Corp
"""


class MdToTex(unittest.TestCase):
    def test_uses_the_template_preamble(self):
        tex = md_to_tex.convert(MD)
        template = (ASSETS / "master-resume.tex").read_text(encoding="utf-8")
        pre = template[template.index("\\documentclass"):template.index("\\begin{document}")]
        self.assertIn(pre, tex)
        self.assertIn("\\newcommand{\\projtitle}", tex)

    def test_converts_layout_and_escapes(self):
        tex = md_to_tex.convert(MD)
        self.assertIn("\\textbf{\\Huge \\scshape Test Applicant}", tex)
        self.assertIn("\\href{mailto:test@example.com}{\\underline{test@example.com}}", tex)
        self.assertIn("\\href{https://github.com/example}{\\underline{github.com/example}}", tex)
        self.assertIn("{Software Engineer Intern}{May 2026 -- Aug. 2026}", tex)
        self.assertIn("{Example Corp}{Orlando, FL}", tex)
        self.assertIn("\\projtitle{https://example.com/trailmap}{Trailmap} $|$ \\emph{TypeScript, React}", tex)
        self.assertIn(r"\textbf{40\%} with Python \& SQL", tex)
        self.assertIn(r"\textbf{Languages}{: C\#, Python}", tex)
        self.assertNotIn("alternate that must not ship", tex)
        self.assertNotIn("Kafka", tex)
        self.assertEqual(tex.count(r"\begin{itemize}"), tex.count(r"\end{itemize}"))

    def test_refuses_unconfirmed_bullets(self):
        with self.assertRaises(ValueError):
            md_to_tex.convert(MD + "- Drafted bullet <!-- confirm -->\n")

    def test_md_master_renders_the_tex_master_page(self):
        md_tex = md_to_tex.convert((ASSETS / "master-resume.md").read_text(encoding="utf-8"))
        master = (ASSETS / "master-resume.tex").read_text(encoding="utf-8")
        a, b = resume_check.parse(md_tex), resume_check.parse(master)
        self.assertEqual([(e["title"], e["bullets"]) for e in a["entries"]],
                         [(e["title"], e["bullets"]) for e in b["entries"]])
        self.assertEqual(a["skills"], b["skills"])
        heads = lambda t: re.findall(r"\\projtitle\{[^}]*\}\{[^}]*\} \$\|\$ \\emph\{[^}]*\}", t)  # noqa: E731
        self.assertEqual(heads(md_tex), heads(resume_check.strip_alternates(master)))


if __name__ == "__main__":
    unittest.main()
