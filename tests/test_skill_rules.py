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


if __name__ == "__main__":
    unittest.main()
