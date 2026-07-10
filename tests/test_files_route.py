"""Tests for /files/ serving from the custom data directory.

The directory is written by other services, so whatever it contains must be
served in a sandboxed (opaque) origin: a malicious HTML file dropped there
must not be able to script the dashboard. Plain data files keep working.
"""
# The env scaffolding is intentionally the same as in the other tests; that
# repetition is what keeps each file standalone.
# pylint: disable=duplicate-code

import os
import shutil
import tempfile
import unittest

os.environ.setdefault("LYRION_HOST", "http://localhost:9000")
os.environ.setdefault("DB_DIR", tempfile.mkdtemp())
os.environ.setdefault("DB_PERSIST_DIR", tempfile.mkdtemp())

# The config env vars above must be set before anything imports config.py.
# pylint: disable=wrong-import-position
from app import create_app


class FilesRouteTest(unittest.TestCase):
    def setUp(self):
        self.datadir = tempfile.mkdtemp()
        with open(os.path.join(self.datadir, "widget.json"), "w", encoding="utf-8") as f:
            f.write('{"tracks": 12}')
        app = create_app()
        app.config["CUSTOM_DATA_DIR"] = self.datadir
        self.client = app.test_client()

    def tearDown(self):
        shutil.rmtree(self.datadir, ignore_errors=True)

    def test_serves_files_with_a_sandbox_csp(self):
        response = self.client.get("/files/widget.json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["tracks"], 12)
        self.assertEqual(response.headers["Content-Security-Policy"], "sandbox")
        self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")

    def test_missing_file_is_404(self):
        self.assertEqual(self.client.get("/files/absent.json").status_code, 404)

    def test_traversal_is_rejected(self):
        response = self.client.get("/files/..%2Fconfig.py")
        self.assertIn(response.status_code, (404, 400))


if __name__ == "__main__":
    unittest.main()
