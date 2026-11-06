import datetime as dt
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills" / "portal-auth" / "scripts"))

import sms_code as sc  # noqa: E402

NOW = dt.datetime(2026, 3, 1, 12, 0, tzinfo=dt.timezone.utc)


def make_db(path, messages):
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE handle (ROWID INTEGER PRIMARY KEY, id TEXT)")
    con.execute("CREATE TABLE message (ROWID INTEGER PRIMARY KEY, date INTEGER, text TEXT, attributedBody BLOB, handle_id INTEGER, is_from_me INTEGER)")
    con.execute("INSERT INTO handle VALUES (1, '+10000000000'), (2, '12345')")
    for minutes_ago, text, body, handle, from_me in messages:
        date = sc.dt_to_apple_ns(NOW - dt.timedelta(minutes=minutes_ago))
        con.execute("INSERT INTO message (date, text, attributedBody, handle_id, is_from_me) VALUES (?,?,?,?,?)",
                    (date, text, body, handle, from_me))
    con.commit()
    con.close()


class SmsCodeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "chat.db"

    def tearDown(self):
        self.tmp.cleanup()

    def test_extract_code_needs_a_hint(self):
        self.assertEqual(sc.extract_code("Your Acme verification code is 482913"), "482913")
        self.assertEqual(sc.extract_code("Use code 123-456 to sign in"), "123456")
        self.assertIsNone(sc.extract_code("Lunch at 1230?"))

    def test_newest_recent_incoming_code_wins(self):
        make_db(self.db, [
            (10, "Your code is 111111", None, 1, 0),      # too old
            (3, "Your code is 222222", None, 2, 0),
            (1, "Your code is 333333", None, 1, 1),       # sent by me
            (2, "Acme verification code: 444444", None, 1, 0),
        ])
        found = sc.find_code(self.db, 5, None, now=NOW)
        self.assertEqual(found["code"], "444444")
        self.assertEqual(sc.find_code(self.db, 5, "12345", now=NOW)["code"], "222222")

    def test_attributed_body_fallback(self):
        body = b"streamtyped\x81NSString\x01+\x1aYour security code is 778899"
        make_db(self.db, [(1, None, body, 2, 0)])
        self.assertEqual(sc.find_code(self.db, 5, None, now=NOW)["code"], "778899")

    def test_nothing_found(self):
        make_db(self.db, [(1, "hello", None, 1, 0)])
        self.assertIsNone(sc.find_code(self.db, 5, None, now=NOW))


if __name__ == "__main__":
    unittest.main()
