"""Tests for the LRCLIB provider's preference for synced (LRC) records.

LRCLIB stores lyrics per upload, so the record `get` matches on the exact
artist/title/album/duration signature can hold plain text only while another
upload of the very same track carries an LRC. Settling for the first record
would cost the karaoke view on tracks that have one.
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


def _record(rec_id, synced=None, plain="la la la", album="Will Of The People", duration=302):
    return {
        "id": rec_id,
        "trackName": "Will Of The People",
        "artistName": "Muse",
        "albumName": album,
        "duration": duration,
        "plainLyrics": plain,
        "syncedLyrics": synced,
    }


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self.payload = payload
        self.status_code = status_code

    def json(self):
        return self.payload


class _Lrclib:
    """Stands in for LRCLIB: one payload for /get, one per /search attempt."""

    def __init__(self, get=None, searches=(), get_status=200):
        self.get = get
        self.searches = list(searches)
        self.get_status = get_status
        self.calls = []

    def __call__(self, url, **kwargs):
        self.calls.append((url, kwargs.get("params", {})))
        if url.endswith("/get"):
            if self.get is None:
                return FakeResponse(None, 404)
            return FakeResponse(self.get, self.get_status)
        return FakeResponse(self.searches.pop(0) if self.searches else [])

    @property
    def search_calls(self):
        return [params for url, params in self.calls if url.endswith("/search")]


class LrclibSyncedPreferenceTest(unittest.TestCase):
    def _fetch(self, fake):
        with patch("services.lyrics.requests.get", side_effect=fake):
            return L._provider_lrclib("Muse", "Will Of The People", "Will Of The People", "302")

    def test_plain_get_hit_is_upgraded_by_a_synced_search_result(self):
        fake = _Lrclib(
            get=_record(1, synced=None),
            searches=[[_record(2, synced=None), _record(22439347, synced="[00:12.00] la")]],
        )
        result = self._fetch(fake)
        self.assertEqual(result["synced"], "[00:12.00] la")
        self.assertTrue(fake.search_calls)

    def test_synced_get_hit_stops_there(self):
        fake = _Lrclib(get=_record(1, synced="[00:12.00] la"))
        result = self._fetch(fake)
        self.assertEqual(result["synced"], "[00:12.00] la")
        self.assertEqual(fake.search_calls, [])

    def test_a_later_attempt_can_still_bring_the_synced_record(self):
        # Album-filtered search first, then the same search without the album.
        fake = _Lrclib(
            get=None,
            searches=[[_record(2, synced=None)], [_record(3, synced="[00:12.00] la")]],
        )
        result = self._fetch(fake)
        self.assertEqual(result["synced"], "[00:12.00] la")
        self.assertEqual(len(fake.search_calls), 2)

    def test_plain_is_kept_when_nothing_is_synced(self):
        fake = _Lrclib(get=_record(1, synced=None, plain="from get"), searches=[[_record(2, synced=None)]])
        result = self._fetch(fake)
        self.assertEqual(result["lyrics"], "from get")
        self.assertIsNone(result["synced"])

    def test_search_only_plain_result_is_used_when_get_missed(self):
        fake = _Lrclib(get=None, searches=[[_record(2, synced=None, plain="from search")]])
        result = self._fetch(fake)
        self.assertEqual(result["lyrics"], "from search")

    def test_nothing_anywhere_returns_none(self):
        self.assertIsNone(self._fetch(_Lrclib(get=None, searches=[[], []])))

    def test_each_search_attempt_logs_its_candidate_counts(self):
        fake = _Lrclib(
            get=None,
            searches=[[_record(2, synced=None)], [_record(3, synced=None), _record(4, synced="[00:12.00] la")]],
        )
        with self.assertLogs("services.lyrics", level="INFO") as captured:
            self._fetch(fake)
        counts = [line for line in captured.output if "candidate(s)" in line]
        self.assertEqual(len(counts), 2)
        self.assertIn("returned 1 candidate(s), 0 synced", counts[0])
        self.assertIn("returned 2 candidate(s), 1 synced", counts[1])


class LrclibDurationMatchTest(unittest.TestCase):
    """An LRC's timestamps only fit the recording they were made for: a live or
    extended upload of the same song scrolls against the wrong timeline."""

    def _fetch(self, fake, duration="302"):
        with patch("services.lyrics.requests.get", side_effect=fake):
            return L._provider_lrclib("Muse", "Will Of The People", "Will Of The People", duration)

    def test_synced_record_of_another_length_loses_to_a_plain_one_that_fits(self):
        fake = _Lrclib(get=None, searches=[[
            _record(2, synced="[01:55.54] la", duration=419),
            _record(3, synced=None, plain="right recording"),
        ]])
        result = self._fetch(fake)
        self.assertIsNone(result["synced"])
        self.assertEqual(result["lyrics"], "right recording")

    def test_another_recording_keeps_its_words_but_loses_its_timings(self):
        fake = _Lrclib(get=None, searches=[[
            _record(2, synced="[01:55.54] la", plain="same song", duration=419),
        ]])
        result = self._fetch(fake)
        self.assertIsNone(result["synced"])
        self.assertEqual(result["lyrics"], "same song")

    def test_the_synced_record_of_the_right_length_wins_over_an_earlier_one(self):
        fake = _Lrclib(get=None, searches=[[
            _record(2, synced="[01:55.54] wrong", duration=419),
            _record(3, synced="[00:12.00] right"),
        ]])
        self.assertEqual(self._fetch(fake)["synced"], "[00:12.00] right")

    def test_a_few_seconds_apart_is_still_the_same_recording(self):
        fake = _Lrclib(get=None, searches=[[_record(2, synced="[00:12.00] la", duration=305)]])
        self.assertEqual(self._fetch(fake)["synced"], "[00:12.00] la")

    def test_an_unknown_track_length_cannot_filter_anything(self):
        fake = _Lrclib(get=None, searches=[[_record(2, synced="[00:12.00] la", duration=419)]])
        self.assertEqual(self._fetch(fake, duration=None)["synced"], "[00:12.00] la")

    def test_each_search_attempt_logs_how_many_candidates_fit(self):
        fake = _Lrclib(get=None, searches=[[
            _record(2, synced="[01:55.54] la", duration=419),
            _record(3, synced=None),
        ]])
        with self.assertLogs("services.lyrics", level="INFO") as captured:
            self._fetch(fake)
        self.assertIn("returned 2 candidate(s), 1 synced, 1 of this length", captured.output[0])


if __name__ == "__main__":
    unittest.main()
