"""Tests for the cover proxy's response filtering (_read_image).

Covers are buffered fully in memory before being re-served, and remote
artwork URLs point at third-party servers: oversized and non-image payloads
must be refused (502) instead of relayed onto the dashboard's origin.

White-box tests: they reach into services.lyrion's private helper on purpose.
"""
# pylint: disable=protected-access

import os
import tempfile
import unittest

from werkzeug.exceptions import HTTPException

os.environ.setdefault("LYRION_HOST", "http://localhost:9000")
os.environ.setdefault("DB_DIR", tempfile.mkdtemp())
os.environ.setdefault("DB_PERSIST_DIR", tempfile.mkdtemp())

import services.lyrion as L  # pylint: disable=wrong-import-position


class FakeResponse:
    def __init__(self, content=b"IMG", content_type="image/jpeg"):
        self.content = content
        self.headers = {"Content-Type": content_type} if content_type else {}

    def raise_for_status(self):
        pass

    def iter_content(self, chunk_size):
        for i in range(0, len(self.content), chunk_size):
            yield self.content[i:i + chunk_size]


class ReadImageTest(unittest.TestCase):
    def test_image_is_relayed_with_its_type(self):
        content, ctype = L._read_image(FakeResponse(b"PNG", "image/png"))
        self.assertEqual((content, ctype), (b"PNG", "image/png"))

    def test_missing_type_defaults_to_jpeg(self):
        _, ctype = L._read_image(FakeResponse(b"IMG", content_type=None))
        self.assertEqual(ctype, "image/jpeg")

    def test_octet_stream_is_relayed_as_generic_image(self):
        _, ctype = L._read_image(FakeResponse(b"IMG", "application/octet-stream"))
        self.assertEqual(ctype, "image/jpeg")

    def test_non_image_type_is_refused(self):
        with self.assertRaises(HTTPException) as ctx:
            L._read_image(FakeResponse(b"<html>", "text/html"))
        self.assertEqual(ctx.exception.code, 502)

    def test_oversized_payload_is_refused(self):
        original = L.COVER_MAX_BYTES
        L.COVER_MAX_BYTES = 8
        try:
            with self.assertRaises(HTTPException) as ctx:
                L._read_image(FakeResponse(b"X" * 9, "image/jpeg"))
            self.assertEqual(ctx.exception.code, 502)
        finally:
            L.COVER_MAX_BYTES = original


if __name__ == "__main__":
    unittest.main()
