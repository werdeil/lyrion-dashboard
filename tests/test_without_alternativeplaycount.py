"""Tests for a Lyrion without the Alternative Play Count plugin: the stats and
the recent covers must still compute, from Lyrion's own play counters."""
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

from services.database import get_recent_album_covers, _compute_stats  # pylint: disable=protected-access


SCHEMA = """
    CREATE TABLE tracks (id INTEGER, url TEXT, urlmd5 TEXT, audio INTEGER,
                         album INTEGER, lyrics TEXT);
    CREATE TABLE albums (id INTEGER, artwork TEXT);
    CREATE TABLE contributor_track (contributor INTEGER, track INTEGER, role INTEGER);
    CREATE TABLE genres (id INTEGER);
    CREATE TABLE tracks_persistent (url TEXT, urlmd5 TEXT, playcount INTEGER,
                                    lastplayed INTEGER, rating INTEGER);
"""

# Two albums with artwork: album 1 played (last play 500), album 2 never
# played. Track 30 belongs to album 2 and was only skipped, which without the
# plugin is indistinguishable from a play — it has no persistent row here so
# it stays unplayed.
TRACKS = [
    (10, "u10", "m10", 1, 1, None),
    (11, "u11", "m11", 1, 1, "la la"),
    (20, "u20", "m20", 1, 2, None),
    (30, "u30", "m30", 1, 2, None),
]
PERSISTENT = [
    ("u10", "m10", 2, 100, 4),
    ("u11", "m11", 3, 500, 0),
    ("u20", "m20", 0, None, 0),
]


class WithoutAlternativePlayCountTest(unittest.TestCase):
    def setUp(self):
        # Only borrows a unique path from NamedTemporaryFile: the handle is
        # closed right away and the file removed in tearDown (delete=False).
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)  # pylint: disable=consider-using-with
        self.tmp.close()
        conn = sqlite3.connect(self.tmp.name)
        conn.executescript(SCHEMA)
        conn.executemany("INSERT INTO tracks VALUES (?, ?, ?, ?, ?, ?)", TRACKS)
        conn.executemany("INSERT INTO tracks_persistent VALUES (?, ?, ?, ?, ?)", PERSISTENT)
        conn.executemany("INSERT INTO albums VALUES (?, ?)", [(1, "ca"), (2, "cb")])
        conn.executemany("INSERT INTO contributor_track VALUES (?, ?, ?)",
                         [(7, 10, 5), (7, 11, 5), (8, 20, 5), (8, 30, 5), (9, 11, 1)])
        conn.execute("INSERT INTO genres VALUES (1)")
        conn.commit()
        conn.close()

        self.app = Flask(__name__)
        self.app.config["DB_PATH"] = self.tmp.name
        self.app.config["DB_PERSIST_PATH"] = self.tmp.name

    def tearDown(self):
        os.unlink(self.tmp.name)

    def test_stats_fall_back_to_the_lyrion_counters(self):
        with self.app.app_context():
            stats = _compute_stats()
        self.assertFalse(stats["apc_available"])
        self.assertEqual(stats["songs_total"], 4)
        self.assertEqual(stats["songs_played_apc"], 2)
        self.assertEqual(stats["songs_unplayed_apc"], 2)
        self.assertEqual(stats["songs_total_plays_apc"], 5)
        # No skip data exists without the plugin.
        self.assertEqual(stats["songs_total_skips_apc"], 0)
        self.assertEqual(stats["albums_played"], 1)
        self.assertEqual(stats["albums_never"], 1)
        self.assertEqual(stats["artists_played"], 1)
        self.assertEqual(stats["artists_unplayed"], 1)
        self.assertEqual(stats["rated_songs"], 1)
        self.assertEqual(stats["songs_with_lyrics"], 1)

    def test_recent_covers_fall_back_to_the_lyrion_counters(self):
        with self.app.app_context():
            self.assertEqual(get_recent_album_covers(), ["ca"])

    def test_the_plugin_table_wins_when_it_exists(self):
        conn = sqlite3.connect(self.tmp.name)
        conn.executescript("""
            CREATE TABLE alternativeplaycount (
                urlmd5 TEXT, playCount INTEGER, lastPlayed INTEGER,
                skipCount INTEGER, lastSkipped INTEGER);
        """)
        # Album 2's track 30 is a real play here, and skips are counted.
        conn.executemany("INSERT INTO alternativeplaycount VALUES (?, ?, ?, ?, ?)", [
            ("m10", 2, 100, 1, 800),
            ("m30", 1, 900, 0, None),
        ])
        conn.commit()
        conn.close()

        with self.app.app_context():
            stats = _compute_stats()
            covers = get_recent_album_covers()
        self.assertTrue(stats["apc_available"])
        self.assertEqual(stats["songs_played_apc"], 2)
        self.assertEqual(stats["songs_total_plays_apc"], 3)
        self.assertEqual(stats["songs_total_skips_apc"], 1)
        self.assertEqual(covers, ["cb", "ca"])


if __name__ == "__main__":
    unittest.main()
