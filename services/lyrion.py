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
    # Lyrion replies with an empty (non-JSON) body when asked about an unknown
    # player id — e.g. a vanished ephemeral player still held in _last_player.
    # Return {} instead of letting r.json() raise; callers read `result` safely.
    try:
        return r.json()
    except ValueError:
        return {}


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
    return data.get("result", {}).get("players_loop", [])


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


# Snapshot of every currently-playing player, shared across clients so Lyrion
# sees one enumeration (1 + N status calls) per TTL rather than that per poll
# per client. Several players playing at once is rare, so the enumeration cost
# is bounded and amortised across all clients.
NOW_PLAYING_TTL = 2

_now_cache = {"players": [], "fetched_at": 0, "expires_at": 0}
_now_lock = threading.Lock()
# The player shown last on the automatic path, so the display stays on it while
# it keeps playing instead of flipping between simultaneously-playing players.
_last_player = {"id": None, "name": None}


def get_active_now_playing(selected_id=None):
    """Now-playing state of the player to display, cached for NOW_PLAYING_TTL.

    When several players play at once the page can pin one via `selected_id`
    (an id it kept from an earlier `players` list); that player wins while it
    is still playing, otherwise we fall back to automatic selection and set
    `selection_active` False so the page drops its now-stale pick. The response
    always carries `players` — [{id, name}] for every player currently playing —
    so the page can offer (and populate) its switcher.

    The cached playback position is aged by the wall time elapsed since the
    snapshot was taken, so the progress bar and karaoke highlight stay accurate
    even when several clients share one cached snapshot.
    """
    with _now_lock:
        now_ts = time.time()
        # expires_at starts at 0, so the first call always fetches; an empty
        # list is a valid cached result (nothing playing) and is kept for the TTL.
        if _now_cache["expires_at"] <= now_ts:
            _now_cache["players"] = _query_playing_players()
            _now_cache["fetched_at"] = time.time()
            _now_cache["expires_at"] = _now_cache["fetched_at"] + NOW_PLAYING_TTL
        playing = _now_cache["players"]
        age = time.time() - _now_cache["fetched_at"]

        players = [{"id": p["player_id"], "name": p["player_name"]} for p in playing]

        chosen = None
        selection_active = False
        if selected_id:
            chosen = next(
                (p for p in playing if p["player_id"] == selected_id), None
            )
            selection_active = chosen is not None
        if chosen is None:
            # No (or stale) selection: pick automatically, which also updates
            # the sticky _last_player — kept inside the lock since that state
            # is shared across threads.
            chosen = _auto_select(playing)

        if chosen is None:
            return {
                "playing": False,
                "mode": "stop",
                "player_name": None,
                "players": players,
                "selection_active": False,
            }
        result = dict(chosen)

    if result.get("playing") and result.get("time") is not None:
        result["time"] += age
    result["players"] = players
    result["selection_active"] = selection_active
    return result


def _auto_select(playing):
    """Pick a player automatically among those playing: keep the one shown last
    if it is still playing (so the display stays put across polls), otherwise
    the first in Lyrion's order. Records the pick in _last_player, or clears it
    when nothing is playing so the shortcut doesn't point at an idle player.

    Only ever reached on the automatic path, so an explicit per-client
    selection never pollutes the sticky auto-pick other clients rely on.
    """
    if not playing:
        _last_player["id"] = None
        _last_player["name"] = None
        return None

    chosen = None
    if _last_player["id"]:
        chosen = next(
            (p for p in playing if p["player_id"] == _last_player["id"]), None
        )
    if chosen is None:
        chosen = playing[0]

    _last_player["id"] = chosen["player_id"]
    _last_player["name"] = chosen["player_name"]
    return chosen


def _query_playing_players():
    """Enumerate players and return those currently playing, in Lyrion's order.

    Lyrion has no single call returning the transport state of every player, so
    we enumerate players and query `status` on each. Every returned entry is the
    get_now_playing payload enriched with player_id/player_name (the id also
    lets the page deep-link "open Lyrion" to this very player, ?player=<id>). A
    paused/stopped player with a track still loaded is deliberately left out.
    """
    playing = []
    for player in get_players():
        player_id = player.get("playerid")
        if not player_id:
            continue
        now = get_now_playing(player_id)
        if now.get("playing") and now.get("track_id"):
            now["player_id"] = player_id
            now["player_name"] = player.get("name")
            playing.append(now)
    return playing
