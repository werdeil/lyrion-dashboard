var I18N = JSON.parse(document.getElementById('i18n-data').textContent);

document.querySelectorAll('.stat-group-title').forEach(function(title) {
    title.addEventListener('click', function() {
        var group = title.closest('.stat-group');
        if (group) {
            group.classList.toggle('collapsed');
        }
    });
});

var LYRION_HOST = document.body.dataset.lyrionHost || '';

// Inside the Android app a native bridge (window.LyrionApp) is injected;
// reveal the header bar (hidden on the web, where the branding lives in the
// tab title) with its menu button wired to the native full-screen settings
// screen (openMenu on current apps, openSettings on ones that predate it).
(function () {
    var appMenu = document.getElementById('app-menu');
    var bridge = window.LyrionApp;
    if (appMenu && bridge && (bridge.openMenu || bridge.openSettings)) {
        document.body.classList.add('in-app');
        appMenu.hidden = false;
        appMenu.addEventListener('click', function (e) {
            e.preventDefault();
            if (bridge.openMenu) {
                bridge.openMenu();
            } else {
                bridge.openSettings();
            }
        });
    }
})();

var nowPlaying = document.getElementById('now-playing');
var el = {
    player: document.getElementById('np-player'),
    playerRow: document.getElementById('np-player-row'),
    playerLink: document.getElementById('np-player-link'),
    playerSwitch: document.getElementById('np-player-switch'),
    title:  document.getElementById('np-title'),
    artist: document.getElementById('np-artist'),
    album:  document.getElementById('np-album'),
    lyrics: document.getElementById('np-lyrics'),
    source: document.getElementById('np-lyrics-source'),
    cover:  document.getElementById('np-cover-img'),
    modeBlock: document.getElementById('np-lyrics-mode-block'),
    autoSwitch: document.getElementById('np-auto-switch'),
    retry:  document.getElementById('np-retry'),
    searchStatus: document.getElementById('np-search-status'),
    progressBar: document.getElementById('np-progress-bar'),
    lyrionLink: document.getElementById('lyrion-link'),
    scrollReset: document.getElementById('np-scroll-reset'),
    empty: document.getElementById('np-empty'),
    emptyMosaic: document.getElementById('np-empty-mosaic'),
    emptyOpen: document.getElementById('np-empty-open'),
    recent: document.getElementById('np-recent'),
    recentPile: document.getElementById('np-recent-pile'),
};

// Web lyrics auto-search is a single on/off switch:
//   'off'  – never query the web, just show the library's lyrics (if any)
//   'auto' – search every track the library lacks (synced) lyrics for
// Display is automatic, never a user choice: we always prefer synced (LRC)
// lyrics and render them as karaoke, falling back to plain text when only plain
// lyrics exist. The chosen state persists in localStorage.
var LYRICS_MODE_KEY = 'np-lyrics-mode';
var lyricsMode = 'off';
try {
    var savedMode = localStorage.getItem(LYRICS_MODE_KEY);
    if (savedMode === 'off' || savedMode === 'auto') {
        lyricsMode = savedMode;
    } else if (localStorage.getItem('np-auto-lyrics') === '1') {
        lyricsMode = 'auto';  // migrate the previous boolean toggle preference
    }
} catch (e) {}

function updateSwitch() {
    if (!el.autoSwitch) { return; }
    var on = lyricsMode === 'auto';
    el.autoSwitch.setAttribute('aria-checked', on ? 'true' : 'false');
    el.autoSwitch.classList.toggle('is-on', on);
    updateRetry();
}

// The manual retry button sits in the spinner's slot: it only shows in auto
// mode and while no search is running (the spinner replaces it meanwhile). It
// greys out while the server would refuse a new search for this track, so a
// click never lands on a fuse instead of a search.
var searching = false;
var retryHeld = false;
function updateRetry() {
    if (!el.retry) { return; }
    el.retry.hidden = searching || lyricsMode !== 'auto';
    el.retry.disabled = retryHeld;
}

// Held for exactly as long as the server says its per-track cooldown will run.
var retryHoldTimer = null;
function holdRetry(seconds) {
    clearTimeout(retryHoldTimer);
    retryHeld = seconds > 0;
    if (retryHeld) {
        retryHoldTimer = setTimeout(function() {
            retryHeld = false;
            updateRetry();
        }, seconds * 1000);
    }
    updateRetry();
}

function persistMode() {
    try { localStorage.setItem(LYRICS_MODE_KEY, lyricsMode); } catch (e) {}
}

var MATERIAL_BASE = LYRION_HOST ? LYRION_HOST + '/material/' : '#';
var IS_ANDROID = /Android/i.test(navigator.userAgent || '');
var MATERIAL_APP_PKG = 'com.craigd.lmsmaterial.app';
function setMaterialLink(anchor, playerId) {
    if (!anchor) { return; }
    if (!LYRION_HOST) { anchor.href = '#'; return; }
    var web = MATERIAL_BASE + (playerId ? '?player=' + encodeURIComponent(playerId) : '');
    if (IS_ANDROID) {
        anchor.href = 'intent://' + web.replace(/^https?:\/\//, '') +
            '#Intent;scheme=https;type=text/html;package=' + MATERIAL_APP_PKG +
            ';S.browser_fallback_url=' + encodeURIComponent(web) + ';end';
    } else {
        anchor.href = web;
        anchor.target = 'lyrion';
        // rel="noopener"/"noreferrer" makes a named target behave like
        // _blank, defeating tab reuse; clear it for the (trusted) server.
        anchor.rel = '';
    }
}

function setLyrionLink(playerId) {
    setMaterialLink(el.lyrionLink, playerId);
    // The player-name link opens Lyrion focused on the very player shown.
    setMaterialLink(el.playerLink, playerId);
    // The empty-state "open Lyrion" button always targets the plain Material
    // page: with nothing playing there is no player to focus.
    setMaterialLink(el.emptyOpen, null);
}

// Player this device follows when several play at once, kept per device (the
// server holds no selection state) and sent to the poll as ?player=<id>.
var SELECTED_PLAYER_KEY = 'lyrion.selectedPlayer';
var selectedPlayer = null;
try { selectedPlayer = localStorage.getItem(SELECTED_PLAYER_KEY) || null; } catch (e) {}

function setSelectedPlayer(id) {
    selectedPlayer = id || null;
    try {
        if (selectedPlayer) { localStorage.setItem(SELECTED_PLAYER_KEY, selectedPlayer); }
        else { localStorage.removeItem(SELECTED_PLAYER_KEY); }
    } catch (e) {}
}

var LYRION_ARROW_PATH = 'M19 19H5V5h7V3H5c-1.11 0-2 .9-2 2v14c0 1.1.89 2 2 2h14c1.1 0 2-.9 2-2v-7h-2v7zM14 3v2h3.59l-9.83 9.83 1.41 1.41L19 6.41V10h2V3h-7z';
var CHEVRON_PATH = 'M7 10l5 5 5-5z';
function makeIcon(pathD, cls) {
    var ns = 'http://www.w3.org/2000/svg';
    var svg = document.createElementNS(ns, 'svg');
    svg.setAttribute('viewBox', '0 0 24 24');
    svg.setAttribute('aria-hidden', 'true');
    svg.setAttribute('focusable', 'false');
    svg.setAttribute('class', cls);
    var path = document.createElementNS(ns, 'path');
    path.setAttribute('d', pathD);
    svg.appendChild(path);
    return svg;
}

function closeSwitchMenu() {
    if (!el.playerSwitch) { return; }
    var menu = el.playerSwitch.querySelector('.np-switch-menu');
    var toggle = el.playerSwitch.querySelector('.np-switch-toggle');
    if (menu) { menu.hidden = true; }
    if (toggle) { toggle.setAttribute('aria-expanded', 'false'); }
}
// Close the menu on an outside click or Escape.
document.addEventListener('click', function (e) {
    if (el.playerSwitch && !el.playerSwitch.contains(e.target)) { closeSwitchMenu(); }
});
document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') { closeSwitchMenu(); }
});

// Signature (player ids + active id) so the DOM is only rebuilt on real change,
// keeping the menu state across steady-state polls.
var lastSwitchKey = null;

function renderPlayerSwitch(data) {
    if (!el.playerSwitch) { return; }
    var players = data.players || [];

    // Followed player stopped (or was ignored): revert to automatic selection.
    if (selectedPlayer && data.selection_active === false) {
        setSelectedPlayer(null);
    }

    if (players.length < 2) {
        el.playerSwitch.hidden = true;
        el.playerSwitch.textContent = '';
        lastSwitchKey = null;
        return;
    }

    el.playerRow.hidden = true;  // the dropdown takes over the name row
    el.playerSwitch.hidden = false;

    var activeId = data.player_id;
    var key = players.map(function (p) { return p.id; }).join(',') + '|' + activeId;
    if (key === lastSwitchKey) { return; }
    lastSwitchKey = key;
    el.playerSwitch.textContent = '';

    // Trigger: the followed player's name + a chevron, opening the menu.
    var toggle = document.createElement('button');
    toggle.type = 'button';
    toggle.className = 'np-switch-toggle';
    toggle.setAttribute('aria-haspopup', 'true');
    toggle.setAttribute('aria-expanded', 'false');
    var toggleName = document.createElement('span');
    toggleName.className = 'np-switch-current';
    toggleName.textContent = data.player_name || '';
    toggle.appendChild(toggleName);
    toggle.appendChild(makeIcon(CHEVRON_PATH, 'np-switch-chevron'));

    var menu = document.createElement('div');
    menu.className = 'np-switch-menu';
    menu.setAttribute('role', 'menu');
    menu.hidden = true;

    players.forEach(function (p) {
        var current = p.id === activeId;
        var item;
        if (current) {
            // The followed player's row opens Lyrion (like the single-player name).
            item = document.createElement('a');
            setMaterialLink(item, p.id);
            item.title = I18N.open_lyrion;
            item.appendChild(document.createTextNode(p.name || ''));
            item.appendChild(makeIcon(LYRION_ARROW_PATH, 'np-switch-arrow'));
            // Let the link open, but close the menu behind it.
            item.addEventListener('click', closeSwitchMenu);
        } else {
            item = document.createElement('button');
            item.type = 'button';
            item.appendChild(document.createTextNode(p.name || ''));
            item.addEventListener('click', function () {
                closeSwitchMenu();
                setSelectedPlayer(p.id);
                poll();
            });
        }
        item.className = 'np-switch-item' + (current ? ' is-current' : '');
        item.setAttribute('role', 'menuitem');
        menu.appendChild(item);
    });

    toggle.addEventListener('click', function (e) {
        e.stopPropagation();
        var open = menu.hidden;
        menu.hidden = !open;
        toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
    });

    el.playerSwitch.appendChild(toggle);
    el.playerSwitch.appendChild(menu);
}
var lastTrackKey = null;
var currentTrack = null;
var lyricsTried = false;
// Web lyrics resolved for the current track ({text, source}), so re-selecting a
// mode reuses the result instead of searching again. Reset on every track.
var webResult = null;

var lrcLines = null;
// The .lrc-line elements paralleling lrcLines, cached at build time so the
// karaoke tick (4×/s) never re-queries the DOM; and the index of the line
// currently highlighted, so ticks where it hasn't moved skip the DOM
// entirely — the active line only changes every few seconds.
var lrcNodes = null;
var lrcActiveIdx = -1;

// Whether the lyrics box auto-scrolls to keep the karaoke-highlighted line in
// view. A manual scroll (wheel/touch) pauses it so the user can read ahead or
// back without fighting the highlight; the reset button (or a new track)
// resumes it.
var autoFollowScroll = true;
// Cumulative scroll distance (px) tracked while auto-follow is still on, so a
// deliberate scroll pauses it but a stray wheel tick or finger brush doesn't.
// Only guards the initial trip out of auto-follow — once paused, scrolling is
// unrestricted.
var SCROLL_PAUSE_THRESHOLD = 60;
var wheelAccum = 0;
var wheelLastAt = 0;
var touchStartY = null;

function setAutoFollow(on) {
    autoFollowScroll = on;
    if (on) {
        wheelAccum = 0;
        touchStartY = null;
    }
    updateScrollReset();
}

// The reset button only makes sense while synced lyrics are on screen with the
// karaoke follow paused. Plain lyrics have no follow to resume, so keep the
// button hidden even if a pause is still remembered (it survives a mode switch
// via keepScroll and reapplies when the synced view comes back).
function updateScrollReset() {
    if (el.scrollReset) { el.scrollReset.hidden = autoFollowScroll || !lrcLines; }
}

var TINT_NEUTRAL = '#8b94a8';
var ACCENT_DEFAULT = '#4f86c6';

function setTint(color) {
    document.documentElement.style.setProperty('--tint-color', color);
}

function setAccent(color) {
    document.documentElement.style.setProperty('--accent-color', color);
}

function resetColors() {
    setTint(TINT_NEUTRAL);
    setAccent(ACCENT_DEFAULT);
}

// Cover colour extraction mirrors Lyrion's Material skin (currentcover.js):
// the tint is the *average* colour (FastAverageColor) while the accent is the
// *dominant* vibrant swatch (Vibrant.js), normalised in HSV so every accent
// lands at a consistent brightness. Helpers below are copied from Material.

function rgb2Hsv(rgb) {
    var r = rgb[0], g = rgb[1], b = rgb[2],
        max = Math.max(r, g, b), min = Math.min(r, g, b),
        d = max - min, h, s = (max === 0 ? 0 : d / max), v = max / 255;
    switch (max) {
        case min: h = 0; break;
        case r: h = (g - b) + d * (g < b ? 6 : 0); h /= 6 * d; break;
        case g: h = (b - r) + d * 2; h /= 6 * d; break;
        case b: h = (r - g) + d * 4; h /= 6 * d; break;
    }
    return [h, s, v];
}

function hsv2Rgb(hsv) {
    var h = hsv[0], s = hsv[1], v = hsv[2], r, g, b,
        i = Math.floor(h * 6),
        f = h * 6 - i,
        p = v * (1 - s),
        q = v * (1 - f * s),
        t = v * (1 - (1 - f) * s);
    switch (i % 6) {
        case 0: r = v; g = t; b = p; break;
        case 1: r = q; g = v; b = p; break;
        case 2: r = p; g = v; b = t; break;
        case 3: r = p; g = q; b = v; break;
        case 4: r = t; g = p; b = v; break;
        case 5: r = v; g = p; b = q; break;
    }
    return [Math.round(r * 255), Math.round(g * 255), Math.round(b * 255)];
}

// Accent normalisation in HSV: fixed brightness (Material's V), saturation
// bounded on both sides.
var ACCENT_V = 0.8235;
// Under the floor the accent reads as the lyrics' own off-white; under the
// minimum the swatch's hue is sampling noise, so ACCENT_DEFAULT stands in.
var ACCENT_SAT_MIN = 0.15;
var ACCENT_SAT_FLOOR = 0.45;
var ACCENT_SAT_MAX = 0.8;

function rgb2Css(rgb) {
    return 'rgb(' + rgb[0] + ',' + rgb[1] + ',' + rgb[2] + ')';
}

// Dark UI: prefer the brightest swatches first, matching Material's order.
var SWATCH_ORDER = ['Vibrant', 'LightVibrant', 'Muted', 'LightMuted', 'DarkVibrant', 'DarkMuted'];

var fac;

function sampleCoverTint() {
    try {
        var img = el.cover;
        if (!img.naturalWidth) { return; }

        // Dominant vibrant swatch -> accent.
        var vRgb;
        try {
            var swatches = new Vibrant(img).swatches();
            for (var i = 0; i < SWATCH_ORDER.length && !vRgb; i++) {
                var sw = swatches[SWATCH_ORDER[i]];
                if (sw && sw.getPopulation() > 0) { vRgb = sw.getRgb(); }
            }
        } catch (e) { /* fall through to average-only */ }

        // Average colour -> tint.
        if (!fac) { fac = new FastAverageColor(); }
        var avg = fac.getColor(img, { mode: 'precision' });
        var avRgb = [avg.value[0], avg.value[1], avg.value[2]];

        setTint(rgb2Css(avRgb));

        var hsv = vRgb && rgb2Hsv(vRgb);
        if (!hsv || hsv[1] < ACCENT_SAT_MIN) {
            setAccent(ACCENT_DEFAULT);
        } else {
            hsv[1] = Math.min(Math.max(hsv[1], ACCENT_SAT_FLOOR), ACCENT_SAT_MAX);
            hsv[2] = ACCENT_V;
            setAccent(rgb2Css(hsv2Rgb(hsv)));
        }
    } catch (e) {
        resetColors();
    }
}

var progress = { time: 0, duration: 0, playing: false, syncedAt: 0 };
// Last measured now-playing round-trip latency (ms), used to back-date syncedAt.
var pollRtt = 0;

function paintProgress() {
    var t = progress.time;
    if (progress.playing) {
        t += (Date.now() - progress.syncedAt) / 1000;
    }
    var pct = progress.duration > 0
        ? Math.max(0, Math.min(100, (t / progress.duration) * 100))
        : 0;
    el.progressBar.style.width = pct + '%';
    if (lrcLines) { syncLyrics(); }
}

var SOURCE_LABELS = {
    library:    I18N.source_library,
    lrclib:     'LRCLIB',
    musixmatch: 'Musixmatch',
    genius:     'Genius',
};

var LRC_LINE_RE = /^\[(\d+):(\d{2}(?:\.\d+)?)\](.*)$/;
var LRC_META_RE = /^\[(ar|ti|al|au|by|offset|length|re|ve):/i;

function parseLRC(text) {
    var lines = text.split(/\r?\n/);
    var parsed = [];
    var offset = 0;
    var lastTime = 0;
    for (var i = 0; i < lines.length; i++) {
        var line = lines[i];
        var meta = line.match(/^\[offset:([+-]?\d+)\]/i);
        if (meta) { offset = parseInt(meta[1], 10) / 1000; continue; }
        if (LRC_META_RE.test(line)) { continue; }
        var m = line.match(LRC_LINE_RE);
        if (!m) {
            // Preserve blank separator lines between verses. They carry no
            // timestamp, so reuse the previous line's time (they sort right
            // after it) and flag them so they never become the active line.
            if (line.trim() === '' && parsed.length) {
                parsed.push({ time: lastTime, text: '', blank: true });
            }
            continue;
        }
        var mm = parseInt(m[1], 10);
        var ss = parseFloat(m[2]);
        var t = mm * 60 + ss + offset;
        lastTime = t;
        // Trim so a timestamp with only whitespace (e.g. "[00:06.13] ") is
        // treated as a blank separator: rendered as a visible gap and never
        // allowed to become the active line, like the untimed blank lines above.
        var txt = (m[3] || '').trim();
        if (txt === '') {
            parsed.push({ time: t, text: '', blank: true });
        } else {
            parsed.push({ time: t, text: txt });
        }
    }
    if (!parsed.length) { return null; }
    parsed.sort(function(a, b) { return a.time - b.time; });
    return parsed;
}

// keepScroll preserves the current scroll position (used when only the mode
// changes); by default the view resets to the top (used on a new track).
function setLyrics(text, isEmpty, keepScroll) {
    var prevScroll = keepScroll ? el.lyrics.scrollTop : 0;
    // A new track (not just a mode switch on the same one) restarts the
    // karaoke follow, since any earlier manual pause no longer applies to it.
    if (!keepScroll) { setAutoFollow(true); }
    el.lyrics.classList.remove('empty', 'lrc-mode');
    el.lyrics.textContent = '';
    lrcLines = null;
    lrcNodes = null;
    lrcActiveIdx = -1;

    if (!text || isEmpty) {
        el.lyrics.textContent = text || I18N.no_lyrics_library;
        el.lyrics.classList.toggle('empty', !!isEmpty || !text);
        el.lyrics.scrollTop = prevScroll;
        updateScrollReset();
        return;
    }

    var parsed = parseLRC(text);
    if (parsed) {
        lrcLines = parsed;
        lrcNodes = [];
        el.lyrics.classList.add('lrc-mode');
        for (var i = 0; i < parsed.length; i++) {
            var div = document.createElement('div');
            div.className = 'lrc-line';
            div.dataset.time = parsed[i].time;
            div.textContent = parsed[i].text || '\u00a0';
            el.lyrics.appendChild(div);
            lrcNodes.push(div);
        }
        // Set the scroll only once the lines exist: doing it before the rebuild
        // would let scroll-behavior:smooth cancel the reset mid-animation.
        el.lyrics.scrollTop = prevScroll;
        syncLyrics();
    } else {
        el.lyrics.textContent = text;
        el.lyrics.scrollTop = prevScroll;
    }
    updateScrollReset();
}

function currentTime() {
    var t = progress.time;
    if (progress.playing) {
        t += (Date.now() - progress.syncedAt) / 1000;
    }
    return t;
}

// Repaint one line's classes from its distance to the current active index.
// Only the handful of lines around the old and new active positions ever
// change state, so repainting is per-line rather than a full sweep.
function paintLine(idx) {
    if (!lrcNodes || idx < 0 || idx >= lrcNodes.length) { return; }
    lrcNodes[idx].classList.toggle('active', idx === lrcActiveIdx);
    lrcNodes[idx].classList.toggle('near', Math.abs(idx - lrcActiveIdx) === 1);
}

// forceScroll re-anchors the view even when the active line hasn't moved —
// used to snap back after a small manual scroll and by the resume button.
function syncLyrics(forceScroll) {
    if (!lrcLines || !lrcNodes || !lrcNodes.length) { return; }
    var t = currentTime();
    var activeIdx = -1;
    for (var i = 0; i < lrcLines.length; i++) {
        if (lrcLines[i].time <= t) {
            // Blank separator lines share the previous line's time; never let
            // one be the active line — keep the last real line highlighted.
            if (!lrcLines[i].blank) { activeIdx = i; }
        } else { break; }
    }

    if (activeIdx !== lrcActiveIdx) {
        // The active line only moves every few seconds while this runs four
        // times a second; when it does move, touch just the lines whose state
        // changes (old and new active lines and their neighbours) instead of
        // rewriting every line of the song.
        var prev = lrcActiveIdx;
        lrcActiveIdx = activeIdx;
        paintLine(prev - 1);
        paintLine(prev);
        paintLine(prev + 1);
        paintLine(activeIdx - 1);
        paintLine(activeIdx);
        paintLine(activeIdx + 1);
        forceScroll = true;
    }

    if (forceScroll && autoFollowScroll && activeIdx >= 0) {
        var active = lrcNodes[activeIdx];
        // Anchor the active line around the upper third of the box rather than
        // dead centre, so fewer past lines linger and more upcoming lines show.
        var target = active.offsetTop - el.lyrics.clientHeight / 3 + active.clientHeight / 2;
        el.lyrics.scrollTop = Math.max(0, target);
    }
}

// Doubles as the synced/plain indicator. Every caller runs right after
// setLyrics() on the same content, so lrcLines already tells whether the
// lyrics on screen are time-synced: if so, tint the line in the accent
// colour; plain lyrics keep the muted default.
function setLyricsSource(source) {
    var label = source && SOURCE_LABELS[source];
    var synced = !!(label && lrcLines);
    el.source.textContent = label
        ? I18N.source_prefix + ' ' + label
        : '';
    el.source.classList.toggle('is-synced', synced);
    el.source.title = synced ? I18N.lyrics_synced_hint : '';
}

// Toggle the "searching the web" spinner. Shown even when local lyrics are
// already on screen, so the user knows a synced version is still being fetched.
// The retry button swaps out for it, which also keeps searches from stacking.
function setSearching(on) {
    searching = on;
    if (el.searchStatus) { el.searchStatus.hidden = !on; }
    updateRetry();
}

// Cover tile (px) the row count is sized around, and the band it is held to.
var MOSAIC_TILE = 130;
var MOSAIC_MIN_ROWS = 3;
var MOSAIC_MAX_ROWS = 4;
var MOSAIC_GAP = 10;
// How long the belt rests between advances, which is what it costs: a backdrop
// in constant motion is recomposited every frame and takes a whole core.
var MOSAIC_STEP_MS = 6000;

// The covers ride one serpentine belt: row 0 left→right, row 1 right→left and
// so on down the card, then a wrap from the bottom back to the top.
var mosaicGeom = null;
var mosaicIds = null;
var mosaicTimer = 0;

function prefersReducedMotion() {
    return !!(window.matchMedia &&
        window.matchMedia('(prefers-reduced-motion: reduce)').matches);
}

// The spare slot per row is load-bearing: it keeps both row ends off the card,
// which is what lets a cover cross rows out of sight (mosaicSlot).
function mosaicGridRows(W, H, rows) {
    // A tile is a gap shorter than its row band, so rows don't touch.
    var rowH = H / rows;
    return {
        rows: rows, rowH: rowH, step: rowH, tile: rowH - MOSAIC_GAP,
        perRow: Math.ceil(W / rowH) + 1,
    };
}

// Layout and cover request both derive from this, so they can't drift.
function mosaicGrid(W, H) {
    return mosaicGridRows(W, H, Math.min(MOSAIC_MAX_ROWS,
        Math.max(MOSAIC_MIN_ROWS, Math.round(H / MOSAIC_TILE))));
}

function mosaicCardW() {
    return el.emptyMosaic.offsetWidth || 900;
}

function mosaicCardH() {
    return el.emptyMosaic.offsetHeight || 500;
}

// A spare per row on top of the belt's slots, so a card that grows a little
// still has distinct covers to fill it.
function mosaicCoversWanted() {
    var grid = mosaicGrid(mosaicCardW(), mosaicCardH());
    return Math.min(grid.rows * (grid.perRow + 1), 200);
}

// Bucketed, so a resize reuses cached thumbnails instead of having Lyrion
// render a new size for every pixel width the card passes through.
function mosaicCoverSize(tile) {
    return Math.min(256, Math.max(96, Math.ceil(tile / 32) * 32));
}

function placeTile(tile, x, y, instant) {
    if (instant) {
        tile.style.transition = 'none';
    }
    tile.style.transform = 'translate3d(' + x + 'px,' + y + 'px,0)';
    if (instant) {
        void tile.offsetWidth;   // flush, so the next write transitions from here
        tile.style.transition = '';
    }
}

// The last slot sits a step past the final row, off the card, and is where the
// belt closes: an odd row count leaves its two ends on opposite sides.
function mosaicSlot(g, s) {
    var closing = s === g.slots - 1;
    var row = closing ? g.rows - 1 : Math.floor(s / g.perRow);
    var k = closing ? g.perRow : (s % g.perRow);
    // Even rows travel right, odd rows left: boustrophedon. The whole belt sits
    // a step to the left, so covers enter from off the edge, not at x=0.
    return {
        x: ((row % 2 === 0) ? k : (g.perRow - k)) * g.step - g.step,
        y: row * g.rowH + MOSAIC_GAP / 2,
    };
}

// A cover glides one step along its row and is placed outright anywhere else,
// the belt only breaking off the card. A row change glides on the row it left.
function positionMosaic(phase) {
    var g = mosaicGeom;
    if (!g) { return; }
    for (var i = 0; i < g.tiles.length; i++) {
        var s = (i + Math.round(phase / g.step)) % g.slots;
        var at = mosaicSlot(g, s);
        var tile = g.tiles[i];
        if (g.dropY[i] !== undefined) {
            placeTile(tile, g.drawnX[i], g.dropY[i], true);
            g.drawnY[i] = g.dropY[i];
            g.dropY[i] = undefined;
        }
        if (g.drawnX[i] === undefined ||
                Math.abs(at.x - g.drawnX[i]) > g.step * 1.5) {
            placeTile(tile, at.x, at.y, true);
            g.drawnY[i] = at.y;
        } else if (g.drawnY[i] === at.y) {
            placeTile(tile, at.x, at.y, false);
        } else {
            placeTile(tile, at.x, g.drawnY[i], false);
            g.dropY[i] = at.y;
        }
        g.drawnX[i] = at.x;
    }
}

// The tiles' CSS transform transition is what glides them to the new slot.
function stepMosaic() {
    var g = mosaicGeom;
    if (!g) { return; }
    g.phase = (g.phase + g.step) % g.length;
    positionMosaic(g.phase);
}

// Safe to call from anywhere: it checks itself that the empty state is the card
// on screen and the page visible, and schedules nothing otherwise.
function startMosaic() {
    if (mosaicTimer || !mosaicGeom || document.hidden) { return; }
    if (!nowPlaying.classList.contains('is-empty') || prefersReducedMotion()) { return; }
    mosaicTimer = setInterval(stepMosaic, MOSAIC_STEP_MS);
}

function stopMosaic() {
    if (!mosaicTimer) { return; }
    clearInterval(mosaicTimer);
    mosaicTimer = 0;
}

// Covers are fetched in parallel (fast) but revealed strictly in belt order —
// row 0 left→right, row 1 right→left, and so on — so the collage fills in along
// the caterpillar's path instead of popping in at random. Tiles start hidden
// (CSS opacity 0); the cursor uncovers them one by one, waiting whenever the
// next tile hasn't downloaded yet and resuming from that tile's load handler.
var MOSAIC_REVEAL_STEP = 25;   // ms between covers appearing
var mosaicRevealCursor = 0;
var mosaicRevealTimer = null;

function advanceMosaicReveal() {
    mosaicRevealTimer = null;
    var g = mosaicGeom;
    if (!g) { return; }
    if (mosaicRevealCursor >= g.tiles.length) { return; }
    var img = g.tiles[mosaicRevealCursor];
    // `complete` is true once the image has loaded *or* errored, so a rare
    // failed cover advances the caterpillar instead of stalling it.
    if (!img.complete) { return; }
    img.classList.add('is-shown');
    mosaicRevealCursor++;
    mosaicRevealTimer = setTimeout(advanceMosaicReveal, MOSAIC_REVEAL_STEP);
}

// Lay the fetched covers out along the belt, sized to the current card. Called
// on first load and again on resize (reusing the covers already fetched).
function layoutMosaic(ids) {
    el.emptyMosaic.textContent = '';
    if (mosaicRevealTimer) { clearTimeout(mosaicRevealTimer); mosaicRevealTimer = null; }
    mosaicRevealCursor = 0;
    var reduce = prefersReducedMotion();
    var W = mosaicCardW();
    var H = mosaicCardH();
    var grid = mosaicGrid(W, H);
    // Too few covers for that many rows: fewer, taller ones. Dropping a row
    // without regrowing the rest would leave bare card at the bottom.
    while (grid.rows > 1 && ids.length < grid.rows * grid.perRow + 1) {
        grid = mosaicGridRows(W, H, grid.rows - 1);
    }
    var count = grid.rows * grid.perRow + 1;
    var size = mosaicCoverSize(grid.tile);

    el.emptyMosaic.style.setProperty('--mosaic-tile', grid.tile + 'px');
    var frag = document.createDocumentFragment();
    var tiles = [];
    for (var i = 0; i < count; i++) {
        var img = document.createElement('img');
        img.className = 'np-mosaic-tile';
        // A finished download (or error) may need to un-stall the reveal cursor
        // if it was waiting on this very tile.
        img.onload = img.onerror = function() {
            if (mosaicRevealTimer === null) { advanceMosaicReveal(); }
        };
        img.src = '/cover/' + encodeURIComponent(ids[i % ids.length]) + '.jpg?size=' + size;
        img.alt = '';
        img.decoding = 'async';
        if (reduce) { img.classList.add('is-shown'); }
        frag.appendChild(img);
        tiles.push(img);
    }
    mosaicGeom = {
        tiles: tiles, step: grid.step, rowH: grid.rowH,
        rows: grid.rows, perRow: grid.perRow, slots: count,
        length: count * grid.step, phase: 0,
        // Where each tile is drawn, and the row drop owed to it.
        drawnX: [], drawnY: [], dropY: [],
    };
    // Placed before entering the document: a tile first rendered already at its
    // position has no earlier transform, so the glide can't fire on layout.
    positionMosaic(0);
    el.emptyMosaic.appendChild(frag);
    // Reduced motion: no caterpillar fill, show everything at once (tiles were
    // already marked shown above); otherwise start the ordered reveal.
    if (reduce) {
        mosaicRevealCursor = tiles.length;
    } else {
        advanceMosaicReveal();
    }
}

// Fill the empty-state background with the most recently played covers.
// Fetched when the empty state shows and invalidated while something plays
// (see render()): playback changes what "recently played" means, so a mosaic
// kept from page load would miss the very listens that just ended.
// On failure the guard resets so the next poll retries; without covers the
// empty state simply stays as plain text, same as before.
var mosaicLoading = false;
var mosaicLoaded = false;
// Re-lays the belt even when the cover list comes back unchanged.
var mosaicDirty = false;
// High-water mark of what has been asked for, so a resize only re-asks when
// the card wants more than any request so far.
var mosaicAsked = 0;
function loadMosaic() {
    if (mosaicLoaded || mosaicLoading || !el.emptyMosaic) { return; }
    mosaicLoading = true;
    // Newest first, so the belt's ordered reveal draws the latest listens first.
    var wanted = mosaicCoversWanted();
    mosaicAsked = Math.max(mosaicAsked, wanted);
    fetch('/mosaic-covers.json?limit=' + wanted)
        .then(function(r) { return r.json(); })
        .then(function(ids) {
            mosaicLoading = false;
            mosaicLoaded = true;
            if (!ids || !ids.length) { return; }
            if (mosaicDirty || !mosaicIds || mosaicIds.join('|') !== ids.join('|')) {
                mosaicIds = ids;
                mosaicDirty = false;
                layoutMosaic(ids);
            }
            if (el.empty) { el.empty.classList.add('has-mosaic'); }
            // Reduced-motion leaves the belt laid out but still (startMosaic).
            startMosaic();
        })
        .catch(function() { mosaicLoading = false; });
}

var mosaicResizeTimer = null;
window.addEventListener('resize', function() {
    if (!mosaicIds) { return; }
    if (mosaicResizeTimer) { clearTimeout(mosaicResizeTimer); }
    mosaicResizeTimer = setTimeout(function() {
        mosaicDirty = true;
        // A hidden card measures nothing usable: leave it stale for next time.
        if (!nowPlaying.classList.contains('is-empty')) { return; }
        if (mosaicCoversWanted() > mosaicAsked) {
            mosaicLoaded = false;
            loadMosaic();
            return;
        }
        mosaicDirty = false;
        layoutMosaic(mosaicIds);
    }, 300);
});

// Recent plays as a pile of sleeves under the cover (desktop only): freshest
// on top, older ones smaller and dimmer. Ratios are fractions of the column.
var RECENT_COVER_SIZE = 300;
// Sizes of the freshest and oldest sleeves; the ones between interpolate.
var RECENT_TOP_RATIO = 0.70;
var RECENT_BOTTOM_RATIO = 0.20;
// Overlap between two sleeves, as a fraction of the upper one's height.
var RECENT_OVERLAP = 0.30;
// Horizontal nudge off centre, alternating by depth — the pile's "tossed" lean.
var RECENT_LANE_SHIFT = 0.08;
// Sanity cap only — renderRecent's fit loop is the real bound. Must stay under
// .np-cover's z-index (30), which a sleeve's own z-index counts up towards.
var RECENT_MAX = 20;
// Fewer sleeves than this doesn't read as a pile; hide the block instead.
var RECENT_MIN = 3;
// Small tilts cycled by depth so the pile looks tossed rather than ruled.
var RECENT_TILTS = [-2.5, 1.8, -1.4, 2.2, -1.8, 1.2];
// The layout that leaves a free column under the cover — must match the CSS
// media query that sets .np-recent to display:flex.
var RECENT_MQ = '(min-width: 1081px) and (min-height: 600px)';
// A first-paint measurement can read 0 before the flex layout settles; retry
// that many frames before giving up rather than hiding the pile for good.
var recentRetries = 0;

function recentLayoutActive() {
    return !!(window.matchMedia && window.matchMedia(RECENT_MQ).matches);
}

// Sizes and offsets for a pile of n sleeves in a w-wide column. Its span
// (last top + size) grows with n, which is what lets renderRecent pick n.
function recentPlan(n, w) {
    var top = w * RECENT_TOP_RATIO;
    var bottom = w * RECENT_BOTTOM_RATIO;
    var plan = [];
    var y = 0;
    for (var i = 0; i < n; i++) {
        var size = n > 1 ? top + (bottom - top) * i / (n - 1) : top;
        plan.push({ size: Math.round(size), top: Math.round(y) });
        y += size * (1 - RECENT_OVERLAP);
    }
    return plan;
}

var recentCovers = null;   // last /recent-covers.json payload (cover ids)
var recentKey = null;      // track key the payload was fetched for
var recentLoading = false;

// Lay the cached cover ids out as a pile sized to the space under the cover.
// Never repeats a cover (unlike the empty-state mosaic, which loops its list
// to fill the belt): with fewer covers than fit the pile is just shorter, and
// below RECENT_MIN it hides entirely.
function renderRecent() {
    if (!el.recent || !el.recentPile) { return; }
    var current = currentTrack || {};
    var seen = {};
    var covers = [];
    for (var i = 0; i < (recentCovers || []).length; i++) {
        var cover = recentCovers[i];
        if (!cover || seen[cover]) { continue; }
        // The album on the big cover heads the play history by definition;
        // keeping it would duplicate the artwork right above the pile.
        if (current.coverid && String(cover) === String(current.coverid)) { continue; }
        seen[cover] = true;
        covers.push(cover);
    }
    // Hidden whenever there's nothing to show or the layout has no free column
    // under the cover (narrow/short screens — the CSS keeps .np-recent
    // display:none there anyway, but gating here avoids a pointless retry loop).
    if (!covers.length || !recentLayoutActive()) {
        el.recent.hidden = true;
        recentRetries = 0;
        return;
    }
    // Un-hide so the media query lays it out, then measure the free column.
    el.recent.hidden = false;
    var w = el.recentPile.clientWidth;
    var h = el.recentPile.clientHeight;
    if (w <= 0 || h <= 0) {
        // The layout is active but the flex chain hasn't resolved a size yet
        // (first-paint race): retry next frame instead of hiding for good.
        if (recentRetries++ < 30) {
            requestAnimationFrame(renderRecent);
        } else {
            el.recent.hidden = true;
        }
        return;
    }
    recentRetries = 0;
    el.recentPile.textContent = '';

    // Largest pile that still fits the column; under RECENT_MIN it hides.
    var plan = null;
    var maxCount = Math.min(covers.length, RECENT_MAX);
    for (var c = RECENT_MIN; c <= maxCount; c++) {
        var candidate = recentPlan(c, w);
        var last = candidate[c - 1];
        if (last.top + last.size > h) { break; }
        plan = candidate;
    }
    if (!plan) {
        el.recent.hidden = true;
        return;
    }
    var count = plan.length;

    for (i = 0; i < count; i++) {
        var size = plan[i].size;
        // Decorative: the pile shows the recent covers, with no name or action,
        // so it isn't focusable — the lift is a mouse-hover flourish only.
        var sleeve = document.createElement('div');
        sleeve.className = 'np-recent-sleeve';
        sleeve.style.width = size + 'px';
        sleeve.style.height = size + 'px';
        sleeve.style.top = plan[i].top + 'px';
        // Centred, then nudged a little off-centre, alternating left/right by
        // depth (freshest left, next right, …): the shrinking stack keeps a
        // tossed feel and each sleeve peeks out to the side of the wider one on
        // top of it, so it stays hoverable.
        var shift = (i % 2 === 0 ? -1 : 1) * Math.round(w * RECENT_LANE_SHIFT);
        sleeve.style.left = Math.round((w - size) / 2 + shift) + 'px';
        sleeve.style.setProperty('--np-recent-rot', RECENT_TILTS[i % RECENT_TILTS.length] + 'deg');
        // Freshest listen frontmost; z decreases with depth so each older
        // sleeve sits behind the one above it.
        sleeve.style.zIndex = String(count - i);
        // Older sleeves sink into the shadow too: full light for the freshest
        // fading towards ~half brightness for the oldest visible one.
        var age = count > 1 ? i / (count - 1) : 0;
        sleeve.style.setProperty('--np-recent-age', (0.95 - 0.5 * age).toFixed(3));
        sleeve.style.setProperty('--np-recent-sat', (1 - 0.25 * age).toFixed(3));

        var img = document.createElement('img');
        img.src = '/cover/' + encodeURIComponent(covers[i]) +
            '.jpg?size=' + RECENT_COVER_SIZE;
        img.alt = '';
        img.decoding = 'async';
        sleeve.appendChild(img);

        el.recentPile.appendChild(sleeve);
    }
}

// Fetch the play history for the pile — once per track, since only a track
// change can reorder it (the album that just finished surfaces on top). On
// failure recentKey keeps its old value, so the next track change retries.
function loadRecent() {
    if (!el.recent || recentLoading || recentKey === lastTrackKey) { return; }
    recentLoading = true;
    var key = lastTrackKey;
    // A few more than the pile can show: the currently playing album is
    // dropped client-side.
    fetch('/recent-covers.json?limit=' + (RECENT_MAX + 4))
        .then(function(r) { return r.json(); })
        .then(function(covers) {
            recentLoading = false;
            recentKey = key;
            recentCovers = covers || [];
            renderRecent();
        })
        .catch(function() { recentLoading = false; });
}

// Re-size the pile to the new space on resize (debounced); reuses the albums
// already fetched, so no extra network.
var recentResizeTimer = null;
window.addEventListener('resize', function() {
    if (!recentCovers) { return; }
    if (recentResizeTimer) { clearTimeout(recentResizeTimer); }
    recentResizeTimer = setTimeout(renderRecent, 300);
});

function render(data) {
    if (!data || !data.track_id) {
        nowPlaying.classList.add('is-empty');
        loadMosaic();
        startMosaic();
        // Drop the pile's cache: the listens that just ended will reorder it,
        // so the next playback refetches instead of showing a stale pile.
        recentCovers = null;
        recentKey = null;
        if (el.recent) { el.recent.hidden = true; }
        el.player.textContent = '';
        if (el.playerSwitch) { el.playerSwitch.hidden = true; el.playerSwitch.textContent = ''; }
        lastSwitchKey = null;
        el.cover.removeAttribute('src');
        closeCoverZoom();
        setLyrionLink(null);
        resetColors();
        lastTrackKey = null;
        currentTrack = null;
        lrcLines = null;
        lrcNodes = null;
        lrcActiveIdx = -1;
        setAutoFollow(true);
        progress = { time: 0, duration: 0, playing: false, syncedAt: 0 };
        el.progressBar.style.width = '0';
        return;
    }

    nowPlaying.classList.remove('is-empty');
    mosaicLoaded = false;
    stopMosaic();

    progress = {
        time: data.time || 0,
        duration: data.duration || 0,
        playing: !!data.playing,
        // Back-date by half the measured round trip so the extrapolation clock
        // starts from when Lyrion actually read the position, not when we got it.
        syncedAt: Date.now() - pollRtt / 2,
    };
    paintProgress();
    setLyrionLink(data.player_id);
    el.player.textContent = data.player_name || '';
    el.playerRow.hidden = !data.player_name;
    renderPlayerSwitch(data);
    el.title.textContent = data.title || '';
    el.artist.textContent = data.artist || '';
    el.album.textContent = data.album
        ? (data.year ? data.album + ' (' + data.year + ')' : data.album)
        : '';

    // Some streamed sources (e.g. a Deezer "flow"/mix) keep a single playlist
    // entry for the whole session and only push new title/artist/album via
    // metadata updates, so track_id alone never changes between songs. Key
    // off the visible metadata too so the cover still refreshes.
    var trackKey = [data.track_id, data.title, data.artist, data.album].join('|');
    if (trackKey !== lastTrackKey) {
        lastTrackKey = trackKey;
        currentTrack = data;
        // Ask for a bounded thumbnail instead of the original artwork (which
        // can be a multi-MB scan): the cover displays at ≤300 CSS px, so 512
        // (the /cover route's cap) keeps retina screens sharp too. Lyrion
        // resizes covers itself; remote artwork has no resize form.
        el.cover.src = data.artwork_url
            ? '/cover/remote.jpg?t=' + encodeURIComponent(trackKey)
            : '/cover/' + (data.coverid || 0) + '.jpg?size=512';
        // Refresh the pile of past listens: the album that just finished
        // belongs on top of it now — and the new track's own album, if it was
        // in the pile, must come out (renderRecent drops it).
        loadRecent();
        syncCoverZoom();
        setLyrics(data.lyrics || I18N.no_lyrics_library, !data.lyrics);
        setLyricsSource(data.lyrics ? 'library' : null);
        lyricsTried = false;
        webResult = null;
        setSearching(false);
        // The cooldown is per track, so a new one starts with a live button.
        holdRetry(0);

        if (el.modeBlock) {
            el.modeBlock.style.display = '';
            updateSwitch();
        }

        // In auto mode, look the lyrics up on the web straight away: from scratch
        // when the library has nothing, or to upgrade its (always plain) text to
        // a synced version when it does.
        if (lyricsMode === 'auto') {
            if (data.lyrics) {
                trySyncedFromWeb();
            } else {
                fetchLyrics();
            }
        }
    }
}

// Why the panel came back empty: a search that ran and found nothing reads
// differently from one the server's fuses held back or that never reached the
// providers — both return instantly, which otherwise looks like a broken retry.
function emptyLyricsMessage(res) {
    if (res && res.throttled) { return I18N.lyrics_throttled; }
    if (res && res.source === 'unavailable') { return I18N.lyrics_unavailable; }
    return I18N.no_lyrics_found;
}

function fetchLyrics() {
    if (!currentTrack) { return; }
    var track = currentTrack;
    setLyrics(I18N.searching, true);
    var params = new URLSearchParams({
        track_id: track.track_id || '',
        artist:   track.artist || '',
        title:    track.title || '',
        album:    track.album || '',
        duration: track.duration || '',
        // A repeat search on the same track bypasses the server cache, so it
        // acts as a retry.
        refresh:  lyricsTried ? '1' : '',
    });
    lyricsTried = true;
    setSearching(true);
    fetch('/lyrics.json?' + params.toString(), { cache: 'no-store' })
        .then(function(r) { return r.json(); })
        .then(function(res) {
            // The track may have changed while the request was in flight; if so,
            // render() has already reset the UI for the new one — don't clobber it.
            if (track !== currentTrack) { return; }
            setSearching(false);
            holdRetry(res.retry_after || 0);
            // Prefer the synced (LRC) version; fall back to plain text.
            var lyrics = res.synced || res.lyrics;
            if (lyrics) {
                webResult = { text: lyrics, source: res.source };
                setLyrics(lyrics, false);
                setLyricsSource(res.source);
            } else {
                setLyrics(emptyLyricsMessage(res), true);
            }
        })
        .catch(function() {
            if (track !== currentTrack) { return; }
            setSearching(false);
            setLyrics(I18N.lyrics_unavailable, true);
        });
}

function trySyncedFromWeb() {
    if (!currentTrack) { return; }
    var track = currentTrack;
    var params = new URLSearchParams({
        track_id: track.track_id || '',
        artist:   track.artist || '',
        title:    track.title || '',
        album:    track.album || '',
        duration: track.duration || '',
        refresh:  lyricsTried ? '1' : '',
    });
    lyricsTried = true;
    setSearching(true);
    fetch('/lyrics.json?' + params.toString(), { cache: 'no-store' })
        .then(function(r) { return r.json(); })
        .then(function(res) {
            if (track !== currentTrack) { return; }
            setSearching(false);
            holdRetry(res.retry_after || 0);
            // Only replace the local plain lyrics if the web returned synced
            // (LRC) lyrics — otherwise keep what the library already has.
            if (res.synced) {
                webResult = { text: res.synced, source: res.source };
                setLyrics(res.synced, false);
                setLyricsSource(res.source);
            }
        })
        .catch(function() {
            if (track !== currentTrack) { return; }
            setSearching(false);
        });
}

// Re-render the library's own lyrics for this track, dropping any web result
// (used when switching back to 'off'). Only the mode changes here, so keep the
// current scroll position instead of jumping back to the top.
function showLocal() {
    var data = currentTrack || {};
    setLyrics(data.lyrics || I18N.no_lyrics_library, !data.lyrics, true);
    setLyricsSource(data.lyrics ? 'library' : null);
}

function setAuto(on) {
    lyricsMode = on ? 'auto' : 'off';
    persistMode();
    updateSwitch();
    if (!currentTrack) { return; }

    if (!on) {
        // Off: no web search, fall back to whatever the library has.
        setSearching(false);
        showLocal();
        return;
    }
    // On: resolve synced lyrics for the current track — but only once. Toggling
    // back on reuses the result already fetched instead of searching again.
    if (webResult) {
        // Re-show the result we already fetched for this track, no new request
        // and without losing the scroll position (mode change, not a new track).
        setLyrics(webResult.text, false, true);
        setLyricsSource(webResult.source);
    } else if (lyricsTried) {
        showLocal();          // already searched and found nothing — keep local
    } else if (currentTrack.lyrics) {
        trySyncedFromWeb();   // plain local text → try once to upgrade to synced
    } else {
        fetchLyrics();        // nothing local → search from scratch
    }
}

if (el.autoSwitch) {
    el.autoSwitch.addEventListener('click', function() {
        setAuto(lyricsMode !== 'auto');
    });
}
updateSwitch();

// Manual retry (rare need, hence icon-only): re-run the web search for the
// current track, bypassing the server cache. Only reachable in auto mode —
// see updateRetry(). With lyrics already on screen the result only replaces
// them when the web returns a synced version (same rule as the auto
// upgrade); from an empty state it searches from scratch and shows whatever
// comes back.
function retryLyrics() {
    if (!currentTrack) { return; }
    webResult = null;
    lyricsTried = true;  // force refresh=1 → bypass the server-side cache
    if (el.lyrics.classList.contains('empty')) {
        fetchLyrics();
    } else {
        trySyncedFromWeb();
    }
}

if (el.retry) {
    el.retry.addEventListener('click', retryLyrics);
}

// Pixels the box can still travel in the direction a gesture pushes it
// (positive delta scrolls down), zero at either end and for unscrollable text.
function scrollRoom(delta) {
    if (delta > 0) {
        return Math.max(0, el.lyrics.scrollHeight - el.lyrics.clientHeight - el.lyrics.scrollTop);
    }
    return Math.max(0, el.lyrics.scrollTop);
}

// A deliberate scroll gesture (wheel or touch drag) on the synced lyrics pauses
// the karaoke auto-follow, so it doesn't fight the user for control. Only the
// travel the box can absorb counts: a gesture pushing against an end it already
// rests at moves nothing, so it can't mean "let me read elsewhere".
// Programmatic scrolls from syncLyrics() never fire these events, so no
// bookkeeping is needed to tell them from a real gesture. The listeners are
// passive — the native scroll applies regardless, so below the threshold resync
// at once rather than letting the next periodic tick snap back as a bounce.
el.lyrics.addEventListener('wheel', function(e) {
    if (!lrcLines || !autoFollowScroll) { return; }
    var now = Date.now();
    // A gap between ticks starts a new gesture, so unrelated bumps spread out
    // over time don't add up into a false trigger.
    if (now - wheelLastAt > 400) { wheelAccum = 0; }
    wheelLastAt = now;
    wheelAccum += Math.min(Math.abs(e.deltaY), scrollRoom(e.deltaY));
    if (wheelAccum > SCROLL_PAUSE_THRESHOLD) {
        setAutoFollow(false);
    } else {
        syncLyrics(true);
    }
}, { passive: true });

el.lyrics.addEventListener('touchstart', function(e) {
    touchStartY = e.touches.length ? e.touches[0].clientY : null;
}, { passive: true });

el.lyrics.addEventListener('touchmove', function(e) {
    if (!lrcLines || !autoFollowScroll || touchStartY === null || !e.touches.length) { return; }
    var moved = touchStartY - e.touches[0].clientY;
    if (Math.min(Math.abs(moved), scrollRoom(moved)) > SCROLL_PAUSE_THRESHOLD) {
        setAutoFollow(false);
    } else {
        syncLyrics(true);
    }
}, { passive: true });

if (el.scrollReset) {
    el.scrollReset.addEventListener('click', function() {
        setAutoFollow(true);
        syncLyrics(true);
    });
}

// Enlarged cover: the card's artwork is a button that blows it up over the
// card itself, dismissed by a click anywhere on it or by Escape.
var coverZoom = {
    root: document.getElementById('cover-zoom'),
    img: document.getElementById('cover-zoom-img'),
    title: document.getElementById('cover-zoom-title'),
    artist: document.getElementById('cover-zoom-artist'),
    album: document.getElementById('cover-zoom-album'),
    close: document.getElementById('cover-zoom-close'),
    button: document.getElementById('np-cover-button'),
};

// The card shows a 512px thumbnail; dropping ?size= asks the same route for
// the original artwork, which is what the enlarged view deserves. The
// remote-artwork URL carries a per-track cache buster instead, so it stays.
function fullCoverSrc(src) {
    return src.indexOf('/cover/remote.jpg') === 0 ? src : src.split('?')[0];
}

function syncCoverZoom() {
    if (!coverZoom.root || coverZoom.root.hidden) { return; }
    var thumb = el.cover.getAttribute('src');
    var full = thumb ? fullCoverSrc(thumb) : '';
    if (full && coverZoom.img.getAttribute('src') !== full) {
        // The thumbnail is already in cache, so it paints at once and the
        // original swaps in only once it has loaded — never a blank frame.
        coverZoom.img.src = thumb;
        var preload = new Image();
        preload.onload = function() {
            if (el.cover.getAttribute('src') === thumb) { coverZoom.img.src = full; }
        };
        preload.src = full;
    }
    coverZoom.title.textContent = el.title.textContent;
    coverZoom.artist.textContent = el.artist.textContent;
    coverZoom.album.textContent = el.album.textContent;
}

function openCoverZoom() {
    if (!coverZoom.root || !el.cover.getAttribute('src')) { return; }
    coverZoom.root.hidden = false;
    coverZoom.button.setAttribute('aria-expanded', 'true');
    syncCoverZoom();
    coverZoom.close.focus();
}

function closeCoverZoom() {
    if (!coverZoom.root || coverZoom.root.hidden) { return; }
    coverZoom.root.hidden = true;
    coverZoom.button.setAttribute('aria-expanded', 'false');
    coverZoom.button.focus();
}

if (coverZoom.button && coverZoom.root) {
    coverZoom.button.addEventListener('click', openCoverZoom);
    coverZoom.root.addEventListener('click', closeCoverZoom);
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') { closeCoverZoom(); }
    });
}

el.cover.addEventListener('load', sampleCoverTint);

// Broken-cover fallback (an inline onerror would violate the CSP); the guard
// keeps a broken placeholder from looping the error event forever.
el.cover.addEventListener('error', function() {
    var fallback = el.cover.dataset.fallback;
    if (fallback && el.cover.src.indexOf(fallback) === -1) {
        el.cover.src = fallback;
    }
});

// Kept in step with the server-side cache (NOW_PLAYING_TTL, 2s), which bounds
// how often Lyrion is queried regardless of poll rate.
var POLL_INTERVAL_MS = 2000;
// A request the OS suspended mid-flight (network handover, doze) can hang for
// minutes without ever failing, so give every poll a deadline of its own.
var POLL_TIMEOUT_MS = 8000;

// Ticks are skipped while a poll is still in flight, so a stuck request can't
// pile up more requests behind it.
var pollInFlight = false;
var pollController = null;
var pollWatchdog = null;
var pollSeq = 0;

// A response that lost its race — aborted, or superseded by a later poll — must
// neither clear the newer poll's flag nor render its stale payload.
function endPoll(seq) {
    if (seq !== pollSeq) { return false; }
    clearTimeout(pollWatchdog);
    pollInFlight = false;
    return true;
}

function abortPoll() {
    if (!pollInFlight) { return; }
    pollSeq++;
    clearTimeout(pollWatchdog);
    pollInFlight = false;
    pollController.abort();
}

function restartPoll() {
    abortPoll();
    poll();
}

function poll() {
    if (pollInFlight) { return; }
    pollInFlight = true;
    var seq = ++pollSeq;
    var controller = new AbortController();
    pollController = controller;
    pollWatchdog = setTimeout(restartPoll, POLL_TIMEOUT_MS);
    // Time the round trip so render() can back-date the position. data.time is
    // measured server-side (when it queries Lyrion), but we only learn it after
    // the whole network round trip, by which point playback has moved on. The
    // measurement sits roughly mid-trip, so half the RTT is a fair estimate of
    // how stale the value already is when it reaches us.
    var sentAt = Date.now();
    // Tell the server which track is already on screen: it skips the lyrics
    // lookup (and the response omits them) while the track hasn't changed —
    // render() only reads data.lyrics on a track change anyway. And, when set,
    // which player this device pinned.
    var params = [];
    if (lastTrackKey !== null) { params.push('known=' + encodeURIComponent(lastTrackKey)); }
    if (selectedPlayer) { params.push('player=' + encodeURIComponent(selectedPlayer)); }
    var url = '/now-playing.json' + (params.length ? '?' + params.join('&') : '');
    // no-store: the URL is stable while the track plays, so a cached body would
    // be exactly the state we poll to leave behind.
    fetch(url, { signal: controller.signal, cache: 'no-store' })
        .then(function(r) { return r.json(); })
        .then(function(data) {
            if (!endPoll(seq)) { return; }
            pollRtt = Date.now() - sentAt;
            render(data);
        })
        .catch(function() { endPoll(seq); });
}

function renderStats(stats) {
    document.querySelectorAll('[data-stat]').forEach(function(el) {
        var value = stats[el.dataset.stat];
        if (value === undefined) { return; }
        var pctKey = el.dataset.statPct;
        if (pctKey) {
            // Rebuilt with text nodes (not innerHTML) so a value could never
            // be interpreted as markup; mirrors the server-rendered structure.
            el.textContent = value + ' ';
            var small = document.createElement('small');
            small.textContent = '(' + stats[pctKey] + '%)';
            el.appendChild(small);
        } else {
            el.textContent = value;
        }
    });
    dimZeroSubRows();
}

function dimZeroSubRows() {
    document.querySelectorAll('.stat-row.sub').forEach(function(row) {
        var valEl = row.querySelector('[data-stat]');
        var n = valEl ? parseInt(valEl.textContent, 10) : NaN;
        row.classList.toggle('is-zero', n === 0);
    });
}

function pollStats() {
    fetch('/stats.json')
        .then(function(r) { return r.json(); })
        .then(renderStats)
        .catch(function() {});
}

// A backgrounded page has its timers throttled and any in-flight poll may
// never settle (the OS can suspend the socket), so on return: abort it, poll again.
function catchUp() {
    if (document.visibilityState === 'hidden') { stopMosaic(); return; }
    startMosaic();
    restartPoll();
}
document.addEventListener('visibilitychange', catchUp);
window.addEventListener('focus', catchUp);
window.addEventListener('pageshow', catchUp);

dimZeroSubRows();
poll();
setInterval(poll, POLL_INTERVAL_MS);
setInterval(pollStats, 60000);
// The extrapolated position advances continuously between network polls, so
// repaint the bar (and, while there are lyrics, the karaoke highlight via
// paintProgress) a few times a second for a smooth follow.
setInterval(paintProgress, 250);
