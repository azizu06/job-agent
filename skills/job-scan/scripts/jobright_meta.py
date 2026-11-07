#!/usr/bin/env python3
"""JobRight helpers for job-scan: first-seen time, posting metadata, checkpoint.

  jobright_meta.py first-seen <job id>...         first-seen time from the id
  jobright_meta.py next-data <file.html>           publishTime and originalUrl from __NEXT_DATA__
  jobright_meta.py window --checkpoint <file>      where this scan should stop, and why
  jobright_meta.py save --checkpoint <file> --id <top card id> [--publish-time T] [--title T] [--company C]

JobRight job ids are MongoDB ObjectIds: the first 8 hex characters are the
unix time the id was created, which is when JobRight first saw the posting.
A repost keeps its old id but gets a fresh publishTime, so the id is the
honest first-seen date.

The window rule: read the feed top-down and stop at the checkpoint id. If the
checkpoint is missing, unreadable or older than --max-hours (default 24),
scan the whole window back to that many hours and say so in the report.
Standard library only.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

UTC = dt.timezone.utc
_OID = re.compile(r"^[0-9a-fA-F]{24}$")


def first_seen(job_id: str) -> dt.datetime | None:
    """First-seen time from a JobRight (MongoDB ObjectId) id, or None if it is not one."""
    job_id = (job_id or "").strip()
    if not _OID.match(job_id):
        return None
    return dt.datetime.fromtimestamp(int(job_id[:8], 16), UTC)


def parse_time(value: str) -> dt.datetime | None:
    """Parse JobRight's publishTime ("2026-11-06 14:05:00", UTC) or an ISO time."""
    value = (value or "").strip()
    if not value:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return dt.datetime.strptime(value[:19], fmt).replace(tzinfo=UTC)
        except ValueError:
            pass
    try:
        t = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=UTC)


_NEXT = re.compile(r"<script[^>]*id=[\"']__NEXT_DATA__[\"'][^>]*>(.*?)</script>", re.S)


def _find_key(obj, key: str):
    if isinstance(obj, dict):
        if key in obj and isinstance(obj[key], (str, int, float)):
            return obj[key]
        for v in obj.values():
            got = _find_key(v, key)
            if got is not None:
                return got
    elif isinstance(obj, list):
        for v in obj:
            got = _find_key(v, key)
            if got is not None:
                return got
    return None


def next_data(html: str) -> dict:
    """publishTime and originalUrl from a /jobs/info/<id> page's __NEXT_DATA__ block.

    Falls back to a plain regex when the block is not valid JSON.
    """
    out = {"publish_time": "", "original_url": ""}
    m = _NEXT.search(html or "")
    if not m:
        return out
    raw = m.group(1)
    try:
        data = json.loads(raw)
        out["publish_time"] = str(_find_key(data, "publishTime") or "")
        out["original_url"] = str(_find_key(data, "originalUrl") or "")
    except ValueError:
        for key, field in (("publishTime", "publish_time"), ("originalUrl", "original_url")):
            g = re.search(r'"%s"\s*:\s*"([^"]*)"' % key, raw)
            if g:
                out[field] = g.group(1)
    out["original_url"] = out["original_url"].replace("\\u0026", "&").replace("\\/", "/")
    return out


def load_checkpoint(path: Path) -> dict | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) and (data.get("job_key") or data.get("id")) else None


def window(checkpoint: dict | None, now: dt.datetime, max_hours: float = 24) -> dict:
    """Decide how far back this scan reads.

    Returns {"stop_at": id or None, "since": ISO, "full_window": bool, "reason": text}.
    """
    since = now - dt.timedelta(hours=max_hours)
    if not checkpoint:
        return {"stop_at": None, "since": since.isoformat(), "full_window": True,
                "reason": f"no checkpoint: scanning the full {max_hours:g}h window"}
    cid = checkpoint.get("job_key") or checkpoint.get("id")
    stamp = parse_time(checkpoint.get("publish_time", "")) or parse_time(checkpoint.get("seen_at", "")) or first_seen(cid)
    if stamp is None:
        return {"stop_at": None, "since": since.isoformat(), "full_window": True,
                "reason": f"checkpoint has no time: scanning the full {max_hours:g}h window"}
    if stamp < since:
        return {"stop_at": None, "since": since.isoformat(), "full_window": True,
                "reason": f"checkpoint is older than {max_hours:g}h ({stamp.isoformat()}): scanning the full window"}
    return {"stop_at": cid, "since": stamp.isoformat(), "full_window": False,
            "reason": f"stop at checkpoint {cid} ({stamp.isoformat()})"}


def cut_at_checkpoint(ids: list[str], stop_at: str | None) -> tuple[list[str], bool]:
    """Cards above the checkpoint, in feed order, and whether the checkpoint was reached."""
    out: list[str] = []
    for i in ids:
        if stop_at and i == stop_at:
            return out, True
        if i not in out:
            out.append(i)
    return out, False


def save_checkpoint(path: Path, job_id: str, publish_time: str = "", title: str = "", company: str = "",
                    now: dt.datetime | None = None) -> dict:
    data = {"job_key": job_id, "publish_time": publish_time, "title": title, "company": company,
            "seen_at": (now or dt.datetime.now(UTC)).replace(microsecond=0).isoformat()}
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data) + "\n", encoding="utf-8")
    tmp.replace(path)
    return data


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("first-seen")
    p.add_argument("ids", nargs="+")
    p = sub.add_parser("next-data")
    p.add_argument("file")
    p = sub.add_parser("window")
    p.add_argument("--checkpoint", required=True)
    p.add_argument("--max-hours", type=float, default=24)
    p = sub.add_parser("save")
    p.add_argument("--checkpoint", required=True)
    p.add_argument("--id", required=True)
    p.add_argument("--publish-time", default="")
    p.add_argument("--title", default="")
    p.add_argument("--company", default="")
    args = ap.parse_args(argv)

    if args.cmd == "first-seen":
        out = {i: (t.isoformat() if (t := first_seen(i)) else None) for i in args.ids}
        print(json.dumps(out, indent=1))
        return 0 if all(out.values()) else 1
    if args.cmd == "next-data":
        print(json.dumps(next_data(Path(args.file).read_text(encoding="utf-8", errors="replace"))))
        return 0
    if args.cmd == "window":
        cp = load_checkpoint(Path(args.checkpoint).expanduser())
        print(json.dumps(window(cp, dt.datetime.now(UTC), args.max_hours)))
        return 0
    print(json.dumps(save_checkpoint(Path(args.checkpoint).expanduser(), args.id, args.publish_time, args.title,
                                     args.company)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
