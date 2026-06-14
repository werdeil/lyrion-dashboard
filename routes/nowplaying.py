from flask import Blueprint, render_template, current_app, jsonify, request

from services.lyrion import get_active_now_playing
from services.database import get_track_lyrics, get_stats
from services.lyrics import fetch_lyrics

nowplaying_bp = Blueprint("nowplaying", __name__)


@nowplaying_bp.route("/")
def index():
    stats = get_stats()
    return render_template(
        "nowplaying.html",
        lyrion_host=current_app.config["LYRION_HOST"],
        stats=stats,
    )


@nowplaying_bp.route("/now-playing.json")
def now_playing_json():
    """Live state of whichever player is currently playing, polled by the page."""
    now = get_active_now_playing()
    now["lyrics"] = get_track_lyrics(now.get("track_id"))
    return jsonify(now)


@nowplaying_bp.route("/lyrics.json")
def lyrics_json():
    """Fetch lyrics from the web for a track, on explicit user request.

    The page calls this only when the local library has no lyrics, passing the
    metadata it already displays so we avoid re-querying Lyrion. Results are
    cached in-memory by services.lyrics, so repeated clicks are cheap.
    """
    result = fetch_lyrics(
        track_id=request.args.get("track_id"),
        artist=request.args.get("artist"),
        title=request.args.get("title"),
        album=request.args.get("album"),
        duration=request.args.get("duration"),
        force=request.args.get("refresh") == "1",
    )
    return jsonify(result)
