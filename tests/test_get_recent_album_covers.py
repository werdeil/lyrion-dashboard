"""Tests for get_recent_album_covers: recently played album covers, deduped."""
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
        conn.executescript("""
            CREATE TABLE tracks (id INTEGER, url TEXT, audio INTEGER, album INTEGER);
            CREATE TABLE albums (id INTEGER, artwork TEXT);
            CREATE TABLE tracks_persistent (url TEXT, lastplayed INTEGER);
        """)
        # 3 albums with covers; album 4 has no artwork.
        conn.executemany("INSERT INTO albums VALUES (?, ?)",
                         [(1, "ca"), (2, "cb"), (3, "cc"), (4, None)])
        # Tracks: album 1 has two tracks, album 2/3/4 one each.
        conn.executemany("INSERT INTO tracks VALUES (?, ?, 1, ?)", [
            (10, "file:///a1.flac", 1),
            (11, "file:///a2.flac", 1),
            (20, "file:///b.flac", 2),
            (30, "file:///c.flac", 3),
            (40, "file:///d.flac", 4),
        ])
        # Play history: album 1's two tracks played at 100 and 500 (album 1's
        # latest = 500). Album 2 at 400, album 3 at 300. Album 4 at 900 (newest)
        # but has no artwork, so it must be excluded.
        conn.executemany("INSERT INTO tracks_persistent VALUES (?, ?)", [
            ("file:///a1.flac", 100),
            ("file:///a2.flac", 500),
            ("file:///b.flac", 400),
            ("file:///c.flac", 300),
            ("file:///d.flac", 900),
        ])
        conn.commit()
        conn.close()

        self.app = Flask(__name__)
        self.app.config["DB_PATH"] = self.tmp.name
        self.app.config["DB_PERSIST_PATH"] = self.tmp.name

    def tearDown(self):
        os.unlink(self.tmp.name)

    def test_newest_first_deduped_by_album(self):
        with self.app.app_context():
            covers = get_recent_album_covers()
        # Album 1 (latest play 500) > album 2 (400) > album 3 (300); album 1
        # appears once despite two played tracks; album 4 excluded (no artwork).
        self.assertEqual(covers, ["ca", "cb", "cc"])

    def test_limit(self):
        with self.app.app_context():
            covers = get_recent_album_covers(limit=2)
        self.assertEqual(covers, ["ca", "cb"])

    def test_no_history(self):
        conn = sqlite3.connect(self.tmp.name)
        conn.execute("DELETE FROM tracks_persistent")
        conn.commit()
        conn.close()
        with self.app.app_context():
            self.assertEqual(get_recent_album_covers(), [])


if __name__ == "__main__":
    unittest.main()
