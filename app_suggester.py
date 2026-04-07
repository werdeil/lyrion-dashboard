import os
import sqlite3
import requests
import urllib3
from flask import Flask, render_template_string, redirect, request, session

urllib3.disable_warnings()

app = Flask(__name__)
app.secret_key = "supersecretkey"

LYRION_HOST = os.getenv("LYRION_HOST")
DB_PATH = os.getenv("DB_PATH")
DB_PERSIST_PATH = os.getenv("DB_PERSIST_PATH")

# --------------------------------------------------
# LYRION JSON RPC
# --------------------------------------------------

def lyrion_request(payload):
    r = requests.post(
        f"{LYRION_HOST}/jsonrpc.js",
        json=payload,
        verify=False,
        timeout=5
    )
    return r.json()

def get_players():
    payload = {
        "id": 1,
        "method": "slim.request",
        "params": ["", ["players", "0", "100"]]
    }
    data = lyrion_request(payload)
    return data["result"].get("players_loop", [])

# --------------------------------------------------
# DATABASE
# --------------------------------------------------

def get_db_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.execute(f"ATTACH DATABASE '{DB_PERSIST_PATH}' AS persist")
    conn.row_factory = sqlite3.Row
    return conn

def get_albums():
    conn = get_db_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT albums.id,
               albums.title,
               contributors.name AS artist,
               albums.artwork
        FROM albums
        JOIN contributors ON albums.contributor = contributors.id
        ORDER BY RANDOM()
        LIMIT 5
    """)
    albums = cur.fetchall()
    conn.close()
    return albums

def get_stats():
    conn = get_db_conn()
    cur = conn.cursor()

    def q(sql):
        try:
            return cur.execute(sql).fetchone()[0] or 0
        except Exception as e:
            print(f"[STATS ERROR] {e}\nSQL: {sql}")
            return 0

    def pct(part, total):
        if total == 0:
            return 0
        return round(part * 100 / total, 1)

    stats = {
        # Albums
        "albums_total": q("SELECT count(distinct albums.id) FROM albums"),
        "albums_played": q("""
            SELECT count(distinct albums.id) FROM albums
            WHERE albums.id NOT IN (
                SELECT tracks.album FROM tracks
                JOIN alternativeplaycount ON tracks.urlmd5=alternativeplaycount.urlmd5
                WHERE tracks.audio=1 AND (alternativeplaycount.playcount=0 OR alternativeplaycount.playcount IS NULL)
            )
        """),
        "albums_not_fully": q("""
            SELECT count(distinct albums.id) FROM albums
            JOIN tracks ON tracks.album=albums.id
            JOIN alternativeplaycount ON tracks.urlmd5=alternativeplaycount.urlmd5
            WHERE tracks.audio=1 AND (alternativeplaycount.playcount=0 OR alternativeplaycount.playcount IS NULL)
            AND albums.id IN (
                SELECT tracks.album FROM tracks
                JOIN alternativeplaycount ON tracks.urlmd5=alternativeplaycount.urlmd5
                WHERE tracks.audio=1 AND alternativeplaycount.playcount>0
            )
        """),
        "albums_never": q("""
            SELECT count(distinct albums.id) FROM albums
            WHERE albums.id NOT IN (
                SELECT tracks.album FROM tracks
                JOIN alternativeplaycount ON tracks.urlmd5=alternativeplaycount.urlmd5
                WHERE tracks.audio=1 AND alternativeplaycount.playcount>0
            )
        """),

        # Album artists
        "artists_total": q("""
            SELECT count(distinct contributors.id) FROM contributors
            LEFT JOIN contributor_track ON contributors.id=contributor_track.contributor
            WHERE contributor_track.role=5
        """),
        "artists_played": q("""
            SELECT count(distinct contributor_track.contributor) FROM contributor_track
            JOIN tracks ON tracks.id=contributor_track.track
            WHERE contributor_track.contributor NOT IN (
                SELECT contributors.id FROM contributors
                JOIN contributor_track ON contributors.id=contributor_track.contributor
                JOIN tracks ON tracks.id=contributor_track.track
                JOIN alternativeplaycount ON tracks.urlmd5=alternativeplaycount.urlmd5
                WHERE tracks.audio=1
                AND (alternativeplaycount.playcount=0 OR alternativeplaycount.playcount IS NULL)
                AND contributor_track.role=5
            ) AND contributor_track.role=5
        """),
        "artists_partial": q("""
            SELECT count(distinct contributor_track.contributor) FROM contributor_track
            LEFT JOIN tracks ON tracks.id=contributor_track.track
            JOIN alternativeplaycount ON tracks.url=alternativeplaycount.url
            WHERE tracks.audio=1
            AND (alternativeplaycount.playcount=0 OR alternativeplaycount.playcount IS NULL)
            AND contributor_track.role=5
            AND contributor_track.contributor IN (
                SELECT contributors.id FROM contributors
                LEFT JOIN contributor_track ON contributors.id=contributor_track.contributor
                JOIN tracks ON tracks.id=contributor_track.track
                JOIN alternativeplaycount ON tracks.urlmd5=alternativeplaycount.urlmd5
                WHERE tracks.audio=1 AND alternativeplaycount.playcount>0
                AND contributor_track.role=5
            )
        """),
        "artists_unplayed": q("""
            SELECT count(distinct contributor_track.contributor) FROM contributor_track
            JOIN tracks ON tracks.id=contributor_track.track
            WHERE contributor_track.contributor NOT IN (
                SELECT contributors.id FROM contributors
                LEFT JOIN contributor_track ON contributors.id=contributor_track.contributor
                JOIN tracks ON tracks.id=contributor_track.track
                JOIN alternativeplaycount ON tracks.urlmd5=alternativeplaycount.urlmd5
                WHERE tracks.audio=1 AND alternativeplaycount.playcount>0
                AND contributor_track.role=5
            ) AND contributor_track.role=5
        """),

        # Songs
        "songs_total": q("SELECT count(*) FROM tracks WHERE audio=1"),
        "songs_played_apc": q("""
            SELECT count(distinct tracks.id) FROM tracks
            JOIN alternativeplaycount ON tracks.urlmd5=alternativeplaycount.urlmd5
            WHERE audio=1 AND alternativeplaycount.playcount>0
        """),
        "songs_unplayed_apc": q("""
            SELECT count(distinct tracks.id) FROM tracks
            JOIN alternativeplaycount ON tracks.urlmd5=alternativeplaycount.urlmd5
            WHERE audio=1 AND ifnull(alternativeplaycount.playcount, 0) = 0
        """),
        "songs_total_plays_apc": q("""
            SELECT sum(alternativeplaycount.playcount) FROM tracks
            JOIN alternativeplaycount ON tracks.url=alternativeplaycount.url
            WHERE audio=1 AND alternativeplaycount.playcount>0
        """),

        # Divers
        "genres": q("SELECT count(*) FROM genres"),
        "rated_songs": q("""
            SELECT count(*) FROM tracks
            JOIN persist.tracks_persistent ON tracks.url=persist.tracks_persistent.url
            WHERE audio=1 AND persist.tracks_persistent.rating>0
        """),
        "songs_with_lyrics": q("""
            SELECT count(distinct tracks.id) FROM tracks
            WHERE audio=1 AND lyrics IS NOT NULL
        """),

        # Velocity
        "velocity_30d": q("""
            SELECT COUNT(*) FROM persist.tracks_persistent
            WHERE lastplayed > strftime('%s','now','-30 days')
        """),
    }

    # Pourcentages albums
    stats["albums_played_pct"]    = pct(stats["albums_played"],    stats["albums_total"])
    stats["albums_not_fully_pct"] = pct(stats["albums_not_fully"], stats["albums_total"])
    stats["albums_never_pct"]     = pct(stats["albums_never"],     stats["albums_total"])

    # Pourcentages artistes
    stats["artists_played_pct"]   = pct(stats["artists_played"],   stats["artists_total"])
    stats["artists_partial_pct"]  = pct(stats["artists_partial"],  stats["artists_total"])
    stats["artists_unplayed_pct"] = pct(stats["artists_unplayed"], stats["artists_total"])

    # Pourcentages songs
    stats["songs_played_pct"]     = pct(stats["songs_played_apc"], stats["songs_total"])
    stats["songs_unplayed_apc_pct"]   = pct(stats["songs_unplayed_apc"],   stats["songs_total"])

    # Pourcentages divers
    stats["rated_songs_pct"]      = pct(stats["rated_songs"],      stats["songs_total"])
    stats["lyrics_pct"]           = pct(stats["songs_with_lyrics"], stats["songs_total"])

    conn.close()
    return stats


# --------------------------------------------------
# ROUTES
# --------------------------------------------------

@app.route("/", methods=["GET", "POST"])
def index():
    players = get_players()

    if request.method == "POST":
        session["player_id"] = request.form.get("player_id")

    selected_player = session.get("player_id")
    albums = get_albums()
    stats = get_stats()

    html = """
    <!doctype html>
    <html>
    <head>
        <title>Lyrion Suggester</title>
        <style>
            * { box-sizing: border-box; }
            body { font-family: Arial; background:#111; color:#eee; margin:0; padding:20px; }
            h1 { margin-top:0; }

            .main-layout {
                display: flex;
                gap: 24px;
                align-items: flex-start;
            }
            .left-panel { flex: 1; min-width: 0; }

            .stats-panel {
                width: 260px;
                flex-shrink: 0;
                background: #1a1a1a;
                border-radius: 10px;
                padding: 16px;
                border: 1px solid #333;
            }
            .stats-panel h2 {
                margin: 0 0 14px 0;
                font-size: 1rem;
                color: #aaa;
                text-transform: uppercase;
                letter-spacing: 1px;
            }
            .stat-group { margin-bottom: 16px; }
            .stat-group-title {
                font-size: 0.75rem;
                color: #888;
                text-transform: uppercase;
                letter-spacing: 1px;
                margin-bottom: 6px;
                border-bottom: 1px solid #333;
                padding-bottom: 4px;
            }
            .stat-row {
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 3px 0;
                font-size: 0.85rem;
            }
            .stat-row.sub {
                padding-left: 10px;
                color: #aaa;
                font-size: 0.8rem;
            }
            .stat-row.sub .stat-label::before { content: "↳ "; color: #555; }
            .stat-value { font-weight: bold; color: #1db954; white-space: nowrap; margin-left: 8px; }
            .stat-row.sub .stat-value { color: #aaa; }
            .velocity-value {
                font-size: 1.4rem;
                font-weight: bold;
                color: #1db954;
                text-align: center;
                margin-top: 4px;
            }
            .velocity-label { text-align: center; font-size: 0.75rem; color: #888; }

            .albums-grid { display: flex; flex-wrap: wrap; gap: 20px; }
            .album { text-align: center; width: 200px; }
            img { width:200px; height:200px; object-fit:cover; border-radius:8px; }
            button { padding:8px 12px; background:#1db954; border:none; color:white; cursor:pointer; border-radius:5px; }
            select { padding:5px; background:#222; color:#eee; border:1px solid #444; border-radius:4px; }
            hr { border-color: #333; margin: 16px 0; }
        </style>
    </head>
    <body>
        <h1>🎵 Lyrion Album Suggester</h1>

        <form method="POST" style="margin-bottom:16px;">
            <label>Player :</label>
            <select name="player_id">
                {% for p in players %}
                    <option value="{{ p.playerid }}"
                        {% if p.playerid == selected_player %}selected{% endif %}>
                        {{ p.name }}
                    </option>
                {% endfor %}
            </select>
            <button type="submit">OK</button>
        </form>

        {% if not selected_player %}
            <p style="color:#e74c3c;">⚠ Sélectionne un player avant de lancer un album</p>
        {% endif %}

        <div class="main-layout">

            <div class="left-panel">
                <div class="albums-grid">
                {% for album in albums %}
                    <div class="album">
                        <img src="{{ lyrion_host }}/music/{{ album.artwork }}/cover.jpg"
                             onerror="this.src='https://via.placeholder.com/200?text=No+Cover'">
                        <p><b>{{ album.title }}</b><br>{{ album.artist }}</p>
                        {% if selected_player %}
                            <a href="/play/{{ album.id }}">
                                <button>▶ Lire</button>
                            </a>
                        {% endif %}
                    </div>
                {% endfor %}
                </div>
            </div>

            <div class="stats-panel">
                <h2>📊 Librairie</h2>

                <div class="stat-group">
                    <div class="stat-group-title">🎵 Albums</div>
                    <div class="stat-row">
                        <span class="stat-label">Total</span>
                        <span class="stat-value">{{ stats.albums_total }}</span>
                    </div>
                    <div class="stat-row sub">
                        <span class="stat-label">Fully played</span>
                        <span>{{ stats.albums_played }} <small>({{ stats.albums_played_pct }}%)</small></span>
                    </div>
                    <div class="stat-row sub">
                        <span class="stat-label">Not fully played</span>
                        <span>{{ stats.albums_not_fully }} <small>({{ stats.albums_not_fully_pct }}%)</small></span>
                    </div>
                    <div class="stat-row sub">
                        <span class="stat-label">Never played</span>
                        <span>{{ stats.albums_never }} <small>({{ stats.albums_never_pct }}%)</small></span>
                    </div>
                </div>

                <!-- Album Artists -->
                <div class="stat-group">
                    <div class="stat-group-title">🎤 Album Artists</div>
                    <div class="stat-row">
                        <span class="stat-label">Total</span>
                        <span class="stat-value">{{ stats.artists_total }}</span>
                    </div>
                    <div class="stat-row sub">
                        <span class="stat-label">Fully played</span>
                        <span>{{ stats.artists_played }} <small>({{ stats.artists_played_pct }}%)</small></span>
                    </div>
                    <div class="stat-row sub">
                        <span class="stat-label">Partially played</span>
                        <span>{{ stats.artists_partial }} <small>({{ stats.artists_partial_pct }}%)</small></span>
                    </div>
                    <div class="stat-row sub">
                        <span class="stat-label">Never played</span>
                        <span>{{ stats.artists_unplayed }} <small>({{ stats.artists_unplayed_pct }}%)</small></span>
                    </div>
                </div>

                <!-- Songs -->
                <div class="stat-group">
                    <div class="stat-group-title">🎶 Songs</div>
                    <div class="stat-row">
                        <span class="stat-label">Total</span>
                        <span class="stat-value">{{ stats.songs_total }}</span>
                    </div>
                    <div class="stat-row sub">
                        <span class="stat-label">Played</span>
                        <span>{{ stats.songs_played_apc }} <small>({{ stats.songs_played_pct }}%)</small></span>
                    </div>
                    <div class="stat-row sub">
                        <span class="stat-label">Unplayed</span>
                        <span>{{ stats.songs_unplayed_apc }} <small>({{ stats.songs_unplayed_apc_pct }}%)</small></span>
                    </div>
                    <div class="stat-row sub">
                        <span class="stat-label">Total plays</span>
                        <span class="stat-value">{{ stats.songs_total_plays_apc }}</span>
                    </div>
                </div>

                <!-- Divers -->
                <div class="stat-group">
                    <div class="stat-group-title">📊 Divers</div>
                    <div class="stat-row">
                        <span class="stat-label">Genres</span>
                        <span class="stat-value">{{ stats.genres }}</span>
                    </div>
                    <div class="stat-row">
                        <span class="stat-label">Rated songs</span>
                        <span>{{ stats.rated_songs }} <small>({{ stats.rated_songs_pct }}%)</small></span>
                    </div>
                    <div class="stat-row">
                        <span class="stat-label">With lyrics</span>
                        <span>{{ stats.songs_with_lyrics }} <small>({{ stats.lyrics_pct }}%)</small></span>
                    </div>
                    <div class="stat-row">
                        <span class="stat-label">Played last 30d</span>
                        <span class="stat-value">{{ stats.velocity_30d }}</span>
                    </div>
                </div>
            </div>
        </div>

    </body>
    </html>
    """

    return render_template_string(
        html,
        players=players,
        albums=albums,
        selected_player=selected_player,
        lyrion_host=LYRION_HOST,
        stats=stats
    )

@app.route("/play/<int:album_id>")
def play(album_id):
    player_id = session.get("player_id")
    if not player_id:
        return "Aucun player sélectionné"

    payload = {
        "id": 1,
        "method": "slim.request",
        "params": [
            player_id,
            ["playlistcontrol", "cmd:load", f"album_id:{album_id}"]
        ]
    }
    lyrion_request(payload)
    return redirect("/")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=1111)
