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

    def test_the_artist_name_is_retried_without_its_leading_article(self):
        fake = _Lrclib(get=None, searches=[[], [], [], [_record(5, synced="[00:12.00] la", album="Pamplemousse", duration=180)]])
        with patch("services.lyrics.requests.get", side_effect=fake):
            result = L._provider_lrclib("Les Fatals Picards", "Chez Tom", "Pamplemousse", "180")
        self.assertEqual(result["synced"], "[00:12.00] la")
        self.assertEqual(
            [p["artist_name"] for p in fake.search_calls],
            ["Les Fatals Picards", "Les Fatals Picards", "Fatals Picards", "Fatals Picards"],
        )

    def test_a_name_without_an_article_is_not_searched_twice(self):
        fake = _Lrclib(get=None, searches=[[], []])
        self._fetch(fake)
        self.assertEqual(len(fake.search_calls), 2)

    def test_each_search_attempt_logs_its_candidate_counts(self):
        fake = _Lrclib(
            get=None,
            searches=[[_record(2, synced=None)], [_record(3, synced=None), _record(4, synced="[00:12.00] la")]],
        )
        with self.assertLogs("services.lyrics", level="INFO") as captured:
            self._fetch(fake)
        counts = [line for line in captured.output if "candidate(s)" in line]
        self.assertEqual(len(counts), 2)
        self.assertIn("returned 1 candidate(s), 1 of this length, 0 of those synced", counts[0])
        self.assertIn("returned 2 candidate(s), 2 of this length, 1 of those synced", counts[1])

    def test_a_miss_logs_a_search_url_to_replay_by_hand(self):
        fake = _Lrclib(get=None, searches=[[], []])
        with self.assertLogs("services.lyrics", level="INFO") as captured:
            self._fetch(fake)
        urls = [line for line in captured.output if "catalogue search" in line]
        self.assertEqual(len(urls), 1)
        self.assertIn("lrclib.net/search/Muse%20Will%20Of%20The%20People", urls[0])


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

    def test_the_closest_length_wins_among_several_synced_records(self):
        fake = _Lrclib(get=None, searches=[[
            _record(2, synced="[00:12.00] two seconds off", duration=304),
            _record(3, synced="[00:12.00] exact"),
            _record(4, synced="[00:12.00] a second off", duration=303),
        ]])
        self.assertEqual(self._fetch(fake)["synced"], "[00:12.00] exact")

    def test_the_fraction_of_a_second_settles_records_of_the_same_length(self):
        fake = _Lrclib(get=None, searches=[[
            _record(2, synced="[00:12.00] rounded upload", duration=242),
            _record(3, synced="[00:12.00] same rip", duration=242.259592),
        ]])
        self.assertEqual(self._fetch(fake, duration="242.266")["synced"], "[00:12.00] same rip")

    def test_synced_records_the_length_cannot_separate_keep_lrclib_order(self):
        fake = _Lrclib(get=None, searches=[[
            _record(2, synced="[00:12.00] first", duration=None),
            _record(3, synced="[00:12.00] second", duration=None),
        ]])
        self.assertEqual(self._fetch(fake)["synced"], "[00:12.00] first")

    def test_a_few_seconds_apart_is_still_the_same_recording(self):
        fake = _Lrclib(get=None, searches=[[_record(2, synced="[00:12.00] la", duration=305)]])
        self.assertEqual(self._fetch(fake)["synced"], "[00:12.00] la")

    def test_an_unknown_track_length_cannot_filter_anything(self):
        fake = _Lrclib(get=None, searches=[[_record(2, synced="[00:12.00] la", duration=419)]])
        self.assertEqual(self._fetch(fake, duration=None)["synced"], "[00:12.00] la")

    def test_each_search_attempt_logs_how_many_candidates_fit(self):
        # The one synced record is of another length, so nothing synced is on
        # offer: the counts narrow down the same set rather than sitting side
        # by side, or this line would read "1 synced" and promise a version
        # the page never gets.
        fake = _Lrclib(get=None, searches=[[
            _record(2, synced="[01:55.54] la", duration=419),
            _record(3, synced=None),
        ]])
        with self.assertLogs("services.lyrics", level="INFO") as captured:
            self._fetch(fake)
        self.assertIn("returned 2 candidate(s), 1 of this length, 0 of those synced", captured.output[0])

    def test_dropping_the_timings_logs_both_lengths_and_the_record(self):
        fake = _Lrclib(get=None, searches=[[_record(22439347, synced="[01:55.54] la", duration=419)]])
        with self.assertLogs("services.lyrics", level="INFO") as captured:
            self._fetch(fake)
        dropped = [line for line in captured.output if "timings dropped" in line]
        self.assertEqual(len(dropped), 1)
        self.assertIn("lrclib.net/tracks/22439347", dropped[0])
        self.assertIn("is 419s, this track is 302s", dropped[0])


if __name__ == "__main__":
    unittest.main()


class LrclibVersionsTest(unittest.TestCase):
    """The other uploads of the same song, which the page cycles through."""

    def _fetch(self, fake, duration="302"):
        with patch("services.lyrics.requests.get", side_effect=fake):
            return L._provider_lrclib("Muse", "Will Of The People", "Will Of The People", duration)

    def test_every_synced_upload_of_this_length_is_offered(self):
        fake = _Lrclib(get=None, searches=[[
            _record(2, synced="[00:12.00] b", album="Deluxe", duration=303),
            _record(3, synced="[00:12.00] a", album="Studio", duration=302),
            _record(4, synced="[00:12.00] c", album="Live", duration=301),
        ]])
        result = self._fetch(fake)
        # Ranked by nearness to 302s, so the winner leads and the rest follow.
        self.assertEqual([v["album"] for v in result["versions"]], ["Studio", "Deluxe", "Live"])
        self.assertEqual(result["synced"], "[00:12.00] a")

    def test_a_candidate_of_another_length_is_left_out(self):
        fake = _Lrclib(get=None, searches=[[
            _record(3, synced="[00:12.00] a", duration=302),
            _record(9, synced="[00:12.00] z", album="Live", duration=480),
        ]])
        self.assertEqual([v["album"] for v in self._fetch(fake)["versions"]], ["Will Of The People"])

    def test_the_plain_get_hit_is_not_offered_twice(self):
        # The record /get matched comes back from /search under the same id.
        fake = _Lrclib(
            get=_record(1, synced=None, plain="from get"),
            searches=[[_record(1, synced=None, plain="from get"),
                       _record(2, synced=None, plain="other upload", album="Deluxe")]],
        )
        result = self._fetch(fake)
        self.assertEqual([v["lyrics"] for v in result["versions"]], ["from get", "other upload"])

    def test_plain_uploads_are_offered_when_nothing_is_synced(self):
        fake = _Lrclib(get=None, searches=[[
            _record(2, synced=None, plain="first"),
            _record(3, synced=None, plain="second", album="Deluxe"),
        ]])
        result = self._fetch(fake)
        self.assertEqual([v["lyrics"] for v in result["versions"]], ["first", "second"])
        self.assertIsNone(result["versions"][0]["synced"])

    def test_the_list_is_capped_so_a_cache_entry_stays_small(self):
        fake = _Lrclib(get=None, searches=[[
            _record(i, synced="[00:12.00] a", album=f"A{i}") for i in range(12)
        ]])
        self.assertEqual(len(self._fetch(fake)["versions"]), L.MAX_VERSIONS)

    def test_a_single_upload_still_yields_one_version(self):
        fake = _Lrclib(get=_record(1, synced="[00:12.00] a"))
        self.assertEqual(len(self._fetch(fake)["versions"]), 1)


class LrclibVersionOrderTest(unittest.TestCase):
    """Synced uploads lead, plain ones fill in behind them."""

    def _fetch(self, fake, duration="302"):
        with patch("services.lyrics.requests.get", side_effect=fake):
            return L._provider_lrclib("Muse", "Will Of The People", "Will Of The People", duration)

    def test_plain_uploads_follow_the_synced_ones(self):
        fake = _Lrclib(get=None, searches=[[
            _record(2, synced=None, plain="plain far", album="P1", duration=304),
            _record(3, synced="[00:12.00] a", album="S1", duration=302),
            _record(4, synced=None, plain="plain near", album="P2", duration=302),
            _record(5, synced="[00:12.00] b", album="S2", duration=303),
        ]])
        result = self._fetch(fake)
        self.assertEqual([v["album"] for v in result["versions"]], ["S1", "S2", "P2", "P1"])
        self.assertEqual(result["synced"], "[00:12.00] a")

    def test_a_cap_sheds_the_plain_ones_first(self):
        records = [_record(i, synced="[00:12.00] a", album=f"S{i}") for i in range(5)]
        records += [_record(90, synced=None, plain="plain", album="P")]
        result = self._fetch(_Lrclib(get=None, searches=[records]))
        self.assertEqual(len(result["versions"]), L.MAX_VERSIONS)
        self.assertNotIn("P", [v["album"] for v in result["versions"]])

    def test_the_signature_hit_is_offered_when_the_search_missed_it(self):
        # /get matched on the exact signature but is plain, so it is a version
        # in its own right even when the search that found the LRC ignores it.
        fake = _Lrclib(
            get=_record(1, synced=None, plain="from get", album="Signature"),
            searches=[[_record(2, synced="[00:12.00] a", album="Other")]],
        )
        result = self._fetch(fake)
        self.assertEqual([v["album"] for v in result["versions"]], ["Other", "Signature"])

    def test_the_signature_hit_is_not_repeated_when_the_search_returns_it(self):
        fake = _Lrclib(
            get=_record(1, synced=None, plain="from get"),
            searches=[[_record(2, synced="[00:12.00] a", album="Other"),
                       _record(1, synced=None, plain="from get")]],
        )
        result = self._fetch(fake)
        # Two versions, not three: the record is in both answers under one id.
        self.assertEqual([v["album"] for v in result["versions"]],
                         ["Other", "Will Of The People"])
        self.assertEqual(result["versions"][1]["lyrics"], "from get")
