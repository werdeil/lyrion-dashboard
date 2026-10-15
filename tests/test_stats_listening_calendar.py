"""Tests for the listening calendar: plays per local day over the last year,
from the Alternative Play Count history."""
# The temp-db + Flask-app scaffolding is intentionally the same as in the
# other database tests; that repetition is what keeps each file standalone.
# pylint: disable=duplicate-code

import os
import sqlite3
import tempfile
import time
from datetime import date, timedelta
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
    CREATE TABLE alternativeplaycount (urlmd5 TEXT, playCount INTEGER, lastPlayed INTEGER,
                                       skipCount INTEGER, lastSkipped INTEGER);
"""
HISTORY_SCHEMA = """
    CREATE TABLE play_history (id INTEGER PRIMARY KEY, url TEXT, urlmd5 TEXT,
                               played INTEGER, client_id TEXT);
"""

DAY = 86400
NOW = int(time.time())
RECENT, MONTHS_AGO, LONG_AGO = NOW - 2 * DAY, NOW - 100 * DAY, NOW - 400 * DAY

TRACKS = [(i, f"u{i}", f"m{i}", 1, 1, None) for i in (1, 2, 3)]
# Track 2 was only skipped: Lyrion bumps its lastplayed, the plugin does not.
PERSISTENT = [
    ("u1", "m1", 2, RECENT, 0),
    ("u2", "m2", 0, RECENT, 0),
    ("u3", "m3", 1, MONTHS_AGO, 0),
]
# m9 is a track no longer in the library.
APC_ROWS = [
    ("m1", 2, RECENT, 0, None),
    ("m2", 0, None, 1, RECENT),
    ("m3", 1, MONTHS_AGO, 0, None),
    ("m9", 4, RECENT, 0, None),
]
# Three plays of one track this month, a stream unknown to the library, older plays.
HISTORY = [RECENT, RECENT - 3600, RECENT - 7200, RECENT, MONTHS_AGO, LONG_AGO]


class ListeningCalendarTest(unittest.TestCase):
    def setUp(self):
        self.library = self._make_db(LIBRARY_SCHEMA)
        self.persist = self._make_db(PERSIST_SCHEMA)
        self.history = self._make_db(HISTORY_SCHEMA)
        conn = sqlite3.connect(self.library)
        conn.executemany("INSERT INTO tracks VALUES (?, ?, ?, ?, ?, ?)", TRACKS)
        conn.execute("INSERT INTO albums VALUES (1, 'ca')")
        conn.commit()
        conn.close()
        conn = sqlite3.connect(self.persist)
        conn.executemany("INSERT INTO tracks_persistent VALUES (?, ?, ?, ?, ?)", PERSISTENT)
        conn.executemany("INSERT INTO alternativeplaycount VALUES (?, ?, ?, ?, ?)", APC_ROWS)
        conn.commit()
        conn.close()
        conn = sqlite3.connect(self.history)
        conn.executemany(
            "INSERT INTO play_history (url, urlmd5, played) VALUES (?, ?, ?)",
            [("u1" if i != 3 else "http://stream", "m1" if i != 3 else "s", played)
             for i, played in enumerate(HISTORY)],
        )
        conn.commit()
        conn.close()

        self.app = Flask(__name__)
        self.app.config["DB_PATH"] = self.library
        self.app.config["DB_PERSIST_PATH"] = self.persist
        self.app.config["APC_HISTORY_PATH"] = self.history

    def tearDown(self):
        for path in (self.library, self.persist, self.history):
            if os.path.exists(path):
                os.unlink(path)

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

    def _calendar(self):
        with self.app.app_context():
            return _compute_stats()["listening_calendar"]

    @staticmethod
    def _day(timestamp):
        return time.strftime("%Y-%m-%d", time.localtime(timestamp))

    def test_counts_plays_per_local_day_over_the_last_year(self):
        calendar = self._calendar()
        self.assertEqual(calendar["today"], date.today().isoformat())
        self.assertEqual(calendar["start"], self._day(LONG_AGO))
        expected = {}
        for played in HISTORY:
            if played >= NOW - 364 * DAY:
                expected[self._day(played)] = expected.get(self._day(played), 0) + 1
        self.assertEqual(calendar["days"], expected)
        self.assertEqual(sum(calendar["days"].values()), 5)

    def test_the_first_calendar_day_is_a_year_back(self):
        oldest = (date.today() - timedelta(days=364)).isoformat()
        self.assertTrue(all(day >= oldest for day in self._calendar()["days"]))

    def test_no_calendar_without_the_history(self):
        os.unlink(self.history)
        self.assertIsNone(self._calendar())

    def test_no_calendar_with_lyrion_counters(self):
        self.app.config["PLAY_COUNTS_SOURCE"] = "lyrion"
        self.assertIsNone(self._calendar())


if __name__ == "__main__":
    unittest.main()
