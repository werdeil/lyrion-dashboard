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

# Coverids are numeric ids or hex hashes; anything else must not reach the upstream URL.
COVERID_RE = re.compile(r"[0-9a-fA-F]+")

# Player ids are MAC addresses (or occasionally IPs); only compared against the
# ids Lyrion already reported, never sent upstream, but keep junk out anyway.
PLAYER_ID_RE = re.compile(r"[0-9A-Fa-f:.\-]{1,64}")

# Fuses for the outbound lyrics searches: per-IP rate limit, per-track cooldown on refresh=1.
LYRICS_RATE = RateLimiter(limit=10, window=60)
REFRESH_COOLDOWN = Cooldown(interval=30)


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

    The page passes ?known=<track key> — the id|title|artist|album key of the
    track it already displays (the same key render() dedupes on). Lyrics are
    only looked up and included when the playing track differs from it, so the
    steady-state poll skips the database entirely; the page only reads lyrics
    on a track change anyway.

    ?player=<id> pins a specific player when several are playing at once (the
    switcher's pick); honoured only while that player is still playing, else the
    response falls back to the automatic selection. A malformed id is ignored.
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
    """Proxy an album cover from Lyrion, served same-origin so the page can
    sample its colours on a canvas. Cached client-side since covers are stable.

    ?size=N asks Lyrion for an NxN thumbnail instead of the full artwork; the
    mosaic uses it to load its many blurred covers cheaply."""
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

    The page passes ?limit= (how many tiles its panel fits), clamped to keep
    the query and the page sane. A library with no play history yet falls back
    to a random selection so the backdrop is never empty.
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

    The page passes ?limit= — as many sleeves as fit under the cover plus a
    small buffer, since it drops the currently playing album client-side —
    clamped to keep the query sane. Unlike the mosaic there is no random
    fallback: with no play history yet the pile simply doesn't show.
    """
    limit = min(max(request.args.get("limit", default=16, type=int), 1), 50)
    return jsonify(get_recent_album_covers(limit))


@nowplaying_bp.route("/stats.json")
def stats_json():
    stats = get_stats()
    return current_app.response_class(
        response=current_app.json.dumps(stats, indent=2, ensure_ascii=False),
        status=200,
        mimetype="application/json",
    )


@nowplaying_bp.route("/lyrics.json")
def lyrics_json():
    """Fetch lyrics from the web for a track, on explicit user request.

    The page calls this only when the local library has no lyrics, passing the
    metadata it already displays so we avoid re-querying Lyrion. Results are
    cached in-memory by services.lyrics, so repeated clicks are cheap. Rate
    limited (see LYRICS_RATE / REFRESH_COOLDOWN above) because every cache
    miss fans out to third-party services from our IP.
    """
    if not LYRICS_RATE.allow(request.remote_addr or "unknown"):
        abort(429)
    force = request.args.get("refresh") == "1"
    if force:
        track_key = "|".join(
            request.args.get(f) or "" for f in ("track_id", "artist", "title")
        )
        force = REFRESH_COOLDOWN.allow(track_key)
    result = fetch_lyrics(
        track_id=request.args.get("track_id"),
        artist=request.args.get("artist"),
        title=request.args.get("title"),
        album=request.args.get("album"),
        duration=request.args.get("duration"),
        force=force,
    )
    return jsonify(result)
