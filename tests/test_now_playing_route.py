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
    "players": [{"id": "p1", "name": "Salon"}, {"id": "p2", "name": "Cuisine"}],
    "selection_active": False,
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


@patch("routes.nowplaying.get_track_lyrics", return_value="la la la")
@patch("routes.nowplaying.get_active_now_playing", return_value=dict(NOW))
class NowPlayingPlayerParamTest(unittest.TestCase):
    """?player= pins one player when several are playing; the response carries
    the list of playing players for the page's switcher."""

    def setUp(self):
        self.client = create_app().test_client()

    def test_player_param_is_forwarded(self, mock_now, _lyrics):
        self.client.get("/now-playing.json", query_string={"player": "aa:bb:cc"})
        mock_now.assert_called_with(selected_id="aa:bb:cc")

    def test_no_player_param_selects_automatically(self, mock_now, _lyrics):
        self.client.get("/now-playing.json")
        mock_now.assert_called_with(selected_id=None)

    def test_malformed_player_is_ignored(self, mock_now, _lyrics):
        # A space isn't a valid player-id char, so the pick is dropped.
        self.client.get("/now-playing.json", query_string={"player": "aa bb"})
        mock_now.assert_called_with(selected_id=None)

    def test_response_exposes_the_playing_players(self, _now, _lyrics):
        data = self.client.get("/now-playing.json").get_json()
        self.assertEqual([p["id"] for p in data["players"]], ["p1", "p2"])
        self.assertIn("selection_active", data)


if __name__ == "__main__":
    unittest.main()
