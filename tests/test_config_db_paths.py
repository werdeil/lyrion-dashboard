"""Tests for how config.py resolves the two Lyrion database paths."""
# No env scaffolding here: this file drives config's env itself and reloads
# the module per case, so it must not inherit paths set at import.

import importlib
import os
import unittest
from unittest.mock import patch

import config

DB_ENV = ("LYRION_DATA_DIR", "DB_DIR", "DB_PERSIST_DIR")


def _reload_with(**env):
    with patch.dict(os.environ, env, clear=False):
        for name in DB_ENV:
            if name not in env:
                os.environ.pop(name, None)
        return importlib.reload(config).Config


class DbPathsTest(unittest.TestCase):
    def tearDown(self):
        importlib.reload(config)

    def test_derived_from_the_data_dir(self):
        cfg = _reload_with(LYRION_DATA_DIR="/srv/lyrion")
        self.assertEqual(cfg.DB_PATH, "/srv/lyrion/cache/library.db")
        self.assertEqual(cfg.DB_PERSIST_PATH, "/srv/lyrion/prefs/persist.db")

    def test_db_dir_overrides_only_the_library(self):
        cfg = _reload_with(LYRION_DATA_DIR="/srv/lyrion", DB_DIR="/mnt/ssd/cache")
        self.assertEqual(cfg.DB_PATH, "/mnt/ssd/cache/library.db")
        self.assertEqual(cfg.DB_PERSIST_PATH, "/srv/lyrion/prefs/persist.db")

    def test_db_persist_dir_overrides_only_the_persist_db(self):
        cfg = _reload_with(LYRION_DATA_DIR="/srv/lyrion", DB_PERSIST_DIR="/etc/lyrion")
        self.assertEqual(cfg.DB_PATH, "/srv/lyrion/cache/library.db")
        self.assertEqual(cfg.DB_PERSIST_PATH, "/etc/lyrion/persist.db")

    def test_overrides_alone_need_no_data_dir(self):
        cfg = _reload_with(DB_DIR="/mnt/ssd/cache", DB_PERSIST_DIR="/etc/lyrion")
        self.assertEqual(cfg.DB_PATH, "/mnt/ssd/cache/library.db")
        self.assertEqual(cfg.DB_PERSIST_PATH, "/etc/lyrion/persist.db")

    def test_nothing_set_yields_bare_filenames(self):
        cfg = _reload_with()
        self.assertEqual(cfg.DB_PATH, "library.db")
        self.assertEqual(cfg.DB_PERSIST_PATH, "persist.db")


if __name__ == "__main__":
    unittest.main()
