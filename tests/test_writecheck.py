import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills" / "your-voice" / "scripts"))

import writecheck as wc  # noqa: E402

PLAIN = "I built a billing service in Python that cut invoice errors by 40%. Your team runs the same stack, so I can start on day one."


class CheckTests(unittest.TestCase):
    def test_plain_answer_is_clean(self):
        r = wc.check(PLAIN, max_chars=500)
        self.assertTrue(r["clean"], r["problems"])
        self.assertEqual(r["chars"], len(PLAIN))

    def test_length_and_word_caps(self):
        r = wc.check(PLAIN, max_chars=50, max_words=10)
        kinds = {p.split()[0] for p in r["problems"]}
        self.assertEqual(kinds, {"LENGTH", "WORDS"})

    def test_dashes_flagged_unless_allowed(self):
        text = "I built it — and shipped it – fast."
        self.assertIn("DASH", " ".join(wc.check(text)["problems"]))
        self.assertTrue(wc.check(text, allow_dashes=True)["clean"])

    def test_curly_quotes_invisible_and_odd_spaces(self):
        text = "It’s “done”.​ And more."
        problems = " ".join(wc.check(text)["problems"])
        for kind in ("CURLY", "INVISIBLE", "SPACE"):
            self.assertIn(kind, problems)

    def test_tag_characters_count_as_invisible(self):
        self.assertIn("INVISIBLE", " ".join(wc.check("ok\U000E0041")["problems"]))

    def test_ai_words_meta_and_opener(self):
        text = "I am thrilled to apply. One project that stands out is how I leverage data."
        problems = " ".join(wc.check(text)["problems"])
        for kind in ("AI-WORDS", "META", "OPENER"):
            self.assertIn(kind, problems)

    def test_allowed_word_is_not_flagged(self):
        text = "I made the parser robust to bad input."
        self.assertFalse(wc.check(text)["clean"])
        self.assertTrue(wc.check(text, allow_words=["robust"])["clean"])

    def test_word_match_is_whole_word(self):
        self.assertTrue(wc.check("The fostering program and showcases are not here: fosters.")["problems"])
        self.assertTrue(wc.check("I read Realmente, a novel.")["clean"])


class NormalizeTests(unittest.TestCase):
    def test_normalize_fixes_only_mechanical_things(self):
        text = "It’s “done”.​ And more — yes."
        out = wc.normalize(text)
        self.assertEqual(out, "It's \"done\". And more — yes.")


class StatsTests(unittest.TestCase):
    def test_stats_measures_samples(self):
        samples = [
            "I like building things. So I started a club at school. We made a robot that sorts trash.",
            "I don't write much. But I can't stop fixing my bike, because it breaks every week.",
        ]
        s = wc.stats(samples)
        self.assertEqual(s["samples"], 2)
        self.assertEqual(s["sentences"], 5)
        self.assertGreater(s["contractions_per_100_words"], 0)
        self.assertEqual(s["dashes"], 0)
        openers = dict(s["top_openers"])
        self.assertEqual(openers.get("i"), 2)
        self.assertIn("because", dict(s["connectives"]))


class CliTests(unittest.TestCase):
    def test_check_exit_codes_and_fix_file(self):
        with tempfile.TemporaryDirectory() as d:
            src = Path(d) / "a.txt"
            src.write_text("It’s done.\n", encoding="utf-8")
            fixed = Path(d) / "a.clean.txt"
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = wc.main(["check", str(src), "--fix", str(fixed), "--json"])
            self.assertEqual(rc, 1)
            self.assertFalse(json.loads(buf.getvalue())["clean"])
            self.assertEqual(fixed.read_text(encoding="utf-8"), "It's done.\n")
            self.assertEqual(src.read_text(encoding="utf-8"), "It’s done.\n")
            with redirect_stdout(io.StringIO()):
                self.assertEqual(wc.main(["check", str(fixed)]), 0)

    def test_stats_cli(self):
        with tempfile.TemporaryDirectory() as d:
            src = Path(d) / "s.txt"
            src.write_text("One sentence here. Another one there.", encoding="utf-8")
            buf = io.StringIO()
            with redirect_stdout(buf):
                self.assertEqual(wc.main(["stats", str(src)]), 0)
            self.assertEqual(json.loads(buf.getvalue())["sentences"], 2)


class CrossFormTests(unittest.TestCase):
    def test_repeated_story_is_flagged(self):
        a = "At Example Corp I moved the nightly import to a queue, so one bad file stopped failing the whole batch."
        b = "I care about reliability. At Example Corp I moved the nightly import to a queue, and it held up."
        r = wc.crossform({"why.txt": a, "project.txt": b})
        self.assertFalse(r["clean"])
        self.assertTrue(any("share the words" in p for p in r["problems"]))

    def test_distinct_answers_are_clean_and_company_can_be_allowed(self):
        a = "The posting at Acme asks for queue work. I moved a nightly import to a queue at my last job."
        b = "I saw that Acme also lists on-call. I wrote the runbook for our school club's event check-in app."
        self.assertFalse(wc.crossform({"a": a, "b": b})["clean"])
        self.assertTrue(wc.crossform({"a": a, "b": b}, allow=["Acme"])["clean"])


if __name__ == "__main__":
    unittest.main()
