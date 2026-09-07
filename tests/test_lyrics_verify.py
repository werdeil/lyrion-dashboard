"""Tests for the lyrics result verification used by the batch CLI.

The batch tool writes lyrics permanently into tags, so it must reject a
provider's result when the matched track doesn't line up with the file. These
cover the normalisation, the match rule, and fetch_lyrics' verify wiring.

White-box tests: they reach into services.lyrics' private helpers on purpose.
"""
# pylint: disable=protected-access

import os
import tempfile
import unittest

os.environ.setdefault("DB_DIR", tempfile.mkdtemp())
os.environ.setdefault("DB_PERSIST_DIR", tempfile.mkdtemp())

import services.lyrics as L  # pylint: disable=wrong-import-position


class NormalizeTest(unittest.TestCase):
    def test_folds_accents_case_and_punctuation(self):
        self.assertEqual(L._normalize("Éléphant!"), "elephant")

    def test_strips_parenthetical_qualifiers(self):
        self.assertEqual(
            L._normalize("Space Debris (Remastered 2019)"),
            L._normalize("Space Debris"),
        )

    def test_strips_feat_credits(self):
        self.assertEqual(L._normalize("Muse feat. Someone"), L._normalize("Muse"))

    def test_empty_and_none(self):
        self.assertEqual(L._normalize(None), "")
        self.assertEqual(L._normalize(""), "")


class FoldNameTest(unittest.TestCase):
    def test_leading_article_is_dropped(self):
        self.assertEqual(L._fold_name("The xx"), L._fold_name("xx"))
        self.assertEqual(L._fold_name("L'Affaire Louis Trio"), L._fold_name("Affaire Louis Trio"))

    def test_plural_disagreement_still_folds_together(self):
        self.assertEqual(L._fold_name("Les Fatals Picards"), L._fold_name("Fatal Picards"))

    def test_an_article_inside_the_name_is_kept(self):
        self.assertNotEqual(L._fold_name("Take The Power Back"), L._fold_name("Take Power Back"))

    def test_short_words_keep_their_s(self):
        self.assertNotEqual(L._fold_name("Yes"), L._fold_name("Ye"))

    def test_different_names_stay_apart(self):
        self.assertNotEqual(L._fold_name("The Beatles"), L._fold_name("The Beach Boys"))


class MatchesRequestTest(unittest.TestCase):
    def _meta(self, **kw):
        base = {"artist": "Muse", "title": "Space Debris", "album": None, "duration": 247}
        base.update(kw)
        return base

    def test_exact_match_within_duration_tolerance(self):
        self.assertTrue(L._matches_request(self._meta(duration=248), "Muse", "Space Debris", "247.1"))

    def test_duration_off_beyond_tolerance(self):
        self.assertFalse(L._matches_request(self._meta(duration=300), "Muse", "Space Debris", "247"))

    def test_title_mismatch(self):
        self.assertFalse(L._matches_request(self._meta(title="Other Song"), "Muse", "Space Debris", "247"))

    def test_artist_mismatch(self):
        self.assertFalse(L._matches_request(self._meta(artist="Radiohead"), "Muse", "Space Debris", "247"))

    def test_no_meta_is_reject(self):
        self.assertFalse(L._matches_request(None, "Muse", "Space Debris", "247"))

    def test_missing_candidate_duration_accepts_on_title_artist(self):
        # Genius-style hit: no duration to compare, so title+artist must carry it.
        self.assertTrue(L._matches_request(self._meta(duration=None), "Muse", "Space Debris", "247"))

    def test_missing_requested_duration_accepts_on_title_artist(self):
        self.assertTrue(L._matches_request(self._meta(duration=248), "Muse", "Space Debris", None))

    def test_artist_tagged_without_its_article_still_matches(self):
        meta = self._meta(artist="Les Fatals Picards", title="Chez Tom")
        self.assertTrue(L._matches_request(meta, "Fatal Picards", "Chez Tom", "247"))

    def test_title_tagged_without_its_article_still_matches(self):
        meta = self._meta(title="The Space Debris")
        self.assertTrue(L._matches_request(meta, "Muse", "Space Debris", "247"))

    def test_qualifier_and_feat_still_match(self):
        meta = self._meta(title="Space Debris (Live)", artist="Muse feat. X", duration=246)
        self.assertTrue(L._matches_request(meta, "Muse", "Space Debris", "247"))


class FetchLyricsVerifyTest(unittest.TestCase):
    def setUp(self):
        L._cache.clear()
        self._orig = L._enabled_providers

    def tearDown(self):
        L._enabled_providers = self._orig
        L._cache.clear()

    def _stub_provider(self, meta):
        def provider(_artist, _title, _album, _duration):
            return {"lyrics": "la la la", "synced": None, "meta": meta}
        L._enabled_providers = lambda: [("fake", provider)]

    def test_verify_accepts_matching_candidate(self):
        self._stub_provider({"artist": "Muse", "title": "Space Debris", "album": None, "duration": 247})
        res = L.fetch_lyrics(None, "Muse", "Space Debris", duration="247", verify=True)
        self.assertEqual(res["source"], "fake")
        self.assertEqual(res["lyrics"], "la la la")

    def test_verify_rejects_mismatching_candidate(self):
        self._stub_provider({"artist": "Someone Else", "title": "Wrong", "album": None, "duration": 999})
        res = L.fetch_lyrics(None, "Muse", "Space Debris", duration="247", verify=True)
        self.assertEqual(res["source"], "rejected")
        self.assertIsNone(res["lyrics"])

    def test_lenient_accepts_mismatching_candidate(self):
        self._stub_provider({"artist": "Someone Else", "title": "Wrong", "album": None, "duration": 999})
        res = L.fetch_lyrics(None, "Muse", "Space Debris", duration="247", verify=False)
        self.assertEqual(res["source"], "fake")
        self.assertEqual(res["lyrics"], "la la la")


if __name__ == "__main__":
    unittest.main()
