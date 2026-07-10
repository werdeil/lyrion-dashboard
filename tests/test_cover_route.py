"""Tests for the /cover/<coverid>.jpg route's coverid validation.

The coverid is spliced into the upstream Lyrion URL, so only plain
numeric/hex ids may reach fetch_cover — anything else (e.g. "..") must be
rejected before any upstream request is made.
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


class CoverRouteTest(unittest.TestCase):
    def setUp(self):
        self.client = create_app().test_client()

    @patch("routes.nowplaying.fetch_cover", return_value=(b"IMG", "image/jpeg"))
    def test_valid_ids_are_proxied(self, mock_fetch):
        for coverid in ("42", "1a2b3c4d", "ABCDEF"):
            response = self.client.get(f"/cover/{coverid}.jpg")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data, b"IMG")
        mock_fetch.assert_any_call("42", None)

    @patch("routes.nowplaying.fetch_cover", return_value=(b"IMG", "image/jpeg"))
    def test_size_is_forwarded(self, mock_fetch):
        response = self.client.get("/cover/42.jpg?size=200")
        self.assertEqual(response.status_code, 200)
        mock_fetch.assert_called_once_with("42", 200)

    @patch("routes.nowplaying.fetch_cover")
    def test_invalid_ids_get_404_without_upstream_request(self, mock_fetch):
        for coverid in ("..", "....", "42x", "a-b", "a.b", "%2e%2e", "a%2Fb"):
            response = self.client.get(f"/cover/{coverid}.jpg")
            self.assertEqual(response.status_code, 404, coverid)
        mock_fetch.assert_not_called()


if __name__ == "__main__":
    unittest.main()
