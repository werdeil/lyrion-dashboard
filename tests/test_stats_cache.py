"""Tests for the get_stats TTL cache.

The stats queries scan the whole library, so get_stats serves a cached copy
for STATS_TTL seconds: within the window the computation must not rerun, an
expired entry must be recomputed, and callers must get a copy they can't
corrupt the cache through.

White-box tests: they reach into services.database's private helpers on purpose.
"""
# pylint: disable=protected-access

import os
import tempfile
import unittest

os.environ.setdefault("LYRION_HOST", "http://localhost:9000")
os.environ.setdefault("DB_DIR", tempfile.mkdtemp())
os.environ.setdefault("DB_PERSIST_DIR", tempfile.mkdtemp())

import services.database as D  # pylint: disable=wrong-import-position


class GetStatsCacheTest(unittest.TestCase):
    def setUp(self):
        self._reset_cache()
        self._orig = D._compute_stats
        self.calls = 0

        def fake_compute():
            self.calls += 1
            return {"albums_total": 7, "compute_run": self.calls}
        D._compute_stats = fake_compute

    def tearDown(self):
        D._compute_stats = self._orig
        self._reset_cache()

    @staticmethod
    def _reset_cache():
        D._stats_cache["value"] = None
        D._stats_cache["expires_at"] = 0

    def test_second_call_within_ttl_reuses_the_cached_result(self):
        first = D.get_stats()
        second = D.get_stats()
        self.assertEqual(self.calls, 1)
        self.assertEqual(first, second)

    def test_expired_cache_is_recomputed(self):
        D.get_stats()
        D._stats_cache["expires_at"] = 0  # force expiry
        stats = D.get_stats()
        self.assertEqual(self.calls, 2)
        self.assertEqual(stats["compute_run"], 2)

    def test_callers_get_a_copy_not_the_cached_dict(self):
        stats = D.get_stats()
        stats["albums_total"] = 999999
        self.assertEqual(D.get_stats()["albums_total"], 7)


if __name__ == "__main__":
    unittest.main()
