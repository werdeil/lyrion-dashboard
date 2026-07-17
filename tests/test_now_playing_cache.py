"""Tests for the now-playing snapshot cache and player selection.

Resolving which players are playing costs 1+N upstream requests; the result is
cached for NOW_PLAYING_TTL seconds shared across clients, the cached playback
position is aged so the karaoke stays accurate, a client can pin one player via
selected_id when several play at once, and the automatic path stays on the
player shown last while it keeps playing.

White-box tests: they stub services.lyrion's query helpers on purpose.
"""
# pylint: disable=protected-access

import os
import tempfile
import unittest

os.environ.setdefault("LYRION_HOST", "http://localhost:9000")
os.environ.setdefault("DB_DIR", tempfile.mkdtemp())
os.environ.setdefault("DB_PERSIST_DIR", tempfile.mkdtemp())

import services.lyrion as L  # pylint: disable=wrong-import-position


class NowPlayingCacheTest(unittest.TestCase):
    def setUp(self):
        self._reset_state()
        self._orig_players = L.get_players
        self._orig_now = L.get_now_playing
        self.players_calls = 0
        self.status_calls = []
        self.playing = {"p1": False, "p2": True}

        def fake_players():
            self.players_calls += 1
            return [{"playerid": "p1", "name": "Salon"},
                    {"playerid": "p2", "name": "Cuisine"}]

        def fake_now(player_id):
            self.status_calls.append(player_id)
            if self.playing.get(player_id):
                return {"playing": True, "mode": "play", "time": 10.0,
                        "duration": 200, "track_id": 42, "title": "Song"}
            return {"playing": False, "mode": "stop"}

        L.get_players = fake_players
        L.get_now_playing = fake_now

    def tearDown(self):
        L.get_players = self._orig_players
        L.get_now_playing = self._orig_now
        self._reset_state()

    @staticmethod
    def _reset_state():
        L._now_cache.update(players=None, fetched_at=0, expires_at=0)
        L._last_player.update(id=None, name=None)

    def test_result_is_cached_within_ttl(self):
        first = L.get_active_now_playing()
        second = L.get_active_now_playing()
        self.assertEqual(self.players_calls, 1)  # one enumeration for both
        self.assertEqual(first["player_id"], "p2")
        self.assertEqual(second["player_id"], "p2")

    def test_cached_position_is_aged(self):
        L.get_active_now_playing()
        # Pretend the snapshot was taken 1.5s ago: time must advance with it.
        L._now_cache["fetched_at"] -= 1.5
        aged = L.get_active_now_playing()
        self.assertAlmostEqual(aged["time"], 11.5, delta=0.2)

    def test_players_lists_every_playing_player(self):
        self.playing["p1"] = True  # both now playing
        result = L.get_active_now_playing()
        ids = [p["id"] for p in result["players"]]
        self.assertEqual(ids, ["p1", "p2"])  # Lyrion's order, preserved
        names = {p["id"]: p["name"] for p in result["players"]}
        self.assertEqual(names, {"p1": "Salon", "p2": "Cuisine"})

    def test_selection_pins_the_requested_player(self):
        self.playing["p1"] = True  # both playing, auto would pick p1
        result = L.get_active_now_playing(selected_id="p2")
        self.assertEqual(result["player_id"], "p2")
        self.assertTrue(result["selection_active"])

    def test_stale_selection_falls_back_to_auto(self):
        # Only p2 is playing; a pick for the idle p1 can't be honoured.
        result = L.get_active_now_playing(selected_id="p1")
        self.assertEqual(result["player_id"], "p2")
        self.assertFalse(result["selection_active"])

    def test_auto_stays_on_the_player_shown_last(self):
        self.playing["p1"] = True  # both playing
        first = L.get_active_now_playing()
        self.assertEqual(first["player_id"], "p1")  # first in order
        L._now_cache["expires_at"] = 0  # force a re-enumeration
        second = L.get_active_now_playing()
        self.assertEqual(second["player_id"], "p1")  # sticky, not flipped

    def test_auto_moves_on_when_the_shown_player_stops(self):
        self.playing["p1"] = True
        L.get_active_now_playing()  # locks onto p1
        L._now_cache["expires_at"] = 0
        self.playing["p1"] = False  # p1 stops, p2 keeps playing
        result = L.get_active_now_playing()
        self.assertEqual(result["player_id"], "p2")

    def test_explicit_selection_does_not_disturb_auto_stickiness(self):
        self.playing["p1"] = True  # both playing
        L.get_active_now_playing()  # auto locks onto p1
        L._now_cache["expires_at"] = 0
        L.get_active_now_playing(selected_id="p2")  # another client pins p2
        self.assertEqual(L._last_player["id"], "p1")  # auto still on p1

    def test_nothing_playing_clears_the_shortcut(self):
        self.playing["p2"] = False
        result = L.get_active_now_playing()
        self.assertFalse(result["playing"])
        self.assertEqual(result["players"], [])
        self.assertIsNone(L._last_player["id"])

    def test_callers_get_a_copy(self):
        L.get_active_now_playing()["title"] = "corrupted"
        self.assertEqual(L.get_active_now_playing()["title"], "Song")


if __name__ == "__main__":
    unittest.main()
