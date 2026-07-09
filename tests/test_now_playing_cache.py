"""Tests for the now-playing snapshot cache and last-player shortcut.

Resolving the active player costs 1+N upstream requests; the result is cached
for NOW_PLAYING_TTL seconds shared across clients, the cached playback
position is aged so the karaoke stays accurate, and the player found playing
last time is probed first so the steady state skips the enumeration.

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
        L._now_cache.update(value=None, fetched_at=0, expires_at=0)
        L._last_player.update(id=None, name=None)

    def test_result_is_cached_within_ttl(self):
        first = L.get_active_now_playing()
        second = L.get_active_now_playing()
        self.assertEqual(self.players_calls, 1)
        self.assertEqual(first["player_id"], "p2")
        self.assertEqual(second["player_id"], "p2")

    def test_cached_position_is_aged(self):
        L.get_active_now_playing()
        # Pretend the snapshot was taken 1.5s ago: time must advance with it.
        L._now_cache["fetched_at"] -= 1.5
        aged = L.get_active_now_playing()
        self.assertAlmostEqual(aged["time"], 11.5, delta=0.2)

    def test_last_player_shortcut_skips_the_enumeration(self):
        L.get_active_now_playing()
        L._now_cache["expires_at"] = 0  # expire the cache, keep the shortcut
        self.status_calls.clear()
        result = L.get_active_now_playing()
        self.assertEqual(self.players_calls, 1)  # no second enumeration
        self.assertEqual(self.status_calls, ["p2"])
        self.assertEqual(result["player_name"], "Cuisine")

    def test_shortcut_falls_back_to_enumeration_when_player_stops(self):
        L.get_active_now_playing()
        L._now_cache["expires_at"] = 0
        self.playing["p2"] = False
        self.playing["p1"] = True
        result = L.get_active_now_playing()
        self.assertEqual(result["player_id"], "p1")
        self.assertEqual(self.players_calls, 2)

    def test_nothing_playing_clears_the_shortcut(self):
        self.playing["p2"] = False
        result = L.get_active_now_playing()
        self.assertFalse(result["playing"])
        self.assertIsNone(L._last_player["id"])

    def test_callers_get_a_copy(self):
        L.get_active_now_playing()["title"] = "corrupted"
        self.assertEqual(L.get_active_now_playing()["title"], "Song")


if __name__ == "__main__":
    unittest.main()
