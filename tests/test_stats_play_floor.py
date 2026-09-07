"""Tests for the play floor: the number of plays every track in the library
has reached, and the count of tracks that went one round further."""
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

TRACKS = [
    (10, "u10", "m10", 1, 1, None),
    (11, "u11", "m11", 1, 1, None),
    (12, "u12", "m12", 1, 1, None),
    (13, "u13", "m13", 1, 1, None),
]


class PlayFloorTest(unittest.TestCase):
    def setUp(self):
        self.library = self._make_db(LIBRARY_SCHEMA)
        self.persist = self._make_db(PERSIST_SCHEMA)
        conn = sqlite3.connect(self.library)
        conn.executemany("INSERT INTO tracks VALUES (?, ?, ?, ?, ?, ?)", TRACKS)
        conn.execute("INSERT INTO albums VALUES (1, 'ca')")
        conn.commit()
        conn.close()

        self.app = Flask(__name__)
        self.app.config["DB_PATH"] = self.library
        self.app.config["DB_PERSIST_PATH"] = self.persist

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

    def _stats(self, playcounts):
        conn = sqlite3.connect(self.persist)
        conn.executemany(
            "INSERT INTO tracks_persistent VALUES (?, ?, ?, ?, ?)",
            [(f"u{tid}", f"m{tid}", count, 100, 0) for tid, count in playcounts],
        )
        conn.commit()
        conn.close()
        with self.app.app_context():
            return _compute_stats()

    def test_an_unplayed_track_keeps_the_floor_at_zero(self):
        stats = self._stats([(10, 3), (11, 2), (12, 1), (13, 0)])
        self.assertEqual(stats["songs_play_floor"], 0)
        self.assertEqual(stats["songs_above_floor"], 3)
        self.assertEqual(stats["songs_above_floor_pct"], 75.0)

    def test_a_track_missing_from_the_play_counts_counts_as_unplayed(self):
        stats = self._stats([(10, 3), (11, 2), (12, 1)])
        self.assertEqual(stats["songs_play_floor"], 0)
        self.assertEqual(stats["songs_above_floor"], 3)

    def test_the_floor_is_the_least_played_track(self):
        stats = self._stats([(10, 5), (11, 4), (12, 3), (13, 3)])
        self.assertEqual(stats["songs_play_floor"], 3)
        self.assertEqual(stats["songs_above_floor"], 2)
        self.assertEqual(stats["songs_above_floor_pct"], 50.0)

    def test_a_library_played_evenly_has_nothing_above_the_floor(self):
        stats = self._stats([(10, 2), (11, 2), (12, 2), (13, 2)])
        self.assertEqual(stats["songs_play_floor"], 2)
        self.assertEqual(stats["songs_above_floor"], 0)
        self.assertEqual(stats["songs_above_floor_pct"], 0)


if __name__ == "__main__":
    unittest.main()
