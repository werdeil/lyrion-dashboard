#!/usr/bin/env python3
"""Regenerate the README screenshots from fake data.

Runs the real Flask app with the Lyrion/SQLite layers monkeypatched to serve
a fake now-playing state (synced LRC lyrics, generated cover art, canned
library stats), then captures it with headless Chromium via Playwright:

- dashboard-en.png   desktop 1440x820, English, rose cover
- dashboard-fr.png   desktop 1440x820, French, same rose cover
- dashboard-mobile.png  phone 390x844, French, teal cover; the library has
                     no lyrics for this track so the (mocked) web search
                     provides them, showing "Source: LRCLIB"
- dashboard-app.png  phone 390x844 in a device frame, English, ember cover,
                     with the Android bridge injected so the in-app settings
                     button shows

Three different covers on purpose: the accent colour (progress bar, artist
name, switch, source line) is sampled from the artwork, so varied covers
show the adaptation.

Usage, from the repo root:

    pip install -r requirements.txt playwright
    playwright install chromium        # once; or set CHROMIUM_PATH
    python scripts/generate_screenshots.py [--out docs/screenshots]

No Lyrion server, database or network is needed.
"""

import argparse
import base64
import math
import os
import sys
import threading

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

# Config reads env at import time; the host only feeds the "open Lyrion" link.
os.environ.setdefault("LYRION_HOST", "https://lyrion.local:9000")

# These imports need the sys.path/env setup above to run first.
# pylint: disable=wrong-import-position
from playwright.sync_api import sync_playwright  # noqa: E402
from werkzeug.serving import make_server  # noqa: E402

# Repo-root imports, resolved by the sys.path insert (invisible to pylint).
import routes.nowplaying as np_routes  # noqa: E402  pylint: disable=import-error
from app import create_app  # noqa: E402  pylint: disable=import-error


# ---------------------------------------------------------------------------
# Fake data
# ---------------------------------------------------------------------------

def _pct(part, total):
    return round(part * 100 / total, 1) if total else 0


def _stats():
    s = {
        "albums_total": 842, "albums_played": 511,
        "albums_not_fully": 268, "albums_never": 63,
        "artists_total": 396, "artists_played": 201,
        "artists_partial": 168, "artists_unplayed": 27,
        "track_artists_total": 612, "track_artists_fully_played": 298,
        "track_artists_partially_played": 279, "track_artists_unplayed": 35,
        "songs_total": 11284, "songs_played_apc": 8930,
        "songs_unplayed_apc": 2354, "songs_total_plays_apc": 46215,
        "songs_total_skips_apc": 1873,
        "genres": 58, "rated_songs": 1024, "songs_with_lyrics": 6725,
        "velocity_30d": 412, "velocity_1year": 3980,
    }
    for key, total in [
        ("albums_played", "albums_total"),
        ("albums_not_fully", "albums_total"),
        ("albums_never", "albums_total"),
        ("artists_played", "artists_total"),
        ("artists_partial", "artists_total"),
        ("artists_unplayed", "artists_total"),
        ("track_artists_fully_played", "track_artists_total"),
        ("track_artists_partially_played", "track_artists_total"),
        ("track_artists_unplayed", "track_artists_total"),
        ("rated_songs", "songs_total"),
        ("songs_with_lyrics", "songs_total"),
    ]:
        s[key + "_pct"] = _pct(s[key], s[total])
    s["songs_played_pct"] = _pct(s["songs_played_apc"], s["songs_total"])
    s["songs_unplayed_apc_pct"] = _pct(s["songs_unplayed_apc"], s["songs_total"])
    return s


FAKE_STATS = _stats()


def _lrc(start, gap, lines, hold_after=None):
    """Build LRC text: one timestamped line every `gap` seconds, blank strings
    becoming untimed separators. `hold_after` marks the line meant to be
    highlighted in the screenshot: the next line is pushed 15s later so the
    karaoke highlight can't move while the capture settles (the timestamps
    themselves are invisible)."""
    out, t = [], start
    for line in lines:
        if line == "":
            out.append("")
            continue
        mm, ss = divmod(t, 60)
        out.append(f"[{int(mm):02d}:{ss:05.2f}]{line}")
        t += gap + (15 if line == hold_after else 0)
    return "\n".join(out)


TRACKS = {
    "rose": {
        "now": {
            "playing": True, "mode": "play", "time": 46.5, "duration": 214,
            "track_id": 1001, "title": "Horizon bleu", "artist": "Nova Ondine",
            "album": "Marées", "coverid": "fake-rose", "artwork_url": None,
            "player_name": "Salon", "player_id": "aa:bb:cc:dd:ee:01",
        },
        "lyrics": _lrc(9, 5.5, [
            "On y va, on y va, tous les deux",
            "Horizon bleu, horizon bleu",
            "La marée nous ramène chez nous",
            "",
            "Les phares s'allument, la nuit se fait douce",
            "On écrit nos noms dans le vent qui pousse",
            "Rien ne s'efface tant qu'on reste ensemble",
            "Le ciel et la mer, on dirait qu'ils se ressemblent",
            "",
            "Horizon bleu, horizon bleu",
            "On y va, on y va, tous les deux",
            "Horizon bleu, horizon bleu",
            "La marée nous ramène chez nous",
            "",
            "On garde le large",
            "On garde nos rires",
            "Jusqu'à l'horizon bleu",
        ], hold_after="On écrit nos noms dans le vent qui pousse"),
    },
    "teal": {
        "now": {
            "playing": True, "mode": "play", "time": 30.5, "duration": 189,
            "track_id": 1002, "title": "Nuit corail", "artist": "Forêt Numérique",
            "album": "Signaux", "coverid": "fake-teal", "artwork_url": None,
            "player_name": "Chambre", "player_id": "aa:bb:cc:dd:ee:02",
        },
        # No library lyrics: the auto web search (mocked below) finds the
        # synced version, so this capture shows a web source (LRCLIB).
        "lyrics": None,
        "web_source": "lrclib",
        "web_lyrics": _lrc(7, 5, [
            "Les diodes clignotent comme des lucioles",
            "Sous les arbres de fibre, la ville s'envole",
            "",
            "Nuit corail, nuit corail",
            "Les écrans s'allument, plus rien ne défaille",
            "Nuit corail, nuit corail",
            "On avance sans bruit dans les broussailles",
            "",
            "Chaque pixel raconte une histoire",
            "Un peu de nous dans la mémoire",
            "On garde le rythme, on garde le fil",
            "Même quand la nuit devient fragile",
            "",
            "Nuit corail, nuit corail",
        ], hold_after="Les écrans s'allument, plus rien ne défaille"),
    },
    "ember": {
        "now": {
            "playing": True, "mode": "play", "time": 29.5, "duration": 201,
            "track_id": 1003, "title": "Braises", "artist": "Les Lanternes",
            "album": "Solstice", "coverid": "fake-ember", "artwork_url": None,
            "player_name": "Cuisine", "player_id": "aa:bb:cc:dd:ee:03",
        },
        "lyrics": _lrc(8, 5, [
            "Un feu qui dort sous la cendre grise",
            "On souffle doucement sur les braises",
            "Les étincelles montent, la nuit se brise",
            "Et nos ombres dansent à leur aise",
            "",
            "Braises, braises, le cœur qui veille",
            "On garde la chaleur pour demain",
            "Braises, braises, jusqu'au soleil",
            "La lumière nous tient la main",
            "",
            "Un feu qui dort jamais ne meurt",
            "On le ranime à chaque heure",
        ], hold_after="Les étincelles montent, la nuit se brise"),
    },
}


# ---------------------------------------------------------------------------
# Generated cover art (SVG rendered to PNG by the same headless Chromium)
# ---------------------------------------------------------------------------

def _wave(y0, amp, period, phase, *, width=600, step=6):
    pts = [
        f"{x},{y0 + amp * math.sin(2 * math.pi * x / period + phase):.1f}"
        for x in range(0, width + step, step)
    ]
    return "M" + " L".join(pts)


def _cover_svg(stops, circles, wave_specs):
    grad = "".join(
        f'<stop offset="{off}" stop-color="{col}"/>' for off, col in stops
    )
    discs = "".join(
        f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{fill}" opacity="{op}"/>'
        for cx, cy, r, op, fill in circles
    )
    waves = "".join(
        f'<path d="{_wave(*spec)}" fill="none" stroke="#ffffff" '
        f'stroke-width="{sw}" opacity="{op}"/>'
        for spec, sw, op in wave_specs
    )
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="600" height="600">'
        '<defs><linearGradient id="g" x1="0" y1="0" x2="0.3" y2="1">'
        f"{grad}</linearGradient></defs>"
        '<rect width="600" height="600" fill="url(#g)"/>'
        f"{discs}{waves}</svg>"
    )


COVER_SVGS = {
    "fake-rose": _cover_svg(
        [(0, "#232a5c"), (0.55, "#8a4d8f"), (1, "#e07ba8")],
        [(180, 200, 150, 0.10, "#ffffff"), (120, 130, 90, 0.12, "#ffffff"),
         (300, 300, 190, 0.07, "#ffffff"), (90, 330, 70, 0.10, "#ffffff")],
        [((330, 26, 300, 0.0), 3, 0.55), ((370, 30, 340, 1.8), 3, 0.35),
         ((410, 24, 280, 3.6), 3, 0.25)],
    ),
    "fake-teal": _cover_svg(
        [(0, "#0e2f2a"), (0.55, "#1f6e5d"), (1, "#63c9a8")],
        [(170, 190, 140, 0.10, "#ffffff"), (110, 120, 85, 0.12, "#e8c56b"),
         (300, 290, 185, 0.07, "#ffffff"), (420, 140, 60, 0.10, "#e8c56b")],
        [((330, 22, 260, 0.8), 3, 0.50), ((368, 28, 320, 2.4), 3, 0.32),
         ((406, 22, 300, 4.2), 3, 0.22)],
    ),
    "fake-ember": _cover_svg(
        [(0, "#33150f"), (0.55, "#a34a22"), (1, "#f0a04b")],
        [(190, 210, 150, 0.10, "#ffffff"), (130, 140, 90, 0.12, "#ffd9a0"),
         (310, 300, 185, 0.07, "#ffffff"), (450, 180, 65, 0.10, "#ffd9a0")],
        [((335, 24, 290, 0.4), 3, 0.52), ((372, 28, 330, 2.1), 3, 0.34),
         ((410, 22, 270, 3.9), 3, 0.24)],
    ),
}


# ---------------------------------------------------------------------------
# Flask app with the data layer monkeypatched
# ---------------------------------------------------------------------------

SCENARIO = {}      # mutated between captures
COVER_PNGS = {}    # coverid -> PNG bytes, filled once Chromium is up

np_routes.get_active_now_playing = lambda: dict(SCENARIO["now"])
np_routes.get_track_lyrics = lambda track_id: SCENARIO["lyrics"]
np_routes.get_stats = lambda: FAKE_STATS
np_routes.fetch_cover = lambda coverid, size=None: (COVER_PNGS[coverid], "image/png")


def _fake_web_lyrics(**_kw):
    """The page (in auto mode) always asks the web: for a synced upgrade when
    the library has lyrics (return nothing, it keeps them), or from scratch
    when it doesn't (return the scenario's synced text with its provider)."""
    return {
        "lyrics": None,
        "synced": SCENARIO.get("web_lyrics"),
        "source": SCENARIO.get("web_source"),
    }


np_routes.fetch_lyrics = _fake_web_lyrics


# ---------------------------------------------------------------------------
# Capture
# ---------------------------------------------------------------------------

# Everything visible and settled: cover decoded, accent sampled from it,
# karaoke line highlighted, web-upgrade search finished (retry button back).
READY_JS = """
() => {
    const cover = document.getElementById('np-cover-img');
    const retry = document.getElementById('np-retry');
    return document.documentElement.style.getPropertyValue('--accent-color') !== ''
        && cover && cover.naturalWidth > 0
        && !!document.querySelector('.lrc-line.active')
        && retry && !retry.hidden;
}
"""

AUTO_MODE_JS = "try { localStorage.setItem('np-lyrics-mode', 'auto'); } catch (e) {}"
ANDROID_BRIDGE_JS = (
    "window.LyrionApp = { openMenu: function () {}, openSettings: function () {} };"
)


def capture(browser, base_url, track, *, locale, viewport, dpr, android=False):
    """Point a fresh browser context at the app showing `track` and return a
    PNG screenshot; `android` injects the WebView bridge so the in-app
    menu button appears."""
    SCENARIO.clear()
    SCENARIO.update(TRACKS[track])
    ctx = browser.new_context(
        locale=locale, viewport=viewport, device_scale_factor=dpr,
    )
    ctx.add_init_script(AUTO_MODE_JS)
    if android:
        ctx.add_init_script(ANDROID_BRIDGE_JS)
    page = ctx.new_page()
    page.goto(base_url)
    page.wait_for_function(READY_JS)
    page.wait_for_timeout(400)  # let the smooth lyrics scroll settle
    shot = page.screenshot()
    ctx.close()
    return shot


def render_cover(browser, svg):
    """Rasterise an SVG cover to PNG bytes with the browser already running."""
    ctx = browser.new_context(viewport={"width": 600, "height": 600})
    page = ctx.new_page()
    page.set_content(f"<body style='margin:0'>{svg}</body>")
    png = page.screenshot()
    ctx.close()
    return png


FRAME_HTML = """
<body style="margin:0; background:transparent;
             display:flex; justify-content:center; align-items:flex-start;">
<div id="phone" style="width:410px; padding:10px; box-sizing:border-box;
                       border-radius:42px; background:#0b0d12;">
  <div style="border-radius:32px; overflow:hidden; background:#101216;">
    <div style="position:relative; height:30px; display:flex; align-items:center;
                justify-content:space-between; padding:0 20px;
                font:600 12px system-ui,sans-serif; color:#c7ccd6;">
      <span>14:32</span>
      <div style="position:absolute; left:50%; top:9px; margin-left:-6px;
                  width:12px; height:12px; border-radius:50%; background:#000;"></div>
      <svg width="34" height="12" viewBox="0 0 34 12" fill="#c7ccd6">
        <path d="M6 10.5 1.5 5.4A7.6 7.6 0 0 1 6 3.8a7.6 7.6 0 0 1 4.5 1.6z"/>
        <rect x="14" y="2" width="16" height="8" rx="2"
              fill="none" stroke="#c7ccd6"/>
        <rect x="15.5" y="3.5" width="10" height="5" rx="1"/>
        <rect x="31" y="4.5" width="2" height="3" rx="1"/>
      </svg>
    </div>
    <img src="data:image/png;base64,{b64}" style="display:block; width:390px;">
  </div>
</div>
</body>
"""


def frame_phone(browser, screenshot_png):
    """Wrap a raw phone capture in a minimal device frame (bezel, status bar,
    punch-hole camera) so the app screenshot reads as 'the Android app'."""
    ctx = browser.new_context(
        viewport={"width": 440, "height": 960}, device_scale_factor=2,
    )
    page = ctx.new_page()
    page.set_content(FRAME_HTML.replace(
        "{b64}", base64.b64encode(screenshot_png).decode("ascii")
    ))
    png = page.locator("#phone").screenshot(omit_background=True)
    ctx.close()
    return png


def main():  # pylint: disable=too-many-locals
    """Serve the mocked app on a random port and write every screenshot."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--out", default=os.path.join(REPO_ROOT, "docs", "screenshots"),
        help="output directory (default: docs/screenshots)",
    )
    args = parser.parse_args()
    os.makedirs(args.out, exist_ok=True)

    server = make_server("127.0.0.1", 0, create_app())
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base_url = f"http://127.0.0.1:{server.server_port}/"

    with sync_playwright() as p:
        launch = {}
        if os.environ.get("CHROMIUM_PATH"):
            launch["executable_path"] = os.environ["CHROMIUM_PATH"]
        browser = p.chromium.launch(**launch)

        for coverid, svg in COVER_SVGS.items():
            COVER_PNGS[coverid] = render_cover(browser, svg)

        desktop = {"width": 1440, "height": 820}
        phone = {"width": 390, "height": 844}

        shots = {
            "dashboard-en.png": capture(
                browser, base_url, "rose",
                locale="en-US", viewport=desktop, dpr=1),
            "dashboard-fr.png": capture(
                browser, base_url, "rose",
                locale="fr-FR", viewport=desktop, dpr=1),
            "dashboard-mobile.png": capture(
                browser, base_url, "teal",
                locale="fr-FR", viewport=phone, dpr=2),
            "dashboard-app.png": frame_phone(browser, capture(
                browser, base_url, "ember",
                locale="en-US", viewport=phone, dpr=2, android=True)),
        }
        browser.close()

    for name, png in shots.items():
        path = os.path.join(args.out, name)
        with open(path, "wb") as fh:
            fh.write(png)
        print(f"wrote {path} ({len(png) // 1024} KiB)")


if __name__ == "__main__":
    main()
