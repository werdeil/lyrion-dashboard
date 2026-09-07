"""Tests for the dashboard's play-floor stat row, which is the only one whose
label and presence are computed rather than fixed."""
# The env + client scaffolding is intentionally the same as in the other route
# tests; that repetition is what keeps each file standalone.
# pylint: disable=duplicate-code

import os
import re
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("LYRION_HOST", "http://localhost:9000")
os.environ.setdefault("DB_DIR", tempfile.mkdtemp())
os.environ.setdefault("DB_PERSIST_DIR", tempfile.mkdtemp())

# The config env vars above must be set before anything imports config.py.
from app import create_app  # pylint: disable=wrong-import-position


def stats(floor, above):
    return {
        "songs_total": 10, "songs_played_apc": 10, "songs_unplayed_apc": 0,
        "songs_play_floor": floor, "songs_above_floor": above,
        "songs_above_floor_pct": above * 10,
    }


class PlayFloorRowTest(unittest.TestCase):
    def setUp(self):
        self.client = create_app().test_client()

    def _row(self, floor, above):
        with patch("routes.nowplaying.get_stats", return_value=stats(floor, above)):
            page = self.client.get("/", headers={"Accept-Language": "en"}).get_data(as_text=True)
        match = re.search(r"<div[^>]*stat-row-above-floor.*?</div>", page, re.S)
        self.assertIsNotNone(match)
        return match.group(0)

    def test_row_is_hidden_while_a_track_is_unplayed(self):
        self.assertIn("hidden", self._row(0, 7))

    def test_row_names_the_level_above_the_floor(self):
        row = self._row(3, 2)
        self.assertNotIn("hidden", row)
        self.assertIn("At least 4 times", row)
        self.assertIn("2 <small>(20%)</small>", row)


if __name__ == "__main__":
    unittest.main()
