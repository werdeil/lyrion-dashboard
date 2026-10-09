"""Web fallback for lyrics.

Results live in a process-local in-memory cache, since `library.db` is read-only;
gunicorn's single threaded worker shares it across requests. Providers are tried
in `LYRICS_PROVIDERS` order: the first synced result wins, else the first plain one.
"""

import logging
import os
import re
import time
import threading
import unicodedata
from collections import OrderedDict
from urllib.parse import quote

import requests

log = logging.getLogger(__name__)

try:
    from bs4 import BeautifulSoup
except ImportError:  # Genius scraping is skipped if bs4 isn't installed.
    BeautifulSoup = None

LRCLIB_SITE = "https://lrclib.net"
LRCLIB_BASE = f"{LRCLIB_SITE}/api"
MXM_BASE = "https://apic-desktop.musixmatch.com/ws/1.1"
NETEASE_BASE = "https://music.163.com/api"
USER_AGENT = "lyrion-custom-data (https://github.com/werdeil)"
# A browser-like UA avoids being blocked when scraping Genius / talking to the
# Musixmatch desktop endpoint or NetEase.
BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)

TTL_HIT = 24 * 3600
TTL_MISS = 3600

# LRCLIB takes 8-10s on busy evenings.
LRCLIB_TIMEOUT = int(os.getenv("LRCLIB_TIMEOUT", "15"))

# Opt-in verification (batch CLI): how far a provider's track length may drift
# from the file's before it counts as another recording.
VERIFY_DURATION_TOLERANCE = int(os.getenv("LYRICS_VERIFY_DURATION_TOLERANCE", "3"))

# Versions offered for one track, the library's own text included. Each carries
# a full lyrics body into the cache, so this caps an entry's weight too.
MAX_VERSIONS = 5

# The cache key includes client-supplied fields, so the cache must stay bounded.
CACHE_MAX_ENTRIES = 1000
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


def _float_duration(duration):
    """Coerce a duration to seconds, fraction kept, or None."""
    if not duration:
        return None
    try:
        # Duration arrives as a string and may be fractional (e.g. "247.144").
        return float(duration)
    except (TypeError, ValueError):
        return None


def _int_duration(duration):
    """Coerce a possibly-fractional string duration to whole seconds, or None."""
    seconds = _float_duration(duration)
    return None if seconds is None else int(seconds)


# A provider takes (artist, title, album, duration) and returns None or {"lyrics", "synced", "meta"},
# meta being the matched candidate's own artist/title/album/duration, for _matches_request.


def _duration_delta(candidate, seconds):
    """Seconds between a candidate's own duration and the request's, fraction kept, or None when either is unknown."""
    got = _float_duration(candidate.get("duration"))
    if seconds is None or got is None:
        return None
    return abs(got - seconds)


def _duration_close(candidate, seconds):
    """True when a candidate's own duration allows it to be the same recording.

    A candidate that carries no duration, or a request that doesn't know its
    own, can't be told apart this way and is left to the caller's other checks.
    """
    delta = _duration_delta(candidate, seconds)
    return delta is None or delta <= VERIFY_DURATION_TOLERANCE


def _by_length(candidates, seconds):
    """Candidates ordered by nearness to the requested length, unknown lengths last.

    `sorted` is stable, so candidates the length cannot separate keep LRCLIB's
    own ordering.
    """
    def gap(candidate):
        delta = _duration_delta(candidate, seconds)
        return float("inf") if delta is None else delta
    return sorted(candidates, key=gap)


def _lrclib_version(payload, seconds):
    """One LRCLIB record in the shape the page cycles through.

    Timestamps only fit the recording they were made for, so the LRC is kept
    only while the record's own length matches the request's.
    """
    return {
        "lyrics": payload.get("plainLyrics"),
        "synced": payload.get("syncedLyrics") if _duration_close(payload, seconds) else None,
        "album": payload.get("albumName"),
        "duration": payload.get("duration"),
    }


def _lrclib_attempts(artist, title, album):
    """Search parameter sets for one track, most specific first.

    The album filter is dropped after being tried, since the search exists to
    forgive the album/duration mismatches `get` won't.
    """
    names = [(artist, title)]
    loose = (_drop_article(artist), _drop_article(title))
    if loose != (artist, title):
        names.append(loose)
    attempts = []
    for name_artist, name_title in names:
        base = {"artist_name": name_artist, "track_name": name_title}
        if album:
            attempts.append({**base, "album_name": album})
        attempts.append(base)
    return attempts


def _lrclib_search_url(artist, title):
    """Browsable URL for this track on LRCLIB's own search page, for the diagnostic logs."""
    query = " ".join(part for part in (artist, title) if part)
    return f"{LRCLIB_SITE}/search/{quote(query, safe='')}"


def _lrclib_candidates(results, seconds, search_params):
    """One search response's candidates, and those worth offering in order.

    The offer is the uploads of this track's length, synced first and plain
    behind, or empty when none is synced.
    """
    close = [c for c in results if _duration_close(c, seconds)]
    synced = [c for c in close if c.get("syncedLyrics")]
    log.info(
        "lrclib: search (artist=%r, album=%r) returned %d candidate(s), %d of this length, %d of those synced",
        search_params.get("artist_name"), search_params.get("album_name"),
        len(results), len(close), len(synced),
    )
    if not synced:
        return close, []
    plain = [c for c in close if not c.get("syncedLyrics")]
    return close, _by_length(synced, seconds) + _by_length(plain, seconds)


def _lrclib_search(artist, title, album, seconds, fallback):
    """Scan LRCLIB's `search` for a synced record of this very recording.

    Returns (record, others): the synced candidate closest to this track's
    length, or `fallback` (the `get` hit, when there was one) if the search
    turns up nothing better, and the rest of the set it was chosen from —
    other uploads of the same song, which the page offers to compare it
    against. Raises ProviderUnavailable if LRCLIB can't be reached.
    """
    others = []
    headers = {"User-Agent": USER_AGENT}
    for search_params in _lrclib_attempts(artist, title, album):
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
        close, ranked = _lrclib_candidates(results, seconds, search_params)
        if ranked:
            if fallback is not None and not any(c.get("id") == fallback.get("id") for c in ranked):
                ranked.append(fallback)
            return ranked[0], ranked[1:]
        pool = close or results
        if pool and not others:
            if fallback is None:
                fallback, others = pool[0], pool[1:]
            else:
                others = [c for c in pool if c.get("id") != fallback.get("id")]
    return fallback, others


def _provider_lrclib(artist, title, album, duration):
    """Ask LRCLIB for a track, preferring a synced record of that very recording.

    Tries the exact `get`, then `search`, which forgives album and duration
    mismatches. LRCLIB stores lyrics per upload, so a `get` hit with no synced
    record of this length is only a fallback while the search looks for one. A synced candidate must
    match the track's duration; one that doesn't still serves as plain text.
    Raises ProviderUnavailable when LRCLIB can't be reached at all.
    """
    headers = {"User-Agent": USER_AGENT}

    params = {"artist_name": artist, "track_name": title}
    if album:
        params["album_name"] = album
    seconds = _float_duration(duration)
    if seconds is not None:
        # LRCLIB's signature is indexed on whole seconds.
        params["duration"] = int(seconds)

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

    others = []
    if payload is None or not _lrclib_version(payload, seconds)["synced"]:
        payload, others = _lrclib_search(artist, title, album, seconds, payload)

    if not payload:
        log.info("lrclib: no record, catalogue search: %s", _lrclib_search_url(artist, title))
        return None
    # Another recording's LRC would run against the wrong timeline, so only its
    # words are kept; the caller then shows them as plain lyrics.
    synced_text = _lrclib_version(payload, seconds)["synced"]
    if payload.get("syncedLyrics") and not synced_text:
        log.info(
            "lrclib: %s/tracks/%s is %ss, this track is %ss - its timings dropped",
            LRCLIB_SITE, payload.get("id"), payload.get("duration"), int(seconds),
        )
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
        "versions": [_lrclib_version(c, seconds) for c in [payload] + others[:MAX_VERSIONS - 1]],
    }


_mxm_token = {"value": None, "expires_at": 0}
_mxm_lock = threading.Lock()
_MXM_HEADERS = {
    "authority": "apic-desktop.musixmatch.com",
    "cookie": "AWSELB=0",
    "User-Agent": BROWSER_UA,
}


def _musixmatch_token():
    """Return a usable Musixmatch user token, cached in-process for 9 hours.

    `MUSIXMATCH_TOKEN` overrides the one the desktop web app is issued. Returns
    None when Musixmatch refuses a usable token, and raises ProviderUnavailable
    when it can't be reached.
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


def _mxm_subtitle(subtitle_list, language):
    """Return a subtitle body from Musixmatch's list, skipping other languages.

    A track can carry several subtitles, translations among them; one that
    declares a language other than the lyrics' would swap out the words.
    """
    for entry in subtitle_list or []:
        subtitle = entry.get("subtitle", {}) if isinstance(entry, dict) else {}
        body = subtitle.get("subtitle_body")
        declared = subtitle.get("subtitle_language")
        if body and (not language or not declared or declared == language):
            return body
    return None


def _mxm_macro_calls(artist, title, album, duration, token):
    """Run the desktop macro and return its `macro_calls` map, or None.

    Raises ProviderUnavailable when Musixmatch can't be reached.
    """
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
        body = r.json().get("message", {}).get("body", {})
    except requests.RequestException as exc:
        raise ProviderUnavailable("musixmatch") from exc
    except (ValueError, AttributeError) as exc:
        log.debug("musixmatch: unreadable response (%s)", exc)
        return None
    return body.get("macro_calls", {}) if isinstance(body, dict) else {}


def _provider_musixmatch(artist, title, album, duration):
    token = _musixmatch_token()
    if not token:
        return None
    calls = _mxm_macro_calls(artist, title, album, duration, token)
    if calls is None:
        return None

    def _body(call):
        node = calls.get(call, {})
        body = node.get("message", {}).get("body") if isinstance(node, dict) else None
        return body if isinstance(body, dict) else {}

    track = _body("matcher.track.get").get("track", {})
    meta = {
        "artist": track.get("artist_name"),
        "title": track.get("track_name"),
        "album": track.get("album_name"),
        "duration": track.get("track_length"),
    }
    # Musixmatch's matcher is fuzzy and answers even when nothing really fits,
    # so a track it doesn't carry comes back as the nearest song it does.
    if not _matches_request(meta, artist, title, duration):
        log.info(
            "musixmatch: matched %r by %r (%ss), not %r by %r (%ss) - dropped",
            meta["title"], meta["artist"], _int_duration(meta["duration"]),
            title, artist, _int_duration(duration),
        )
        return None

    lyrics_node = _body("track.lyrics.get").get("lyrics", {})
    lyrics = lyrics_node.get("lyrics_body") or None
    synced = _mxm_subtitle(
        _body("track.subtitles.get").get("subtitle_list"), lyrics_node.get("lyrics_language")
    )

    if lyrics or synced:
        return {"lyrics": lyrics, "synced": synced, "meta": meta}
    return None


_NETEASE_HEADERS = {"User-Agent": BROWSER_UA, "Referer": "https://music.163.com/"}
_LRC_TIMESTAMP_RE = re.compile(r"^\[\d+:\d{2}", re.MULTILINE)
# NetEase prepends the song credits as timed lines, in Chinese whatever the song's language.
_NETEASE_CREDIT_RE = re.compile(
    r"^\[[\d:.]+\]\s*(?:作词|作詞|作曲|编曲|編曲|制作人|製作人|监制|混音|母带|录音|和声|出品|词|曲)\s*[:：]"
)


def _netease_song_meta(song):
    """Read a search hit into a verification meta, whichever field names the endpoint used."""
    artists = [a.get("name") for a in song.get("artists") or song.get("ar") or [] if isinstance(a, dict)]
    album = song.get("album") or song.get("al") or {}
    millis = song.get("duration") or song.get("dt")
    return {
        "artists": [a for a in artists if a],
        "title": song.get("name"),
        "album": album.get("name") if isinstance(album, dict) else None,
        "duration": millis / 1000 if isinstance(millis, (int, float)) and millis > 0 else None,
    }


def _netease_pick(songs, artist, title, duration):
    """Return (id, meta) of the search hit that is this recording, nearest in length, or None.

    The search is free-text and always answers with its nearest songs, so each
    hit must pass _matches_request against one of its credited artists.
    """
    matches = []
    for song in songs:
        if not isinstance(song, dict) or not song.get("id"):
            continue
        meta = _netease_song_meta(song)
        credited = next(
            (a for a in meta["artists"] if _matches_request(dict(meta, artist=a), artist, title, duration)), None
        )
        if credited:
            matches.append({
                "id": song["id"], "artist": credited, "title": meta["title"],
                "album": meta["album"], "duration": meta["duration"],
            })
    if not matches:
        return None
    best = _by_length(matches, _float_duration(duration))[0]
    return best.pop("id"), best


def _provider_netease(artist, title, _album, duration):
    """Ask NetEase Cloud Music for a track's LRC.

    Searches `artist title`, keeps the hit that verifies against the request and
    fetches its lyrics; an LRC without timestamps is returned as plain text.
    Raises ProviderUnavailable when NetEase can't be reached.
    """
    try:
        r = requests.get(
            f"{NETEASE_BASE}/search/get/web",
            params={"s": f"{artist} {title}", "type": 1, "limit": 10, "offset": 0},
            headers=_NETEASE_HEADERS,
            timeout=6,
        )
        if r.status_code != 200:
            log.info("netease: search returned HTTP %s", r.status_code)
            return None
        songs = (r.json().get("result") or {}).get("songs") or []
    except requests.RequestException as exc:
        raise ProviderUnavailable("netease") from exc
    except (ValueError, AttributeError) as exc:
        log.debug("netease: unreadable search response (%s)", exc)
        return None

    picked = _netease_pick(songs, artist, title, duration)
    if not picked:
        if songs:
            log.info("netease: %d search results, none is %r by %r", len(songs), title, artist)
        return None
    song_id, meta = picked

    try:
        r = requests.get(
            f"{NETEASE_BASE}/song/lyric",
            params={"id": song_id, "lv": 1, "kv": 1, "tv": -1},
            headers=_NETEASE_HEADERS,
            timeout=6,
        )
        if r.status_code != 200:
            log.info("netease: lyrics of song %s returned HTTP %s", song_id, r.status_code)
            return None
        text = ((r.json().get("lrc") or {}).get("lyric") or "").strip()
    except requests.RequestException as exc:
        raise ProviderUnavailable("netease") from exc
    except (ValueError, AttributeError) as exc:
        log.debug("netease: unreadable lyrics response (%s)", exc)
        return None

    lines = [line for line in text.splitlines() if not _NETEASE_CREDIT_RE.match(line.strip())]
    text = "\n".join(lines).strip()
    log.debug("netease: song %s (%r, %ss), %d characters", song_id, meta["album"], _int_duration(meta["duration"]), len(text))
    if not text:
        return None
    if _LRC_TIMESTAMP_RE.search(text):
        return {"lyrics": None, "synced": text, "meta": meta}
    return {"lyrics": text, "synced": None, "meta": meta}


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

    # Genius search is free-text only, so the album joins the query to tell
    # re-recordings apart.
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
    "netease": _provider_netease,
    "genius": _provider_genius,
}
DEFAULT_PROVIDER_ORDER = "lrclib,musixmatch,netease,genius"
PLAIN_ONLY_PROVIDERS = {"genius"}


def _enabled_providers():
    """Resolve the ordered provider list from `LYRICS_PROVIDERS`.

    Unknown names are ignored.
    """
    raw = os.getenv("LYRICS_PROVIDERS", DEFAULT_PROVIDER_ORDER)
    names = [n.strip().lower() for n in raw.split(",") if n.strip()]
    return [(n, PROVIDERS[n]) for n in names if n in PROVIDERS]


# Qualifiers and credits that should not defeat a match: parenthetical/bracketed
# notes ("(Remastered 2011)", "[Live]") and everything from a "feat." onwards.
_PAREN_RE = re.compile(r"[\(\[\{].*?[\)\]\}]")
_FEAT_RE = re.compile(r"\b(feat|ft|featuring)\b.*", re.IGNORECASE)
_NONALNUM_RE = re.compile(r"[^a-z0-9]+")
# A library and a catalogue routinely disagree on a leading article and the
# plural it carries ("Les Fatals Picards" tagged as "Fatal Picards").
_ARTICLE_RE = re.compile(r"^(?:the|an?|le|la|les|l|un|une|des|el|los|las|il|der|die|das)\b['\s]+", re.IGNORECASE)


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


def _drop_article(text):
    return _ARTICLE_RE.sub("", text) if text else text


def _fold_name(text):
    words = _drop_article(_normalize(text)).split()
    return " ".join(w[:-1] if len(w) > 3 and w.endswith("s") else w for w in words)


def _matches_request(meta, artist, title, duration):
    """True if a provider's matched candidate lines up with the requested track.

    Title and artist must be equal once folded (see _fold_name). When both
    durations are known they must fall within VERIFY_DURATION_TOLERANCE seconds;
    a candidate with no duration (e.g. Genius) is accepted on title and artist.
    """
    if not meta:
        return False
    if _fold_name(meta.get("title")) != _fold_name(title):
        return False
    if _fold_name(meta.get("artist")) != _fold_name(artist):
        return False
    return _duration_close(meta, _float_duration(duration))


def _log_rejected(name, meta, artist, title, duration):
    log.info(
        "lyrics: %s answered with %r by %r (%ss), not %r by %r (%ss) - rejected",
        name, meta.get("title"), meta.get("artist"), _int_duration(meta.get("duration")),
        title, artist, _int_duration(duration),
    )


def _search_providers(artist, title, album, duration, verify):
    """Try each enabled provider in order and return the first usable result.

    A plain-only result is held while the later providers able to sync are asked
    for a synced one, unless `verify` is set: the batch CLI only stores plain text.
    Same shape as fetch_lyrics' return value, without any caching: "unavailable"
    means not one provider answered, which the caller must not confuse with a
    search that ran and came up empty.
    """
    rejected = False
    unreachable = 0
    plain = None
    providers = _enabled_providers()
    if not providers:
        # An empty list is how an operator turns the web search off, so this is
        # an outcome to state once per search, not a fault to warn about.
        log.info("lyrics: web search disabled, LYRICS_PROVIDERS=%r resolves to no provider",
                 os.getenv("LYRICS_PROVIDERS"))
    for name, provider in providers:
        if plain and name in PLAIN_ONLY_PROVIDERS:
            continue
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
            _log_rejected(name, found.get("meta") or {}, artist, title, duration)
            rejected = True
            continue
        log.debug(
            "lyrics: %s matched in %d ms (synced=%s, plain=%s)",
            name, _elapsed_ms(started), bool(found.get("synced")), bool(found.get("lyrics")),
        )
        result = {"lyrics": found.get("lyrics"), "synced": found.get("synced"), "source": name}
        if found.get("versions"):
            result["versions"] = found["versions"]
        if result["synced"] or verify:
            return result
        if plain is None:
            log.info("lyrics: %s has plain lyrics only, asking the next providers for synced ones", name)
            plain = result

    if plain:
        return plain
    if unreachable and unreachable == len(providers):
        return {"lyrics": None, "synced": None, "source": "unavailable"}
    return {"lyrics": None, "synced": None, "source": "rejected" if rejected else "none"}


def fetch_lyrics(track_id, artist, title, album=None, duration=None, force=False, verify=False):
    """Resolve lyrics for the current track from the web, with caching.

    Tries each enabled provider in order and keeps the first synced result, else
    the first plain one.
    Returns a dict {"lyrics": str|None, "synced": str|None, "source": str}.
    `source` is the winning provider name (kept across cache hits), "none" when
    nothing was found, "rejected"
    when a candidate came back but failed verification, or "unavailable" when no
    provider could be reached — the one outcome that is not cached, so a search
    is retried as soon as they answer again.

    A provider that found several uploads of the song also returns "versions"
    for the page to cycle through: the winner first, then the rest synced
    before plain, at most MAX_VERSIONS long.

    With `verify=True` (the batch CLI, which writes into tags), a result is only
    accepted when its own metadata matches the requested track (see
    _matches_request).
    """
    if not title or not artist:
        log.info("lyrics: search skipped, track %s has no artist or title", track_id)
        return {"lyrics": None, "synced": None, "source": "none"}
    if any(f and len(str(f)) > MAX_FIELD_LEN for f in (track_id, artist, title, album)):
        log.info("lyrics: search skipped for track %s, a metadata field exceeds %d chars", track_id, MAX_FIELD_LEN)
        return {"lyrics": None, "synced": None, "source": "none"}

    # Streams like a Deezer flow keep one track_id across songs; `verify` is in the
    # key since a lenient and a verified lookup can differ.
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
