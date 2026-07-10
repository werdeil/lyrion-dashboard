"""Tests for /lyrics.json's rate limiting wiring.

Every cache miss on this endpoint fans out to third-party lyrics services
from our IP, so the route fuses runaway clients (per-IP limit) and throttles
the cache-bypassing ?refresh=1 (per-track cooldown, degrading to a normal
cached lookup rather than an error).
"""
# The env scaffolding is intentionally the same as in the other tests; that
# repetition is what keeps each file standalone.
# pylint: disable=duplicate-code

import os
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("LYRION_HOST", "http://localhost:9000")
os.environ.setdefault("DB_DIR", tempfile.mkdtemp())
os.environ.setdefault("DB_PERSIST_DIR", tempfile.mkdtemp())

# The config env vars above must be set before anything imports config.py.
# pylint: disable=wrong-import-position
from app import create_app
import routes.nowplaying as R

FOUND = {"lyrics": "la la la", "synced": None, "source": "fake"}


class LyricsRouteTest(unittest.TestCase):
    def setUp(self):
        self.client = create_app().test_client()
        self._reset_fuses()

    def tearDown(self):
        self._reset_fuses()

    @staticmethod
    def _reset_fuses():
        # pylint: disable=protected-access
        R.LYRICS_RATE._hits.clear()
        R.REFRESH_COOLDOWN._last.clear()

    @patch("routes.nowplaying.fetch_lyrics", return_value=FOUND)
    def test_requests_beyond_the_per_ip_limit_get_429(self, mock_fetch):
        for _ in range(R.LYRICS_RATE.limit):
            response = self.client.get("/lyrics.json?artist=Muse&title=Song")
            self.assertEqual(response.status_code, 200)
        response = self.client.get("/lyrics.json?artist=Muse&title=Song")
        self.assertEqual(response.status_code, 429)
        self.assertEqual(mock_fetch.call_count, R.LYRICS_RATE.limit)

    @patch("routes.nowplaying.fetch_lyrics", return_value=FOUND)
    def test_refresh_is_honoured_once_then_degrades_to_cached(self, mock_fetch):
        self.client.get("/lyrics.json?artist=Muse&title=Song&refresh=1")
        self.assertTrue(mock_fetch.call_args.kwargs["force"])
        self.client.get("/lyrics.json?artist=Muse&title=Song&refresh=1")
        self.assertFalse(mock_fetch.call_args.kwargs["force"])

    @patch("routes.nowplaying.fetch_lyrics", return_value=FOUND)
    def test_refresh_cooldown_is_per_track(self, mock_fetch):
        self.client.get("/lyrics.json?artist=Muse&title=Song&refresh=1")
        self.client.get("/lyrics.json?artist=Muse&title=Other&refresh=1")
        self.assertTrue(mock_fetch.call_args.kwargs["force"])


if __name__ == "__main__":
    unittest.main()
