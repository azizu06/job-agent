import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills" / "tailor-resume" / "scripts"))

import resume_gate  # noqa: E402


class GateReceipt(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.pdf = self.dir / "Jordan-Lee-Resume.pdf"
        self.pdf.write_bytes(b"%PDF-1.4\n% gated\n")
        self.src = self.dir / "copy.tex"
        self.src.write_text("x", encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def test_no_receipt_fails(self):
        ok, msg = resume_gate.verify(self.pdf)
        self.assertFalse(ok)
        self.assertIn("no gate receipt", msg)

    def test_receipt_passes_until_the_pdf_changes(self):
        resume_gate.write_receipt(self.pdf, self.src, [])
        self.assertTrue(resume_gate.verify(self.pdf)[0])
        self.assertEqual(resume_gate.main(["--verify", str(self.pdf)]), 0)
        self.pdf.write_bytes(b"%PDF-1.4\n% rebuilt after the gate\n")
        ok, msg = resume_gate.verify(self.pdf)
        self.assertFalse(ok)
        self.assertIn("changed after the gate", msg)
        self.assertEqual(resume_gate.main(["--verify", str(self.pdf)]), 1)

    def test_missing_inputs_exit_2(self):
        self.assertEqual(resume_gate.main(["--pdf", str(self.dir / "nope.pdf"), "--resume", str(self.src),
                                           "--master", str(self.src)]), 2)


if __name__ == "__main__":
    unittest.main()
