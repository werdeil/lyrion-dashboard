"""Tests for the /health endpoint and the version it reports."""
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
from config import Config


class HealthTest(unittest.TestCase):
    def test_reports_ok_and_version(self):
        response = create_app().test_client().get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["status"], "ok")
        self.assertEqual(response.get_json()["version"], Config.VERSION)

    def test_version_matches_the_version_file(self):
        version_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "VERSION")
        with open(version_file, encoding="utf-8") as handle:
            self.assertEqual(Config.VERSION, handle.read().strip())


if __name__ == "__main__":
    unittest.main()
