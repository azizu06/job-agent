import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills" / "tailor-resume" / "scripts"))

import apply_uniform  # noqa: E402

JAKE = r"""\documentclass[letterpaper,11pt]{article}
% Sections formatting
\titleformat{\section}{\vspace{-4pt}\scshape\raggedright\large}{}{0em}{}[\color{black}\titlerule \vspace{-5pt}]
\newcommand{\resumeItem}[1]{\item\small{{#1 \vspace{-2pt}}}}
\newcommand{\resumeItemListEnd}{\end{itemize}\vspace{-5pt}}
\begin{document}
\section{Education}
  \resumeSubHeadingListStart
    \resumeSubheading{School}{City}{Degree}{2028}
  \resumeSubHeadingListEnd
\section{Projects}
  \resumeProjectHeading{\href{https://example.com/x}{\underline{\textbf{Thing}}} $|$ \emph{Go}}{}
\section{Technical Skills}
 \begin{itemize}[leftmargin=0.15in, label={}]
 \end{itemize}
\end{document}
"""


class ApplyUniform(unittest.TestCase):
    def test_converts_a_jake_file(self):
        out = apply_uniform.convert(JAKE)
        self.assertIn("\\newlength{\\bulletpitch}", out)
        self.assertIn("\\projtitle{https://example.com/x}{Thing}", out)
        self.assertIn("\\resumeSubHeadingListEnd\\vspace{\\eduadjust}", out)
        self.assertIn("\\vspace{\\skilltop}\\begin{itemize}[leftmargin=0.15in, label={}, topsep=0pt, partopsep=0pt]", out)
        self.assertNotIn("\\vspace{-2pt}", out)  # the old per-item spacing is gone
        self.assertEqual(out.count("\\newcommand{\\resumeItemListEnd}"), 1)

    def test_refuses_an_already_uniform_file(self):
        with self.assertRaises(ValueError):
            apply_uniform.convert(apply_uniform.convert(JAKE))


if __name__ == "__main__":
    unittest.main()
