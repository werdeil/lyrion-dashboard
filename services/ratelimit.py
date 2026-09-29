"""Tiny in-process rate limiting, no external dependency.

Plain dicts under a lock, sized for a LAN's handful of clients; idle entries are
swept on every call, so the maps stay bounded.
"""

import threading
import time


class RateLimiter:
    """Allow at most `limit` calls per sliding `window` seconds per key."""

    def __init__(self, limit, window):
        self.limit = limit
        self.window = window
        self._hits = {}  # key -> list of call timestamps within the window
        self._lock = threading.Lock()

    def allow(self, key):
        now = time.time()
        cutoff = now - self.window
        with self._lock:
            for idle in [k for k, ts in self._hits.items() if ts[-1] <= cutoff]:
                del self._hits[idle]
            hits = [t for t in self._hits.get(key, []) if t > cutoff]
            if len(hits) >= self.limit:
                self._hits[key] = hits
                return False
            hits.append(now)
            self._hits[key] = hits
            return True


class Cooldown:
    """Allow a key at most once per `interval` seconds."""

    def __init__(self, interval):
        self.interval = interval
        self._last = {}  # key -> timestamp of the last allowed call
        self._lock = threading.Lock()

    def allow(self, key):
        now = time.time()
        cutoff = now - self.interval
        with self._lock:
            for idle in [k for k, t in self._last.items() if t <= cutoff]:
                del self._last[idle]
            if self._last.get(key, 0) > cutoff:
                return False
            self._last[key] = now
            return True

    def remaining(self, key):
        """Seconds before `key` is allowed again, 0.0 when it already is."""
        with self._lock:
            return max(0.0, self.interval - (time.time() - self._last.get(key, 0)))
