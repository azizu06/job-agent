#!/usr/bin/env python3
"""Turn a tailored Markdown resume (the master-resume.md layout) into LaTeX.

Use it when pandoc is missing or broken: a Markdown resume then only needs a
LaTeX engine (tectonic) to become a PDF.

  python3 md_to_tex.py copy.md -o copy.tex && tectonic copy.tex

Layout read: a `## Header` section whose first line is "Name | item | item",
`##` sections, `### ` entries, `- ` bullets. HTML comments (including
`<!-- alt -->` blocks and `<!-- confirm -->` marks) are dropped. A bullet that
still carries `<!-- confirm -->` is an error: tailoring must never ship it.
Standard library only.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

SPECIAL = {"\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#", "_": r"\_",
           "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}"}

PREAMBLE = r"""\documentclass[10pt]{article}
\usepackage[margin=0.6in]{geometry}
\usepackage{enumitem}
\usepackage[hidelinks]{hyperref}
\setlist[itemize]{leftmargin=1.2em,itemsep=1pt,topsep=2pt,parsep=0pt}
\setlength{\parindent}{0pt}
\pagestyle{empty}
\begin{document}
"""


def esc(text: str) -> str:
    return "".join(SPECIAL.get(c, c) for c in text)


def convert(md: str) -> str:
    if "<!-- confirm -->" in md:
        raise ValueError("a bullet still ends in <!-- confirm -->; ask the user before using it")
    md = re.sub(r"<!--\s*alt\s*-->.*?<!--\s*/alt\s*-->", "", md, flags=re.S)
    md = re.sub(r"<!--.*?-->", "", md, flags=re.S)
    out, section, in_list = [PREAMBLE], "", False

    def close_list():
        nonlocal in_list
        if in_list:
            out.append("\\end{itemize}\n")
            in_list = False

    for raw in md.splitlines():
        line = raw.rstrip()
        if not line.strip() or line.startswith("# "):
            continue
        if line.startswith("## "):
            close_list()
            section = line[3:].strip()
            if section.lower() != "header":
                out.append(f"\\vspace{{4pt}}{{\\large\\bfseries {esc(section)}}}\\\\[-6pt]\\rule{{\\linewidth}}{{0.4pt}}\n")
            continue
        if section.lower() == "header":
            parts = [p.strip() for p in line.split("|")]
            out.append(f"\\begin{{center}}{{\\LARGE\\bfseries {esc(parts[0])}}}\\\\[2pt]"
                       f"{esc(' | '.join(parts[1:]))}\\end{{center}}\n")
            continue
        if line.startswith("### "):
            close_list()
            out.append(f"\\textbf{{{esc(line[4:].strip())}}}\n")
            continue
        if line.lstrip().startswith("- "):
            if not in_list:
                out.append("\\begin{itemize}\n")
                in_list = True
            out.append(f"\\item {esc(line.lstrip()[2:].strip())}\n")
            continue
        close_list()
        out.append(esc(line.strip()) + "\\\\\n")
    close_list()
    out.append("\\end{document}\n")
    return "".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("markdown")
    ap.add_argument("-o", "--out", help="output .tex (default: next to the input)")
    args = ap.parse_args(argv)
    src = Path(args.markdown)
    out = Path(args.out) if args.out else src.with_suffix(".tex")
    try:
        out.write_text(convert(src.read_text(encoding="utf-8")), encoding="utf-8")
    except ValueError as exc:
        print(f"md_to_tex: {exc}", file=sys.stderr)
        return 1
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
