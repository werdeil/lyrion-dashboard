"""Tests for get_random_cover_ids: random album artwork ids for the mosaic."""
# The temp-db + Flask-app scaffolding is intentionally the same as in the
# other database tests; that repetition is what keeps each file standalone.
# pylint: disable=duplicate-code

import os
import sqlite3
import tempfile
import unittest

os.environ.setdefault("LYRION_HOST", "http://localhost:9000")
os.environ.setdefault("DB_DIR", tempfile.mkdtemp())
os.environ.setdefault("DB_PERSIST_DIR", tempfile.mkdtemp())

# The config env vars above must be set before anything imports config.py.
# pylint: disable=wrong-import-position
from flask import Flask

from services.database import get_random_cover_ids


class GetRandomCoverIdsTest(unittest.TestCase):
    def setUp(self):
        # Only borrows a unique path from NamedTemporaryFile: the handle is
        # closed right away and the file removed in tearDown (delete=False).
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)  # pylint: disable=consider-using-with
        self.tmp.close()
        conn = sqlite3.connect(self.tmp.name)
        conn.execute("CREATE TABLE albums (id INTEGER, artwork TEXT)")
        # 5 albums with artwork (one duplicated coverid), 2 without.
        rows = [
            (1, "aaa"), (2, "bbb"), (3, "ccc"), (4, "ddd"), (5, "aaa"),
            (6, None), (7, None),
        ]
        conn.executemany("INSERT INTO albums VALUES (?, ?)", rows)
        conn.commit()
        conn.close()

        self.app = Flask(__name__)
        self.app.config["DB_PATH"] = self.tmp.name
        self.app.config["DB_PERSIST_PATH"] = self.tmp.name

    def tearDown(self):
        os.unlink(self.tmp.name)

    def test_returns_distinct_artwork_ids(self):
        with self.app.app_context():
            ids = get_random_cover_ids()
        self.assertCountEqual(ids, ["aaa", "bbb", "ccc", "ddd"])

    def test_respects_limit(self):
        with self.app.app_context():
            ids = get_random_cover_ids(limit=2)
        self.assertEqual(len(ids), 2)
        self.assertTrue(set(ids) <= {"aaa", "bbb", "ccc", "ddd"})

    def test_empty_library(self):
        conn = sqlite3.connect(self.tmp.name)
        conn.execute("DELETE FROM albums")
        conn.commit()
        conn.close()
        with self.app.app_context():
            self.assertEqual(get_random_cover_ids(), [])


if __name__ == "__main__":
    unittest.main()
