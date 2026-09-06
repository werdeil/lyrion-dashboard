"""Tests for the Musixmatch provider's guards against another song's lyrics.

Its matcher is fuzzy and answers even when the track isn't in its catalogue, so
an obscure title comes back as the nearest song it does have — in whatever
language that happens to be. A track can also carry translated subtitles.
"""
# The env scaffolding is intentionally the same as in the other tests; that
# repetition is what keeps each file standalone.
# pylint: disable=duplicate-code,protected-access

import os
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("DB_DIR", tempfile.mkdtemp())
os.environ.setdefault("DB_PERSIST_DIR", tempfile.mkdtemp())

import services.lyrics as L  # pylint: disable=wrong-import-position


def _macro(track=None, lyrics=None, subtitles=None):
    calls = {}
    if track is not None:
        calls["matcher.track.get"] = {"message": {"body": {"track": track}}}
    if lyrics is not None:
        calls["track.lyrics.get"] = {"message": {"body": {"lyrics": lyrics}}}
    if subtitles is not None:
        calls["track.subtitles.get"] = {"message": {"body": {"subtitle_list": subtitles}}}
    return {"message": {"body": {"macro_calls": calls}}}


def _subtitle(body, language=None):
    entry = {"subtitle_body": body}
    if language:
        entry["subtitle_language"] = language
    return {"subtitle": entry}


TRACK = {
    "track_name": "Space Debris",
    "artist_name": "Muse",
    "album_name": "Absolution",
    "track_length": 247,
}


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload
        self.status_code = 200

    def json(self):
        return self.payload


class MusixmatchTest(unittest.TestCase):
    def _fetch(self, payload, artist="Muse", title="Space Debris", duration="247"):
        with patch.object(L, "_musixmatch_token", return_value="tok"), \
             patch.object(L.requests, "get", return_value=FakeResponse(payload)):
            return L._provider_musixmatch(artist, title, None, duration)

    def test_matching_track_returns_both_forms(self):
        found = self._fetch(_macro(
            TRACK,
            {"lyrics_body": "la la la", "lyrics_language": "en"},
            [_subtitle("[00:01.00] la la la", "en")],
        ))
        self.assertEqual(found["lyrics"], "la la la")
        self.assertEqual(found["synced"], "[00:01.00] la la la")
        self.assertEqual(found["meta"]["title"], "Space Debris")

    def test_another_song_is_dropped(self):
        payload = _macro(
            {"track_name": "Nu Ma Uita", "artist_name": "Elena", "track_length": 199},
            {"lyrics_body": "nu ma uita", "lyrics_language": "ro"},
            [_subtitle("[00:01.00] nu ma uita", "ro")],
        )
        self.assertIsNone(self._fetch(payload))

    def test_same_song_other_recording_is_dropped(self):
        payload = _macro(
            {**TRACK, "track_length": 400},
            {"lyrics_body": "la la la", "lyrics_language": "en"},
            None,
        )
        self.assertIsNone(self._fetch(payload))

    def test_unmatched_request_is_dropped(self):
        self.assertIsNone(self._fetch(_macro({}, {"lyrics_body": "la la la"}, None)))

    def test_translated_subtitle_is_skipped_for_the_original(self):
        found = self._fetch(_macro(
            TRACK,
            {"lyrics_body": "la la la", "lyrics_language": "en"},
            [_subtitle("[00:01.00] nie zapomnij", "pl"), _subtitle("[00:01.00] la la la", "en")],
        ))
        self.assertEqual(found["synced"], "[00:01.00] la la la")

    def test_only_translated_subtitles_leaves_plain_lyrics(self):
        found = self._fetch(_macro(
            TRACK,
            {"lyrics_body": "la la la", "lyrics_language": "en"},
            [_subtitle("[00:01.00] nie zapomnij", "pl")],
        ))
        self.assertIsNone(found["synced"])
        self.assertEqual(found["lyrics"], "la la la")

    def test_subtitle_without_a_declared_language_is_kept(self):
        found = self._fetch(_macro(
            TRACK,
            {"lyrics_body": "la la la", "lyrics_language": "en"},
            [_subtitle("[00:01.00] la la la")],
        ))
        self.assertEqual(found["synced"], "[00:01.00] la la la")

    def test_empty_macro_yields_nothing(self):
        self.assertIsNone(self._fetch({"message": {"body": {}}}))


if __name__ == "__main__":
    unittest.main()
