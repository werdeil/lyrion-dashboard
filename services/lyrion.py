import threading
import time

import requests
import urllib3
from flask import abort, current_app

urllib3.disable_warnings()

# Shared Session so upstream requests reuse their TCP connections.
_session = requests.Session()

# Covers are buffered whole in memory before being re-served; cap what we accept.
COVER_MAX_BYTES = 10 * 1024 * 1024


def _read_image(r):
    """Buffer a streamed cover response, returning (content, content_type).

    Aborts with 502 on oversized or non-image payloads; the page's broken
    cover fallback takes over from there."""
    r.raise_for_status()
    content_type = (r.headers.get("Content-Type") or "image/jpeg").lower()
    if content_type.startswith("application/octet-stream"):
        # Some radio/plugin servers are sloppy about image types; the payload
        # only ever lands in an <img>, so relay it as a generic image.
        content_type = "image/jpeg"
    if not content_type.startswith("image/"):
        abort(502)
    chunks, total = [], 0
    for chunk in r.iter_content(64 * 1024):
        chunks.append(chunk)
        total += len(chunk)
        if total > COVER_MAX_BYTES:
            abort(502)
    return b"".join(chunks), content_type


def lyrion_request(payload):
    host = current_app.config["LYRION_HOST"]
    # TLS verification is off for the self-signed local Lyrion; audit S1
    # (security audit in PR #15) documents this accepted risk.
    r = _session.post(
        f"{host}/jsonrpc.js",
        json=payload,
        verify=False,
        timeout=5,
    )
    return r.json()


def fetch_cover(coverid, size=None):
    """Fetch an album cover from Lyrion so the page can serve it same-origin.

    Loading the cover through our own host (instead of pointing the <img> at
    LYRION_HOST directly) lets the page read the image pixels on a canvas to
    derive a tint colour — cross-origin images would taint the canvas.

    With `size` set, ask Lyrion for a square thumbnail (`cover_NxN_o.jpg`, `o`
    = keep aspect ratio) instead of the full-resolution artwork — used by the
    blurred empty-state mosaic, where dozens of covers load at once and full
    art would be needlessly heavy. Lyrion generates and caches these itself;
    if a given server doesn't serve the resized form we fall back to the full
    cover so the tile still shows.
    """
    host = current_app.config["LYRION_HOST"]
    name = f"cover_{size}x{size}_o.jpg" if size else "cover.jpg"
    # verify=False for the self-signed local Lyrion — see audit S1.
    r = _session.get(f"{host}/music/{coverid}/{name}", verify=False, timeout=5, stream=True)
    if size and r.status_code == 404:
        r.close()
        r = _session.get(f"{host}/music/{coverid}/cover.jpg", verify=False, timeout=5, stream=True)
    return _read_image(r)


def fetch_remote_cover(url):
    """Fetch artwork from a remote stream's artwork_url (Deezer, Spotify, radio
    icons, etc.) so the page can serve it same-origin, same reasoning as
    fetch_cover. These are public CDN URLs, not the local Lyrion host, so
    certificate verification stays on."""
    r = _session.get(url, timeout=5, stream=True)
    return _read_image(r)


def get_players():
    payload = {
        "id": 1,
        "method": "slim.request",
        "params": ["", ["players", "0", "100"]],
    }
    data = lyrion_request(payload)
    return data["result"].get("players_loop", [])


def get_now_playing(player_id):
    """Return the current track + transport state of a player.

    Uses the JSON-RPC `status` query for the current playlist position (`-`),
    asking for one item with the tags we display: a=artist, A=role-keyed
    artist lists, l=album, y=year, d=duration, c=coverid, K=artwork_url. With tag A
    the multiple artists come back joined by ", " under a role key
    (`trackartist` for the track's contributors, `artist` for the ARTIST
    role) — we prefer `trackartist` so a "feat." line shows everyone,
    matching Lyrion's display. Title and the Lyrion track id come back by
    default; that id is the key used to look up lyrics in the SQLite
    `tracks` table.

    Streamed tracks (Deezer, Spotify, radio, ...) have no local coverid, but
    plugins for those services attach an `artwork_url` to the track instead —
    that's what tag K surfaces. It's sometimes relative to the Lyrion host.
    """
    payload = {
        "id": 1,
        "method": "slim.request",
        "params": [player_id, ["status", "-", 1, "tags:aAldcKy"]],
    }
    data = lyrion_request(payload)
    result = data.get("result", {})
    loop = result.get("playlist_loop") or []
    track = loop[0] if loop else None

    if not track:
        return {"playing": False, "mode": result.get("mode", "stop")}

    artwork_url = track.get("artwork_url")
    if artwork_url and not artwork_url.startswith("http"):
        host = current_app.config["LYRION_HOST"]
        artwork_url = f"{host}/{artwork_url.lstrip('/')}"

    return {
        "playing": result.get("mode") == "play",
        "mode": result.get("mode", "stop"),
        "time": result.get("time"),
        "duration": result.get("duration") or track.get("duration"),
        "track_id": track.get("id"),
        "title": track.get("title"),
        "artist": track.get("trackartist") or track.get("artist") or track.get("albumartist"),
        "album": track.get("album"),
        "year": track.get("year"),
        "coverid": track.get("coverid"),
        "artwork_url": artwork_url,
    }


# Now-playing snapshot shared across clients, so Lyrion sees one enumeration
# per TTL instead of 1+N requests per poll per client.
NOW_PLAYING_TTL = 2

_now_cache = {"value": None, "fetched_at": 0, "expires_at": 0}
_now_lock = threading.Lock()
_last_player = {"id": None, "name": None}


def get_active_now_playing():
    """Now-playing state of the player that is currently playing, cached for
    NOW_PLAYING_TTL seconds (see above).

    The cached playback position is aged by the wall time elapsed since the
    value was fetched, so the progress bar and karaoke highlight stay accurate
    even when several clients share one cached snapshot.
    """
    with _now_lock:
        now_ts = time.time()
        if _now_cache["value"] is None or _now_cache["expires_at"] <= now_ts:
            _now_cache["value"] = _query_active_now_playing()
            _now_cache["fetched_at"] = time.time()
            _now_cache["expires_at"] = _now_cache["fetched_at"] + NOW_PLAYING_TTL
        result = dict(_now_cache["value"])
        age = time.time() - _now_cache["fetched_at"]
    if result.get("playing") and result.get("time") is not None:
        result["time"] += age
    return result


def _query_active_now_playing():
    """Ask Lyrion which player is playing, and what.

    Lyrion has no single call returning the transport state of every player,
    so we enumerate players and query `status` on each, returning the first one
    whose mode is 'play' — except that the player found playing last time is
    tried first, skipping the enumeration while it keeps playing. If none is
    actually playing, we return a not-playing payload so the page shows its
    empty state — a paused/stopped player with a track still loaded is
    deliberately not surfaced.
    """
    if _last_player["id"]:
        now = get_now_playing(_last_player["id"])
        if now.get("playing") and now.get("track_id"):
            now["player_name"] = _last_player["name"]
            now["player_id"] = _last_player["id"]
            return now

    for player in get_players():
        player_id = player.get("playerid")
        if not player_id or player_id == _last_player["id"]:
            continue

        now = get_now_playing(player_id)
        if now.get("playing") and now.get("track_id"):
            _last_player["id"] = player_id
            _last_player["name"] = player.get("name")
            now["player_name"] = player.get("name")
            # Exposed so the page can deep-link the "open Lyrion" button to the
            # Material skin focused on this very player (?player=<id>).
            now["player_id"] = player_id
            return now

    # Nothing playing: drop the shortcut so the next refresh goes straight to
    # the enumeration instead of probing a player known to be idle.
    _last_player["id"] = None
    _last_player["name"] = None
    return {"playing": False, "mode": "stop", "player_name": None}
