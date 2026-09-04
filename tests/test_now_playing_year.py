"""Lyrion reports an unknown album year as 0 rather than omitting the tag, so
get_now_playing must normalize it away — the page appends "(year)" to the album
name for anything truthy, and "0" (a string) would sail through that check.
"""
# pylint: disable=duplicate-code

import os
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("LYRION_HOST", "http://localhost:9000")
os.environ.setdefault("DB_DIR", tempfile.mkdtemp())
os.environ.setdefault("DB_PERSIST_DIR", tempfile.mkdtemp())

from app import create_app  # pylint: disable=wrong-import-position
import services.lyrion as L  # pylint: disable=wrong-import-position


def _status(year):
    track = {"id": 42, "title": "Bole Chudiyan", "album": "Kabhi Khushi Kabhie Gham"}
    if year is not None:
        track["year"] = year
    return {"result": {"mode": "play", "time": 12, "playlist_loop": [track]}}


class NowPlayingYearTest(unittest.TestCase):
    def setUp(self):
        self.app = create_app()

    def _year(self, raw):
        with self.app.app_context(), \
                patch.object(L, "lyrion_request", return_value=_status(raw)):
            return L.get_now_playing("cc:cc:01:fa:21:db")["year"]

    def test_known_year_is_an_int(self):
        self.assertEqual(self._year(2001), 2001)
        self.assertEqual(self._year("2001"), 2001)

    def test_unknown_year_is_none(self):
        for raw in (0, "0", None, "", "unknown"):
            with self.subTest(raw=raw):
                self.assertIsNone(self._year(raw))


if __name__ == "__main__":
    unittest.main()
