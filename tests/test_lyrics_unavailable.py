"""Tests telling an empty search apart from one that never happened.

A provider that can't be reached returns nothing, exactly like a provider that
has no match — but caching that as a miss would fuse every later search for
TTL_MISS, long after a passing outage is over. Providers raise
ProviderUnavailable for it, and fetch_lyrics only skips the cache when no
provider answered at all.
"""
# The env scaffolding is intentionally the same as in the other tests; that
# repetition is what keeps each file standalone.
# pylint: disable=duplicate-code,protected-access

import os
import tempfile
import unittest

os.environ.setdefault("DB_DIR", tempfile.mkdtemp())
os.environ.setdefault("DB_PERSIST_DIR", tempfile.mkdtemp())

import services.lyrics as L  # pylint: disable=wrong-import-position

FOUND = {"lyrics": "la la la", "synced": None, "meta": None}


def _unreachable(name):
    def provider(*_args):
        provider.calls += 1
        raise L.ProviderUnavailable(name)
    provider.calls = 0
    return provider


def _silent():
    def provider(*_args):
        provider.calls += 1
    provider.calls = 0
    return provider


def _finds():
    def provider(*_args):
        provider.calls += 1
        return dict(FOUND)
    provider.calls = 0
    return provider


class UnavailableProvidersTest(unittest.TestCase):
    def setUp(self):
        L._cache.clear()
        self._orig = L._enabled_providers

    def tearDown(self):
        L._enabled_providers = self._orig
        L._cache.clear()

    def _use(self, *providers):
        L._enabled_providers = lambda: [(f"p{i}", p) for i, p in enumerate(providers)]

    def test_all_providers_unreachable_reports_unavailable(self):
        self._use(_unreachable("a"), _unreachable("b"))
        res = L.fetch_lyrics(None, "Muse", "Space Debris")
        self.assertEqual(res, {"lyrics": None, "synced": None, "source": "unavailable"})

    def test_an_unavailable_search_is_not_cached(self):
        down = _unreachable("a")
        self._use(down)
        L.fetch_lyrics(None, "Muse", "Space Debris")
        self.assertEqual(len(L._cache), 0)
        L.fetch_lyrics(None, "Muse", "Space Debris")
        self.assertEqual(down.calls, 2)

    def test_a_recovered_provider_is_searched_again_without_force(self):
        down = _unreachable("a")
        self._use(down)
        self.assertEqual(L.fetch_lyrics(None, "Muse", "Space Debris")["source"], "unavailable")
        back = _finds()
        self._use(back)
        self.assertEqual(L.fetch_lyrics(None, "Muse", "Space Debris")["source"], "p0")
        self.assertEqual(back.calls, 1)

    def test_a_reachable_provider_with_no_match_still_caches_a_miss(self):
        silent = _silent()
        self._use(_unreachable("a"), silent)
        res = L.fetch_lyrics(None, "Muse", "Space Debris")
        self.assertEqual(res["source"], "none")
        self.assertEqual(len(L._cache), 1)
        L.fetch_lyrics(None, "Muse", "Space Debris")
        self.assertEqual(silent.calls, 1)

    def test_a_later_provider_still_answers_when_an_earlier_one_is_down(self):
        self._use(_unreachable("a"), _finds())
        res = L.fetch_lyrics(None, "Muse", "Space Debris")
        self.assertEqual(res["lyrics"], "la la la")
        self.assertEqual(res["source"], "p1")


if __name__ == "__main__":
    unittest.main()
