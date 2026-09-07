"""Tests for the play-depth buckets: how the played tracks split between one
play, a few and many."""
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

from services.database import _compute_stats  # pylint: disable=protected-access


LIBRARY_SCHEMA = """
    CREATE TABLE tracks (id INTEGER, url TEXT, urlmd5 TEXT, audio INTEGER,
                         album INTEGER, lyrics TEXT);
    CREATE TABLE albums (id INTEGER, artwork TEXT);
    CREATE TABLE contributor_track (contributor INTEGER, track INTEGER, role INTEGER);
    CREATE TABLE genres (id INTEGER);
"""
PERSIST_SCHEMA = """
    CREATE TABLE tracks_persistent (url TEXT, urlmd5 TEXT, playcount INTEGER,
                                    lastplayed INTEGER, rating INTEGER);
"""

# One track per bucket boundary: unplayed, once, the edges of 2-4, and beyond.
PLAYCOUNTS = [0, 1, 2, 4, 5, 40]


class PlayDepthTest(unittest.TestCase):
    def setUp(self):
        self.library = self._make_db(LIBRARY_SCHEMA)
        self.persist = self._make_db(PERSIST_SCHEMA)
        conn = sqlite3.connect(self.library)
        conn.executemany(
            "INSERT INTO tracks VALUES (?, ?, ?, 1, 1, NULL)",
            [(i, f"u{i}", f"m{i}") for i in range(len(PLAYCOUNTS))],
        )
        conn.execute("INSERT INTO albums VALUES (1, 'ca')")
        conn.commit()
        conn.close()
        conn = sqlite3.connect(self.persist)
        conn.executemany(
            "INSERT INTO tracks_persistent VALUES (?, ?, ?, 100, 0)",
            [(f"u{i}", f"m{i}", count) for i, count in enumerate(PLAYCOUNTS)],
        )
        conn.commit()
        conn.close()

        self.app = Flask(__name__)
        self.app.config["DB_PATH"] = self.library
        self.app.config["DB_PERSIST_PATH"] = self.persist
        with self.app.app_context():
            self.stats = _compute_stats()

    def tearDown(self):
        os.unlink(self.library)
        os.unlink(self.persist)

    @staticmethod
    def _make_db(schema):
        # Only borrows a unique path from NamedTemporaryFile: the handle is
        # closed right away and the file removed in tearDown (delete=False).
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)  # pylint: disable=consider-using-with
        tmp.close()
        conn = sqlite3.connect(tmp.name)
        conn.executescript(schema)
        conn.commit()
        conn.close()
        return tmp.name

    def test_each_bucket_holds_its_own_range(self):
        self.assertEqual(self.stats["songs_played_once"], 1)
        self.assertEqual(self.stats["songs_played_2_4"], 2)
        self.assertEqual(self.stats["songs_played_5_plus"], 2)

    def test_the_buckets_partition_the_played_tracks(self):
        buckets = sum(self.stats[k] for k in
                      ("songs_played_once", "songs_played_2_4", "songs_played_5_plus"))
        self.assertEqual(buckets, self.stats["songs_played_apc"])
        self.assertEqual(buckets + self.stats["songs_unplayed_apc"], self.stats["songs_total"])

    def test_percentages_are_shares_of_the_whole_library(self):
        self.assertEqual(self.stats["songs_played_once_pct"], round(100 / 6, 1))
        self.assertEqual(self.stats["songs_played_2_4_pct"], round(200 / 6, 1))
        self.assertEqual(self.stats["songs_played_5_plus_pct"], round(200 / 6, 1))


if __name__ == "__main__":
    unittest.main()
