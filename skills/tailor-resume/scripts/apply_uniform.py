#!/usr/bin/env python3
"""Convert a Jake's-template resume .tex to the default template's uniform spacing model.

Many students start from Jake Gutierrez's LaTeX resume. The default template here
(skills/job-setup/assets/master-resume.tex) is that layout with one length per gap
kind, so layout_check.py can hold every gap to the same size. This script swaps an
old file's section and heading macros for the template's, and rewrites:
  \\href{url}{\\underline{\\textbf{Name}}}  ->  \\projtitle{url}{Name}   (underlines at one depth)
  the Education list end                    ->  adds \\vspace{\\eduadjust}
  the Technical Skills list start           ->  adds \\vspace{\\skilltop} and zero list spacing

  python3 apply_uniform.py resume.tex [more.tex ...]

It writes `<file>.bak-uniform` first and skips files that already use the model.
Nothing else in the file changes: content, header and fonts stay as they were.
Standard library only.
"""

from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

TEMPLATE = Path(__file__).resolve().parents[2] / "job-setup" / "assets" / "master-resume.tex"


def template_macros() -> str:
    src = TEMPLATE.read_text(encoding="utf-8")
    a = src.index("\\newlength{\\sectionabove}")
    b = src.index("\n", src.index("\\newcommand{\\resumeItemListEnd}")) + 1
    return src[a:b]


def convert(tex: str) -> str:
    if "\\newlength{\\bulletpitch}" in tex:
        raise ValueError("already uses the uniform spacing model")
    start = tex.find("% Sections formatting")
    if start < 0:
        start = tex.index("\\titleformat{\\section}")
    end = tex.index("\n", tex.index("\\newcommand{\\resumeItemListEnd}")) + 1
    tex = tex[:start] + template_macros() + tex[end:]
    tex = re.sub(r"\\href\{([^}]*)\}\{\\underline\{\\textbf\{([^}]*)\}\}\}", r"\\projtitle{\1}{\2}", tex)
    tex = re.sub(r"(\\section\{Education\}.*?\\resumeSubHeadingListEnd)(?!\\vspace)", r"\1\\vspace{\\eduadjust}",
                 tex, count=1, flags=re.S)
    tex = re.sub(r"(\\section\{Technical Skills\}\s*)\\begin\{itemize\}\[leftmargin=0\.15in, label=\{\}\]",
                 r"\1\\vspace{\\skilltop}\\begin{itemize}[leftmargin=0.15in, label={}, topsep=0pt, partopsep=0pt]", tex)
    return tex


def main(argv: list[str] | None = None) -> int:
    files = sys.argv[1:] if argv is None else argv
    if not files:
        print(__doc__)
        return 2
    rc = 0
    for f in files:
        path = Path(f)
        try:
            new = convert(path.read_text(encoding="utf-8"))
        except ValueError as exc:
            print(f"skipped {f}: {exc}")
            continue
        shutil.copy(path, str(path) + ".bak-uniform")
        path.write_text(new, encoding="utf-8")
        print(f"converted {f}: projtitles {new.count(chr(92) + 'projtitle{')}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
