import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills" / "tailor-resume" / "scripts"))

import resume_check as rc  # noqa: E402

MASTER = """## Experience
### Example Corp, Software Engineer Intern
- Built a billing service that cut invoice errors by 40% across 3 regions
<!-- alt -->
- Moved 12 cron jobs to a queue, saving 5 hours a week
<!-- /alt -->

## Projects
### Trailmap
- A hiking app that plans routes from trail data for 2,000 users
"""


class ResumeCheckTests(unittest.TestCase):
    def test_clean_copy_passes(self):
        resume = """## Experience
### Example Corp, Software Engineer Intern
- Built a billing service that cut invoice errors by 40% across 3 regions
- Moved 12 cron jobs to a queue, saving 5 hours a week

## Projects
### Trailmap
- A hiking app that plans routes from trail data for 2,000 users
"""
        self.assertEqual(rc.run_checks(MASTER, resume, 3, 210, 2), [])

    def test_alternates_are_skipped_when_parsing(self):
        entries = rc.parse_entries(MASTER)
        self.assertEqual(len(entries[0]["bullets"]), 1)

    def test_flags_unconfirmed_bullet(self):
        resume = "## Projects\n### Trailmap\n- A hiking app that plans routes from trail data <!-- confirm -->\n"
        problems = rc.run_checks(MASTER, resume, 3, 210, 2)
        self.assertTrue(any(p.startswith("CONFIRM") for p in problems))

    def test_flags_new_metric(self):
        resume = MASTER.replace("40%", "65%")
        problems = rc.run_checks(MASTER, resume, 3, 210, 2)
        self.assertTrue(any(p.startswith("METRIC '65%'") for p in problems))

    def test_flags_bullet_cap_length_verbs_identity(self):
        resume = """## Projects
### Thing
- Built stuff with Python
- Built more stuff
- Built even more stuff
- Built one too many
"""
        problems = rc.run_checks(MASTER, resume, 3, 20, 2)
        kinds = {p.split()[0] for p in problems}
        self.assertEqual(kinds, {"BULLETS", "LENGTH", "VERB", "IDENTITY"})


if __name__ == "__main__":
    unittest.main()
