#!/usr/bin/env python3
"""Measure how much of a job description's vocabulary a resume covers.

Standard library only. Reads plain text, Markdown or LaTeX. For a PDF,
convert it first (for example `pdftotext resume.pdf resume.txt`).

Examples:
  python3 keyword_coverage.py --jd jd.txt --resume tailored.md
  python3 keyword_coverage.py --jd jd.txt --resume tailored.md --before master.md
  python3 keyword_coverage.py --jd jd.txt --resume tailored.md --terms terms.txt --json

A terms file has one term per line. Aliases follow on the same line after
`|`, for example `Kubernetes | k8s`. Lines starting with `#` are ignored.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

# Canonical term -> extra spellings that count as the same skill.
# Keep entries lowercase. Ambiguous short words (go, r, c, rest) are left
# out on purpose; add them through a terms file when a posting needs them.
VOCAB: dict[str, list[str]] = {
    "python": [],
    "java": [],
    "javascript": ["js", "ecmascript"],
    "typescript": ["ts"],
    "c++": ["cpp"],
    "c#": ["csharp"],
    "golang": [],
    "rust": [],
    "kotlin": [],
    "swift": [],
    "ruby": [],
    "scala": [],
    "php": [],
    "sql": [],
    "bash": ["shell scripting"],
    "html": ["html5"],
    "css": ["css3"],
    "react": ["react.js", "reactjs"],
    "react native": [],
    "next.js": ["nextjs"],
    "vue": ["vue.js", "vuejs"],
    "angular": [],
    "node.js": ["nodejs", "node"],
    "express": ["express.js"],
    "django": [],
    "flask": [],
    "fastapi": [],
    "spring boot": ["spring"],
    ".net": ["dotnet"],
    "graphql": [],
    "rest api": ["rest apis", "restful", "restful api", "restful apis"],
    "grpc": [],
    "microservices": ["microservice"],
    "postgresql": ["postgres"],
    "mysql": [],
    "mongodb": ["mongo"],
    "redis": [],
    "dynamodb": [],
    "elasticsearch": [],
    "kafka": ["apache kafka"],
    "spark": ["apache spark", "pyspark"],
    "airflow": ["apache airflow"],
    "snowflake": [],
    "databricks": [],
    "aws": ["amazon web services"],
    "gcp": ["google cloud", "google cloud platform"],
    "azure": ["microsoft azure"],
    "docker": [],
    "kubernetes": ["k8s"],
    "terraform": [],
    "ci/cd": ["cicd", "ci cd", "continuous integration", "continuous delivery"],
    "github actions": [],
    "jenkins": [],
    "git": [],
    "linux": [],
    "machine learning": ["ml"],
    "deep learning": [],
    "pytorch": [],
    "tensorflow": [],
    "scikit-learn": ["sklearn"],
    "pandas": [],
    "numpy": [],
    "llm": ["llms", "large language model", "large language models"],
    "rag": ["retrieval augmented generation", "retrieval-augmented generation"],
    "nlp": ["natural language processing"],
    "computer vision": [],
    "data pipelines": ["data pipeline", "etl"],
    "distributed systems": ["distributed system"],
    "system design": [],
    "data structures": [],
    "algorithms": [],
    "object-oriented programming": ["oop", "object oriented programming", "object-oriented"],
    "unit testing": ["unit tests", "pytest", "jest", "junit"],
    "observability": ["monitoring"],
    "agile": ["scrum"],
    "full-stack": ["full stack", "fullstack"],
    "front-end": ["frontend", "front end"],
    "back-end": ["backend", "back end"],
    "mobile": ["ios", "android"],
    "api design": [],
    "security": [],
    "cloud": [],
}

# All-caps words that show up in postings but are not skills.
STOP_ACRONYMS = {
    "US", "USA", "EEO", "EOE", "PTO", "OR", "AND", "THE", "FOR", "WITH", "BS",
    "BA", "MS", "MBA", "PHD", "GPA", "HR", "CEO", "CTO", "VP", "NYC", "SF",
    "LA", "TX", "CA", "NY", "WA", "FL", "IL", "MA", "CO", "OF", "TO", "IN",
    "ON", "AT", "AN", "IS", "AS", "BE", "WE", "YOU", "OUR", "ALL", "ANY",
    "NEW", "NOT", "ADA", "FAQ", "ID", "OK", "AM", "PM", "EST", "PST", "UTC",
    "Q1", "Q2", "Q3", "Q4", "FTE", "LLC", "INC", "LTD", "USD", "K", "M",
}

_BOUNDARY_BEFORE = r"(?<![a-z0-9+#])"
_BOUNDARY_AFTER = r"(?![a-z0-9+#])"


@dataclass(frozen=True)
class Term:
    name: str
    variants: tuple[str, ...] = field(default_factory=tuple)

    def spellings(self) -> tuple[str, ...]:
        return (self.name.lower(),) + tuple(v.lower() for v in self.variants)


def normalize(text: str) -> str:
    """Lowercase, strip LaTeX markup, and collapse whitespace."""
    text = re.sub(r"(?<!\\)%.*$", " ", text, flags=re.MULTILINE)
    text = re.sub(r"\\([%&#_$])", r"\1", text)
    text = re.sub(r"\\[a-zA-Z@]+\*?", " ", text)
    text = text.replace("{", " ").replace("}", " ").replace("~", " ")
    text = text.lower()
    text = re.sub(r"\s+", " ", text)
    return text


def _pattern(spelling: str) -> re.Pattern[str]:
    escaped = r"\s+".join(re.escape(part) for part in spelling.split())
    return re.compile(_BOUNDARY_BEFORE + escaped + _BOUNDARY_AFTER)


def has_term(normalized_text: str, term: Term) -> bool:
    return any(_pattern(s).search(normalized_text) for s in term.spellings())


def _vocab_terms() -> list[Term]:
    return [Term(name, tuple(variants)) for name, variants in VOCAB.items()]


def _canonical_lookup() -> dict[str, str]:
    lookup: dict[str, str] = {}
    for name, variants in VOCAB.items():
        lookup[name] = name
        for v in variants:
            lookup[v] = name
    return lookup


def _tech_tokens(raw_text: str) -> list[str]:
    """Words that look like tool names even when they are not in VOCAB."""
    found: list[str] = []
    # CamelCase or mixed case with an inner capital: PyTorch, GraphQL, FastAPI.
    found += re.findall(r"\b[A-Z][a-z]+[A-Z][A-Za-z]*\b", raw_text)
    # Dotted names: Node.js, Vue.js, ASP.NET.
    found += re.findall(r"\b[A-Za-z]+\.(?:js|JS|NET|net|io)\b", raw_text)
    # Acronyms of 2 to 6 capitals, optionally with digits: AWS, GCP, S3, EC2.
    found += re.findall(r"\b[A-Z][A-Z0-9]{1,5}\b", raw_text)
    return found


def extract_terms(jd_text: str) -> list[Term]:
    """Terms from the job description: known vocabulary plus tool-like words."""
    norm = normalize(jd_text)
    terms = [t for t in _vocab_terms() if has_term(norm, t)]
    seen = {t.name for t in terms}
    lookup = _canonical_lookup()
    for token in _tech_tokens(jd_text):
        if token.upper() in STOP_ACRONYMS or token.isdigit():
            continue
        low = token.lower()
        canonical = lookup.get(low, low)
        if canonical in seen:
            continue
        seen.add(canonical)
        terms.append(Term(token))
    return terms


def parse_terms_file(text: str) -> list[Term]:
    terms: list[Term] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split("|") if p.strip()]
        terms.append(Term(parts[0], tuple(parts[1:])))
    return terms


def coverage(resume_text: str, terms: list[Term]) -> dict:
    norm = normalize(resume_text)
    matched = [t.name for t in terms if has_term(norm, t)]
    missing = [t.name for t in terms if t.name not in matched]
    total = len(terms)
    pct = round(100.0 * len(matched) / total, 1) if total else 0.0
    return {"total": total, "matched": matched, "missing": missing, "percent": pct}


def compare(before_text: str, after_text: str, terms: list[Term]) -> dict:
    before = coverage(before_text, terms)
    after = coverage(after_text, terms)
    newly = [t for t in after["matched"] if t not in before["matched"]]
    lost = [t for t in before["matched"] if t not in after["matched"]]
    return {"before": before, "after": after, "newly_matched": newly, "lost": lost}


def _read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8", errors="replace")


def _fmt(result: dict) -> str:
    return f"{len(result['matched'])}/{result['total']} ({result['percent']}%)"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--jd", required=True, help="job description text file")
    ap.add_argument("--resume", required=True, help="resume to score (txt, md or tex)")
    ap.add_argument("--before", help="earlier resume (for example the master) for a before/after report")
    ap.add_argument("--terms", help="terms file that replaces automatic extraction")
    ap.add_argument("--also", help="terms file added on top of automatic extraction")
    ap.add_argument("--min", type=float, help="exit 1 when coverage is below this percent")
    ap.add_argument("--json", action="store_true", help="print JSON instead of text")
    args = ap.parse_args(argv)

    jd_text = _read(args.jd)
    terms = parse_terms_file(_read(args.terms)) if args.terms else extract_terms(jd_text)
    if args.also:
        have = {t.name.lower() for t in terms}
        terms += [t for t in parse_terms_file(_read(args.also)) if t.name.lower() not in have]

    resume_text = _read(args.resume)
    if args.before:
        report = compare(_read(args.before), resume_text, terms)
        final = report["after"]
    else:
        report = coverage(resume_text, terms)
        final = report

    if args.json:
        print(json.dumps(report, indent=2))
    elif args.before:
        print(f"Before: {_fmt(report['before'])}")
        print(f"After:  {_fmt(report['after'])}")
        print("Newly matched: " + (", ".join(report["newly_matched"]) or "none"))
        if report["lost"]:
            print("Lost: " + ", ".join(report["lost"]))
        print("Still missing: " + (", ".join(report["after"]["missing"]) or "none"))
    else:
        print(f"Coverage: {_fmt(report)}")
        print("Matched: " + (", ".join(report["matched"]) or "none"))
        print("Missing: " + (", ".join(report["missing"]) or "none"))

    if args.min is not None and final["percent"] < args.min:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
