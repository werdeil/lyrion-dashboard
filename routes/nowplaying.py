import logging
import re

from flask import Blueprint, render_template, current_app, jsonify, request, Response, abort

from services.lyrion import get_active_now_playing, fetch_cover, fetch_remote_cover
from services.database import (
    get_track_lyrics,
    get_stats,
    get_random_cover_ids,
    get_recent_album_covers,
)
from services.lyrics import fetch_lyrics
from services.ratelimit import RateLimiter, Cooldown
from i18n import pick_lang, TRANSLATIONS

nowplaying_bp = Blueprint("nowplaying", __name__)

log = logging.getLogger(__name__)

# Coverids are numeric ids or hex hashes; anything else must not reach the upstream URL.
COVERID_RE = re.compile(r"[0-9a-fA-F]+")

# Player ids are MAC addresses (or IPs); only matched against ids Lyrion
# reported, never sent upstream, but keep junk out anyway.
PLAYER_ID_RE = re.compile(r"[0-9A-Fa-f:.\-]{1,64}")

# Fuses for the outbound lyrics searches: a per-IP rate limit, and a per-track
# cooldown on refresh=1 that only has to absorb a double-click.
LYRICS_RATE = RateLimiter(limit=10, window=60)
REFRESH_COOLDOWN = Cooldown(interval=5)
THROTTLED_RESULT = {"lyrics": None, "synced": None, "source": "none", "throttled": True}


@nowplaying_bp.route("/")
def index():
    stats = get_stats()
    lang = pick_lang(request.accept_languages)
    return render_template(
        "nowplaying.html",
        lyrion_host=current_app.config["LYRION_HOST"],
        stats=stats,
        lang=lang,
        t=TRANSLATIONS[lang],
    )


@nowplaying_bp.route("/now-playing.json")
def now_playing_json():
    """Live state of the player to display, polled by the page.

    ?known={track key}, the id|title|artist|album of the track on screen, omits
    the lyrics and skips their lookup while that track still plays. ?player={id}
    pins a player while it keeps playing, else the automatic selection applies;
    a malformed id is ignored.
    """
    selected = request.args.get("player")
    if selected and not PLAYER_ID_RE.fullmatch(selected):
        selected = None
    now = get_active_now_playing(selected_id=selected)
    track_key = "|".join(
        str(now.get(f)) if now.get(f) is not None else ""
        for f in ("track_id", "title", "artist", "album")
    )
    if request.args.get("known") != track_key:
        now["lyrics"] = get_track_lyrics(now.get("track_id"))
    return jsonify(now)


@nowplaying_bp.route("/cover/<coverid>.jpg")
def cover(coverid):
    """Proxy an album cover from Lyrion same-origin, so the page can sample it on a canvas.

    Cached client-side. ?size=N asks for Lyrion's NxN thumbnail instead of the full artwork."""
    if not COVERID_RE.fullmatch(coverid):
        abort(404)
    size = request.args.get("size", type=int)
    if size is not None:
        size = min(max(size, 16), 512)
    content, content_type = fetch_cover(coverid, size)
    return Response(
        content,
        content_type=content_type,
        headers={"Cache-Control": "public, max-age=86400"},
    )


@nowplaying_bp.route("/cover/remote.jpg")
def cover_remote():
    """Proxy the artwork_url of the currently playing remote/streaming track
    (Deezer, Spotify, radio, ...), same-origin like /cover/<id>.jpg.

    Looked up server-side from Lyrion instead of taking a URL from the
    client, so this can't be used as an open image proxy.
    """
    now = get_active_now_playing()
    artwork_url = now.get("artwork_url")
    if not artwork_url:
        abort(404)
    content, content_type = fetch_remote_cover(artwork_url)
    return Response(
        content,
        content_type=content_type,
        headers={"Cache-Control": "public, max-age=86400"},
    )


@nowplaying_bp.route("/mosaic-covers.json")
def mosaic_covers_json():
    """Album cover ids for the empty-state mosaic: the most recently played
    albums, newest first, one cover per album.

    ?limit= (the tiles the panel fits) is clamped. A library with no play
    history yet gets a random selection instead.
    """
    limit = min(max(request.args.get("limit", default=24, type=int), 1), 200)
    covers = get_recent_album_covers(limit)
    if not covers:
        covers = get_random_cover_ids(limit)
    return jsonify(covers)


@nowplaying_bp.route("/recent-covers.json")
def recent_covers_json():
    """Cover ids of the most recently played albums, newest first, for the
    pile of sleeves under the now-playing cover.

    ?limit= is clamped. Unlike the mosaic there is no random fallback: with no
    play history yet the pile doesn't show.
    """
    limit = min(max(request.args.get("limit", default=16, type=int), 1), 50)
    return jsonify(get_recent_album_covers(limit))


@nowplaying_bp.route("/stats.json")
def stats_json():
    return jsonify(get_stats())


@nowplaying_bp.route("/lyrics.json")
def lyrics_json():
    """Fetch lyrics for a track from the web, from the metadata the page displays.

    Fused by LYRICS_RATE and, on ?refresh=1, REFRESH_COOLDOWN. `"throttled": true`
    marks a search a fuse kept from running that came back empty; `"retry_after"`
    (seconds) comes with any ?refresh=1, for as long as a new search would be refused.
    """
    if not LYRICS_RATE.allow(request.remote_addr or "unknown"):
        log.warning("lyrics: rate limit hit by %s, search refused", request.remote_addr)
        return jsonify(THROTTLED_RESULT), 429
    force = request.args.get("refresh") == "1"
    held = False
    retry_after = 0.0
    if force:
        track_key = "|".join(
            request.args.get(f) or "" for f in ("track_id", "artist", "title")
        )
        force = REFRESH_COOLDOWN.allow(track_key)
        held = not force
        retry_after = REFRESH_COOLDOWN.remaining(track_key)
        if held:
            log.info("lyrics: refresh held by the cooldown for %.1fs (%s)", retry_after, track_key)
    result = fetch_lyrics(
        track_id=request.args.get("track_id"),
        artist=request.args.get("artist"),
        title=request.args.get("title"),
        album=request.args.get("album"),
        duration=request.args.get("duration"),
        force=force,
    )
    # Copied, not annotated in place: what the service returns is its own, and
    # a cached entry handed out twice must not collect one request's flags.
    response = dict(result)
    if held and not (result["lyrics"] or result["synced"]):
        response["throttled"] = True
    if retry_after:
        response["retry_after"] = round(retry_after, 1)
    return jsonify(response)
