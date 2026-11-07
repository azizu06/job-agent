"""apply-fill upload guard: gate stamp before upload, DataTransfer script, shown name and size."""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills" / "apply-fill" / "scripts"))

import upload_guard as ug  # noqa: E402


class Guard(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = Path(self.tmp.name).resolve()
        self.pdf = self.d / "Test-Resume.pdf"
        self.pdf.write_bytes(b"%PDF-1.4\n" + b"x" * 86000)

    def tearDown(self):
        self.tmp.cleanup()

    def test_stamp_then_check_then_edit_invalidates(self):
        stamp = self.d / "gate.json"
        res = ug.stamp(self.pdf, stamp, [sys.executable, "-c", "print('VERDICT: PASS')"])
        self.assertEqual(res["verdict"], "PASS")
        self.assertEqual(ug.check(self.pdf, stamp), (True, "gate passed for this exact file"))
        self.pdf.write_bytes(self.pdf.read_bytes() + b"edit")
        ok, why = ug.check(self.pdf, stamp)
        self.assertFalse(ok)
        self.assertIn("changed after the gate", why)

    def test_failed_gate_writes_no_stamp(self):
        stamp = self.d / "gate.json"
        res = ug.stamp(self.pdf, stamp, [sys.executable, "-c", "import sys; sys.exit(1)"])
        self.assertEqual(res["verdict"], "FAIL")
        self.assertFalse(stamp.exists())
        self.assertFalse(ug.check(self.pdf, stamp)[0])

    def test_rejects_relative_and_non_pdf(self):
        with self.assertRaises(ValueError):
            ug.check_pdf(Path("resume.pdf"))
        bad = self.d / "x.pdf"
        bad.write_text("hello")
        with self.assertRaises(ValueError):
            ug.check_pdf(bad)

    def test_verify_shown_name_and_size(self):
        size = self.pdf.stat().st_size
        self.assertTrue(ug.verify(self.pdf, "Test-Resume.pdf", "86 KB")[0])
        self.assertTrue(ug.verify(self.pdf, "Test-Resume.pdf", "84 KB")[0])   # base 1024
        self.assertTrue(ug.verify(self.pdf, "Test-Resume.pdf", str(size))[0])
        ok, problems = ug.verify(self.pdf, "Other.pdf", "12 KB")
        self.assertFalse(ok)
        self.assertEqual(len(problems), 2)

    def test_datatransfer_js(self):
        js = ug.datatransfer_js(self.pdf, "#resume")
        self.assertIn("new DataTransfer()", js)
        self.assertIn('"#resume"', js)
        self.assertIn(f"expected: {self.pdf.stat().st_size}", js)


if __name__ == "__main__":
    unittest.main()
