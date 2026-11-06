import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "tailor-resume" / "scripts" / "keyword_coverage.py"
sys.path.insert(0, str(SCRIPT.parent))

import keyword_coverage as kc  # noqa: E402

JD = """We are hiring a Backend Engineer. You will build REST APIs in Python and
Go, deploy on AWS with Docker and Kubernetes, and keep CI/CD green.
Nice to have: PyTorch, GraphQL, PostgreSQL. EEO employer. US only."""


class NormalizeTests(unittest.TestCase):
    def test_strips_latex_and_lowercases(self):
        text = r"\resumeItem{Built a \textbf{Kubernetes} operator in C\# % hidden"
        norm = kc.normalize(text)
        self.assertIn("kubernetes", norm)
        self.assertIn("c#", norm)
        self.assertNotIn("hidden", norm)
        self.assertNotIn("textbf", norm)


class MatchingTests(unittest.TestCase):
    def test_alias_counts(self):
        term = kc.Term("kubernetes", ("k8s",))
        self.assertTrue(kc.has_term(kc.normalize("Ran services on k8s"), term))

    def test_word_boundary(self):
        self.assertFalse(kc.has_term(kc.normalize("JavaScript only"), kc.Term("java")))
        self.assertTrue(kc.has_term(kc.normalize("Java, Spring"), kc.Term("java")))

    def test_symbols_in_terms(self):
        self.assertTrue(kc.has_term(kc.normalize("Wrote C++ and C#"), kc.Term("c++")))
        self.assertTrue(kc.has_term(kc.normalize("Wrote C++ and C#"), kc.Term("c#")))
        self.assertFalse(kc.has_term(kc.normalize("Wrote C"), kc.Term("c++")))

    def test_multiword_spans_whitespace(self):
        text = kc.normalize("distributed\n   systems at scale")
        self.assertTrue(kc.has_term(text, kc.Term("distributed systems")))


class ExtractionTests(unittest.TestCase):
    def test_finds_vocab_and_tool_words(self):
        names = {t.name for t in kc.extract_terms(JD)}
        for expected in ("python", "aws", "docker", "kubernetes", "ci/cd", "rest api", "pytorch", "graphql", "postgresql"):
            self.assertIn(expected, names)

    def test_skips_noise_acronyms(self):
        names = {t.name.upper() for t in kc.extract_terms(JD)}
        self.assertNotIn("EEO", names)
        self.assertNotIn("US", names)

    def test_no_duplicate_of_vocab_via_acronym(self):
        names = [t.name.lower() for t in kc.extract_terms(JD)]
        self.assertEqual(names.count("aws"), 1)


class LiveJdNoiseTests(unittest.TestCase):
    """Noise seen on a real Greenhouse posting during the 2026-11 dry run."""

    LIVE = """Raft (https://TeamRaft.com) is hiring. Onsite at Raft HQ in McLean, VA.
    Apply at job-boards.greenhouse.io. Work in RaftLabs with Linux, Git and Bash.
    Send your CV. VEVRAA federal contractor. AI/ML and IT infrastructure."""

    def test_drops_urls_states_boilerplate_and_surnames(self):
        names = {t.name for t in kc.extract_terms(self.LIVE)}
        for noise in ("greenhouse.io", "VA", "HQ", "CV", "VEVRAA", "McLean"):
            self.assertNotIn(noise, names)
        for real in ("linux", "git", "bash", "AI", "IT"):
            self.assertIn(real, names)

    def test_requisition_ids_are_not_terms(self):
        names = {t.name for t in kc.extract_terms("Requisition GH-1001 (also WD-2002, JR0286834). Uses AWS and S3.")}
        for noise in ("GH", "WD", "JR0286834"):
            self.assertNotIn(noise, names)
        self.assertIn("aws", names)
        self.assertIn("S3", names)

    def test_company_flag_drops_company_words(self):
        names = {t.name for t in kc.extract_terms(self.LIVE, company="Raft")}
        self.assertNotIn("TeamRaft", names)
        self.assertNotIn("RaftLabs", names)
        self.assertIn("linux", names)

    def test_shape_acronyms_match_case_sensitively(self):
        terms = [t for t in kc.extract_terms(self.LIVE) if t.name in ("IT", "AI")]
        self.assertEqual(len(terms), 2)
        self.assertEqual(kc.coverage("I shipped it and kept it fast", terms)["matched"], [])
        self.assertEqual(sorted(kc.coverage("Ran IT support and AI evals", terms)["matched"]), ["AI", "IT"])

    def test_vocab_terms_stay_case_insensitive(self):
        terms = kc.extract_terms("Experience with AWS and SQL")
        self.assertEqual(kc.coverage("aws lambda, sql", terms)["percent"], 100.0)


class CoverageTests(unittest.TestCase):
    def setUp(self):
        self.terms = [kc.Term("python"), kc.Term("aws"), kc.Term("kubernetes", ("k8s",)), kc.Term("graphql")]

    def test_counts_and_percent(self):
        result = kc.coverage("Python services on AWS", self.terms)
        self.assertEqual(result["matched"], ["python", "aws"])
        self.assertEqual(result["missing"], ["kubernetes", "graphql"])
        self.assertEqual(result["percent"], 50.0)

    def test_compare_reports_delta(self):
        report = kc.compare("Python on AWS", "Python on AWS and k8s", self.terms)
        self.assertEqual(report["newly_matched"], ["kubernetes"])
        self.assertEqual(report["lost"], [])
        self.assertEqual(report["after"]["missing"], ["graphql"])

    def test_empty_terms(self):
        self.assertEqual(kc.coverage("anything", [])["percent"], 0.0)

    def test_terms_file(self):
        terms = kc.parse_terms_file("# comment\nKubernetes | k8s\n\nGo | golang\n")
        self.assertEqual(terms, [kc.Term("Kubernetes", ("k8s",)), kc.Term("Go", ("golang",))])


class CliTests(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True)

    def test_json_before_after_and_min(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / "jd.txt").write_text(JD)
            (d / "master.md").write_text("Python and Docker")
            (d / "new.md").write_text("Python, Docker, Kubernetes, AWS, REST APIs, CI/CD")
            out = self.run_cli("--jd", str(d / "jd.txt"), "--resume", str(d / "new.md"), "--before", str(d / "master.md"), "--json")
            self.assertEqual(out.returncode, 0, out.stderr)
            data = json.loads(out.stdout)
            self.assertIn("kubernetes", data["newly_matched"])
            self.assertGreater(data["after"]["percent"], data["before"]["percent"])
            strict = self.run_cli("--jd", str(d / "jd.txt"), "--resume", str(d / "master.md"), "--min", "90")
            self.assertEqual(strict.returncode, 1)
            self.assertIn("Missing:", strict.stdout)


if __name__ == "__main__":
    unittest.main()
