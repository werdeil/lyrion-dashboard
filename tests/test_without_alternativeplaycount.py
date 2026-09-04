"""Tests for play counts read from Lyrion's own counters instead of the
Alternative Play Count plugin — because the plugin is absent, or because
PLAY_COUNTS_SOURCE=lyrion asks for it. The plugin's table is looked for in
both databases, since it lives in persist.db on a real install."""
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
APC_SCHEMA = """
    CREATE TABLE alternativeplaycount (urlmd5 TEXT, playCount INTEGER, lastPlayed INTEGER,
                                       skipCount INTEGER, lastSkipped INTEGER);
"""

# Album 1 played (last play 500), album 2 not played and its track 30 unknown
# to Lyrion's counters — the plugin, below, has it as a play.
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
APC_ROWS = [
    ("m10", 2, 100, 1, 800),
    ("m30", 1, 900, 0, None),
]


class WithoutAlternativePlayCountTest(unittest.TestCase):
    def setUp(self):
        self.library = self._make_db(LIBRARY_SCHEMA)
        self.persist = self._make_db(PERSIST_SCHEMA)
        conn = sqlite3.connect(self.library)
        conn.executemany("INSERT INTO tracks VALUES (?, ?, ?, ?, ?, ?)", TRACKS)
        conn.executemany("INSERT INTO albums VALUES (?, ?)", [(1, "ca"), (2, "cb")])
        conn.executemany("INSERT INTO contributor_track VALUES (?, ?, ?)",
                         [(7, 10, 5), (7, 11, 5), (8, 20, 5), (8, 30, 5), (9, 11, 1)])
        conn.execute("INSERT INTO genres VALUES (1)")
        conn.commit()
        conn.close()
        conn = sqlite3.connect(self.persist)
        conn.executemany("INSERT INTO tracks_persistent VALUES (?, ?, ?, ?, ?)", PERSISTENT)
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

    def _install_plugin_table(self, path):
        conn = sqlite3.connect(path)
        conn.executescript(APC_SCHEMA)
        conn.executemany("INSERT INTO alternativeplaycount VALUES (?, ?, ?, ?, ?)", APC_ROWS)
        conn.commit()
        conn.close()

    def _stats_and_covers(self):
        with self.app.app_context():
            return _compute_stats(), get_recent_album_covers()

    def assert_reads_the_plugin(self):
        stats, covers = self._stats_and_covers()
        self.assertTrue(stats["apc_available"])
        self.assertEqual(stats["songs_played_apc"], 2)
        self.assertEqual(stats["songs_total_plays_apc"], 3)
        self.assertEqual(stats["songs_total_skips_apc"], 1)
        self.assertEqual(covers, ["cb", "ca"])

    def assert_reads_the_lyrion_counters(self):
        stats, covers = self._stats_and_covers()
        self.assertFalse(stats["apc_available"])
        self.assertEqual(stats["songs_played_apc"], 2)
        self.assertEqual(stats["songs_total_plays_apc"], 5)
        self.assertEqual(stats["songs_total_skips_apc"], 0)
        self.assertEqual(covers, ["ca"])

    def test_stats_fall_back_to_the_lyrion_counters(self):
        with self.app.app_context():
            stats = _compute_stats()
        self.assertFalse(stats["apc_available"])
        self.assertEqual(stats["songs_total"], 4)
        self.assertEqual(stats["songs_unplayed_apc"], 2)
        self.assertEqual(stats["albums_played"], 1)
        self.assertEqual(stats["albums_never"], 1)
        self.assertEqual(stats["artists_played"], 1)
        self.assertEqual(stats["artists_unplayed"], 1)
        self.assertEqual(stats["rated_songs"], 1)
        self.assertEqual(stats["songs_with_lyrics"], 1)

    def test_recent_covers_fall_back_to_the_lyrion_counters(self):
        self.assert_reads_the_lyrion_counters()

    def test_the_plugin_table_wins_from_persist_db(self):
        self._install_plugin_table(self.persist)
        self.assert_reads_the_plugin()

    def test_the_plugin_table_wins_from_library_db(self):
        self._install_plugin_table(self.library)
        self.assert_reads_the_plugin()

    def test_play_counts_source_lyrion_ignores_an_installed_plugin(self):
        self._install_plugin_table(self.persist)
        self.app.config["PLAY_COUNTS_SOURCE"] = "lyrion"
        self.assert_reads_the_lyrion_counters()


if __name__ == "__main__":
    unittest.main()
