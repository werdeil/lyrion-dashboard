"""Tests for /now-playing.json's ?known= contract.

The page passes the track key it already displays; the route must skip the
lyrics lookup (and omit the field) while the playing track matches, and keep
including lyrics for new tracks and for clients that don't send the key.
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

NOW = {
    "playing": True, "mode": "play", "time": 10.0, "duration": 200,
    "track_id": 42, "title": "Song", "artist": "Muse", "album": "Album",
    "year": 2001, "coverid": "abc", "artwork_url": None,
    "player_name": "Salon", "player_id": "p1",
}
# The exact key the page builds: [track_id, title, artist, album].join('|').
KEY = "42|Song|Muse|Album"


@patch("routes.nowplaying.get_track_lyrics", return_value="la la la")
@patch("routes.nowplaying.get_active_now_playing", return_value=dict(NOW))
class NowPlayingKnownTest(unittest.TestCase):
    def setUp(self):
        self.client = create_app().test_client()

    def test_no_known_includes_lyrics(self, _now, mock_lyrics):
        data = self.client.get("/now-playing.json").get_json()
        self.assertEqual(data["lyrics"], "la la la")
        mock_lyrics.assert_called_once_with(42)

    def test_matching_known_skips_the_lookup_and_the_field(self, _now, mock_lyrics):
        data = self.client.get(
            "/now-playing.json", query_string={"known": KEY}
        ).get_json()
        self.assertNotIn("lyrics", data)
        mock_lyrics.assert_not_called()

    def test_stale_known_includes_lyrics(self, _now, mock_lyrics):
        data = self.client.get(
            "/now-playing.json", query_string={"known": "41|Old|Song|Album"}
        ).get_json()
        self.assertEqual(data["lyrics"], "la la la")
        mock_lyrics.assert_called_once()


if __name__ == "__main__":
    unittest.main()
