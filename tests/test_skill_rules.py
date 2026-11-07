"""Guard rules in the skill text that end-to-end QA found broken."""

import unittest
from pathlib import Path

SKILLS = Path(__file__).resolve().parents[1] / "skills"


def section(text: str, start: str, end: str) -> str:
    i = text.index(start)
    return text[i:text.index(end, i)]


class SetupJobRightStep(unittest.TestCase):
    def setUp(self):
        text = (SKILLS / "job-setup" / "SKILL.md").read_text(encoding="utf-8")
        self.step = section(text, "**JobRight feed**", "**Master resume**")

    def test_opens_its_own_tab(self):
        self.assertIn("new_page", self.step)
        self.assertIn("never click, type or change the sort in a tab you did not open", self.step)
        self.assertNotIn("reuse a JobRight tab", self.step)

    def test_asks_before_changing_the_account_sort(self):
        self.assertIn("May I switch it to Most Recent?", self.step)
        self.assertNotIn("select Most Recent yourself", self.step)


class SetupAutoAllowStep(unittest.TestCase):
    def test_records_the_no_answer(self):
        text = (SKILLS / "job-setup" / "SKILL.md").read_text(encoding="utf-8")
        step = section(text, "**Hands-free Allow clicks**", "**Gmail and connectors**")
        self.assertIn("If no: record `browser.auto_allow: false`", step)


class SetupWorkspace(unittest.TestCase):
    def setUp(self):
        self.text = (SKILLS / "job-setup" / "SKILL.md").read_text(encoding="utf-8")

    def test_keeps_job_agent_home(self):
        self.assertIn("never offer to switch to another folder", self.text)

    def test_never_clobbers_progress(self):
        self.assertIn("never replace an existing file with an empty one", self.text)


class LongAnswersAreTyped(unittest.TestCase):
    def test_apply_fill_types_long_values(self):
        text = (SKILLS / "apply-fill" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("100 characters or more", text)
        self.assertIn("never `fill`", text)


class ApplierOwnConnection(unittest.TestCase):
    def test_applier_never_borrows_the_parent_browser(self):
        text = (SKILLS / "job-setup" / "assets" / "job-applier.md").read_text(encoding="utf-8")
        self.assertIn("do not fall back to any other browser server", text)
        run = (SKILLS / "job-run" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("return parked instead of using the orchestrator's", run)


class PageIdsAreChecked(unittest.TestCase):
    def test_apply_fill_rechecks_page_ids_by_url(self):
        text = (SKILLS / "apply-fill" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("Page ids can change under you", text)
        self.assertIn("find your tab by URL", text)
        self.assertIn("Never run `evaluate_script` on a page whose URL you have not confirmed", text)

    def test_job_run_finds_tabs_by_url(self):
        text = (SKILLS / "job-run" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("find it by its URL with `list_pages`", text)


class ExamplePreferences(unittest.TestCase):
    def test_has_schedule_interval(self):
        text = (SKILLS / "job-setup" / "assets" / "preferences.example.yaml").read_text(encoding="utf-8")
        self.assertRegex(text, r"\nschedule:\n  every_hours: 0 ")


if __name__ == "__main__":
    unittest.main()
