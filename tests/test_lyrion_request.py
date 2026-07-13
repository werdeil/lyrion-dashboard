"""Lyrion answers a status query for an unknown player id — an ephemeral
player that has disappeared, which it drops from the players list entirely —
with an empty body that isn't JSON. lyrion_request must tolerate that instead
of raising, so a vanished _last_player can't abort now-playing resolution
before the live players are enumerated (the "stuck until a docker restart" bug).
"""
# pylint: disable=protected-access

import os
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("LYRION_HOST", "http://localhost:9000")
os.environ.setdefault("DB_DIR", tempfile.mkdtemp())
os.environ.setdefault("DB_PERSIST_DIR", tempfile.mkdtemp())

from app import create_app  # pylint: disable=wrong-import-position
import services.lyrion as L  # pylint: disable=wrong-import-position


class _EmptyBody:
    """Stands in for the empty (non-JSON) response Lyrion returns for an
    unknown player id — r.json() raises ValueError, like requests does."""

    def json(self):
        raise ValueError("Expecting value: line 1 column 1 (char 0)")


class LyrionEmptyBodyTest(unittest.TestCase):
    def setUp(self):
        self.app = create_app()

    def test_lyrion_request_tolerates_empty_body(self):
        with self.app.app_context(), \
                patch.object(L._session, "post", return_value=_EmptyBody()):
            self.assertEqual(L.lyrion_request({"id": 1}), {})

    def test_get_players_tolerates_empty_body(self):
        with self.app.app_context(), \
                patch.object(L._session, "post", return_value=_EmptyBody()):
            self.assertEqual(L.get_players(), [])

    def test_get_now_playing_tolerates_empty_body(self):
        # A vanished player resolves to a clean not-playing state, so the
        # shortcut falls through to the enumeration instead of crashing.
        with self.app.app_context(), \
                patch.object(L._session, "post", return_value=_EmptyBody()):
            result = L.get_now_playing("cc:cc:01:fa:21:db")
        self.assertFalse(result["playing"])


if __name__ == "__main__":
    unittest.main()
