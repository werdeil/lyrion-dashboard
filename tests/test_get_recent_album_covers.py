"""Tests for get_recent_album_covers: recently played album covers, deduped,
ranked by real plays (Alternative Play Count) and ignoring skips."""
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

from services.database import get_recent_album_covers


class GetRecentAlbumCoversTest(unittest.TestCase):
    def setUp(self):
        # Only borrows a unique path from NamedTemporaryFile: the handle is
        # closed right away and the file removed in tearDown (delete=False).
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)  # pylint: disable=consider-using-with
        self.tmp.close()
        conn = sqlite3.connect(self.tmp.name)
        # Mixed-case APC columns like the real plugin, to confirm the query's
        # lowercase references still match (SQLite is case-insensitive).
        conn.executescript("""
            CREATE TABLE tracks (id INTEGER, urlmd5 TEXT, audio INTEGER, album INTEGER);
            CREATE TABLE albums (id INTEGER, artwork TEXT);
            CREATE TABLE alternativeplaycount (
                urlmd5 TEXT, playCount INTEGER, lastPlayed INTEGER,
                skipCount INTEGER, lastSkipped INTEGER);
        """)
        conn.executemany("INSERT INTO albums VALUES (?, ?)",
                         [(1, "ca"), (2, "cb"), (3, "cc"), (4, "cd"), (5, None)])
        # Album 1: two played tracks (latest play 500). Album 2 played (400),
        # album 3 played (300). Album 4: only skipped (playcount 0) but skipped
        # very recently — must be excluded. Album 5: played but no artwork.
        conn.executemany("INSERT INTO tracks VALUES (?, ?, 1, ?)", [
            (10, "m1a", 1),
            (11, "m1b", 1),
            (20, "m2", 2),
            (30, "m3", 3),
            (40, "m4", 4),
            (50, "m5", 5),
        ])
        conn.executemany(
            "INSERT INTO alternativeplaycount VALUES (?, ?, ?, ?, ?)", [
                ("m1a", 1, 100, 0, None),   # album 1, played at 100
                ("m1b", 2, 500, 1, 700),    # album 1, played at 500 (also skipped later)
                ("m2", 3, 400, 0, None),    # album 2, played at 400
                ("m3", 1, 300, 0, None),    # album 3, played at 300
                ("m4", 0, None, 5, 900),    # album 4, only skipped (newest touch)
                ("m5", 4, 600, 0, None),    # album 5, played but no artwork
            ])
        conn.commit()
        conn.close()

        self.app = Flask(__name__)
        self.app.config["DB_PATH"] = self.tmp.name
        self.app.config["DB_PERSIST_PATH"] = self.tmp.name

    def tearDown(self):
        os.unlink(self.tmp.name)

    def test_ranks_by_real_play_dedupes_and_ignores_skips(self):
        with self.app.app_context():
            covers = get_recent_album_covers()
        # Album 1 (last real play 500) > album 2 (400) > album 3 (300); album 1
        # appears once despite two tracks, and its later skip at 700 does not
        # promote it further. Album 4 (skip-only) and album 5 (no artwork) are
        # both excluded.
        self.assertEqual(covers, ["ca", "cb", "cc"])

    def test_limit(self):
        with self.app.app_context():
            covers = get_recent_album_covers(limit=2)
        self.assertEqual(covers, ["ca", "cb"])

    def test_no_plays(self):
        conn = sqlite3.connect(self.tmp.name)
        conn.execute("UPDATE alternativeplaycount SET playCount = 0, lastPlayed = NULL")
        conn.commit()
        conn.close()
        with self.app.app_context():
            self.assertEqual(get_recent_album_covers(), [])


if __name__ == "__main__":
    unittest.main()
