"""Tests for the diagnostic logs of the lyrics chain.

These logs are what `docker logs` shows when a track ends up without lyrics,
so each outcome — found, nothing found, provider down, provider crashed,
candidate rejected — must be traceable to a line.
"""
# The env scaffolding is intentionally the same as in the other tests; that
# repetition is what keeps each file standalone.
# pylint: disable=duplicate-code,protected-access

import logging
import os
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("LYRION_HOST", "https://lyrion.test:9000")
os.environ.setdefault("DB_DIR", tempfile.mkdtemp())
os.environ.setdefault("DB_PERSIST_DIR", tempfile.mkdtemp())

import logsetup  # pylint: disable=wrong-import-position
import services.lyrics as L  # pylint: disable=wrong-import-position

FOUND = {"lyrics": "la la la", "synced": None, "meta": {"artist": "A", "title": "T", "duration": 100}}


class LyricsLoggingTest(unittest.TestCase):
    def setUp(self):
        L._cache.clear()
        self._orig = L._enabled_providers

    def tearDown(self):
        L._enabled_providers = self._orig
        L._cache.clear()

    def _use(self, name, provider):
        L._enabled_providers = lambda: [(name, provider)]

    def test_result_line_names_the_source(self):
        self._use("lrclib", lambda *_a: dict(FOUND))
        with self.assertLogs("services.lyrics", level="INFO") as captured:
            L.fetch_lyrics("1", "A", "T")
        self.assertTrue(any("-> lrclib" in line for line in captured.output))

    def test_empty_search_is_logged_as_none(self):
        self._use("lrclib", lambda *_a: None)
        with self.assertLogs("services.lyrics", level="INFO") as captured:
            L.fetch_lyrics("1", "A", "T")
        self.assertTrue(any("-> none" in line for line in captured.output))

    def test_unreachable_provider_is_logged_with_its_cause(self):
        def provider(*_args):
            raise L.ProviderUnavailable("lrclib") from TimeoutError("connect timed out")

        self._use("lrclib", provider)
        with self.assertLogs("services.lyrics", level="WARNING") as captured:
            L.fetch_lyrics("1", "A", "T")
        self.assertTrue(any("unreachable" in line and "connect timed out" in line for line in captured.output))

    def test_crashing_provider_is_logged_and_the_chain_continues(self):
        def broken(*_args):
            raise ValueError("boom")

        L._enabled_providers = lambda: [("genius", broken), ("lrclib", lambda *_a: dict(FOUND))]
        with self.assertLogs("services.lyrics", level="WARNING") as captured:
            result = L.fetch_lyrics("1", "A", "T")
        self.assertEqual(result["source"], "lrclib")
        self.assertTrue(any("genius failed" in line and "boom" in line for line in captured.output))

    def test_rejected_candidate_logs_what_came_back(self):
        other = {"lyrics": "nope", "synced": None,
                 "meta": {"artist": "Other", "title": "Other song", "duration": 100}}
        self._use("lrclib", lambda *_a: dict(other))
        with self.assertLogs("services.lyrics", level="INFO") as captured:
            L.fetch_lyrics("1", "A", "T", verify=True)
        self.assertTrue(any("rejected" in line and "Other song" in line for line in captured.output))

    def test_missing_metadata_is_logged_rather_than_silent(self):
        with self.assertLogs("services.lyrics", level="INFO") as captured:
            L.fetch_lyrics("1", "", "T")
        self.assertTrue(any("no artist or title" in line for line in captured.output))


class ConfigureLoggingTest(unittest.TestCase):
    def setUp(self):
        self._configured = logsetup._state["configured"]
        self._root_handlers = list(logging.getLogger().handlers)
        self._root_level = logging.getLogger().level

    def tearDown(self):
        logsetup._state["configured"] = self._configured
        logging.getLogger().handlers = self._root_handlers
        logging.getLogger().setLevel(self._root_level)

    def test_only_the_first_call_configures(self):
        logsetup._state["configured"] = False
        logging.getLogger().handlers = []
        self.assertTrue(logsetup.configure_logging("WARNING"))
        self.assertEqual(len(logging.getLogger().handlers), 1)
        self.assertFalse(logsetup.configure_logging("WARNING"))
        self.assertEqual(len(logging.getLogger().handlers), 1)

    def test_level_comes_from_the_environment(self):
        with patch.dict(os.environ, {"LOG_LEVEL": "debug"}):
            self.assertEqual(logsetup.default_level(), "DEBUG")

    def test_unknown_level_falls_back_to_info(self):
        with patch.dict(os.environ, {"LOG_LEVEL": "chatty", "DEV": ""}):
            self.assertEqual(logsetup.default_level(), "INFO")

    def test_dev_mode_defaults_to_debug(self):
        with patch.dict(os.environ, {"LOG_LEVEL": "", "DEV": "1"}):
            self.assertEqual(logsetup.default_level(), "DEBUG")


if __name__ == "__main__":
    unittest.main()
