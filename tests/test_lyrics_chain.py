"""Tests for the order in which the provider chain settles on a result."""
# The env scaffolding is intentionally the same as in the other tests; that
# repetition is what keeps each file standalone.
# pylint: disable=duplicate-code,protected-access

import os
import tempfile
import unittest

os.environ.setdefault("DB_DIR", tempfile.mkdtemp())
os.environ.setdefault("DB_PERSIST_DIR", tempfile.mkdtemp())

import services.lyrics as L  # pylint: disable=wrong-import-position

META = {"artist": "Muse", "title": "Space Debris", "album": None, "duration": None}
PLAIN = {"lyrics": "la la la", "synced": None, "meta": META}
SYNCED = {"lyrics": "la la la", "synced": "[00:01.00]la la la", "meta": META}


def _answers(found):
    def provider(*_args):
        provider.calls += 1
        if isinstance(found, Exception):
            raise found
        return dict(found) if found else None
    provider.calls = 0
    return provider


class ProviderChainTest(unittest.TestCase):
    def setUp(self):
        L._cache.clear()
        self._orig = L._enabled_providers

    def tearDown(self):
        L._enabled_providers = self._orig
        L._cache.clear()

    def _use(self, *named):
        L._enabled_providers = lambda: list(named)

    def test_a_synced_result_ends_the_chain(self):
        first, second = _answers(SYNCED), _answers(SYNCED)
        self._use(("lrclib", first), ("musixmatch", second))
        res = L.fetch_lyrics(None, "Muse", "Space Debris")
        self.assertEqual(res["source"], "lrclib")
        self.assertEqual(second.calls, 0)

    def test_a_plain_result_lets_the_next_provider_offer_a_synced_one(self):
        self._use(("lrclib", _answers(PLAIN)), ("musixmatch", _answers(SYNCED)))
        res = L.fetch_lyrics(None, "Muse", "Space Debris")
        self.assertEqual(res["source"], "musixmatch")
        self.assertEqual(res["synced"], SYNCED["synced"])

    def test_the_first_plain_result_stands_when_no_synced_one_turns_up(self):
        self._use(("lrclib", _answers(PLAIN)), ("musixmatch", _answers({"lyrics": "other", "synced": None})))
        res = L.fetch_lyrics(None, "Muse", "Space Debris")
        self.assertEqual(res["source"], "lrclib")
        self.assertEqual(res["lyrics"], PLAIN["lyrics"])

    def test_the_plain_result_survives_a_later_provider_being_down(self):
        self._use(("lrclib", _answers(PLAIN)), ("musixmatch", _answers(L.ProviderUnavailable("musixmatch"))))
        self.assertEqual(L.fetch_lyrics(None, "Muse", "Space Debris")["source"], "lrclib")

    def test_a_plain_only_provider_is_skipped_once_plain_lyrics_are_held(self):
        genius = _answers(PLAIN)
        self._use(("lrclib", _answers(PLAIN)), ("musixmatch", _answers(None)), ("genius", genius))
        self.assertEqual(L.fetch_lyrics(None, "Muse", "Space Debris")["source"], "lrclib")
        self.assertEqual(genius.calls, 0)

    def test_a_plain_only_provider_still_answers_when_nothing_was_found(self):
        self._use(("lrclib", _answers(None)), ("genius", _answers(PLAIN)))
        self.assertEqual(L.fetch_lyrics(None, "Muse", "Space Debris")["source"], "genius")

    def test_netease_is_still_asked_once_plain_lyrics_are_held(self):
        synced_only = {"lyrics": None, "synced": "[00:01.00]la la la", "meta": META}
        self._use(("lrclib", _answers(PLAIN)), ("musixmatch", _answers(None)), ("netease", _answers(synced_only)))
        res = L.fetch_lyrics(None, "Muse", "Space Debris")
        self.assertEqual(res["source"], "netease")
        self.assertEqual(res["synced"], synced_only["synced"])

    def test_verify_keeps_the_first_plain_result(self):
        second = _answers(SYNCED)
        self._use(("lrclib", _answers(PLAIN)), ("musixmatch", second))
        res = L.fetch_lyrics(None, "Muse", "Space Debris", verify=True)
        self.assertEqual(res["source"], "lrclib")
        self.assertEqual(second.calls, 0)


if __name__ == "__main__":
    unittest.main()
