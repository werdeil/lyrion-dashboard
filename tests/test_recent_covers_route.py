"""Tests for the /recent-covers.json route: payload passthrough and the
?limit= clamp that keeps the query sane."""
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

COVERS = ["ca", "cb", "cc"]


class RecentCoversRouteTest(unittest.TestCase):
    def setUp(self):
        self.client = create_app().test_client()

    @patch("routes.nowplaying.get_recent_album_covers", return_value=COVERS)
    def test_returns_cover_ids_json(self, mock_get):
        response = self.client.get("/recent-covers.json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), COVERS)
        mock_get.assert_called_once_with(16)  # default limit

    @patch("routes.nowplaying.get_recent_album_covers", return_value=[])
    def test_limit_is_forwarded_and_clamped(self, mock_get):
        self.client.get("/recent-covers.json?limit=7")
        mock_get.assert_called_with(7)
        self.client.get("/recent-covers.json?limit=0")
        mock_get.assert_called_with(1)
        self.client.get("/recent-covers.json?limit=9999")
        mock_get.assert_called_with(50)


if __name__ == "__main__":
    unittest.main()
