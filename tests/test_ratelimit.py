"""Tests for the in-process rate limiting primitives.

RateLimiter allows `limit` calls per sliding window per key; Cooldown allows a
key once per interval. Both sweep idle entries on every call so their state
stays bounded by the active clients.

White-box tests: they rewind internal timestamps rather than sleeping.
"""
# pylint: disable=protected-access

import unittest

from services.ratelimit import RateLimiter, Cooldown


class RateLimiterTest(unittest.TestCase):
    def test_allows_up_to_limit_then_denies(self):
        rl = RateLimiter(limit=2, window=60)
        self.assertTrue(rl.allow("ip1"))
        self.assertTrue(rl.allow("ip1"))
        self.assertFalse(rl.allow("ip1"))

    def test_keys_are_independent(self):
        rl = RateLimiter(limit=1, window=60)
        self.assertTrue(rl.allow("ip1"))
        self.assertTrue(rl.allow("ip2"))
        self.assertFalse(rl.allow("ip1"))

    def test_window_slides(self):
        rl = RateLimiter(limit=1, window=60)
        self.assertTrue(rl.allow("ip1"))
        # Rewind the recorded hit past the window: quota is available again.
        rl._hits["ip1"] = [t - 61 for t in rl._hits["ip1"]]
        self.assertTrue(rl.allow("ip1"))

    def test_idle_keys_are_swept(self):
        rl = RateLimiter(limit=1, window=60)
        rl.allow("old")
        rl._hits["old"] = [t - 61 for t in rl._hits["old"]]
        rl.allow("new")
        self.assertEqual(set(rl._hits), {"new"})


class CooldownTest(unittest.TestCase):
    def test_second_call_within_interval_is_denied(self):
        cd = Cooldown(interval=30)
        self.assertTrue(cd.allow("track1"))
        self.assertFalse(cd.allow("track1"))

    def test_keys_are_independent(self):
        cd = Cooldown(interval=30)
        self.assertTrue(cd.allow("track1"))
        self.assertTrue(cd.allow("track2"))

    def test_allowed_again_after_interval(self):
        cd = Cooldown(interval=30)
        self.assertTrue(cd.allow("track1"))
        cd._last["track1"] -= 31
        self.assertTrue(cd.allow("track1"))

    def test_idle_keys_are_swept(self):
        cd = Cooldown(interval=30)
        cd.allow("old")
        cd._last["old"] -= 31
        cd.allow("new")
        self.assertEqual(set(cd._last), {"new"})


if __name__ == "__main__":
    unittest.main()
