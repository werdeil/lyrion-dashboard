"""get_now_playing reads the player's level from the status `mixer volume`,
which Lyrion negates while the player is muted."""
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


def _status(volume):
    result = {"mode": "play", "time": 12, "playlist_loop": [{"id": 42, "title": "Teardrop"}]}
    if volume is not None:
        result["mixer volume"] = volume
    return {"result": result}


class NowPlayingVolumeTest(unittest.TestCase):
    def setUp(self):
        self.app = create_app()

    def _now(self, raw):
        with self.app.app_context(), \
                patch.object(L, "lyrion_request", return_value=_status(raw)):
            now = L.get_now_playing("cc:cc:01:fa:21:db")
        return now["volume"], now["muted"]

    def test_level_is_an_int(self):
        self.assertEqual(self._now(42), (42, False))
        self.assertEqual(self._now("42"), (42, False))
        self.assertEqual(self._now(0), (0, False))

    def test_negative_level_means_muted(self):
        self.assertEqual(self._now(-35), (35, True))
        self.assertEqual(self._now("-35"), (35, True))

    def test_missing_level_is_none(self):
        for raw in (None, "", "n/a"):
            with self.subTest(raw=raw):
                self.assertEqual(self._now(raw), (None, False))


if __name__ == "__main__":
    unittest.main()
