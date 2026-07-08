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
// reveal the header's settings button and wire it to the native screen.
(function () {
    var appSettings = document.getElementById('app-settings');
    if (appSettings && window.LyrionApp && window.LyrionApp.openSettings) {
        appSettings.hidden = false;
        appSettings.addEventListener('click', function (e) {
            e.preventDefault();
            window.LyrionApp.openSettings();
        });
    }
})();

var nowPlaying = document.getElementById('now-playing');
var el = {
    player: document.getElementById('np-player'),
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
// mode and while no search is running (the spinner replaces it meanwhile).
var searching = false;
function updateRetry() {
    if (!el.retry) { return; }
    el.retry.hidden = searching || lyricsMode !== 'auto';
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
    // The empty-state "open Lyrion" button always targets the plain Material
    // page: with nothing playing there is no player to focus.
    setMaterialLink(el.emptyOpen, null);
}
var lastTrackKey = null;
var currentTrack = null;
var lyricsTried = false;
// Web lyrics resolved for the current track ({text, source}), so re-selecting a
// mode reuses the result instead of searching again. Reset on every track.
var webResult = null;

var lrcLines = null;

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

function isGrey(rgb) {
    return Math.abs(rgb[0] - rgb[1]) < 2 &&
           Math.abs(rgb[0] - rgb[2]) < 2 &&
           Math.abs(rgb[1] - rgb[2]) < 2;
}

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

        // Grey covers (or no usable swatch) fall back to the default accent,
        // exactly like Material does.
        if (isGrey(avRgb) || !vRgb || isGrey(vRgb)) {
            setAccent(ACCENT_DEFAULT);
        } else {
            var hsv = rgb2Hsv(vRgb);
            hsv[2] = 0.8235;                 // fixed brightness (Material's V)
            hsv[1] = Math.min(hsv[1], 0.8);  // cap saturation
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

    if (!text || isEmpty) {
        el.lyrics.textContent = text || I18N.no_lyrics;
        el.lyrics.classList.toggle('empty', !!isEmpty || !text);
        el.lyrics.scrollTop = prevScroll;
        updateScrollReset();
        return;
    }

    var parsed = parseLRC(text);
    if (parsed) {
        lrcLines = parsed;
        el.lyrics.classList.add('lrc-mode');
        for (var i = 0; i < parsed.length; i++) {
            var div = document.createElement('div');
            div.className = 'lrc-line';
            div.dataset.time = parsed[i].time;
            div.textContent = parsed[i].text || '\u00a0';
            el.lyrics.appendChild(div);
        }
        // Set the scroll only once the lines exist: setting it before the
        // rebuild let scroll-behavior:smooth cancel the reset mid-animation, so
        // the view never returned to the top on a track change.
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

function syncLyrics() {
    if (!lrcLines || !lrcLines.length) { return; }
    var t = currentTime();
    var activeIdx = -1;
    for (var i = 0; i < lrcLines.length; i++) {
        if (lrcLines[i].time <= t) {
            // Blank separator lines share the previous line's time; never let
            // one be the active line — keep the last real line highlighted.
            if (!lrcLines[i].blank) { activeIdx = i; }
        } else { break; }
    }

    var children = el.lyrics.querySelectorAll('.lrc-line');
    for (var j = 0; j < children.length; j++) {
        children[j].classList.remove('active', 'near');
        if (j === activeIdx) {
            children[j].classList.add('active');
        } else if (Math.abs(j - activeIdx) === 1) {
            children[j].classList.add('near');
        }
    }

    if (activeIdx >= 0 && activeIdx < children.length && autoFollowScroll) {
        var active = children[activeIdx];
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

// Square cover tile (px) the mosaic layout is sized around: sets how many
// rows and columns of covers fit the card. Kept fairly small so the belt stays
// dense enough that its wrap seam is never a visible gap, even on short phone
// cards with few rows.
var MOSAIC_TILE = 130;
// Thumbnail size requested for mosaic covers. They're blurred and downscaled,
// so a small thumbnail is indistinguishable from full art but loads far
// faster (dozens fetch at once) — a bit above the tile size for DPR headroom.
var MOSAIC_COVER_SIZE = 200;
// Gap between covers on the belt (both between covers in a row and between
// rows), and how fast the belt travels (px/s).
var MOSAIC_GAP = 10;
var MOSAIC_SPEED = 26;

// The covers ride one continuous serpentine belt: laid end to end, they cross
// row 0 left→right, drop to row 1 and cross it right→left, and so on down the
// card, then wrap from the bottom back to the top. `mosaicGeom` holds the
// measured geometry; positionMosaic() maps each tile's position along the belt
// (phase) to an (x, y) on screen, and stepMosaic() advances the phase.
var mosaicGeom = null;
var mosaicIds = null;
var mosaicRAFStarted = false;

function positionMosaic(phase) {
    var g = mosaicGeom;
    if (!g) { return; }
    for (var i = 0; i < g.tiles.length; i++) {
        // Distance of this tile along the belt, wrapped into [0, total length).
        var p = (i * g.step + phase) % g.length;
        if (p < 0) { p += g.length; }
        var row = Math.floor(p / g.rowLen);
        var within = p - row * g.rowLen;
        // Even rows travel right, odd rows left (so a cover leaving one row's
        // edge continues from the row below): boustrophedon.
        var x = (row % 2 === 0) ? within : (g.rowLen - within);
        // Shift left by one step so tiles enter from just off the left/right
        // edge rather than popping in at x=0. The tile is MOSAIC_GAP shorter
        // than its row band, so half a gap of top padding centres it and leaves
        // a gap between rows.
        var y = row * g.rowH + MOSAIC_GAP / 2;
        g.tiles[i].style.transform =
            'translate3d(' + (x - g.step) + 'px,' + y + 'px,0)';
    }
}

function stepMosaic(ts) {
    var g = mosaicGeom;
    // Only advance while the empty state is actually on screen (offsetParent is
    // null when a parent is display:none, i.e. something is playing).
    if (g && el.emptyMosaic.offsetParent !== null) {
        if (!g.last) { g.last = ts; }
        // Clamp dt so a background tab (rAF paused) doesn't lurch on return.
        var dt = Math.min(ts - g.last, 100);
        g.last = ts;
        g.phase = (g.phase + MOSAIC_SPEED * dt / 1000) % g.length;
        positionMosaic(g.phase);
    } else if (g) {
        g.last = 0;
    }
    requestAnimationFrame(stepMosaic);
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
    var reduce = window.matchMedia &&
        window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    var W = el.emptyMosaic.offsetWidth || 900;
    var H = el.emptyMosaic.offsetHeight || 500;
    var rows = Math.max(3, Math.round(H / MOSAIC_TILE));
    var rowH = H / rows;
    // Tile is a gap shorter than the row band so rows don't touch vertically;
    // the horizontal step keeps the same gap between covers along the row.
    var tile = rowH - MOSAIC_GAP;
    var step = tile + MOSAIC_GAP;
    // One extra slot per row so a cover is always entering as another leaves.
    var perRow = Math.ceil(W / step) + 1;
    // With fewer covers than a full grid, drop rows so each surviving row stays
    // full of distinct covers rather than repeating them across the card.
    if (ids.length >= perRow) {
        rows = Math.min(rows, Math.floor(ids.length / perRow));
    } else {
        rows = 1;
        perRow = ids.length;
    }
    var count = rows * perRow;

    el.emptyMosaic.style.setProperty('--mosaic-tile', tile + 'px');
    var tiles = [];
    for (var i = 0; i < count; i++) {
        var img = document.createElement('img');
        img.className = 'np-mosaic-tile';
        // A finished download (or error) may need to un-stall the reveal cursor
        // if it was waiting on this very tile.
        img.onload = img.onerror = function() {
            if (mosaicRevealTimer === null) { advanceMosaicReveal(); }
        };
        img.src = '/cover/' + encodeURIComponent(ids[i % ids.length]) + '.jpg?size=' + MOSAIC_COVER_SIZE;
        img.alt = '';
        img.decoding = 'async';
        if (reduce) { img.classList.add('is-shown'); }
        el.emptyMosaic.appendChild(img);
        tiles.push(img);
    }
    mosaicGeom = {
        tiles: tiles, step: step, rowH: rowH,
        rowLen: perRow * step, length: rows * perRow * step,
        phase: 0, last: 0,
    };
    positionMosaic(0);
    // Reduced motion: no caterpillar fill, show everything at once (tiles were
    // already marked shown above); otherwise start the ordered reveal.
    if (reduce) {
        mosaicRevealCursor = tiles.length;
    } else {
        advanceMosaicReveal();
    }
}

// Fill the empty-state background with random covers from the library, once
// per page load (the selection is random anyway, no point refreshing it).
// On failure the guard resets so the next poll retries; without covers the
// empty state simply stays as plain text, same as before.
var mosaicLoading = false;
var mosaicLoaded = false;
function loadMosaic() {
    if (mosaicLoaded || mosaicLoading || !el.emptyMosaic) { return; }
    mosaicLoading = true;
    // Ask for about as many covers as the belt has slots: rows that fill the
    // card height times a row a little wider than the card. The endpoint
    // returns the most recently played albums (newest first), so the belt's
    // ordered reveal draws the latest listens first.
    var cols = Math.ceil(el.emptyMosaic.offsetWidth / MOSAIC_TILE) || 6;
    var rows = Math.max(3, Math.round(el.emptyMosaic.offsetHeight / MOSAIC_TILE));
    var wanted = Math.min(rows * (cols + 2), 200);
    fetch('/mosaic-covers.json?limit=' + wanted)
        .then(function(r) { return r.json(); })
        .then(function(ids) {
            mosaicLoading = false;
            mosaicLoaded = true;
            if (!ids || !ids.length) { return; }
            mosaicIds = ids;
            layoutMosaic(ids);
            if (el.empty) { el.empty.classList.add('has-mosaic'); }
            // Honour reduced-motion: lay the belt out but leave it still.
            var reduce = window.matchMedia &&
                window.matchMedia('(prefers-reduced-motion: reduce)').matches;
            if (!reduce && !mosaicRAFStarted) {
                mosaicRAFStarted = true;
                requestAnimationFrame(stepMosaic);
            }
        })
        .catch(function() { mosaicLoading = false; });
}

// Re-lay the belt to the new size on resize (debounced); reuses the covers
// already fetched, so no extra network. The running rAF picks up the new
// geometry automatically.
var mosaicResizeTimer = null;
window.addEventListener('resize', function() {
    if (!mosaicIds) { return; }
    if (mosaicResizeTimer) { clearTimeout(mosaicResizeTimer); }
    mosaicResizeTimer = setTimeout(function() { layoutMosaic(mosaicIds); }, 300);
});

function render(data) {
    if (!data || !data.track_id) {
        nowPlaying.classList.add('is-empty');
        loadMosaic();
        el.player.textContent = '';
        el.cover.removeAttribute('src');
        setLyrionLink(null);
        resetColors();
        lastTrackKey = null;
        currentTrack = null;
        lrcLines = null;
        setAutoFollow(true);
        progress = { time: 0, duration: 0, playing: false, syncedAt: 0 };
        el.progressBar.style.width = '0';
        return;
    }

    nowPlaying.classList.remove('is-empty');

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
        el.cover.src = data.artwork_url
            ? '/cover/remote.jpg?t=' + encodeURIComponent(trackKey)
            : '/cover/' + (data.coverid || 0) + '.jpg';
        setLyrics(data.lyrics || I18N.no_lyrics, !data.lyrics);
        setLyricsSource(data.lyrics ? 'library' : null);
        lyricsTried = false;
        webResult = null;
        setSearching(false);

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
            // Prefer the synced (LRC) version; fall back to plain text.
            var lyrics = res.synced || res.lyrics;
            if (lyrics) {
                webResult = { text: lyrics, source: res.source };
                setLyrics(lyrics, false);
                setLyricsSource(res.source);
            } else {
                setLyrics(I18N.no_lyrics_web, true);
            }
        })
        .catch(function() {
            if (track !== currentTrack) { return; }
            setSearching(false);
            setLyrics(I18N.no_lyrics_web, true);
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
    setLyrics(data.lyrics || I18N.no_lyrics, !data.lyrics, true);
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

// Short lyrics that already fit the box have nothing to scroll — a gesture
// on them can't mean "let me scroll away from the highlight", so don't let it
// trip auto-follow off.
function isLyricsScrollable() {
    return el.lyrics.scrollHeight > el.lyrics.clientHeight + 1;
}

// A deliberate scroll gesture (wheel or touch drag) on the synced lyrics
// pauses the karaoke auto-follow, so it doesn't fight the user for control.
// Programmatic scrolling from syncLyrics() never fires these events, so
// telling it apart from a real gesture needs no extra bookkeeping — only
// telling a real gesture apart from an incidental bump does, via the
// SCROLL_PAUSE_THRESHOLD accumulated below. These listeners are passive, so
// the browser applies the native scroll regardless of that bookkeeping; below
// the threshold, resync immediately rather than waiting for the next
// periodic syncLyrics() tick, otherwise the delayed snap-back reads as a
// bounce. Above the threshold, let the native scroll ride and pause instead.
el.lyrics.addEventListener('wheel', function(e) {
    if (!lrcLines || !autoFollowScroll || !isLyricsScrollable()) { return; }
    var now = Date.now();
    // A gap between ticks starts a new gesture, so unrelated bumps spread out
    // over time don't add up into a false trigger.
    if (now - wheelLastAt > 400) { wheelAccum = 0; }
    wheelLastAt = now;
    wheelAccum += Math.abs(e.deltaY);
    if (wheelAccum > SCROLL_PAUSE_THRESHOLD) {
        setAutoFollow(false);
    } else {
        syncLyrics();
    }
}, { passive: true });

el.lyrics.addEventListener('touchstart', function(e) {
    touchStartY = e.touches.length ? e.touches[0].clientY : null;
}, { passive: true });

el.lyrics.addEventListener('touchmove', function(e) {
    if (!lrcLines || !autoFollowScroll || !isLyricsScrollable() || touchStartY === null || !e.touches.length) { return; }
    if (Math.abs(e.touches[0].clientY - touchStartY) > SCROLL_PAUSE_THRESHOLD) {
        setAutoFollow(false);
    } else {
        syncLyrics();
    }
}, { passive: true });

if (el.scrollReset) {
    el.scrollReset.addEventListener('click', function() {
        setAutoFollow(true);
        syncLyrics();
    });
}

el.cover.addEventListener('load', sampleCoverTint);

function poll() {
    // Time the round trip so render() can back-date the position. data.time is
    // measured server-side (when it queries Lyrion), but we only learn it after
    // the whole network round trip, by which point playback has moved on. The
    // measurement sits roughly mid-trip, so half the RTT is a fair estimate of
    // how stale the value already is when it reaches us.
    var sentAt = Date.now();
    fetch('/now-playing.json')
        .then(function(r) { return r.json(); })
        .then(function(data) {
            pollRtt = Date.now() - sentAt;
            render(data);
        })
        .catch(function() {});
}

function renderStats(stats) {
    document.querySelectorAll('[data-stat]').forEach(function(el) {
        var value = stats[el.dataset.stat];
        if (value === undefined) { return; }
        var pctKey = el.dataset.statPct;
        if (pctKey) {
            el.innerHTML = value + ' <small>(' + stats[pctKey] + '%)</small>';
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

document.addEventListener('visibilitychange', function() {
    // Background tabs throttle setInterval, so the now-playing view can lag
    // behind by far more than the poll period; catch up as soon as the tab
    // is looked at again instead of waiting for the next tick.
    if (document.visibilityState === 'visible') {
        poll();
    }
});

dimZeroSubRows();
poll();
setInterval(poll, 5000);
setInterval(pollStats, 60000);
setInterval(paintProgress, 1000);
// The progress repaint (and thus the LRC highlight) only ticks once a second,
// which leaves the karaoke highlight up to ~1s late. The extrapolated position
// advances continuously between network polls, so refresh the highlight a few
// times a second while playing for a smoother follow. Gated on playback so it
// doesn't fight manual scrolling while paused, where the 1s tick already covers.
setInterval(function () {
    if (lrcLines && progress.playing) { syncLyrics(); }
}, 250);
