"""Verify Codex discovers the canonical skills with their resources intact."""

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class CodexDiscovery(unittest.TestCase):
    def test_every_skill_has_a_relative_discovery_link(self):
        canonical = ROOT / "skills"
        discovery = ROOT / ".agents" / "skills"
        expected = {p.parent.name for p in canonical.glob("*/SKILL.md")}
        self.assertEqual(len(expected), 10)
        self.assertEqual({p.name for p in discovery.iterdir()}, expected)
        for name in sorted(expected):
            with self.subTest(skill=name):
                link = discovery / name
                self.assertTrue(link.is_symlink())
                self.assertFalse(link.readlink().is_absolute())
                self.assertEqual(link.resolve(strict=True), canonical / name)
                self.assertEqual((link / "SKILL.md").read_bytes(),
                                 (canonical / name / "SKILL.md").read_bytes())

    def test_discovered_skills_retain_all_bundled_resources(self):
        canonical = ROOT / "skills"
        discovery = ROOT / ".agents" / "skills"
        for source in canonical.rglob("*"):
            if source.is_file() and "__pycache__" not in source.parts:
                with self.subTest(resource=source.relative_to(canonical)):
                    exposed = discovery / source.relative_to(canonical)
                    self.assertEqual(exposed.resolve(strict=True), source)

    def test_sibling_script_paths_work_from_discovered_skills(self):
        skill = ROOT / ".agents" / "skills" / "job-run"
        for sibling, script in (("tracker", "tracker_csv.py"),
                                ("job-gate", "apply_queue.py"),
                                ("tailor-resume", "resume_gate.py")):
            with self.subTest(skill=sibling):
                path = skill / ".." / sibling / "scripts" / script
                self.assertEqual(path.resolve(strict=True),
                                 ROOT / "skills" / sibling / "scripts" / script)


if __name__ == "__main__":
    unittest.main()
