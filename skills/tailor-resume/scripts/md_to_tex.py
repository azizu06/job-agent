#!/usr/bin/env python3
"""Turn a Markdown resume (the master-resume.md layout) into LaTeX in the default template.

The output uses the exact preamble, macros and spacing of
skills/job-setup/assets/master-resume.tex, so a Markdown master renders in the same
layout and passes the same gate. It needs only a LaTeX engine, no pandoc:

  python3 md_to_tex.py copy.md -o copy.tex && tectonic copy.tex

Layout read:
  ## Header            first line: Name | phone | email | link | link
  ## Education         ### School | Location        then a line: Degree | Date
  ## Experience        ### Title | Dates            then a line: Company | Location, then `- ` bullets
  ## Projects          ### [Name](https://url) | Stack, list        then `- ` bullets
  ## Technical Skills  `- Label: a, b, c` rows ("Skills" and "Skills bank" work too)
Any other section (for example "Confirmed terms") is master-only and never prints.
`**bold**` becomes bold. HTML comments, `<!-- alt -->` blocks and their alternates are
dropped. A bullet that still carries `<!-- confirm -->` is an error: tailoring must never
ship it. A heading with no ` | ` still renders, with an empty right column (the layout
gate will flag the missing date). Standard library only.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

TEMPLATE = Path(__file__).resolve().parents[2] / "job-setup" / "assets" / "master-resume.tex"
SPECIAL = {"\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#", "_": r"\_",
           "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}"}
SKILL_SECTIONS = {"technical skills", "skills", "skills bank"}
PRINTED = {"education", "experience", "projects"} | SKILL_SECTIONS


def esc(text: str) -> str:
    return "".join(SPECIAL.get(c, c) for c in text)


def inline(text: str) -> str:
    """Escape text, keeping **bold** spans as \\textbf and " | " as the template's $|$."""
    parts = re.split(r"\*\*(.+?)\*\*", text)
    out = "".join(f"\\textbf{{{esc(p)}}}" if i % 2 else esc(p) for i, p in enumerate(parts))
    return out.replace(" | ", " $|$ ")


def preamble() -> str:
    """The template's preamble, from \\documentclass through \\begin{document}."""
    src = TEMPLATE.read_text(encoding="utf-8")
    start = src.index("\\documentclass")
    end = src.index("\\begin{document}") + len("\\begin{document}")
    return src[start:end] + "\n"


def split2(line: str) -> tuple[str, str]:
    left, _, right = line.rpartition(" | ")
    if not _:
        return line.strip(), ""
    return left.strip(), right.strip()


def contact(item: str) -> str:
    item = item.strip()
    m = re.fullmatch(r"\[([^\]]+)\]\(([^)]+)\)", item)
    if m:
        return f"\\href{{{m.group(2)}}}{{\\underline{{{esc(m.group(1))}}}}}"
    if re.fullmatch(r"[^@\s]+@[^@\s]+\.\w+", item):
        return f"\\href{{mailto:{item}}}{{\\underline{{{esc(item)}}}}}"
    if re.fullmatch(r"(https?://)?[\w-]+(\.[\w-]+)+(/\S*)?", item) and not re.fullmatch(r"[\d.\-() ]+", item):
        url = item if item.startswith("http") else "https://" + item
        return f"\\href{{{url}}}{{\\underline{{{esc(re.sub(r'^https?://', '', item))}}}}}"
    return esc(item)


def convert(md: str) -> str:
    if "<!-- confirm -->" in md:
        raise ValueError("a bullet still ends in <!-- confirm -->; ask the user before using it")
    md = re.sub(r"<!--\s*alt\s*-->.*?<!--\s*/alt\s*-->", "", md, flags=re.S | re.I)
    md = re.sub(r"<!--.*?-->", "", md, flags=re.S)

    sections: list[tuple[str, list[str]]] = []
    for raw in md.splitlines():
        line = raw.rstrip()
        if line.startswith("## ") and not line.startswith("### "):
            sections.append((line[3:].strip(), []))
        elif sections and line.strip() and not line.startswith("# "):
            sections[-1][1].append(line)

    out = [preamble(), "\n"]
    for name, lines in sections:
        key = name.lower()
        if key == "header":
            items = [p.strip() for p in lines[0].split("|")] if lines else ["Your Name"]
            out.append("\\begin{center}\n"
                       f"    \\textbf{{\\Huge \\scshape {esc(items[0])}}} \\\\ \\vspace{{1pt}}\n"
                       f"    \\small {' $|$ '.join(contact(i) for i in items[1:])}\n"
                       "\\end{center}\n\n")
            continue
        if key not in PRINTED:
            continue  # master-only sections: Confirmed terms, notes
        if key in SKILL_SECTIONS:
            rows = [re.sub(r"^\s*[-*] ", "", l).strip() for l in lines if re.match(r"^\s*[-*] ", l)]
            body = " \\\\\n".join(f"     \\textbf{{{esc(lab.strip())}}}{{: {inline(val.strip())}}}"
                                  for lab, _, val in (r.partition(":") for r in rows))
            out.append("\\section{Technical Skills}\n"
                       " \\vspace{\\skilltop}\\begin{itemize}[leftmargin=0.15in, label={}, topsep=0pt, partopsep=0pt]\n"
                       f"    \\small{{\\item{{\n{body}\n    }}}}\n \\end{{itemize}}\n\n")
            continue
        out.append(f"\\section{{{esc(name)}}}\n  \\resumeSubHeadingListStart\n")
        i = 0
        while i < len(lines):
            line = lines[i]
            if not line.startswith("### "):
                i += 1
                continue
            head = line[4:].strip()
            i += 1
            sub = ""
            if i < len(lines) and not lines[i].startswith("### ") and not re.match(r"^\s*[-*] ", lines[i]):
                sub = lines[i].strip()
                i += 1
            bullets = []
            while i < len(lines) and re.match(r"^\s*[-*] ", lines[i]):
                bullets.append(re.sub(r"^\s*[-*] ", "", lines[i]).strip())
                i += 1
            if key == "projects":
                left, stack = split2(head)
                m = re.fullmatch(r"\[([^\]]+)\]\(([^)]+)\)", left)
                title = f"\\projtitle{{{m.group(2)}}}{{{esc(m.group(1))}}}" if m else f"\\textbf{{{esc(left)}}}"
                tail = f" $|$ \\emph{{{esc(stack)}}}" if stack else ""
                out.append(f"    \\resumeProjectHeading\n      {{{title}{tail}}}{{}}\n")
            else:
                a, b = split2(head)
                c, d = split2(sub)
                out.append(f"    \\resumeSubheading\n      {{{inline(a)}}}{{{inline(b)}}}\n"
                           f"      {{{inline(c)}}}{{{inline(d)}}}\n")
            if bullets:
                out.append("      \\resumeItemListStart\n")
                out += [f"        \\resumeItem{{{inline(b)}}}\n" for b in bullets]
                out.append("      \\resumeItemListEnd\n")
        end = "  \\resumeSubHeadingListEnd"
        out.append(end + ("\\vspace{\\eduadjust}\n\n" if key == "education" else "\n\n"))
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
