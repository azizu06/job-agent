#!/usr/bin/env python3
"""Content checks for a tailored resume against its master. Standard library only.

Reads LaTeX (the default template, skills/job-setup/assets/master-resume.tex) or
Markdown (master-resume.md). Alternates never count: LaTeX `\\iffalse ... \\fi`
blocks and Markdown `<!-- alt --> ... <!-- /alt -->` blocks are skipped.

Violations (each fails the check):
  CONFIRM   a bullet still carries `<!-- confirm -->` (setup drafted it, the user has not confirmed it)
  BULLETS   an entry has more than --max-bullets bullets (hard cap 3: swap or reword, never add)
  EMPTY     an Experience or Projects entry has no bullets
  LENGTH    a bullet is longer than --max-chars (a rough proxy for 2 rendered lines; the PDF gate is exact)
  METRIC    a number in the copy that never appears in the master (no invented metrics)
  VERB      the same opening verb starts more than --max-verb-repeats bullets
  IDENTITY  a project's first bullet has no "<noun> that <does what>" phrase in its first 60%
  HACKATHON a bullet about a hackathon win does not name the hackathon with its host school
            ("<School>'s <Hackathon>") and the project count ("of 180 projects")
  UNREAL    a bullet says mock, synthetic, simulated, sandbox, testnet, fake, dummy, toy, demo,
            proof of concept, prototype, test data, seeded, hard-coded or staged.
            Allowed: "software-in-the-loop simulation", "staged rollout/release/deploy"
  AITOOL    a bullet whose point is using AI coding tools (Claude Code, Codex, Copilot, Cursor)
  PROJTITLE a LaTeX project heading that is not \\projtitle{<url>}{<name>}

Warnings (printed, never fail; fix them when the master has the evidence):
  NOMETRIC  a bullet with no number
  SKILLDUP  a Skills row term already used in a bullet (Skills slots should add new keywords)

  python3 resume_check.py --master master.tex --resume tailored.tex
Exit code 1 when any violation is found.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from pathlib import Path

METRIC_RE = re.compile(r"(?<![A-Za-z])\$?\d[\d,.]*\s*(?:%|x|k|m|b|ms|s|\+)?(?![A-Za-z])", re.IGNORECASE)
IDENTITY_NOUNS = (
    "app|application|tool|service|server|platform|library|site|website|dashboard|bot|agent|api|cli|"
    "extension|game|system|pipeline|engine|framework|plugin|model|robot|rover|portal|marketplace|"
    "assistant|tracker|simulator|compiler|database|sdk|device|interface|map|feed|network|workflow|"
    "visualizer|editor|scheduler|monitor|analyzer|planner|generator|chatbot|backend|frontend|utility")
IDENTITY_RE = re.compile(rf"\b(?:{IDENTITY_NOUNS})s?\b[^.;]{{0,30}}?\b(?:that|which|where|behind)\s+\w+", re.IGNORECASE)
IDENTITY_MAX_POS = 0.6
WIN_RE = re.compile(r"\b(?:won|winning|wins|placed|placing|took (?:1st|2nd|3rd|first|second|third)|awarded)\b", re.I)
HACK_RE = re.compile(r"hack|\bprojects\b|\bteams\b|\btrack\b", re.I)
COUNT_RE = re.compile(r"\b\d[\d,]*\+?\s+(?:projects|teams|submissions)\b", re.I)
HOST_RE = re.compile(r"\b[A-Z][\w.&-]*(?:\s+(?:of\s+)?[A-Z][\w.&-]*)*'s\s+[A-Z]")
UNREAL_RE = re.compile(
    r"\b(planted|simulated|mock(?:ed|s|-up)?|seeded|hard-?coded|synthetic|sandbox(?:ed|es)?|testnet|fake|dummy|"
    r"toy|demos?|proof[- ]of[- ]concept|test data|staged(?! (?:rollouts?|releases?|deploy\w*))|prototypes?)\b", re.I)
SIM_RE = re.compile(r"\bsimulat(?:ion|ions|or|ors|ing)\b", re.I)
SIM_OK_RE = re.compile(r"(?:software-in-the-loop|SITL)\s*$", re.I)
AITOOL_RE = re.compile(r"Claude Code|\bCodex\b|Copilot|\bCursor\b|\bAI (?:coding )?(?:agents?|assistants?)\b|ChatGPT", re.I)


# ---------- parsing ----------

def strip_alternates(text: str) -> str:
    text = re.sub(r"\\iffalse\b.*?\\fi\b", "", text, flags=re.DOTALL)
    return re.sub(r"<!--\s*alt\s*-->.*?<!--\s*/alt\s*-->", "", text, flags=re.DOTALL | re.IGNORECASE)


def is_latex(text: str) -> bool:
    return "\\begin{document}" in text or "\\resumeItem" in text


def tex_plain(s: str) -> str:
    """LaTeX fragment to the text a reader sees."""
    s = re.sub(r"\\projtitle\{[^}]*\}\{([^}]*)\}", r"\1", s)
    s = re.sub(r"\\href\{[^}]*\}\{", "{", s)
    s = re.sub(r"\\([%&#_$])", r"\1", s)
    s = s.replace("~", " ").replace("$|$", "|").replace("--", "-")
    s = re.sub(r"\\[a-zA-Z]+\*?", "", s)
    s = re.sub(r"[{}$]", "", s)
    return re.sub(r"\s+", " ", s).strip()


def md_plain(s: str) -> str:
    s = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", s)
    return re.sub(r"\s+", " ", s.replace("**", "").replace("__", "")).strip()


def _group(s: str, i: int) -> tuple[str, int]:
    """Brace group starting at s[i] == '{' -> (content, index after it)."""
    depth = 0
    for j in range(i, len(s)):
        if s[j] == "{" and (j == 0 or s[j - 1] != "\\"):
            depth += 1
        elif s[j] == "}" and s[j - 1] != "\\":
            depth -= 1
            if depth == 0:
                return s[i + 1:j], j + 1
    return s[i + 1:], len(s)


def _groups(s: str, i: int, n: int) -> tuple[list[str], int]:
    out = []
    for _ in range(n):
        while i < len(s) and s[i] != "{":
            i += 1
        g, i = _group(s, i)
        out.append(g)
    return out, i


def parse_tex(text: str) -> dict:
    body = strip_alternates(re.sub(r"(?<!\\)%.*$", "", text, flags=re.MULTILINE))
    entries: list[dict] = []
    skills: list[str] = []
    parts = re.split(r"\\section\*?\{([^}]*)\}", body)
    for name, chunk in zip(parts[1::2], parts[2::2]):
        section = name.strip().lower()
        if "skill" in section:
            for m in re.finditer(r"\\textbf\{([^}]*)\}\s*\{?:", chunk):
                row, _ = _group(chunk, chunk.index("{", m.end() - 2)) if chunk[m.end() - 2] == "{" else (chunk[m.end():].split("\\\\")[0], 0)
                skills.append(tex_plain(m.group(1)) + ": " + tex_plain(row.lstrip(":")))
            continue
        for m in re.finditer(r"\\resume(Subheading|ProjectHeading)\b", chunk):
            n = 4 if m.group(1) == "Subheading" else 2
            args, end = _groups(chunk, m.end(), n)
            nxt = re.search(r"\\resume(?:Subheading|ProjectHeading)\b", chunk[end:])
            seg = chunk[end:end + nxt.start()] if nxt else chunk[end:]
            bullets = []
            for b in re.finditer(r"\\resumeItem\{", seg):
                raw, _ = _group(seg, b.end() - 1)
                bullets.append(tex_plain(raw))
            if n == 4:
                title = f"{tex_plain(args[2])} / {tex_plain(args[0])}"
            else:
                title = tex_plain(args[0]).split("|")[0].strip()
            entries.append({"title": title, "section": section, "bullets": bullets, "heading": args[0],
                            "kind": "project" if n == 2 else "entry"})
    return {"entries": entries, "skills": skills}


def parse_md(text: str) -> dict:
    entries: list[dict] = []
    skills: list[str] = []
    section = ""
    current: dict | None = None
    for raw in strip_alternates(text).splitlines():
        line = raw.rstrip()
        if line.startswith("## ") and not line.startswith("### "):
            section, current = line[3:].strip().lower(), None
        elif line.startswith("### "):
            current = {"title": md_plain(line[4:]).split("|")[0].strip(), "section": section, "bullets": [],
                       "heading": line[4:], "kind": "project" if "project" in section else "entry"}
            entries.append(current)
        elif re.match(r"^\s*[-*] ", line):
            item = re.sub(r"^\s*[-*] ", "", line).strip()
            if "skill" in section:
                skills.append(md_plain(re.sub(r"<!--.*?-->", "", item)))
            elif current is not None:
                current["bullets"].append(md_plain(re.sub(r"<!--.*?-->", "", item)).strip())
    return {"entries": entries, "skills": skills}


def parse(text: str) -> dict:
    return parse_tex(text) if is_latex(text) else parse_md(text)


def parse_entries(text: str) -> list[dict]:
    """Return [{'title', 'section', 'bullets', ...}] in document order (both formats)."""
    return parse(text)["entries"]


def plain_text(text: str) -> str:
    """Whole document as the reader sees it, alternates included (the master's evidence pool)."""
    if is_latex(text):
        return tex_plain(re.sub(r"(?<!\\)%.*$", "", text, flags=re.MULTILINE))
    return md_plain(text)


def metrics(text: str) -> set[str]:
    found = set()
    for m in METRIC_RE.finditer(text):
        token = re.sub(r"\s+", "", m.group(0).strip().lower().replace(",", "")).rstrip(".")
        # Years and single digits are too common to police.
        if re.fullmatch(r"(19|20)\d\d", token) or re.fullmatch(r"\d", token):
            continue
        found.add(token)
    return found


# ---------- checks ----------

def check_bullet_wording(title: str, b: str) -> list[str]:
    problems = []
    m = UNREAL_RE.search(b)
    if m:
        problems.append(f"UNREAL {title}: {m.group(0)!r} makes the work sound not real; name the real mechanism: {b[:60]}...")
    for sm in SIM_RE.finditer(b):
        if not SIM_OK_RE.search(b[max(0, sm.start() - 30):sm.start()]):
            problems.append(f"UNREAL {title}: 'simulat*' outside software-in-the-loop simulation: {b[:60]}...")
    if AITOOL_RE.search(b):
        problems.append(f"AITOOL {title}: AI coding tools belong in the Skills row, not a bullet: {b[:60]}...")
    if WIN_RE.search(b) and HACK_RE.search(b) and not (COUNT_RE.search(b) and HOST_RE.search(b)):
        problems.append(f"HACKATHON {title}: a win names the hackathon with its host school (\"<School>'s <Hackathon>\") "
                        f"and the project count (\"of 180 projects\"): {b[:60]}...")
    return problems


def run_checks(master: str, resume: str, max_bullets: int = 3, max_chars: int = 230,
               max_verb_repeats: int = 2, warnings: list[str] | None = None) -> list[str]:
    problems: list[str] = []
    for line in resume.splitlines():
        if "<!-- confirm -->" in line:
            problems.append(f"CONFIRM unconfirmed bullet from setup: {line.strip()[:60]}...")
    doc = parse(resume)
    entries = doc["entries"]
    bullets = [b for e in entries for b in e["bullets"]]
    latex = is_latex(resume)

    for e in entries:
        t = e["title"]
        if len(e["bullets"]) > max_bullets:
            problems.append(f"BULLETS {t}: {len(e['bullets'])} bullets, cap is {max_bullets}")
        if not e["bullets"] and ("experience" in e["section"] or "project" in e["section"]):
            problems.append(f"EMPTY {t}: no bullets")
        for b in e["bullets"]:
            if len(b) > max_chars:
                problems.append(f"LENGTH {t}: {len(b)} chars: {b[:60]}...")
            problems += check_bullet_wording(t, b)
        if "project" in e["section"] and e["bullets"]:
            first = e["bullets"][0]
            m = IDENTITY_RE.search(first)
            if not m:
                problems.append(f"IDENTITY {t}: first bullet does not say what the project is, "
                                f"as \"<noun> that <does what>\": {first[:70]}...")
            elif m.start() > IDENTITY_MAX_POS * len(first):
                problems.append(f"IDENTITY {t}: the \"<noun> that <does what>\" phrase is buried past the first 60%: {first[:70]}...")
        if latex and e["kind"] == "project" and not re.search(r"\\projtitle\{https?://[^}]+\}", e["heading"]):
            problems.append(f"PROJTITLE {t}: project heading must be \\projtitle{{<url>}}{{<name>}}")

    master_metrics = metrics(plain_text(master))
    for b in bullets:
        for m in sorted(metrics(b) - master_metrics):
            problems.append(f"METRIC {m!r} is not in the master: {b[:60]}...")

    verbs = Counter(b.split()[0].lower().strip(",.") for b in bullets if b.split())
    for verb, n in verbs.items():
        if n > max_verb_repeats:
            problems.append(f"VERB '{verb}' opens {n} bullets, limit is {max_verb_repeats}")

    if warnings is not None:
        for e in entries:
            for b in e["bullets"]:
                if not re.search(r"\d", b):
                    warnings.append(f"NOMETRIC {e['title']}: add a real number if the master has one: {b[:60]}...")
        text = " ".join(bullets).lower()
        dup = [term.strip() for row in doc["skills"] for term in re.split(r",\s*", row.split(":", 1)[-1])
               if len(term.strip()) > 1 and re.search(r"(?<![\w.])" + re.escape(term.strip().lower()) + r"(?![\w])", text)]
        if dup:
            warnings.append("SKILLDUP already in bullets: " + ", ".join(dup) + ". When a JD keyword is missing from the page, "
                            "give it one of these Skills slots")
    return problems


def summary(resume: str) -> list[str]:
    doc = parse(resume)
    out = ["entries (bullets per entry):"]
    out += [f"  {e['section'][:10]:10} {len(e['bullets'])}  {e['title']}" for e in doc["entries"]]
    out.append("project order: " + " > ".join(e["title"] for e in doc["entries"] if "project" in e["section"]))
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--master", required=True)
    ap.add_argument("--resume", required=True)
    ap.add_argument("--max-bullets", type=int, default=3)
    ap.add_argument("--max-chars", type=int, default=230)
    ap.add_argument("--max-verb-repeats", type=int, default=2)
    args = ap.parse_args(argv)
    master = Path(args.master).read_text(encoding="utf-8")
    resume = Path(args.resume).read_text(encoding="utf-8")
    warnings: list[str] = []
    problems = run_checks(master, resume, args.max_bullets, args.max_chars, args.max_verb_repeats, warnings)
    for line in summary(resume):
        print(line)
    for w in warnings:
        print("warn " + w)
    for p in problems:
        print(p)
    print(f"content violations: {len(problems)}")
    print("VERDICT: " + ("FAIL" if problems else "PASS"))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
