"""Web fallback for lyrics, fetched on explicit user request.

Lyrion's `library.db` is read-only, so lyrics fetched from the web cannot be
stored there. We keep them in a process-local in-memory cache instead: gunicorn
runs a single worker with threads, so all requests share this dict. A positive
result is cached longer than a miss, so a track that simply has no lyrics online
is not retried on every click while a transient failure can recover sooner.
"""

import time
import threading

import requests

LRCLIB_BASE = "https://lrclib.net/api"
USER_AGENT = "lyrion-custom-data (https://github.com/werdeil)"

# How long a cached entry stays valid, in seconds.
TTL_HIT = 24 * 3600
TTL_MISS = 3600

_cache = {}
_cache_lock = threading.Lock()


def _cache_get(track_id):
    with _cache_lock:
        entry = _cache.get(track_id)
        if entry and entry["expires_at"] > time.time():
            return entry["value"]
        if entry:
            _cache.pop(track_id, None)
    return None


def _cache_set(track_id, value, ttl):
    with _cache_lock:
        _cache[track_id] = {"value": value, "expires_at": time.time() + ttl}


def _query_lrclib(artist, title, album, duration):
    """Ask LRCLIB for a track, returning its lyrics payload or None.

    Tries the exact `get` endpoint first (best match when artist/title/album/
    duration line up with their database), then falls back to `search` which is
    more forgiving about album and duration mismatches.
    """
    headers = {"User-Agent": USER_AGENT}

    params = {"artist_name": artist, "track_name": title}
    if album:
        params["album_name"] = album
    if duration:
        try:
            # Duration arrives as a string and may be fractional (e.g. "247.144").
            params["duration"] = int(float(duration))
        except (TypeError, ValueError):
            pass

    try:
        r = requests.get(f"{LRCLIB_BASE}/get", params=params, headers=headers, timeout=5)
        if r.status_code == 200:
            return r.json()
    except requests.RequestException:
        return None

    try:
        r = requests.get(
            f"{LRCLIB_BASE}/search",
            params={"artist_name": artist, "track_name": title},
            headers=headers,
            timeout=5,
        )
        if r.status_code == 200:
            results = r.json()
            if results:
                return results[0]
    except requests.RequestException:
        return None

    return None


def fetch_lyrics(track_id, artist, title, album=None, duration=None, force=False):
    """Resolve lyrics for the current track from the web, with caching.

    Returns a dict {"lyrics": str|None, "synced": str|None, "source": str}.
    `source` is "cache" or "lrclib" on a hit, "none" when nothing was found.
    """
    if not title or not artist:
        return {"lyrics": None, "synced": None, "source": "none"}

    cache_key = track_id or f"{artist}|{title}"
    if not force:
        cached = _cache_get(cache_key)
        if cached is not None:
            return {**cached, "source": "cache"}

    payload = _query_lrclib(artist, title, album, duration)
    if payload:
        result = {
            "lyrics": payload.get("plainLyrics"),
            "synced": payload.get("syncedLyrics"),
            "source": "lrclib",
        }
    else:
        result = {"lyrics": None, "synced": None, "source": "none"}

    found = bool(result["lyrics"] or result["synced"])
    _cache_set(cache_key, {"lyrics": result["lyrics"], "synced": result["synced"]},
               TTL_HIT if found else TTL_MISS)
    return result
