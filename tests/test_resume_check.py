import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills" / "tailor-resume" / "scripts"))

import resume_check as rc  # noqa: E402

ASSETS = ROOT / "skills" / "job-setup" / "assets"
TEX_MASTER = (ASSETS / "master-resume.tex").read_text(encoding="utf-8")
MD_MASTER = (ASSETS / "master-resume.md").read_text(encoding="utf-8")

MASTER = """## Experience
### Software Engineer Intern | May 2026 -- Aug. 2026
Example Corp | Orlando, FL
- Built a billing service that cut invoice errors by 40% across 3 regions
<!-- alt -->
- Moved 12 cron jobs to a queue, saving 5 hours a week
<!-- /alt -->

## Projects
### [Trailmap](https://example.com/trailmap) | TypeScript
- A hiking app that plans routes from trail data for 2,000 users
"""


def kinds(problems):
    return {p.split()[0] for p in problems}


def one_project(bullet: str, extra: str = "") -> str:
    return f"## Projects\n### [Thing](https://example.com) | Go\n- A tool that sorts mail for 2,000 users\n- {bullet}\n{extra}"


class Templates(unittest.TestCase):
    def test_tex_master_passes_against_itself(self):
        self.assertEqual(rc.run_checks(TEX_MASTER, TEX_MASTER), [])

    def test_md_master_passes_against_itself(self):
        self.assertEqual(rc.run_checks(MD_MASTER, MD_MASTER), [])

    def test_both_masters_hold_the_same_page(self):
        tex = [(e["title"], e["bullets"]) for e in rc.parse_entries(TEX_MASTER) if e["bullets"]]
        md = [(e["title"].split(" / ")[-1], e["bullets"]) for e in rc.parse_entries(MD_MASTER) if e["bullets"]]
        self.assertEqual([b for _, b in tex], [b for _, b in md])
        self.assertEqual(rc.parse(TEX_MASTER)["skills"], rc.parse(MD_MASTER)["skills"])

    def test_tex_alternates_are_skipped(self):
        titles = [e["title"] for e in rc.parse_entries(TEX_MASTER)]
        self.assertNotIn("Quill", titles)
        all_bullets = " ".join(b for e in rc.parse_entries(TEX_MASTER) for b in e["bullets"])
        self.assertNotIn("Containerized", all_bullets)
        self.assertTrue(all(len(e["bullets"]) <= 3 for e in rc.parse_entries(TEX_MASTER)))

    def test_alternate_numbers_count_as_master_evidence(self):
        swapped = TEX_MASTER.replace("\\resumeItem{Blocked \\textbf{30 failing deploys}",
                                     "\\resumeItem{Designed \\textbf{REST APIs} for \\textbf{3 internal teams}.}\n%", 1)
        self.assertNotIn("METRIC", kinds(rc.run_checks(TEX_MASTER, swapped)))


class Passing(unittest.TestCase):
    def test_clean_copy_passes(self):
        resume = MASTER.replace("<!-- alt -->\n", "").replace("<!-- /alt -->\n", "")
        self.assertEqual(rc.run_checks(MASTER, resume), [])

    def test_allowed_wording(self):
        ok = [
            "Validated the planner in software-in-the-loop simulation across 2,000 runs",
            "Cut failed releases by 40% with a staged rollout behind feature flags",
            "Won the Best Civic Hack of 180 projects at Lakeside University's LakeHacks",
        ]
        for b in ok:
            self.assertEqual(rc.run_checks(b + " 2,000 180 40%", one_project(b)), [], b)


class Failing(unittest.TestCase):
    def test_flags_unconfirmed_bullet(self):
        resume = "## Projects\n### Trailmap\n- A hiking app that plans routes from trail data <!-- confirm -->\n"
        self.assertIn("CONFIRM", kinds(rc.run_checks(MASTER, resume)))

    def test_flags_new_metric(self):
        resume = MASTER.replace("40%", "65%")
        self.assertTrue(any(p.startswith("METRIC '65%'") for p in rc.run_checks(MASTER, resume)))

    def test_flags_new_metric_in_tex(self):
        resume = TEX_MASTER.replace("\\textbf{40\\%}", "\\textbf{45\\%}")
        self.assertTrue(any(p.startswith("METRIC '45%'") for p in rc.run_checks(TEX_MASTER, resume)))

    def test_flags_fourth_bullet(self):
        resume = TEX_MASTER.replace("\\resumeItem{Moved", "\\resumeItem{Wrote 12 tests.}\n\\resumeItem{Moved", 1)
        self.assertIn("BULLETS", kinds(rc.run_checks(TEX_MASTER, resume)))

    def test_flags_length_verbs_identity(self):
        resume = """## Projects
### Thing
- Built stuff with Python
- Built more stuff
- Built even more stuff
"""
        self.assertEqual(kinds(rc.run_checks(MASTER, resume, 3, 20, 2)), {"LENGTH", "VERB", "IDENTITY"})

    def test_identity_must_be_noun_that_does(self):
        for first in ("Built a dashboard with React and Go for 2,000 users",
                      "Used Go, React, Redis, Postgres, Docker, Linux and many more tools to build a dashboard that ranks"):
            resume = f"## Projects\n### Thing\n- {first}\n"
            self.assertIn("IDENTITY", kinds(rc.run_checks(first, resume)), first)

    def test_hackathon_win_needs_host_school_and_count(self):
        for b in ("Won Best Civic Hack at LakeHacks with 180 projects competing",
                  "Won Best Civic Hack of 180 projects at LakeHacks",
                  "Won Best Civic Hack at Lakeside University's LakeHacks"):
            self.assertIn("HACKATHON", kinds(rc.run_checks(b + " 2,000 180", one_project(b))), b)

    def test_not_real_wording(self):
        for word in ("mock", "synthetic", "simulated", "sandbox", "testnet", "fake", "dummy", "toy", "demo",
                     "proof of concept", "prototype", "test data", "staged", "seeded", "hard-coded"):
            b = f"Built a {word} pipeline for 2,000 users"
            self.assertIn("UNREAL", kinds(rc.run_checks("2,000", one_project(b))), word)
        b = "Tested routing in a traffic simulation for 2,000 users"
        self.assertIn("UNREAL", kinds(rc.run_checks("2,000", one_project(b))))

    def test_ai_tool_usage_bullet(self):
        b = "Shipped 2,000 lines a week with Claude Code and Copilot"
        self.assertIn("AITOOL", kinds(rc.run_checks("2,000", one_project(b))))

    def test_tex_project_needs_projtitle(self):
        resume = TEX_MASTER.replace("\\projtitle{https://github.com/jordan-lee-example/shuttle}{Shuttle}",
                                    "\\textbf{Shuttle}")
        self.assertIn("PROJTITLE", kinds(rc.run_checks(TEX_MASTER, resume)))

    def test_warnings_do_not_fail(self):
        warnings = []
        resume = one_project("Wrote docs for the team")
        self.assertEqual(rc.run_checks("2,000", resume, warnings=warnings), [])
        self.assertTrue(any(w.startswith("NOMETRIC") for w in warnings))


class Cli(unittest.TestCase):
    def test_main_exit_codes(self):
        master = str(ASSETS / "master-resume.tex")
        self.assertEqual(rc.main(["--master", master, "--resume", master]), 0)


if __name__ == "__main__":
    unittest.main()
