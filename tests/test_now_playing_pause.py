"""get_now_playing tells a paused player from a stopped one, and from one that
was switched off while paused."""
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


class NowPlayingPauseTest(unittest.TestCase):
    def setUp(self):
        self.app = create_app()

    def _now(self, mode, **extra):
        result = {"mode": mode, "time": 12, "playlist_loop": [{"id": 42, "title": "Teardrop"}], **extra}
        with self.app.app_context(), \
                patch.object(L, "lyrion_request", return_value={"result": result}):
            now = L.get_now_playing("cc:cc:01:fa:21:db")
        return now["playing"], now["paused"]

    def test_transport_modes(self):
        self.assertEqual(self._now("play"), (True, False))
        self.assertEqual(self._now("pause"), (False, True))
        self.assertEqual(self._now("stop"), (False, False))

    def test_a_powered_off_player_is_not_paused(self):
        self.assertEqual(self._now("pause", power=0), (False, False))
        self.assertEqual(self._now("pause", power="0"), (False, False))
        self.assertEqual(self._now("pause", power=1), (False, True))


if __name__ == "__main__":
    unittest.main()
