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


def _status(**extra):
    track = {"id": 42, "title": "Tamacun", "album": "Re-Foc", "disc": "2", **extra}
    return {"result": {"mode": "play", "time": 12, "playlist_loop": [track]}}


class NowPlayingDiscTitleTest(unittest.TestCase):
    def setUp(self):
        self.app = create_app()

    def _now_playing(self, status):
        with self.app.app_context(), \
                patch.object(L, "lyrion_request", return_value=status) as request:
            return L.get_now_playing("cc:cc:01:fa:21:db"), request.call_args[0][0]

    def test_status_requests_the_disc_tag(self):
        _, payload = self._now_playing(_status())
        tags = payload["params"][1][3]
        self.assertIn("i", tags.removeprefix("tags:"))

    def test_disc_subtitle_is_the_disc_title(self):
        track, _ = self._now_playing(_status(discsubtitle="Live in Madrid"))
        self.assertEqual(track["disc_title"], "Live in Madrid")

    def test_disc_without_subtitle_has_no_title(self):
        for extra in ({}, {"discsubtitle": ""}):
            with self.subTest(extra=extra):
                track, _ = self._now_playing(_status(**extra))
                self.assertIsNone(track["disc_title"])


if __name__ == "__main__":
    unittest.main()
