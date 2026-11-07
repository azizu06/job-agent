#!/usr/bin/env python3
"""Read the small YAML subset job-agent's profile files use. Standard library only.

Supports: comments, nested maps by indentation, lists of scalars or maps
("- item", "- key: value"), inline maps ({ max: 2, window_days: 180 }),
inline lists ([a, b]), quoted strings, numbers, true/false, null and blanks.
It is not a general YAML parser; it reads preferences.yaml and
standing-answers.yaml as setup writes them.

  prefs_yaml.py <file.yaml>     print the file as JSON
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


def _strip_comment(line: str) -> str:
    out, quote = [], None
    for i, ch in enumerate(line):
        if quote:
            if ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
        elif ch == "#" and (i == 0 or line[i - 1] in " \t"):
            break
        out.append(ch)
    return "".join(out).rstrip()


def _split_top(text: str, sep: str = ",") -> list[str]:
    parts, depth, quote, cur = [], 0, None, []
    for ch in text:
        if quote:
            cur.append(ch)
            if ch == quote:
                quote = None
            continue
        if ch in "\"'":
            quote = ch
        elif ch in "[{":
            depth += 1
        elif ch in "]}":
            depth -= 1
        elif ch == sep and depth == 0:
            parts.append("".join(cur).strip())
            cur = []
            continue
        cur.append(ch)
    if "".join(cur).strip():
        parts.append("".join(cur).strip())
    return parts


def scalar(text: str):
    t = text.strip()
    if t == "" or t in ("~", "null", "Null", "NULL"):
        return None
    if t[0] == "{" and t[-1] == "}":
        out = {}
        for part in _split_top(t[1:-1]):
            k, _, v = part.partition(":")
            out[k.strip().strip("\"'")] = scalar(v)
        return out
    if t[0] == "[" and t[-1] == "]":
        return [scalar(p) for p in _split_top(t[1:-1])]
    if len(t) >= 2 and t[0] == t[-1] and t[0] in "\"'":
        return t[1:-1]
    if t in ("true", "True", "yes"):
        return True
    if t in ("false", "False", "no"):
        return False
    if re.fullmatch(r"-?\d+", t):
        return int(t)
    if re.fullmatch(r"-?\d+\.\d*", t):
        return float(t)
    return t


_KEY = re.compile(r"^([^:#\[\]{}]+?):(?:\s+(.*))?$")


def loads(text: str):
    lines = []
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        line = _strip_comment(raw)
        if line.strip():
            lines.append((len(line) - len(line.lstrip(" ")), line.strip()))
    pos = 0

    def block(indent: int):
        nonlocal pos
        if pos >= len(lines):
            return None
        if lines[pos][1].startswith("- ") or lines[pos][1] == "-":
            out_list = []
            while pos < len(lines) and lines[pos][0] == indent and (lines[pos][1].startswith("- ") or lines[pos][1] == "-"):
                item = lines[pos][1][1:].strip()
                pos += 1
                m = _KEY.match(item)
                if m and not item.startswith(("\"", "'")):
                    # a map item: first key on the dash line, the rest indented under it
                    d = {m.group(1).strip(): scalar(m.group(2) or "") if m.group(2) else None}
                    if m.group(2) is None and pos < len(lines) and lines[pos][0] > indent + 2:
                        d[m.group(1).strip()] = block(lines[pos][0])
                    if pos < len(lines) and lines[pos][0] == indent + 2:
                        more = block(indent + 2)
                        if isinstance(more, dict):
                            d.update(more)
                    out_list.append(d)
                else:
                    out_list.append(scalar(item))
            return out_list
        out = {}
        while pos < len(lines) and lines[pos][0] == indent:
            text_ = lines[pos][1]
            m = _KEY.match(text_)
            if not m:
                raise ValueError(f"cannot read line: {text_!r}")
            key, value = m.group(1).strip().strip("\"'"), m.group(2)
            pos += 1
            if value is not None and value != "":
                out[key] = scalar(value)
            elif pos < len(lines) and lines[pos][0] > indent:
                out[key] = block(lines[pos][0])
            elif pos < len(lines) and lines[pos][0] == indent and lines[pos][1].startswith("- "):
                out[key] = block(indent)
            else:
                out[key] = None
        return out

    result = block(lines[0][0]) if lines else {}
    return result if result is not None else {}


def load(path) -> dict:
    return loads(Path(path).expanduser().read_text(encoding="utf-8")) or {}


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    print(json.dumps(load(sys.argv[1]), indent=1, default=str))
