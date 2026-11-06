import os
import string
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills" / "portal-auth" / "scripts"))

import portal_creds as pc  # noqa: E402


class FakeKeyring:
    def __init__(self):
        self.store = {}

    def set_password(self, service, user, pw):
        self.store[(service, user)] = pw

    def get_password(self, service, user):
        return self.store.get((service, user))


class PortalCredsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = os.environ.get("JOB_AGENT_HOME")
        os.environ["JOB_AGENT_HOME"] = self.tmp.name

    def tearDown(self):
        if self.old is None:
            os.environ.pop("JOB_AGENT_HOME", None)
        else:
            os.environ["JOB_AGENT_HOME"] = self.old
        self.tmp.cleanup()

    def test_normalize_domain(self):
        self.assertEqual(pc.normalize_domain("https://acme.wd5.myworkdayjobs.com/en-US/careers"), "acme.wd5.myworkdayjobs.com")
        self.assertEqual(pc.normalize_domain("www.Example.com"), "example.com")
        with self.assertRaises(ValueError):
            pc.normalize_domain("")

    def test_generated_password_has_every_class(self):
        for _ in range(50):
            pw = pc.generate_password(16)
            self.assertEqual(len(pw), 16)
            self.assertTrue(any(c in string.ascii_lowercase for c in pw))
            self.assertTrue(any(c in string.ascii_uppercase for c in pw))
            self.assertTrue(any(c in string.digits for c in pw))
            self.assertTrue(any(c in pc.SYMBOLS for c in pw))
        self.assertTrue(pc.generate_password(20, symbols=False).isalnum())
        with self.assertRaises(ValueError):
            pc.generate_password(8)

    def test_store_and_lookup_keep_password_out_of_index(self):
        kr = FakeKeyring()
        pc.store("acme.example.com", "user@example.com", "S3cret-Value-123", kr=kr)
        self.assertEqual(pc.lookup("acme.example.com", kr=kr), ("user@example.com", "S3cret-Value-123"))
        index_text = pc.index_path().read_text()
        self.assertIn("user@example.com", index_text)
        self.assertNotIn("S3cret-Value-123", index_text)
        self.assertIsNone(pc.lookup("other.example.com", kr=kr))


if __name__ == "__main__":
    unittest.main()
