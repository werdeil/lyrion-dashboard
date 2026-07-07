"""Tests for get_track_lyrics: returns the stored lyrics text, or None."""

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

from services.database import get_track_lyrics


SAMPLE = "First line\nSecond line\nThird line\n"


class GetTrackLyricsTest(unittest.TestCase):
    def setUp(self):
        # Only borrows a unique path from NamedTemporaryFile: the handle is
        # closed right away and the file removed in tearDown (delete=False).
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)  # pylint: disable=consider-using-with
        self.tmp.close()
        conn = sqlite3.connect(self.tmp.name)
        conn.execute("CREATE TABLE tracks (id TEXT, lyrics TEXT)")
        conn.execute("INSERT INTO tracks VALUES ('has', ?)", (SAMPLE,))
        conn.execute("INSERT INTO tracks VALUES ('empty', NULL)")
        conn.commit()
        conn.close()

        self.app = Flask(__name__)
        self.app.config["DB_PATH"] = self.tmp.name
        self.app.config["DB_PERSIST_PATH"] = self.tmp.name

    def tearDown(self):
        os.unlink(self.tmp.name)

    def test_returns_lyrics_text(self):
        with self.app.app_context():
            self.assertEqual(get_track_lyrics("has"), SAMPLE)

    def test_missing_lyrics(self):
        with self.app.app_context():
            self.assertIsNone(get_track_lyrics("empty"))

    def test_missing_track(self):
        with self.app.app_context():
            self.assertIsNone(get_track_lyrics("nope"))

    def test_none_track_id(self):
        with self.app.app_context():
            self.assertIsNone(get_track_lyrics(None))


if __name__ == "__main__":
    unittest.main()
