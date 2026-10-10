"""Tests for the NetEase Cloud Music provider: picking the right search hit and cleaning its LRC."""
# The env scaffolding is intentionally the same as in the other tests; that
# repetition is what keeps each file standalone.
# pylint: disable=duplicate-code,protected-access

import os
import tempfile
import unittest
from unittest.mock import patch

import requests

os.environ.setdefault("DB_DIR", tempfile.mkdtemp())
os.environ.setdefault("DB_PERSIST_DIR", tempfile.mkdtemp())

import services.lyrics as L  # pylint: disable=wrong-import-position


def _song(song_id, name, artists, millis, album="Absolution"):
    return {"id": song_id, "name": name, "ar": [{"name": a} for a in artists],
            "al": {"name": album}, "dt": millis}


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self.payload = payload
        self.status_code = status_code

    def json(self):
        return self.payload


class NeteaseTest(unittest.TestCase):
    def _fetch(self, songs, lyric=None, artist="Muse", title="Space Debris", duration="247"):
        responses = {
            "search": FakeResponse({"result": {"songs": songs}, "code": 200}),
            "lyric": FakeResponse({"lrc": {"lyric": lyric}, "code": 200}),
        }
        calls = []

        def fake_get(url, **kwargs):
            calls.append((url, kwargs.get("params")))
            return responses["lyric" if url.endswith("/song/lyric") else "search"]

        with patch.object(L.requests, "get", side_effect=fake_get):
            found = L._provider_netease(artist, title, None, duration)
        return found, calls

    def test_synced_lyrics_with_credits_dropped(self):
        lrc = "[00:00.000] 作词 : Matt Bellamy\n[00:01.000] 作曲 : Matt Bellamy\n[00:12.34]la la la"
        found, _ = self._fetch([_song(7, "Space Debris", ["Muse"], 247000)], lrc)
        self.assertEqual(found["synced"], "[00:12.34]la la la")
        self.assertIsNone(found["lyrics"])
        self.assertEqual(found["meta"]["duration"], 247.0)

    def test_untimed_text_is_plain(self):
        found, _ = self._fetch([_song(7, "Space Debris", ["Muse"], 247000)], "la la la\nla la")
        self.assertEqual(found["lyrics"], "la la la\nla la")
        self.assertIsNone(found["synced"])

    def test_another_song_is_dropped_without_fetching_lyrics(self):
        found, calls = self._fetch([_song(9, "Nu Ma Uita", ["Elena"], 199000)], "[00:01.00]nu ma uita")
        self.assertIsNone(found)
        self.assertEqual(len(calls), 1)

    def test_nearest_length_among_matches_wins(self):
        songs = [
            _song(1, "Space Debris (Live)", ["Muse"], 249000),
            _song(2, "Space Debris", ["Muse"], 300000),
            _song(3, "Space Debris", ["Muse"], 247200),
        ]
        _, calls = self._fetch(songs, "[00:01.00]la")
        self.assertEqual(calls[-1][1]["id"], 3)

    def test_any_credited_artist_matches(self):
        found, _ = self._fetch([_song(5, "Space Debris", ["Someone", "Muse"], 247000)], "[00:01.00]la")
        self.assertEqual(found["meta"]["artist"], "Muse")

    def test_no_lyrics_collected(self):
        with patch.object(L.requests, "get", side_effect=[
            FakeResponse({"result": {"songs": [_song(7, "Space Debris", ["Muse"], 247000)]}, "code": 200}),
            FakeResponse({"nolyric": True, "code": 200}),
        ]):
            self.assertIsNone(L._provider_netease("Muse", "Space Debris", None, "247"))

    def test_blocked_search_finds_nothing(self):
        for payload in ({"result": "35b1748964af8a7c", "code": 200}, {"code": -462, "message": "blocked"}):
            with patch.object(L.requests, "get", return_value=FakeResponse(payload)) as get:
                self.assertIsNone(L._provider_netease("Muse", "Space Debris", None, "247"))
            self.assertEqual(get.call_count, 1)

    def test_unreachable_raises(self):
        with patch.object(L.requests, "get", side_effect=requests.ConnectionError("down")):
            with self.assertRaises(L.ProviderUnavailable):
                L._provider_netease("Muse", "Space Debris", None, "247")

    def test_registered_before_genius(self):
        order = L.DEFAULT_PROVIDER_ORDER.split(",")
        self.assertLess(order.index("netease"), order.index("genius"))


if __name__ == "__main__":
    unittest.main()
