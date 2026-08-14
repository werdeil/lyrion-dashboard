"""Web fallback for lyrics, fetched on explicit user request.

Lyrion's `library.db` is read-only, so lyrics fetched from the web cannot be
stored there. We keep them in a process-local in-memory cache instead: gunicorn
runs a single worker with threads, so all requests share this dict. A positive
result is cached longer than a miss, so a track that simply has no lyrics online
is not retried on every click while a transient failure can recover sooner.

Several providers are tried in order (configurable via `LYRICS_PROVIDERS`); the
first one that returns anything wins. LRCLIB and Musixmatch can return synced
lyrics (LRC), so they come before Genius, which only offers plain text.
"""

import logging
import os
import re
import time
import threading
import unicodedata
from collections import OrderedDict

import requests

log = logging.getLogger(__name__)

try:
    from bs4 import BeautifulSoup
except ImportError:  # Genius scraping is skipped if bs4 isn't installed.
    BeautifulSoup = None

LRCLIB_BASE = "https://lrclib.net/api"
MXM_BASE = "https://apic-desktop.musixmatch.com/ws/1.1"
USER_AGENT = "lyrion-custom-data (https://github.com/werdeil)"
# A browser-like UA avoids being blocked when scraping Genius / talking to the
# Musixmatch desktop endpoint.
BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)

# How long a cached entry stays valid, in seconds.
TTL_HIT = 24 * 3600
TTL_MISS = 3600

# LRCLIB can get slow under load (8-10s on busy evenings); this is a
# user-initiated fallback, not a hot path, so give it a generous budget.
LRCLIB_TIMEOUT = int(os.getenv("LRCLIB_TIMEOUT", "15"))

# When verifying a result against the requested track (opt-in, used by the batch
# CLI), how far the provider's reported track length may drift from the file's
# own duration before we treat it as a different recording. Seconds; overridable
# for libraries whose durations are noisy.
VERIFY_DURATION_TOLERANCE = int(os.getenv("LYRICS_VERIFY_DURATION_TOLERANCE", "3"))

# The cache key includes client-supplied fields, so the cache must stay bounded.
CACHE_MAX_ENTRIES = 1000
# Metadata fields longer than this are refused.
MAX_FIELD_LEN = 512

_cache = OrderedDict()
_cache_lock = threading.Lock()


class ProviderUnavailable(Exception):
    """A provider could not be reached, as opposed to having no match to give."""


def _cache_get(key):
    with _cache_lock:
        entry = _cache.get(key)
        if entry and entry["expires_at"] > time.time():
            _cache.move_to_end(key)
            return entry["value"]
        if entry:
            _cache.pop(key, None)
    return None


def _cache_set(key, value, ttl):
    with _cache_lock:
        now = time.time()
        for expired in [k for k, e in _cache.items() if e["expires_at"] <= now]:
            del _cache[expired]
        _cache.pop(key, None)
        while len(_cache) >= CACHE_MAX_ENTRIES:
            _cache.popitem(last=False)
        _cache[key] = {"value": value, "expires_at": now + ttl}


def _elapsed_ms(started):
    return int((time.monotonic() - started) * 1000)


def _int_duration(duration):
    """Coerce a possibly-fractional string duration to whole seconds, or None."""
    if not duration:
        return None
    try:
        # Duration arrives as a string and may be fractional (e.g. "247.144").
        return int(float(duration))
    except (TypeError, ValueError):
        return None


# --- Providers -------------------------------------------------------------
# Each provider takes (artist, title, album, duration) and returns either a
# dict {"lyrics": str|None, "synced": str|None, "meta": dict|None} when it found
# something, or None. "meta" carries the matched candidate's own
# {artist, title, album, duration} so the caller can verify the result really
# corresponds to the requested track (see _matches_request); providers set the
# fields they can and leave the rest None.


def _duration_close(candidate, seconds):
    """True when a candidate's own duration allows it to be the same recording.

    A candidate that carries no duration, or a request that doesn't know its
    own, can't be told apart this way and is left to the caller's other checks.
    """
    got = _int_duration(candidate.get("duration"))
    return seconds is None or got is None or abs(got - seconds) <= VERIFY_DURATION_TOLERANCE


def _provider_lrclib(artist, title, album, duration):
    """Ask LRCLIB for a track, preferring a synced (LRC) record of that recording.

    Tries the exact `get` endpoint first (best match when artist/title/album/
    duration line up with their database), then falls back to `search` which is
    more forgiving about album and duration mismatches. LRCLIB stores lyrics per
    upload, so the signature `get` matches can hold plain text while another
    upload of the same track carries an LRC: a plain-only hit is kept only as a
    fallback while the search looks for a synced one. Timestamps only fit the
    recording they were made for, so a synced candidate is taken on its duration
    matching, and one that doesn't match still serves as plain text. Raises
    ProviderUnavailable when LRCLIB can't be reached at all.
    """
    headers = {"User-Agent": USER_AGENT}

    params = {"artist_name": artist, "track_name": title}
    if album:
        params["album_name"] = album
    seconds = _int_duration(duration)
    if seconds is not None:
        params["duration"] = seconds

    payload = None
    try:
        r = requests.get(f"{LRCLIB_BASE}/get", params=params, headers=headers, timeout=LRCLIB_TIMEOUT)
        if r.status_code == 200:
            payload = r.json()
        else:
            log.debug("lrclib: get returned HTTP %s, falling back to search", r.status_code)
    except requests.RequestException as exc:
        log.debug("lrclib: get failed (%s), falling back to search", exc)
        payload = None

    if payload is None or not payload.get("syncedLyrics"):
        base = {"artist_name": artist, "track_name": title}
        # Try an album-filtered search first for precision, then retry without
        # the album. The search fallback exists precisely to forgive album/
        # duration mismatches, so we must not let a differing album name (e.g.
        # a "(Deluxe)" edition) suppress an otherwise valid hit.
        attempts = [{**base, "album_name": album}, base] if album else [base]
        for search_params in attempts:
            try:
                r = requests.get(
                    f"{LRCLIB_BASE}/search",
                    params=search_params,
                    headers=headers,
                    timeout=LRCLIB_TIMEOUT,
                )
            except requests.RequestException as exc:
                raise ProviderUnavailable("lrclib") from exc
            if r.status_code != 200:
                log.info("lrclib: search returned HTTP %s", r.status_code)
                continue
            results = r.json() or []
            close = [c for c in results if _duration_close(c, seconds)]
            synced = [c for c in close if c.get("syncedLyrics")]
            log.info(
                "lrclib: search (album=%r) returned %d candidate(s), %d synced, %d of this length",
                search_params.get("album_name"),
                len(results), sum(1 for c in results if c.get("syncedLyrics")), len(close),
            )
            if synced:
                payload = synced[0]
                break
            if payload is None and (close or results):
                payload = (close or results)[0]

    if not payload:
        return None
    # Another recording's LRC would run against the wrong timeline, so only its
    # words are kept; the caller then shows them as plain lyrics.
    synced_text = payload.get("syncedLyrics") if _duration_close(payload, seconds) else None
    log.debug(
        "lrclib: record %s (%r, %ss), synced=%s",
        payload.get("id"), payload.get("albumName"), payload.get("duration"),
        bool(synced_text),
    )
    return {
        "lyrics": payload.get("plainLyrics"),
        "synced": synced_text,
        "meta": {
            "artist": payload.get("artistName"),
            "title": payload.get("trackName"),
            "album": payload.get("albumName"),
            "duration": payload.get("duration"),
        },
    }


_mxm_token = {"value": None, "expires_at": 0}
_mxm_lock = threading.Lock()
_MXM_HEADERS = {
    "authority": "apic-desktop.musixmatch.com",
    "cookie": "AWSELB=0",
    "User-Agent": BROWSER_UA,
}


def _musixmatch_token():
    """Return a usable Musixmatch user token, cached in-process.

    A token can be supplied via `MUSIXMATCH_TOKEN`; otherwise we fetch the one
    the web desktop app uses. Tokens are valid for hours, so we cache it and
    refresh lazily. Returns None when Musixmatch refuses to issue a usable
    token, and raises ProviderUnavailable when it can't be reached.
    """
    with _mxm_lock:
        if _mxm_token["value"] and _mxm_token["expires_at"] > time.time():
            return _mxm_token["value"]

        override = os.getenv("MUSIXMATCH_TOKEN")
        if override:
            _mxm_token.update(value=override, expires_at=time.time() + 9 * 3600)
            return override

        try:
            r = requests.get(
                f"{MXM_BASE}/token.get",
                params={"app_id": "web-desktop-app-v1.0"},
                headers=_MXM_HEADERS,
                timeout=5,
            )
            token = (r.json().get("message", {}).get("body", {}) or {}).get("user_token")
        except requests.RequestException as exc:
            raise ProviderUnavailable("musixmatch") from exc
        except (ValueError, AttributeError) as exc:
            log.warning("musixmatch: token endpoint returned an unusable body (%s)", exc)
            return None

        # Musixmatch hands out a sentinel token when rate-limiting; reject it.
        if not token or token.startswith("UpgradeOnly"):
            log.warning("musixmatch: no usable token (rate-limited), provider skipped")
            return None
        _mxm_token.update(value=token, expires_at=time.time() + 9 * 3600)
        return token


def _provider_musixmatch(artist, title, album, duration):
    token = _musixmatch_token()
    if not token:
        return None

    params = {
        "format": "json",
        "namespace": "lyrics_richsynched",
        "subtitle_format": "lrc",
        "app_id": "web-desktop-app-v1.0",
        "usertoken": token,
        "q_artist": artist,
        "q_track": title,
    }
    if album:
        params["q_album"] = album
    seconds = _int_duration(duration)
    if seconds is not None:
        params["q_duration"] = seconds

    try:
        r = requests.get(
            f"{MXM_BASE}/macro.subtitles.get", params=params, headers=_MXM_HEADERS, timeout=6
        )
        calls = r.json().get("message", {}).get("body", {})
        calls = calls.get("macro_calls", {}) if isinstance(calls, dict) else {}
    except requests.RequestException as exc:
        raise ProviderUnavailable("musixmatch") from exc
    except (ValueError, AttributeError) as exc:
        log.debug("musixmatch: unreadable response (%s)", exc)
        return None

    def _body(call):
        node = calls.get(call, {})
        body = node.get("message", {}).get("body") if isinstance(node, dict) else None
        return body if isinstance(body, dict) else {}

    synced = None
    subtitle_list = _body("track.subtitles.get").get("subtitle_list")
    if subtitle_list:
        synced = subtitle_list[0].get("subtitle", {}).get("subtitle_body") or None

    lyrics = _body("track.lyrics.get").get("lyrics", {}).get("lyrics_body") or None

    if lyrics or synced:
        # The matcher echoes the track it actually matched; keep it so the
        # caller can confirm it lines up with what we asked for.
        track = _body("matcher.track.get").get("track", {})
        return {
            "lyrics": lyrics,
            "synced": synced,
            "meta": {
                "artist": track.get("artist_name"),
                "title": track.get("track_name"),
                "album": track.get("album_name"),
                "duration": track.get("track_length"),
            },
        }
    return None


def _parse_genius_html(html):
    if BeautifulSoup is None:
        return None
    soup = BeautifulSoup(html, "html.parser")
    containers = soup.select('[data-lyrics-container="true"]')
    if not containers:
        return None
    # Genius wraps non-lyrics noise (contributor counts, translation links,
    # the song description) in elements flagged for exclusion — drop them.
    for noise in soup.select('[data-exclude-from-selection="true"]'):
        noise.decompose()
    text = "\n".join(c.get_text(separator="\n") for c in containers).strip()
    return text or None


def _provider_genius(artist, title, album, _duration):
    if BeautifulSoup is None:
        log.warning("genius: beautifulsoup4 is not installed, provider skipped")
        return None

    # Genius search is free-text only (no album field), so we fold the album
    # into the query. Its matcher tolerates the extra terms and it helps
    # disambiguate re-recordings/live versions that share an artist and title.
    query = f"{artist} {title} {album}" if album else f"{artist} {title}"
    try:
        r = requests.get(
            "https://genius.com/api/search/multi",
            params={"q": query},
            headers={"User-Agent": BROWSER_UA},
            timeout=6,
        )
        sections = r.json().get("response", {}).get("sections", [])
    except requests.RequestException as exc:
        raise ProviderUnavailable("genius") from exc
    except (ValueError, AttributeError) as exc:
        log.debug("genius: unreadable search response (%s)", exc)
        return None

    url = None
    hit_meta = None
    for section in sections:
        if section.get("type") != "song":
            continue
        for hit in section.get("hits", []):
            result = hit.get("result", {})
            url = result.get("url")
            if url:
                # Genius exposes no reliable duration/album on a search hit, so
                # verification can only lean on title + primary artist.
                hit_meta = {
                    "artist": (result.get("primary_artist") or {}).get("name"),
                    "title": result.get("title"),
                    "album": None,
                    "duration": None,
                }
                break
        if url:
            break
    if not url:
        log.debug("genius: no song hit for %r", query)
        return None

    try:
        page = requests.get(url, headers={"User-Agent": BROWSER_UA}, timeout=6)
    except requests.RequestException as exc:
        raise ProviderUnavailable("genius") from exc
    if page.status_code != 200:
        log.info("genius: song page %s returned HTTP %s", url, page.status_code)
        return None

    text = _parse_genius_html(page.text)
    if text:
        return {"lyrics": text, "synced": None, "meta": hit_meta}
    log.info("genius: no lyrics container found on %s (page layout changed or bot-blocked)", url)
    return None


PROVIDERS = {
    "lrclib": _provider_lrclib,
    "musixmatch": _provider_musixmatch,
    "genius": _provider_genius,
}
DEFAULT_PROVIDER_ORDER = "lrclib,musixmatch,genius"


def _enabled_providers():
    """Resolve the ordered provider list from `LYRICS_PROVIDERS`.

    Unknown names are ignored, so an operator can disable a flaky provider just
    by dropping it from the list.
    """
    raw = os.getenv("LYRICS_PROVIDERS", DEFAULT_PROVIDER_ORDER)
    names = [n.strip().lower() for n in raw.split(",") if n.strip()]
    return [(n, PROVIDERS[n]) for n in names if n in PROVIDERS]


# Qualifiers and credits that should not defeat a match: parenthetical/bracketed
# notes ("(Remastered 2011)", "[Live]") and everything from a "feat." onwards.
_PAREN_RE = re.compile(r"[\(\[\{].*?[\)\]\}]")
_FEAT_RE = re.compile(r"\b(feat|ft|featuring)\b.*", re.IGNORECASE)
_NONALNUM_RE = re.compile(r"[^a-z0-9]+")


def _normalize(text):
    """Fold a title/artist to a comparable core: accents stripped, lower-cased,
    parenthetical qualifiers and "feat." credits removed, punctuation collapsed."""
    if not text:
        return ""
    text = unicodedata.normalize("NFKD", str(text))
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.lower()
    text = _PAREN_RE.sub(" ", text)
    text = _FEAT_RE.sub(" ", text)
    text = _NONALNUM_RE.sub(" ", text)
    return " ".join(text.split())


def _matches_request(meta, artist, title, duration):
    """True if a provider's matched candidate lines up with the requested track.

    Title and artist must be equal after normalisation. When both durations are
    known they must fall within VERIFY_DURATION_TOLERANCE seconds — the surest
    way to tell the real recording from a live/remix/cover of the same song. A
    candidate that carries no duration (e.g. Genius) is accepted on title +
    artist alone, since that is all it can offer.
    """
    if not meta:
        return False
    if _normalize(meta.get("title")) != _normalize(title):
        return False
    if _normalize(meta.get("artist")) != _normalize(artist):
        return False
    return _duration_close(meta, _int_duration(duration))


def _search_providers(artist, title, album, duration, verify):
    """Try each enabled provider in order and return the first usable result.

    Same shape as fetch_lyrics' return value, without any caching: "unavailable"
    means not one provider answered, which the caller must not confuse with a
    search that ran and came up empty.
    """
    rejected = False
    unreachable = 0
    providers = _enabled_providers()
    if not providers:
        log.warning("lyrics: no usable provider in LYRICS_PROVIDERS=%r", os.getenv("LYRICS_PROVIDERS"))
    for name, provider in providers:
        started = time.monotonic()
        try:
            found = provider(artist, title, album, duration)
        except ProviderUnavailable as exc:
            unreachable += 1
            log.warning("lyrics: %s unreachable after %d ms (%s)", name, _elapsed_ms(started), exc.__cause__ or exc)
            continue
        except Exception as exc:
            # A misbehaving provider must not break the chain.
            log.warning("lyrics: %s failed after %d ms (%s: %s)", name, _elapsed_ms(started), type(exc).__name__, exc)
            continue
        if not (found and (found.get("lyrics") or found.get("synced"))):
            log.info("lyrics: %s has no match (%d ms)", name, _elapsed_ms(started))
            continue
        if verify and not _matches_request(found.get("meta"), artist, title, duration):
            # A candidate came back but doesn't match the requested track; skip
            # it rather than write the wrong lyrics, and try the next provider.
            meta = found.get("meta") or {}
            log.info(
                "lyrics: %s answered with %r by %r (%ss), not %r by %r (%ss) - rejected",
                name, meta.get("title"), meta.get("artist"), _int_duration(meta.get("duration")),
                title, artist, _int_duration(duration),
            )
            rejected = True
            continue
        log.debug(
            "lyrics: %s matched in %d ms (synced=%s, plain=%s)",
            name, _elapsed_ms(started), bool(found.get("synced")), bool(found.get("lyrics")),
        )
        return {"lyrics": found.get("lyrics"), "synced": found.get("synced"), "source": name}

    if unreachable and unreachable == len(providers):
        return {"lyrics": None, "synced": None, "source": "unavailable"}
    return {"lyrics": None, "synced": None, "source": "rejected" if rejected else "none"}


def fetch_lyrics(track_id, artist, title, album=None, duration=None, force=False, verify=False):
    """Resolve lyrics for the current track from the web, with caching.

    Tries each enabled provider in order and keeps the first non-empty result.
    Returns a dict {"lyrics": str|None, "synced": str|None, "source": str}.
    `source` is the winning provider name (kept across cache hits so the UI can
    show where the lyrics came from), "none" when nothing was found, "rejected"
    when a candidate came back but failed verification, or "unavailable" when no
    provider could be reached — the one outcome that is not cached, so a search
    is retried as soon as they answer again.

    With `verify=True` (used by the batch CLI, which writes lyrics permanently
    into tags), a provider's result is only accepted when its own metadata
    matches the requested track (see _matches_request). This trades some recall
    for precision: better to leave a file without lyrics than to stamp it with
    the wrong song's.
    """
    if not title or not artist:
        log.info("lyrics: search skipped, track %s has no artist or title", track_id)
        return {"lyrics": None, "synced": None, "source": "none"}
    if any(f and len(str(f)) > MAX_FIELD_LEN for f in (track_id, artist, title, album)):
        log.info("lyrics: search skipped for track %s, a metadata field exceeds %d chars", track_id, MAX_FIELD_LEN)
        return {"lyrics": None, "synced": None, "source": "none"}

    # track_id alone isn't a reliable cache key: streamed "flow"/mix sources
    # can keep the same playlist track_id for an entire session while artist
    # and title change underneath it, which would otherwise serve the first
    # song's lyrics for every later one. `verify` is part of the key too, since
    # a lenient and a verified lookup can legitimately differ.
    cache_key = f"{track_id or ''}|{artist}|{title}|{int(bool(verify))}"
    if not force:
        cached = _cache_get(cache_key)
        if cached is not None:
            log.info("lyrics: cache hit for %r by %r (source=%s), no search made", title, artist, cached["source"])
            return dict(cached)

    started = time.monotonic()
    log.debug("lyrics: searching %r by %r (album=%r, duration=%s, verify=%s)", title, artist, album, duration, verify)
    result = _search_providers(artist, title, album, duration, verify)
    log.info(
        "lyrics: %r by %r -> %s (synced=%s, plain=%s) in %d ms",
        title, artist, result["source"], bool(result["synced"]), bool(result["lyrics"]), _elapsed_ms(started),
    )
    if result["source"] == "unavailable":
        # Nothing was learned about the track, so caching this as a miss would
        # fuse every search for TTL_MISS over a passing outage.
        return result

    hit = bool(result["lyrics"] or result["synced"])
    _cache_set(cache_key, dict(result), TTL_HIT if hit else TTL_MISS)
    return result
