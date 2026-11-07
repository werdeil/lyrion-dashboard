"""Tests for the Musixmatch provider on its signed web API, with the operator's account token."""
# The env scaffolding is intentionally the same as in the other tests; that
# repetition is what keeps each file standalone.
# pylint: disable=duplicate-code,protected-access

import base64
import hashlib
import hmac
import os
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

os.environ.setdefault("DB_DIR", tempfile.mkdtemp())
os.environ.setdefault("DB_PERSIST_DIR", tempfile.mkdtemp())

import services.lyrics as L  # pylint: disable=wrong-import-position


def _answer(body, status=200):
    return {"message": {"header": {"status_code": status}, "body": body}}


def _track(track_id, name, artist, length, subtitles=1, lyrics=1):
    return {"track": {
        "track_id": track_id, "track_name": name, "artist_name": artist, "album_name": "Album",
        "track_length": length, "has_subtitles": subtitles, "has_lyrics": lyrics, "instrumental": 0,
    }}


def _subtitle(body, language=None):
    entry = {"subtitle_body": body}
    if language:
        entry["subtitle_language"] = language
    return {"subtitle": entry}


NOKIA = _track(226291677, "NOKIA", "Drake", 241)
LYRICS = _answer({"lyrics": {"lyrics_body": "la la la", "lyrics_language": "en"}})
SUBTITLES = _answer({"subtitle_list": [_subtitle("[00:01.00] la la la", "en")]})


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self.payload = payload
        self.status_code = status_code

    def json(self):
        if isinstance(self.payload, Exception):
            raise self.payload
        return self.payload


class MusixmatchTest(unittest.TestCase):
    def setUp(self):
        L._mxm_key["value"] = {}
        self.routes = {}
        self.calls = []
        env = patch.dict(os.environ, {"MUSIXMATCH_TOKEN": "tok"})
        fetch_key = patch.object(L, "_mxm_fetch_key", return_value=("secret", "1.2.3"))
        get = patch.object(L.requests, "get", side_effect=self._get)
        for p in (env, get):
            p.start()
            self.addCleanup(p.stop)
        self.fetch_key = fetch_key.start()
        self.addCleanup(fetch_key.stop)

    def _get(self, url, **_kwargs):
        endpoint = urlsplit(url).path.rsplit("/", 1)[-1]
        self.calls.append(url)
        answer = self.routes.get(endpoint, FakeResponse(_answer([], 404)))
        return answer if isinstance(answer, FakeResponse) else FakeResponse(answer)

    def _fetch(self, artist="Muse", title="Space Debris", duration="247"):
        return L._provider_musixmatch(artist, title, None, duration)

    def _endpoints(self):
        return [urlsplit(u).path.rsplit("/", 1)[-1] for u in self.calls]

    def test_no_token_skips_the_provider_with_a_single_warning(self):
        L._mxm_warned.clear()
        with patch.dict(os.environ, {"MUSIXMATCH_TOKEN": ""}), \
             self.assertLogs("services.lyrics", "WARNING") as logs:
            names = [n for n, _ in L._enabled_providers()]
            L._enabled_providers()
            self.assertIsNone(self._fetch())
        self.assertNotIn("musixmatch", names)
        self.assertIn("lrclib", names)
        self.assertEqual(len(logs.records), 1)
        self.assertIn("MUSIXMATCH_TOKEN", logs.output[0])
        self.assertEqual(self.calls, [])

    def test_token_keeps_the_provider_in_the_default_order(self):
        names = [n for n, _ in L._enabled_providers()]
        self.assertEqual(names[:2], ["lrclib", "musixmatch"])

    def test_refused_token_is_an_outage_after_one_key_reload(self):
        self.routes["track.search"] = _answer({}, 401)
        with self.assertRaises(L.ProviderUnavailable) as caught:
            self._fetch()
        self.assertIn("MUSIXMATCH_TOKEN", str(caught.exception))
        self.assertEqual(self.fetch_key.call_count, 2)
        with self.assertRaises(L.ProviderUnavailable):
            self._fetch()
        self.assertEqual(self.fetch_key.call_count, 2)

    def test_http_403_is_an_outage(self):
        self.routes["track.search"] = FakeResponse(ValueError("not json"), 403)
        with self.assertRaises(L.ProviderUnavailable):
            self._fetch()

    def test_rotated_signing_key_is_reloaded_and_retried(self):
        answers = iter([FakeResponse(_answer({}, 401)), FakeResponse(_answer({"track_list": []}))])
        with patch.object(L.requests, "get", side_effect=lambda url, **_: next(answers)):
            self.assertIsNone(self._fetch())
        self.assertEqual(self.fetch_key.call_count, 2)

    def test_closest_matching_candidate_wins(self):
        self.routes["track.search"] = _answer({"track_list": [
            _track(1, "Hysteria", "Muse", 227),
            _track(2, "Space Debris", "Muse", 249),
            _track(3, "Space Debris", "Muse", 247),
            _track(4, "Space Debris", "Muse", 400),
        ]})
        self.routes["track.lyrics.get"] = LYRICS
        self.routes["track.subtitles.get"] = SUBTITLES
        self.assertIsNotNone(self._fetch())
        self.assertIn("track_id=3", self.calls[1])

    def test_a_synced_candidate_beats_a_plain_one_of_closer_length(self):
        self.routes["track.search"] = _answer({"track_list": [
            _track(3, "Space Debris", "Muse", 247, subtitles=0),
            _track(2, "Space Debris", "Muse", 249),
        ]})
        self.routes["track.lyrics.get"] = LYRICS
        self.routes["track.subtitles.get"] = SUBTITLES
        found = self._fetch()
        self.assertEqual(found["synced"], "[00:01.00] la la la")
        self.assertIn("track_id=2", self.calls[1])

    def test_lrc_is_returned_alongside_the_plain_text(self):
        self.routes["track.search"] = _answer({"track_list": [_track(3, "Space Debris", "Muse", 247)]})
        self.routes["track.lyrics.get"] = LYRICS
        self.routes["track.subtitles.get"] = SUBTITLES
        found = self._fetch()
        self.assertEqual(found["synced"], "[00:01.00] la la la")
        self.assertEqual(found["lyrics"], "la la la")
        subtitle_call = parse_qs(urlsplit(self.calls[-1]).query)
        self.assertEqual(subtitle_call["subtitle_format"], ["lrc"])

    def test_plain_only_track_skips_the_subtitle_call(self):
        self.routes["track.search"] = _answer({"track_list": [_track(3, "Space Debris", "Muse", 247, subtitles=0)]})
        self.routes["track.lyrics.get"] = LYRICS
        found = self._fetch()
        self.assertIsNone(found["synced"])
        self.assertNotIn("track.subtitles.get", self._endpoints())

    def test_translated_subtitle_is_skipped_for_the_original(self):
        self.routes["track.search"] = _answer({"track_list": [_track(3, "Space Debris", "Muse", 247)]})
        self.routes["track.lyrics.get"] = LYRICS
        self.routes["track.subtitles.get"] = _answer({"subtitle_list": [
            _subtitle("[00:01.00] nie zapomnij", "pl"), _subtitle("[00:01.00] la la la", "en"),
        ]})
        self.assertEqual(self._fetch()["synced"], "[00:01.00] la la la")

    def test_another_song_is_never_returned(self):
        self.routes["track.search"] = _answer({"track_list": [_track(9, "Nu Ma Uita", "Elena", 199)]})
        with self.assertLogs("services.lyrics", "INFO") as logs:
            self.assertIsNone(self._fetch(duration=None))
        self.assertIn("(length unknown)", logs.output[0])
        self.assertNotIn("Nones", logs.output[0])
        self.assertEqual(self._endpoints(), ["track.search"])

    def test_placeholder_answer_is_an_outage(self):
        self.routes["track.search"] = _answer({"track_list": [NOKIA]})
        with self.assertRaises(L.ProviderUnavailable) as caught:
            self._fetch("Henri Salvador", "Embrasse-la", "162")
        self.assertIn("NOKIA", str(caught.exception))

    def test_placeholder_track_asked_for_is_kept(self):
        self.routes["track.search"] = _answer({"track_list": [NOKIA]})
        self.routes["track.lyrics.get"] = LYRICS
        self.routes["track.subtitles.get"] = SUBTITLES
        self.assertEqual(self._fetch("Drake", "NOKIA", "241")["lyrics"], "la la la")

    def test_empty_search_has_no_match(self):
        self.routes["track.search"] = _answer([])
        self.assertIsNone(self._fetch())

    def test_overloaded_answer_is_an_outage(self):
        self.routes["track.search"] = FakeResponse(ValueError("not json"), 503)
        with self.assertRaises(L.ProviderUnavailable):
            self._fetch()

    def test_unreachable_is_an_outage(self):
        with patch.object(L.requests, "get", side_effect=L.requests.ConnectionError("down")):
            with self.assertRaises(L.ProviderUnavailable):
                self._fetch()

    def test_request_is_signed_with_the_token_and_the_date(self):
        with patch.object(L.time, "strftime", return_value="20261101"):
            url = L._mxm_signed_url("track.search", {"q_track": "Space Debris"}, "tok", "secret")
        unsigned, signature = url.split("&signature=", 1)
        query = parse_qs(urlsplit(url).query)
        self.assertEqual(query["app_id"], ["mxm-com-v1.0"])
        self.assertEqual(query["usertoken"], ["tok"])
        self.assertEqual(query["signature_protocol"], ["sha256"])
        expected = base64.b64encode(hmac.new(b"secret", (unsigned + "20261101").encode(), hashlib.sha256).digest())
        self.assertEqual(query["signature"], [expected.decode()])
        self.assertTrue(signature.endswith("&signature_protocol=sha256"))


class SigningKeyTest(unittest.TestCase):
    def test_key_is_read_from_the_site_script(self):
        encoded = base64.b64encode(b"s3cret").decode()[::-1]
        page = type("R", (), {"text": '<script src="/_next/static/chunks/pages/_app-abc.js"></script>'})
        script = type("R", (), {"text": f'x=Buffer.from( "{encoded}" .split("")'})
        urls = []

        def get(url, **_kwargs):
            urls.append(url)
            return page if url.endswith("/search") else script

        with patch.object(L.requests, "get", side_effect=get):
            self.assertEqual(L._mxm_fetch_key(), ("s3cret", None))
        self.assertEqual(urls[1], "https://www.musixmatch.com/_next/static/chunks/pages/_app-abc.js")

    def test_site_without_the_script_is_an_outage(self):
        page = type("R", (), {"text": "<html></html>", "status_code": 200})
        with patch.object(L.requests, "get", return_value=page):
            with self.assertRaises(L.ProviderUnavailable):
                L._mxm_fetch_key()


class LengthLabelTest(unittest.TestCase):
    def test_a_missing_length_is_named(self):
        self.assertEqual(L._length_label(None), "length unknown")
        self.assertEqual(L._length_label("162.4"), "162s")


if __name__ == "__main__":
    unittest.main()
