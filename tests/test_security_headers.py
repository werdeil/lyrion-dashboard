"""Tests for the global security headers set on every response."""
# The env scaffolding is intentionally the same as in the other tests; that
# repetition is what keeps each file standalone.
# pylint: disable=duplicate-code

import os
import tempfile
import unittest

os.environ.setdefault("LYRION_HOST", "http://localhost:9000")
os.environ.setdefault("DB_DIR", tempfile.mkdtemp())
os.environ.setdefault("DB_PERSIST_DIR", tempfile.mkdtemp())

# The config env vars above must be set before anything imports config.py.
# pylint: disable=wrong-import-position
from app import create_app


class SecurityHeadersTest(unittest.TestCase):
    def test_every_response_carries_the_headers(self):
        response = create_app().test_client().get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers["Content-Security-Policy"], "default-src 'self'"
        )
        self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(response.headers["X-Frame-Options"], "SAMEORIGIN")


if __name__ == "__main__":
    unittest.main()
