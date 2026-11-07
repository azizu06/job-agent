#!/usr/bin/env python3
"""Apply job-gate's rules to scanned postings. Standard library only.

  gate.py --prefs profile/preferences.yaml --scan state/scan-X.json \
      [--tracker tracker.csv] [--queue state/queue.json] [--now ISO] [--write-queue] [--report]

The agent does the reading (live posting, Gmail, tracker, Simplify banner,
referrals) and writes what it found into each scan item. This script makes
the decisions the same way every run and prints a JSON result, or a plain
report with --report. With --write-queue it adds the passes to the queue
through apply_queue.py, which never re-adds a dropped entry.

Scan item fields the gate reads (all optional except company and title):
  job_key, id (JobRight id), company, title, location, work_mode (onsite|hybrid|remote),
  term_text, pay_text, levels_hourly, levels_note, first_seen (ISO), publish_time,
  employer_published (ISO), employer_date_source, req_id, link, apply_url,
  kind (job|event), event_date, genai_restricted, genai_quote,
  prior_check {gmail, tracker, simplify: clear|found|error|unknown, note},
  referral {state: none|link|contact|pending, link, name, email},
  prestige (tier name), step_up (bool), step_up_reason, fit (number, higher is better),
  source.

Rules, in order (preferences keys in brackets):
  1. title: target roles, role-fit cut words with title overrides, excluded words  [target_roles,
     exclude_title_words, role_fit]
  2. linkedin-only apply link is cut
  3. term: a stated term must match [term]; no stated term follows [term_missing]
  4. freshness: first seen within [freshness.first_seen_hours] (default
     max_posting_age_days x 24) AND the employer's own publish date within
     [freshness.employer_max_days]. Either too old = REPOST
  5. location and work mode [locations, remote_ok, work_mode.remote_requires_prestige]
  6. pay [pay_floor]: posted midpoint, else a levels.fyi number, else a stated
     step up [pay_floor.step_up_route]; the route is written on the entry
  7. prestige [prestige.require]
  8. skip list [companies_to_skip]
  9. GenAI restriction [genai_restriction: flag | skip]
 10. prior application check, FAIL CLOSED [prior_check.fail_closed]
 11. dedupe by company + req ID against the tracker and the queue
 12. per-company caps over rolling windows [caps], then the best
     [caps.best_per_company] siblings by fit, then pay; the rest are dropped
Referral pending: the pass is queued as WAIT-REFERRAL and not filled.
Events (kind: event) pass unless they are over; they are filled, never submitted.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent.parent / "tracker" / "scripts"))
sys.path.insert(0, str(HERE.parent.parent / "job-scan" / "scripts"))

import apply_queue  # noqa: E402
import jobright_meta  # noqa: E402
import prefs_yaml  # noqa: E402
import tracker_csv  # noqa: E402

UTC = dt.timezone.utc
HOURS_PER_YEAR = 2080


# ---------- pay ----------

_MONEY = re.compile(r"\$\s*([\d,]+(?:\.\d+)?)\s*([kK])?")


def pay_unit(text: str) -> str:
    t = text.lower()
    if re.search(r"/\s*(yr|year|annum)|per (year|annum)|a year|annual|salary", t):
        return "year"
    if re.search(r"/\s*mo|per month|a month|monthly", t):
        return "month"
    if re.search(r"/\s*(hr|hour)|per hour|an hour|hourly", t):
        return "hour"
    return ""


def hourly_midpoint(text: str) -> float | None:
    """Midpoint of a posted pay range in dollars per hour, or None if no amount is posted."""
    vals = [float(v.replace(",", "")) * (1000 if k else 1) for v, k in _MONEY.findall(text or "")]
    if not vals:
        return None
    mid = sum(vals[:2]) / len(vals[:2])
    unit = pay_unit(text) or ("year" if mid >= 1000 * 10 else "month" if mid >= 1000 else "hour")
    if unit == "year":
        return mid / HOURS_PER_YEAR
    if unit == "month":
        return mid * 12 / HOURS_PER_YEAR
    return mid


def floor_hourly(pay_floor: dict) -> float:
    amount = float(pay_floor.get("amount") or 0)
    unit = (pay_floor.get("unit") or "hour").lower()
    return amount / HOURS_PER_YEAR if unit == "year" else amount * 12 / HOURS_PER_YEAR if unit == "month" else amount


# ---------- helpers ----------

def _words(items) -> list[str]:
    return [str(x).strip() for x in (items or []) if str(x or "").strip()]


def _has_word(text: str, word: str) -> bool:
    return re.search(r"(?<![A-Za-z0-9])" + re.escape(word.lower()) + r"(?![A-Za-z0-9])", text.lower()) is not None


def _has_role(title: str, role: str) -> bool:
    """Like _has_word, but a role's last word may carry -ing or -s: "Software Engineering Intern" is a Software Engineer role."""
    pat = r"(?<![A-Za-z0-9])" + re.escape(role.lower()) + r"(?:ing|s)?(?![A-Za-z0-9])"
    return re.search(pat, title.lower()) is not None


_SEASON = r"(?:spring|summer|fall|autumn|winter)"
_TERM_IN_TITLE = re.compile(_SEASON + r"(?:\s*/\s*" + _SEASON + r")*\s*(?:'|\u2019)?\s*(?:20)?\d{2}\b", re.I)


def norm_term(text: str) -> str:
    """Lowercase, and write a two-digit year in full: "Summer '27" and "Summer 27" read as "summer 2027"."""
    t = re.sub(r"\s+", " ", (text or "").lower().replace("\u2019", "'"))
    t = re.sub(r"(" + _SEASON + r")\s*'?\s*(\d{2})\b(?!\d)", r"\1 20\2", t)
    return t


def term_from_title(title: str) -> str:
    """A term the title states, like "[Summer 2027]", "Summer '27" or "(Winter/Spring 2027)"; empty when there is none."""
    m = _TERM_IN_TITLE.search(title or "")
    return m.group(0) if m else ""


def _time(value) -> dt.datetime | None:
    return jobright_meta.parse_time(str(value)) if value else None


def fmt_time(t: dt.datetime | None) -> str:
    return t.astimezone(UTC).strftime("%b %d %H:%M UTC") if t else "time unknown"


def job_key(job: dict) -> str:
    if job.get("job_key"):
        return str(job["job_key"])
    return f"{job.get('company', '')}|{job.get('req_id') or job.get('title', '')}|{job.get('link', '')}"


def tier_of(job: dict, prefs: dict) -> str:
    if job.get("prestige"):
        return str(job["prestige"])
    tiers = (prefs.get("prestige") or {}).get("tiers") or {}
    for name, companies in tiers.items():
        if any(tracker_csv.norm_company(c) == tracker_csv.norm_company(job.get("company", "")) for c in companies or []):
            return str(name)
    return ""


def is_step_up(job: dict, prefs: dict) -> tuple[bool, str]:
    if job.get("step_up"):
        return True, str(job.get("step_up_reason") or "stated step up")
    tier = tier_of(job, prefs)
    pass_tiers = _words((prefs.get("prestige") or {}).get("step_up_tiers"))
    if tier and (not pass_tiers or tier in pass_tiers):
        return True, f"prestige tier {tier}"
    return False, ""


# ---------- the gate ----------

def gate_one(job: dict, prefs: dict, now: dt.datetime) -> dict:
    """Return {"decision": pass|near|cut|role_cut|prior_failed|applied, "gate", "why", "entry"}."""
    title = job.get("title", "")
    company = job.get("company", "")
    entry = {k: job.get(k) for k in ("company", "title", "req_id", "link", "apply_url", "location", "pay_text",
                                     "jd_path", "kind", "event_date", "source") if job.get(k) not in (None, "")}
    entry["job_key"] = job_key(job)
    flags: list[str] = []

    def out(decision, gate="", why="", **extra):
        entry.update(extra)
        if flags:
            entry["flags"] = flags
        return {"decision": decision, "gate": gate, "why": why, "entry": entry}

    # 1. title
    fit = prefs.get("role_fit") or {}
    overrides = _words(fit.get("title_overrides"))
    overridden = any(_has_role(title, w) for w in overrides)
    for w in _words(prefs.get("exclude_title_words")):
        if _has_word(title, w):
            return out("role_cut", "title", f"title has excluded word {w!r}")
    if not overridden:
        for w in _words(fit.get("cut_title_words")):
            if _has_word(title, w):
                return out("role_cut", "role_fit", f"title has role-fit cut word {w!r}")
    targets = _words(prefs.get("target_roles")) + _words(fit.get("tailored_title_words")) + overrides
    is_event = (job.get("kind") or "job") == "event"
    if targets and not is_event and not any(_has_role(title, w) for w in targets):
        return out("role_cut", "title", "title matches no target role")
    if any(_has_role(title, w) for w in _words(fit.get("tailored_title_words"))) and not any(
            _has_role(title, w) for w in _words(prefs.get("target_roles"))):
        entry["fit_tier"] = "tailored"

    # 2. linkedin-only
    apply_url = (job.get("apply_url") or job.get("link") or "").lower()
    if re.search(r"https?://([a-z0-9-]+\.)*linkedin\.com/", apply_url):
        return out("cut", "linkedin_only", "the only apply link is on linkedin.com")

    # events: RSVP and QR links are passes, filled and never submitted
    if is_event:
        when = _time(job.get("event_date"))
        if when and when < now:
            return out("cut", "event_over", f"event was {fmt_time(when)}")
        return out("pass", why="event: fill the RSVP, never submit", state=apply_queue.QUEUED, never_submit=True)

    # 3. term
    term = str(prefs.get("term") or "").strip()
    term_text = job.get("term_text") or term_from_title(title)
    if term:
        if term_text:
            if norm_term(term) not in norm_term(term_text):
                return out("near", "term", f"stated term {term_text!r} is not {term!r}")
        elif (prefs.get("term_missing") or "near_miss") != "pass":
            return out("near", "term", "no term stated")
        else:
            flags.append("no term stated")

    # 4. freshness: two checks
    fresh = prefs.get("freshness") or {}
    exempt = _words(fresh.get("exempt_sources"))
    seen_hours = float(fresh.get("first_seen_hours") or (float(prefs.get("max_posting_age_days") or 3) * 24))
    employer_days = fresh.get("employer_max_days")
    seen = _time(job.get("first_seen")) or jobright_meta.first_seen(str(job.get("id") or ""))
    if job.get("source") not in exempt and seen is not None and now - seen > dt.timedelta(hours=seen_hours):
        return out("cut", "repost", f"REPOST: first seen {fmt_time(seen)}, over {seen_hours:g}h ago")
    published = _time(job.get("employer_published"))
    if published is not None and employer_days not in (None, "") and now - published > dt.timedelta(days=float(employer_days)):
        src = job.get("employer_date_source") or "employer posting"
        return out("cut", "repost", f"REPOST: {src} published {fmt_time(published)}, over {float(employer_days):g} days ago")
    entry["first_seen"] = seen.isoformat() if seen else ""
    if published:
        entry["employer_published"] = published.isoformat()

    # 5. location and work mode
    mode = (job.get("work_mode") or "").lower()
    loc = job.get("location") or ""
    locations = _words(prefs.get("locations"))
    remote = mode == "remote" or "remote" in loc.lower()
    if locations and not remote and loc and not any(
            l.lower() in loc.lower() or loc.lower() in l.lower() for l in locations if "remote" not in l.lower()):
        return out("near", "location", f"location {loc!r} is not in your locations")
    if remote:
        if not prefs.get("remote_ok", True):
            return out("near", "location", "remote, and remote_ok is false")
        if (prefs.get("work_mode") or {}).get("remote_requires_prestige"):
            ok, _ = is_step_up(job, prefs)
            if not ok:
                return out("near", "work_mode", "remote at a company outside your prestige tiers")

    # 6. pay
    pf = prefs.get("pay_floor") or {}
    floor = floor_hourly(pf)
    posted = hourly_midpoint(job.get("pay_text") or "")
    step_ok, step_why = is_step_up(job, prefs)
    use_step = pf.get("step_up_route", False)
    levels = job.get("levels_hourly")
    if posted is not None:
        entry["pay_hourly"] = round(posted, 2)
        if posted >= floor:
            entry["pay_route"] = f"posted midpoint ${posted:.0f}/hr"
        elif use_step and step_ok:
            entry["pay_route"] = f"posted ${posted:.0f}/hr is under ${floor:.0f}/hr; passes as a step up: {step_why}"
        else:
            return out("near", "pay", f"posted midpoint ${posted:.0f}/hr is under ${floor:.0f}/hr")
    elif levels not in (None, "") and pf.get("lookup", "none") != "none" and float(levels) >= floor:
        entry["pay_route"] = f"no pay posted; levels.fyi ${float(levels):.0f}/hr ({job.get('levels_note') or 'no note'})"
    elif use_step and step_ok:
        entry["pay_route"] = f"no pay data at or over ${floor:.0f}/hr; passes as a step up: {step_why}"
    else:
        missing = pf.get("missing_pay", "check_live")
        if missing == "allow":
            entry["pay_route"] = "no pay posted; allowed by missing_pay"
        elif missing == "cut":
            return out("cut", "pay", "no pay posted")
        else:
            why = "pay not posted"
            if levels not in (None, ""):
                why += f"; levels.fyi ${float(levels):.0f}/hr is under ${floor:.0f}/hr"
            return out("near", "pay", why)

    # 7. prestige
    if (prefs.get("prestige") or {}).get("require") and not step_ok:
        return out("near", "prestige", "not in your prestige tiers and no step-up reason")
    if step_ok:
        entry["prestige"] = step_why

    # 8. skip list
    for c in _words(prefs.get("companies_to_skip")):
        if tracker_csv.norm_company(c) == tracker_csv.norm_company(company):
            return out("cut", "skip_list", f"{company} is on companies_to_skip")

    # 9. GenAI restriction: no ban list; the JD decides
    if job.get("genai_restricted"):
        mode_ = genai_mode(prefs)
        if mode_ == "skip":
            return out("cut", "genai_policy", f"posting restricts GenAI: {job.get('genai_quote') or 'see JD'}")
        flags.append("GenAI rule in posting")
        entry["genai_quote"] = job.get("genai_quote") or ""

    # 10. prior application check, fail closed
    pc = job.get("prior_check")
    if (prefs.get("prior_check") or {}).get("fail_closed", True):
        if not isinstance(pc, dict):
            return out("prior_failed", "prior_check", "prior-application check did not run")
        needed = _words((prefs.get("prior_check") or {}).get("sources")) or ["gmail", "tracker"]
        for src in needed:
            if pc.get(src) in (None, "", "error", "unknown"):
                return out("prior_failed", "prior_check", f"{src} check could not run ({pc.get(src) or 'missing'})")
    if isinstance(pc, dict):
        hits = [s for s, v in pc.items() if v == "found"]
        if hits:
            return out("applied", "prior_check", f"already applied per {', '.join(hits)}: {pc.get('note') or ''}".strip())

    # referral
    ref = job.get("referral") or {}
    state = apply_queue.QUEUED
    if ref.get("state") == "pending":
        state = apply_queue.WAIT_REFERRAL
        entry["referral"] = ref
    elif ref.get("state") in ("link", "contact"):
        entry["referral"] = ref
    return out("pass", state=state, fit=job.get("fit"))


def genai_mode(prefs: dict) -> str:
    mode = prefs.get("genai_restriction")
    if mode in ("flag", "skip"):
        return mode
    return "skip" if prefs.get("skip_if_genai_banned") else "flag"


def cap_for(company: str, prefs: dict) -> tuple[int | None, int | None]:
    caps = prefs.get("caps") or {}
    for name, rule in (caps.get("per_company") or {}).items():
        if tracker_csv.norm_company(name) == tracker_csv.norm_company(company):
            rule = rule or {}
            return rule.get("max"), rule.get("window_days")
    return caps.get("per_company_default"), caps.get("window_days_default")


def run(jobs: list[dict], prefs: dict, rows: list[dict], queue: dict, now: dt.datetime) -> dict:
    res = {"passes": [], "already_applied": [], "near_misses": [], "cuts": {}, "role_cut_count": 0,
           "prior_check_failed": [], "dropped": [], "scanned": len(jobs)}
    by_company: dict[str, list[dict]] = {}
    for job in jobs:
        r = gate_one(job, prefs, now)
        e = r["entry"]
        e["times"] = {"first_seen": e.get("first_seen", ""), "publish_time": job.get("publish_time", "")}
        if r["decision"] == "role_cut":
            res["role_cut_count"] += 1
            continue
        if r["decision"] == "cut":
            res["cuts"].setdefault(r["gate"], []).append(dict(e, why=r["why"]))
            continue
        if r["decision"] == "near":
            res["near_misses"].append(dict(e, gate=r["gate"], why=r["why"]))
            continue
        if r["decision"] == "prior_failed":
            res["prior_check_failed"].append(dict(e, why=r["why"]))
            continue
        if r["decision"] == "applied":
            res["already_applied"].append(dict(e, why=r["why"]))
            continue
        # 11. dedupe against the tracker and the queue
        if job.get("req_id") or job.get("title"):
            row = tracker_csv.find(rows, e["company"], job.get("req_id", ""), "" if job.get("req_id") else job.get("title", ""))
            if row is not None:
                res["already_applied"].append(dict(e, why=f"tracker row {row.get('req_id') or row.get('role')} ({row.get('status')})"))
                continue
        q = apply_queue.find(queue, e)
        if q is not None:
            key = "already_applied" if not q["state"].startswith(apply_queue.DROPPED) else "dropped"
            res[key].append(dict(e, why=f"already in the queue as {q['state']}"))
            continue
        by_company.setdefault(tracker_csv.norm_company(e["company"]), []).append(e)

    # 12. caps and siblings
    best_n = int((prefs.get("caps") or {}).get("best_per_company") or 0)
    for _, group in by_company.items():
        company = group[0]["company"]
        mx, window = cap_for(company, prefs)
        since = (now - dt.timedelta(days=float(window))).date().isoformat() if window else None
        used = tracker_csv.count(rows, company=company, since=since) if mx is not None else 0
        room = None if mx is None else max(int(mx) - used, 0)
        group.sort(key=lambda e: (-(float(e.get("fit") or 0)), -(e.get("pay_hourly") or 0)))
        limit = min(x for x in (room, best_n or None) if x is not None) if (room is not None or best_n) else len(group)
        for i, e in enumerate(group):
            if i < limit:
                res["passes"].append(e)
            else:
                why = (f"cap: {used} of {mx} used" + (f" in {window} days" if window else "")) if room is not None and i >= room \
                    else f"sibling: only the best {best_n} per company; best is {group[0]['title']}"
                res["dropped"].append(dict(e, why=why))
    return res


def report(res: dict, window: str = "") -> str:
    lines = [f"Scanned {res['scanned']} postings" + (f", window {window}" if window else "") + "."]
    lines.append(f"{res['role_cut_count']} obvious role cuts, not listed.")

    def item(e):
        pay = e.get("pay_route") or e.get("pay_text") or "no pay"
        t = e.get("times", {})
        when = t.get("publish_time") or t.get("first_seen") or ""
        return f"- {e['company']} | {e['title']} | {when or 'time unknown'} | {pay} | {e.get('apply_url') or e.get('link') or ''}" + \
               (f" | {'; '.join(e['flags'])}" if e.get("flags") else "") + \
               (f" | WAIT-REFERRAL" if e.get("state") == apply_queue.WAIT_REFERRAL else "")

    lines.append("\n1. Passes")
    lines += [item(e) for e in res["passes"]] or ["- none"]
    lines.append("\n2. Already applied or possible duplicate")
    lines += [item(e) + f" | {e['why']}" for e in res["already_applied"]] or ["- none"]
    lines.append("\n3. Near misses")
    lines += [item(e) + f" | {e['gate']}: {e['why']}" for e in res["near_misses"]] or ["- none"]
    if res["prior_check_failed"]:
        lines.append("\nNot passed: the prior-application check could not run (fails closed)")
        lines += [item(e) + f" | {e['why']}" for e in res["prior_check_failed"]]
    if res["cuts"]:
        lines.append("\nCuts by gate")
        for gate, items in sorted(res["cuts"].items()):
            lines.append(f"- {gate}: {len(items)}")
            lines += [f"  - {e['company']} {e['title']}: {e['why']}" for e in items]
    if res["dropped"]:
        lines.append("\nDropped (siblings and caps)")
        lines += [f"- {e['company']} {e['title']}: {e['why']}" for e in res["dropped"]]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--prefs", required=True)
    ap.add_argument("--scan", required=True, help="scan JSON: a list of postings, or {\"items\": [...], \"window\": text}")
    ap.add_argument("--tracker", help="tracker CSV for dedupe and caps")
    ap.add_argument("--queue", help="state/queue.json")
    ap.add_argument("--now", help="ISO time, for tests")
    ap.add_argument("--write-queue", action="store_true")
    ap.add_argument("--report", action="store_true", help="print the plain three-group report")
    args = ap.parse_args(argv)

    prefs = prefs_yaml.load(args.prefs)
    data = json.loads(Path(args.scan).expanduser().read_text(encoding="utf-8"))
    jobs = data.get("items", []) if isinstance(data, dict) else data
    window = data.get("window", "") if isinstance(data, dict) else ""
    rows = tracker_csv.load(Path(args.tracker).expanduser()) if args.tracker else []
    qpath = Path(args.queue).expanduser() if args.queue else None
    queue = apply_queue.load(qpath) if qpath else apply_queue.empty()
    now = jobright_meta.parse_time(args.now) if args.now else dt.datetime.now(UTC)
    res = run(jobs, prefs, rows, queue, now)
    if args.write_queue and qpath:
        for e in res["passes"]:
            apply_queue.add(queue, e, now=now)
        for e in res["dropped"]:
            apply_queue.add(queue, dict(e, state=f"{apply_queue.DROPPED}: {e['why']}"), now=now)
        apply_queue.save(qpath, queue)
    print(report(res, window) if args.report else json.dumps(res, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
