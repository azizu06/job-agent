import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills" / "tailor-resume" / "scripts"))

import md_to_tex  # noqa: E402

MD = """## Header
Test Applicant | City, ST | test@example.com

## Experience
### Example Corp, Software Engineer Intern (May 2026 to Aug 2026)
- Cut invoice mismatches by 40% with Python & SQL
<!-- alt -->
- An alternate that must not ship
<!-- /alt -->

## Skills
- Languages: C#, Python
"""


class MdToTex(unittest.TestCase):
    def test_converts_layout_and_escapes(self):
        tex = md_to_tex.convert(MD)
        self.assertIn(r"\begin{document}", tex)
        self.assertIn("Test Applicant", tex)
        self.assertIn(r"\textbf{Example Corp, Software Engineer Intern (May 2026 to Aug 2026)}", tex)
        self.assertIn(r"40\% with Python \& SQL", tex)
        self.assertIn(r"C\#", tex)
        self.assertNotIn("alternate that must not ship", tex)
        self.assertEqual(tex.count(r"\begin{itemize}"), tex.count(r"\end{itemize}"))

    def test_refuses_unconfirmed_bullets(self):
        with self.assertRaises(ValueError):
            md_to_tex.convert(MD + "- Drafted bullet <!-- confirm -->\n")


if __name__ == "__main__":
    unittest.main()
