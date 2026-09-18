"""Tests for /log-level, which switches verbosity without a restart.

The level lives on the root logger, so each test puts it back: leaving DEBUG
behind would flood the rest of the suite.
"""
# The env scaffolding is intentionally the same as in the other tests; that
# repetition is what keeps each file standalone.
# pylint: disable=duplicate-code

import logging
import os
import tempfile
import unittest

os.environ.setdefault("LYRION_HOST", "http://localhost:9000")
os.environ.setdefault("DB_DIR", tempfile.mkdtemp())
os.environ.setdefault("DB_PERSIST_DIR", tempfile.mkdtemp())

# The config env vars above must be set before anything imports config.py.
# pylint: disable=wrong-import-position
from app import create_app


class LogLevelRouteTest(unittest.TestCase):
    def setUp(self):
        self.client = create_app().test_client()
        self.original = logging.getLogger().level

    def tearDown(self):
        logging.getLogger().setLevel(self.original)

    def test_get_reports_the_current_level(self):
        logging.getLogger().setLevel("WARNING")
        response = self.client.get("/log-level")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["level"], "WARNING")

    def test_post_switches_the_root_logger(self):
        response = self.client.post("/log-level?level=debug")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["level"], "DEBUG")
        self.assertTrue(logging.getLogger().isEnabledFor(logging.DEBUG))

    def test_post_accepts_a_form_body_and_a_json_body(self):
        self.client.post("/log-level", data={"level": "error"})
        self.assertEqual(logging.getLogger().level, logging.ERROR)
        self.client.post("/log-level", json={"level": "info"})
        self.assertEqual(logging.getLogger().level, logging.INFO)

    def test_an_unknown_level_is_refused_and_changes_nothing(self):
        logging.getLogger().setLevel("INFO")
        response = self.client.post("/log-level?level=verbose")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(logging.getLogger().level, logging.INFO)

    def test_the_default_says_what_a_restart_would_restore(self):
        self.client.post("/log-level?level=debug")
        # tests/__init__ pins LOG_LEVEL=CRITICAL, so that is what the env asks for.
        self.assertEqual(self.client.get("/log-level").get_json()["default"], "CRITICAL")


if __name__ == "__main__":
    unittest.main()
