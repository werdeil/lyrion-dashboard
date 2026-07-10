"""Tests for the lyrics cache bounds.

The cache key includes client-supplied artist/title (via /lyrics.json), so the
cache must not grow without limit: entry count is capped with LRU eviction,
expired entries are swept on every write, and absurdly long metadata fields are
refused before they reach the cache or the providers.

White-box tests: they reach into services.lyrics' private helpers on purpose.
"""
# pylint: disable=protected-access

import os
import tempfile
import unittest

os.environ.setdefault("DB_DIR", tempfile.mkdtemp())
os.environ.setdefault("DB_PERSIST_DIR", tempfile.mkdtemp())

import services.lyrics as L  # pylint: disable=wrong-import-position


class CacheBoundsTest(unittest.TestCase):
    def setUp(self):
        L._cache.clear()
        self._orig_max = L.CACHE_MAX_ENTRIES
        L.CACHE_MAX_ENTRIES = 3

    def tearDown(self):
        L.CACHE_MAX_ENTRIES = self._orig_max
        L._cache.clear()

    def test_entry_count_is_capped(self):
        for i in range(10):
            L._cache_set(f"key{i}", {"n": i}, ttl=60)
        self.assertEqual(len(L._cache), 3)

    def test_eviction_drops_least_recently_used(self):
        L._cache_set("a", "va", ttl=60)
        L._cache_set("b", "vb", ttl=60)
        L._cache_set("c", "vc", ttl=60)
        # Touch "a" so "b" becomes the least recently used entry.
        self.assertEqual(L._cache_get("a"), "va")
        L._cache_set("d", "vd", ttl=60)
        self.assertIsNone(L._cache_get("b"))
        self.assertEqual(L._cache_get("a"), "va")
        self.assertEqual(L._cache_get("d"), "vd")

    def test_expired_entries_are_swept_on_write(self):
        L._cache_set("stale1", "v", ttl=-1)
        L._cache_set("stale2", "v", ttl=-1)
        L._cache_set("fresh", "v", ttl=60)
        self.assertEqual(set(L._cache), {"fresh"})

    def test_rewriting_a_key_does_not_evict_others(self):
        L._cache_set("a", "va", ttl=60)
        L._cache_set("b", "vb", ttl=60)
        L._cache_set("c", "vc", ttl=60)
        L._cache_set("c", "vc2", ttl=60)
        self.assertEqual(set(L._cache), {"a", "b", "c"})
        self.assertEqual(L._cache_get("c"), "vc2")


class OversizedFieldsTest(unittest.TestCase):
    def setUp(self):
        L._cache.clear()
        self._orig = L._enabled_providers
        self.provider_calls = []

        def provider(artist, title, album, duration):
            self.provider_calls.append((artist, title, album, duration))
            return {"lyrics": "la la la", "synced": None, "meta": None}
        L._enabled_providers = lambda: [("fake", provider)]

    def tearDown(self):
        L._enabled_providers = self._orig
        L._cache.clear()

    def test_oversized_title_is_refused_without_caching_or_fetching(self):
        res = L.fetch_lyrics(None, "Muse", "x" * (L.MAX_FIELD_LEN + 1))
        self.assertEqual(res, {"lyrics": None, "synced": None, "source": "none"})
        self.assertEqual(self.provider_calls, [])
        self.assertEqual(len(L._cache), 0)

    def test_oversized_track_id_is_refused(self):
        res = L.fetch_lyrics("t" * (L.MAX_FIELD_LEN + 1), "Muse", "Space Debris")
        self.assertEqual(res["source"], "none")
        self.assertEqual(self.provider_calls, [])

    def test_normal_fields_still_fetch_and_cache(self):
        res = L.fetch_lyrics(None, "Muse", "Space Debris")
        self.assertEqual(res["source"], "fake")
        self.assertEqual(len(self.provider_calls), 1)
        self.assertEqual(len(L._cache), 1)


if __name__ == "__main__":
    unittest.main()
