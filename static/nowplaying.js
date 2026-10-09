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

// Injected by the Android app; shells that predate openMenu only have openSettings.
var APP_BRIDGE = window.LyrionApp;

(function () {
    var appMenu = document.getElementById('app-menu');
    var bridge = APP_BRIDGE;
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
    volume: document.getElementById('np-volume'),
    volumeLevel: document.getElementById('np-volume-level'),
    title:  document.getElementById('np-title'),
    artist: document.getElementById('np-artist'),
    album:  document.getElementById('np-album'),
    lyrics: document.getElementById('np-lyrics'),
    source: document.getElementById('np-lyrics-source'),
    sourceLabel: document.getElementById('np-lyrics-source-label'),
    cover:  document.getElementById('np-cover-img'),
    retry:  document.getElementById('np-retry'),
    lyricsTools: document.querySelector('.np-lyrics-tools'),
    progressBar: document.getElementById('np-progress-bar'),
    lyrionLink: document.getElementById('lyrion-link'),
    scrollReset: document.getElementById('np-scroll-reset'),
    empty: document.getElementById('np-empty'),
    emptyMosaic: document.getElementById('np-empty-mosaic'),
    emptyOpen: document.getElementById('np-empty-open'),
    recent: document.getElementById('np-recent'),
    recentPile: document.getElementById('np-recent-pile'),
};

// Greys out while the server would refuse a new search for this track, so a
// click never lands on a fuse.
var searching = false;
var retryHeld = false;
// Set when a search behind the library's text failed, which the box itself never shows.
var searchFailure = null;
function updateRetry() {
    if (!el.retry) { return; }
    el.retry.hidden = !currentTrack;
    el.retry.disabled = retryHeld || searching;
    el.retry.classList.toggle('is-busy', searching);
    var failed = !!searchFailure && !searching;
    var label = failed ? searchFailure + ' \u00b7 ' + I18N.retry_lyrics : I18N.retry_lyrics;
    el.retry.classList.toggle('is-failed', failed);
    el.retry.title = label;
    el.retry.setAttribute('aria-label', label);
    syncTools();
}

// The row draws the pill, so it hides whenever neither control shows.
function syncTools() {
    if (!el.lyricsTools) { return; }
    el.lyricsTools.hidden = (!el.source || el.source.hidden) && (!el.retry || el.retry.hidden);
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
    setMaterialLink(el.playerLink, playerId);
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

// Keyed by artist|title, not the track id, which a rescan renumbers.
var HIDDEN_LYRICS_KEY = 'lyrion.hiddenLyrics';
var HIDDEN_LYRICS_MAX = 200;
var hiddenLyrics = [];
try { hiddenLyrics = JSON.parse(localStorage.getItem(HIDDEN_LYRICS_KEY)) || []; } catch (e) {}
if (!Array.isArray(hiddenLyrics)) { hiddenLyrics = []; }

function hashText(text) {
    var h = 5381;
    for (var i = 0; i < text.length; i++) {
        h = ((h << 5) + h + text.charCodeAt(i)) | 0;
    }
    return (h >>> 0).toString(36);
}

function hiddenKey(version) {
    return [currentTrack.artist || '', currentTrack.title || ''].join('|').toLowerCase()
        + '|' + hashText(textKey(version.text));
}

function isHidden(version) {
    return hiddenLyrics.indexOf(hiddenKey(version)) >= 0;
}

function rememberHidden(hide) {
    for (var i = 0; i < versions.length; i++) {
        var key = hiddenKey(versions[i]);
        var at = hiddenLyrics.indexOf(key);
        if (at >= 0) { hiddenLyrics.splice(at, 1); }
        if (hide) { hiddenLyrics.push(key); }
    }
    if (hiddenLyrics.length > HIDDEN_LYRICS_MAX) {
        hiddenLyrics.splice(0, hiddenLyrics.length - HIDDEN_LYRICS_MAX);
    }
    try { localStorage.setItem(HIDDEN_LYRICS_KEY, JSON.stringify(hiddenLyrics)); } catch (e) {}
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
document.addEventListener('click', function (e) {
    if (el.playerSwitch && !el.playerSwitch.contains(e.target)) { closeSwitchMenu(); }
});
document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') { closeSwitchMenu(); }
});

// Rebuilt only when the players or the active one change, so the menu keeps its state.
var lastSwitchKey = null;

function renderPlayerSwitch(data) {
    if (!el.playerSwitch) { return; }
    var players = data.players || [];

    if (selectedPlayer && data.selection_active === false) {
        setSelectedPlayer(null);
    }

    if (players.length < 2) {
        el.playerSwitch.hidden = true;
        el.playerSwitch.textContent = '';
        lastSwitchKey = null;
        return;
    }

    el.playerRow.hidden = true;
    el.playerSwitch.hidden = false;

    var activeId = data.player_id;
    var key = players.map(function (p) { return p.id; }).join(',') + '|' + activeId;
    if (key === lastSwitchKey) { return; }
    lastSwitchKey = key;
    el.playerSwitch.textContent = '';

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
            item = document.createElement('a');
            setMaterialLink(item, p.id);
            item.title = I18N.open_lyrion;
            item.appendChild(document.createTextNode(p.name || ''));
            item.appendChild(makeIcon(LYRION_ARROW_PATH, 'np-switch-arrow'));
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
function renderVolume(data) {
    var known = data && typeof data.volume === 'number';
    el.volume.hidden = !known;
    if (!known) { return; }
    el.volume.classList.toggle('is-muted', !!data.muted);
    el.volumeLevel.textContent = data.volume;
    var label = I18N.volume + ' ' + data.volume + ' %' + (data.muted ? ' (' + I18N.volume_muted + ')' : '');
    el.volume.setAttribute('aria-label', label);
    el.volume.title = label;
    // The badge sits in whichever label names the player: the link, or the switch's toggle.
    var toggle = !el.playerSwitch.hidden && el.playerSwitch.querySelector('.np-switch-toggle');
    var host = toggle || el.playerLink;
    var anchor = host.querySelector(toggle ? '.np-switch-chevron' : '.np-player-arrow');
    if (el.volume.nextSibling !== anchor) { host.insertBefore(el.volume, anchor); }
}

var lastTrackKey = null;
var currentTrack = null;
var lyricsTried = false;
// Mirrors services.lyrics.MAX_VERSIONS, which bounds a response; only the page
// knows whether a library text takes one of those places.
var MAX_VERSIONS = 5;
var versions = [];
var versionIdx = -1;
var lyricsHidden = false;

var lrcLines = null;
// Cached with the active index, so the 4×/s karaoke tick skips the DOM while the line holds.
var lrcNodes = null;
var lrcActiveIdx = -1;

// A manual scroll pauses the follow; the reset button or a new track resumes it.
var autoFollowScroll = true;
// Only guards the trip out of auto-follow, so a stray wheel tick or brush doesn't pause it.
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

// Plain lyrics have no follow to resume, even with a pause remembered across a mode switch.
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

// Mirrors Lyrion Material's currentcover.js; the HSV helpers are copied from it.

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
// Vibrant samples its input at its layout size, so it reads a copy at the size
// library covers are fetched, which also bounds the cost of remote artwork.
var COVER_SIZE = 512;
var swatchCanvas;
// Past these bounds object-fit: cover crops the artwork.
var COVER_R_MIN = 0.5;
var COVER_R_MAX = 2;

function coverRatio(img) {
    var r = img.naturalWidth && img.naturalHeight ? img.naturalWidth / img.naturalHeight : 1;
    return Math.min(Math.max(r, COVER_R_MIN), COVER_R_MAX);
}

function swatchSource(img) {
    if (!swatchCanvas) {
        swatchCanvas = document.createElement('canvas');
        swatchCanvas.width = swatchCanvas.height = COVER_SIZE;
    }
    var ctx = swatchCanvas.getContext('2d');
    ctx.clearRect(0, 0, COVER_SIZE, COVER_SIZE);
    ctx.drawImage(img, 0, 0, COVER_SIZE, COVER_SIZE);
    return swatchCanvas;
}

function sampleCoverTint() {
    try {
        var img = el.cover;
        if (!img.naturalWidth) { return; }

        var vRgb;
        try {
            var swatches = new Vibrant(swatchSource(img)).swatches();
            for (var i = 0; i < SWATCH_ORDER.length && !vRgb; i++) {
                var sw = swatches[SWATCH_ORDER[i]];
                if (sw && sw.getPopulation() > 0) { vRgb = sw.getRgb(); }
            }
        } catch (e) { /* fall through to average-only */ }

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

// scaleX rather than width: compositor-only, so this tick costs no layout or paint.
function setProgressBar(bar, pct) {
    bar.style.transform = 'scaleX(' + pct / 100 + ')';
}

function paintProgress() {
    var t = progress.time;
    if (progress.playing) {
        t += (Date.now() - progress.syncedAt) / 1000;
    }
    var pct = progress.duration > 0
        ? Math.max(0, Math.min(100, (t / progress.duration) * 100))
        : 0;
    setProgressBar(el.progressBar, pct);
    if (coverZoom && coverZoom.progressBar) { setProgressBar(coverZoom.progressBar, pct); }
    if (lrcLines) { syncLyrics(); }
}

var SOURCE_LABELS = {
    library:    I18N.source_library,
    lrclib:     'LRCLIB',
    musixmatch: 'Musixmatch',
    netease:    'NetEase',
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
            // Blank separators take the previous line's time, flagged so they never become active.
            if (line.trim() === '' && parsed.length) {
                parsed.push({ time: lastTime, text: '', blank: true });
            }
            continue;
        }
        var mm = parseInt(m[1], 10);
        var ss = parseFloat(m[2]);
        var t = mm * 60 + ss + offset;
        lastTime = t;
        // A timestamp with only whitespace is a blank separator too.
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
        updateRetry();
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
    updateRetry();
}

function currentTime() {
    var t = progress.time;
    if (progress.playing) {
        t += (Date.now() - progress.syncedAt) / 1000;
    }
    return t;
}

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
            if (!lrcLines[i].blank) { activeIdx = i; }
        } else { break; }
    }

    if (activeIdx !== lrcActiveIdx) {
        // Only the old and new active lines and their neighbours change state.
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
        // Anchored on the upper third, so more upcoming lines show.
        var target = active.offsetTop - el.lyrics.clientHeight / 3 + active.clientHeight / 2;
        el.lyrics.scrollTop = Math.max(0, target);
    }
}

function versionLength(version) {
    var secs = version && version.duration;
    if (!secs) { return ''; }
    return ' \u00b7 ' + Math.floor(secs / 60) + ':' + ('0' + (Math.round(secs) % 60)).slice(-2);
}

// Callers run right after setLyrics(), so lrcLines tells whether the text on screen is synced.
function updateSource() {
    if (!el.source) { return; }
    var version = versions[versionIdx];
    var label = version && (lyricsHidden ? I18N.lyrics_hidden_chip : sourceLabel(version));
    var synced = !!(label && lrcLines);
    var canCycle = versions.length > 0 && !searching;
    var ranked = versions.length > 1 && !searching;
    el.source.hidden = !label;
    el.source.disabled = !canCycle;
    el.sourceLabel.textContent = searching ? I18N.searching : (label
        ? label + (ranked && lyricsHidden ? ' (0/' + versions.length + ')' : '')
            + (ranked && !lyricsHidden ? versionLength(version) + ' (' + (versionIdx + 1) + '/' + versions.length + ')' : '')
        : '');
    el.source.classList.toggle('is-synced', synced);
    el.source.title = [
        synced ? I18N.lyrics_synced_hint : '',
        canCycle ? I18N.switch_version : '',
    ].filter(Boolean).join(' \u00b7 ');
    syncTools();
}

function showVersion(idx, keepScroll) {
    var version = versions[idx];
    if (!version) { return; }
    versionIdx = idx;
    lyricsHidden = false;
    setLyrics(version.text, false, keepScroll);
    updateSource();
}

// The chip needs a version behind it, or it hides along with the way back.
function showHidden() {
    versionIdx = Math.max(versionIdx, 0);
    lyricsHidden = true;
    setLyrics(I18N.lyrics_hidden, true);
    updateSource();
}

function allHidden() {
    for (var i = 0; i < versions.length; i++) {
        if (!isHidden(versions[i])) { return false; }
    }
    return versions.length > 0;
}

// Older responses carry only the winning upload, hence the fallback shape.
// Synced entries lead, as they do server-side, so a cap trims from the back.
function webVersions(res) {
    var list = (res && res.versions) || [{
        lyrics: res && res.lyrics, synced: res && res.synced,
        album: null, duration: null,
    }];
    var synced = [];
    var plain = [];
    for (var i = 0; i < list.length; i++) {
        var version = list[i];
        var entry = {
            source: res.source, duration: version.duration,
            text: version.synced, synced: true,
        };
        if (version.synced) { synced.push(entry); }
        if (version.lyrics) {
            plain.push({
                source: res.source, duration: version.duration,
                text: version.lyrics, synced: false,
            });
        }
    }
    return synced.concat(plain);
}

// Timestamps count, so an upload's synced and plain forms never collapse.
function textKey(text) {
    return (text || '').replace(/\s+/g, ' ').trim();
}

function offeredAs(text) {
    var key = textKey(text);
    for (var i = 0; i < versions.length; i++) {
        if (textKey(versions[i].text) === key) { return versions[i]; }
    }
    return null;
}

function noteEcho(version, source) {
    version.echoes = version.echoes || [];
    if (source !== version.source && version.echoes.indexOf(source) < 0) {
        version.echoes.push(source);
    }
}

function sourceLabel(version) {
    var names = [version.source].concat(version.echoes || []);
    var labels = [];
    for (var i = 0; i < names.length; i++) {
        if (SOURCE_LABELS[names[i]]) { labels.push(SOURCE_LABELS[names[i]]); }
    }
    return labels.join(' + ');
}

// Preference order: the version the page lands on must stay 1/n.
function versionRank(version) {
    var rank = version.synced ? 0 : (version.source === 'library' ? 1 : 2);
    return isHidden(version) ? rank + 3 : rank;
}

function rankVersions() {
    var ranked = versions.map(function(version, i) {
        return { version: version, rank: versionRank(version), i: i };
    });
    ranked.sort(function(a, b) { return a.rank - b.rank || a.i - b.i; });
    versions = ranked.map(function(entry) { return entry.version; });
    // The library's text is never the one shed.
    for (var j = versions.length - 1; versions.length > MAX_VERSIONS && j >= 0; j--) {
        if (versions[j].source !== 'library') { versions.splice(j, 1); }
    }
}

function pushWebVersions(res) {
    var web = webVersions(res);
    var added = 0;
    for (var i = 0; i < web.length; i++) {
        var same = offeredAs(web[i].text);
        if (same) { noteEcho(same, web[i].source); }
        else { versions.push(web[i]); added++; }
    }
    rankVersions();
    return added;
}

function landOnVersions(current) {
    if (allHidden()) { showHidden(); return; }
    if (!current || lyricsHidden || versions[0].synced) { showVersion(0); return; }
    versionIdx = versions.indexOf(current);
    updateSource();
}

if (el.source) {
    el.source.addEventListener('click', function() {
        if (!versions.length) { return; }
        holdLyricsHeight();
        if (lyricsHidden) {
            rememberHidden(false);
            showVersion(0);
        } else if (versionIdx < versions.length - 1) {
            showVersion(versionIdx + 1, true);
        } else {
            rememberHidden(true);
            showHidden();
        }
    });
}

// Released on a width change only: the mobile URL bar resizes the height on scroll.
var heldWidth = 0;
function holdLyricsHeight() {
    // The fitted layouts size the box from the viewport (flex-basis 0), not from its text.
    if (getComputedStyle(el.lyrics).flexBasis === '0px') { return; }
    el.lyrics.style.minHeight = el.lyrics.offsetHeight + 'px';
    heldWidth = window.innerWidth;
}

function releaseLyricsHeight() {
    el.lyrics.style.minHeight = '';
}

window.addEventListener('resize', function() {
    if (window.innerWidth !== heldWidth) { releaseLyricsHeight(); }
});

function setSearching(on) {
    searching = on;
    updateSource();
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
    // Even rows travel right, odd rows left; the belt starts a step off the left edge.
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

// Fetched in parallel, revealed strictly in belt order: the cursor waits on a tile
// still downloading and resumes from its load handler.
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

// A finished download (or error) may need to un-stall the reveal cursor if it
// was waiting on this very tile.
function mosaicTileSettled() {
    if (mosaicRevealTimer === null) { advanceMosaicReveal(); }
}

function layoutMosaic(ids) {
    el.emptyMosaic.textContent = '';
    if (mosaicRevealTimer) { clearTimeout(mosaicRevealTimer); mosaicRevealTimer = null; }
    mosaicRevealCursor = 0;
    var reduce = prefersReducedMotion();
    var W = mosaicCardW();
    var H = mosaicCardH();
    var grid = mosaicGrid(W, H);
    // Too few covers for that many rows: fewer, taller ones, never a bare band.
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
        img.onload = function() {
            this.style.setProperty('--mosaic-r', coverRatio(this));
            mosaicTileSettled();
        };
        img.onerror = mosaicTileSettled;
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
    if (reduce) {
        mosaicRevealCursor = tiles.length;
    } else {
        advanceMosaicReveal();
    }
}

// Invalidated while something plays (see render()), since playback changes what
// "recently played" means; a failure resets the guard so the next poll retries.
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

// Ratios are fractions of the pile's column.
var RECENT_COVER_SIZE = 512;
// Sizes of the freshest and oldest sleeves; the ones between interpolate.
var RECENT_TOP_RATIO = 0.70;
var RECENT_BOTTOM_RATIO = 0.20;
// Overlap between two sleeves, as a fraction of the upper one's height.
var RECENT_OVERLAP = 0.30;
// Horizontal nudge off centre, alternating by depth.
var RECENT_LANE_SHIFT = 0.08;
// Sanity cap only — renderRecent's fit loop is the real bound. Must stay under
// .np-cover's z-index (30), which a sleeve's own z-index counts up towards.
var RECENT_MAX = 20;
// Fewer sleeves than this doesn't read as a pile; hide the block instead.
var RECENT_MIN = 3;
var RECENT_HOVER_GROW_MIN = 1.05;
// Lift duration, scaled between these two by how far the sleeve travels.
var RECENT_HOVER_MS_MIN = 200;
var RECENT_HOVER_MS_MAX = 400;
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
var recentSleeves = [];

// Never repeats a cover, unlike the mosaic: with fewer covers the pile is just shorter.
function renderRecent() {
    if (!el.recent || !el.recentPile) { return; }
    var current = currentTrack || {};
    var seen = {};
    var covers = [];
    for (var i = 0; i < (recentCovers || []).length; i++) {
        var cover = recentCovers[i];
        if (!cover || seen[cover]) { continue; }
        // The album on the big cover heads the history; kept, it would repeat the artwork.
        if (current.coverid && String(cover) === String(current.coverid)) { continue; }
        seen[cover] = true;
        covers.push(cover);
    }
    // Gated here too, or a pile the CSS hides would loop through the retries below.
    if (!covers.length || !recentLayoutActive()) {
        el.recent.hidden = true;
        recentRetries = 0;
        return;
    }
    // Un-hidden before measuring, or it has no size.
    el.recent.hidden = false;
    var w = el.recentPile.clientWidth;
    var h = el.recentPile.clientHeight;
    if (w <= 0 || h <= 0) {
        // First-paint race: the flex chain has no size yet.
        if (recentRetries++ < 30) {
            requestAnimationFrame(renderRecent);
        } else {
            el.recent.hidden = true;
        }
        return;
    }
    recentRetries = 0;
    el.recentPile.textContent = '';

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
    recentSleeves = [];
    var maxTravel = plan[0].size - plan[count - 1].size;

    for (i = 0; i < count; i++) {
        var size = plan[i].size;
        var sleeve = document.createElement('div');
        sleeve.className = 'np-recent-sleeve';
        // Alternating sides, each sleeve peeks out from under the wider one and stays hoverable.
        var shift = (i % 2 === 0 ? -1 : 1) * Math.round(w * RECENT_LANE_SHIFT);
        var left = Math.round((w - size) / 2 + shift);
        sleeve.style.setProperty('--np-recent-w', size + 'px');
        sleeve.style.setProperty('--np-recent-x', left + 'px');
        var lifted = Math.max(plan[0].size, Math.round(size * RECENT_HOVER_GROW_MIN));
        sleeve.style.setProperty('--np-recent-w2', lifted + 'px');
        sleeve.style.setProperty('--np-recent-x2',
            Math.round(left + (size - lifted) / 2) + 'px');
        sleeve.style.setProperty('--np-recent-rot', RECENT_TILTS[i % RECENT_TILTS.length] + 'deg');
        sleeve.style.setProperty('--np-recent-z', String(count - i));
        var age = count > 1 ? i / (count - 1) : 0;
        sleeve.style.setProperty('--np-recent-age', (0.95 - 0.5 * age).toFixed(3));
        sleeve.style.setProperty('--np-recent-sat', (1 - 0.25 * age).toFixed(3));
        var travel = maxTravel > 0 ? (plan[0].size - size) / maxTravel : 0;
        sleeve.style.setProperty('--np-recent-ms', Math.round(RECENT_HOVER_MS_MIN +
            (RECENT_HOVER_MS_MAX - RECENT_HOVER_MS_MIN) * travel) + 'ms');

        var img = document.createElement('img');
        img.onload = fitSleeve;
        img.src = '/cover/' + encodeURIComponent(covers[i]) +
            '.jpg?size=' + RECENT_COVER_SIZE;
        img.alt = '';
        img.decoding = 'async';
        sleeve.appendChild(img);

        el.recentPile.appendChild(sleeve);
        recentSleeves.push({ el: sleeve, img: img, size: size, lifted: lifted, r: 1 });
    }
    stackRecent();
}

// The overlap and the lift follow each artwork's real height; renderRecent's fit
// loop assumes squares, the tallest case, so the pile never outgrows its column.
function stackRecent() {
    var y = 0;
    for (var i = 0; i < recentSleeves.length; i++) {
        var s = recentSleeves[i];
        var fh = Math.min(1, 1 / s.r);
        var h = s.size * fh;
        s.el.style.setProperty('--np-recent-r', s.r);
        s.el.style.setProperty('--np-recent-y', Math.round(y) + 'px');
        s.el.style.setProperty('--np-recent-y2', Math.round(y + h - s.lifted * fh) + 'px');
        y += h * (1 - RECENT_OVERLAP);
    }
}

function fitSleeve() {
    for (var i = 0; i < recentSleeves.length; i++) {
        if (recentSleeves[i].img === this) {
            recentSleeves[i].r = coverRatio(this);
            stackRecent();
            return;
        }
    }
}

// Once per track, as only a track change reorders the history; on failure
// recentKey stays, so the next track change retries.
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
        // The listens that just ended reorder the pile, so the next playback refetches it.
        recentCovers = null;
        recentKey = null;
        if (el.recent) { el.recent.hidden = true; }
        el.player.textContent = '';
        if (el.playerSwitch) { el.playerSwitch.hidden = true; el.playerSwitch.textContent = ''; }
        lastSwitchKey = null;
        renderVolume(null);
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
        setProgressBar(el.progressBar, 0);
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
    renderVolume(data);
    el.title.textContent = data.title || '';
    el.artist.textContent = data.artist || '';
    el.album.textContent = data.album
        ? (data.year ? data.album + ' (' + data.year + ')' : data.album)
        : '';

    // Streams like a Deezer flow keep one track_id across songs, so the key
    // includes the visible metadata.
    var trackKey = [data.track_id, data.title, data.artist, data.album].join('|');
    if (trackKey !== lastTrackKey) {
        lastTrackKey = trackKey;
        releaseLyricsHeight();
        currentTrack = data;
        // COVER_SIZE is the /cover route's cap; remote artwork has no resize form.
        el.cover.src = data.artwork_url
            ? '/cover/remote.jpg?t=' + encodeURIComponent(trackKey)
            : '/cover/' + (data.coverid || 0) + '.jpg?size=' + COVER_SIZE;
        loadRecent();
        syncCoverZoom();
        versions = data.lyrics ? [{ text: data.lyrics, source: 'library' }] : [];
        versionIdx = data.lyrics ? 0 : -1;
        lyricsHidden = false;
        if (!data.lyrics) { setLyrics(I18N.no_lyrics_library, true); }
        else if (allHidden()) { showHidden(); }
        else { showVersion(0); }
        updateSource();
        lyricsTried = false;
        searchFailure = null;
        setSearching(false);
        // The cooldown is per track, so a new one starts with a live button.
        holdRetry(0);

        if (data.lyrics) {
            trySyncedFromWeb();
        } else {
            fetchLyrics();
        }
    }
}

// Throttled and unavailable answers return instantly, so they need their own
// message, or the retry looks broken.
function searchFailureMessage(res) {
    if (res && res.throttled) { return I18N.lyrics_throttled; }
    if (res && res.source === 'unavailable') { return I18N.lyrics_unavailable; }
    return null;
}

function emptyLyricsMessage(res) {
    return searchFailureMessage(res) || I18N.no_lyrics_found;
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
            // render() may have moved on to another track while this was in flight.
            if (track !== currentTrack) { return; }
            setSearching(false);
            holdRetry(res.retry_after || 0);
            if (pushWebVersions(res)) {
                landOnVersions(null);
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
    searchFailure = null;
    setSearching(true);
    fetch('/lyrics.json?' + params.toString(), { cache: 'no-store' })
        .then(function(r) { return r.json(); })
        .then(function(res) {
            if (track !== currentTrack) { return; }
            searchFailure = searchFailureMessage(res);
            setSearching(false);
            holdRetry(res.retry_after || 0);
            var current = versions[versionIdx];
            // An answer that only repeated the text on screen still refreshes the chip.
            if (!pushWebVersions(res)) { updateSource(); return; }
            landOnVersions(current);
        })
        .catch(function() {
            if (track !== currentTrack) { return; }
            searchFailure = I18N.lyrics_unavailable;
            setSearching(false);
        });
}

function retryLyrics() {
    if (!currentTrack) { return; }
    // Drop the previous answer, or the new one stacks a second copy onto the cycle.
    versions = versions.filter(function(version) { return version.source === 'library'; });
    versionIdx = versions.length ? 0 : -1;
    for (var i = 0; i < versions.length; i++) { versions[i].echoes = []; }
    lyricsTried = true;  // force refresh=1 → bypass the server-side cache
    if (currentTrack.lyrics) {
        trySyncedFromWeb();  // the library's text stays unless the web beats it
    } else {
        fetchLyrics();
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

// Only travel the box can absorb counts. syncLyrics() never fires these events, and the
// native scroll applies regardless, so below the threshold resync at once.
el.lyrics.addEventListener('wheel', function(e) {
    if (!lrcLines || !autoFollowScroll) { return; }
    var now = Date.now();
    // A gap between ticks starts a new gesture.
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

// Pull-to-refresh, app only. The zone leaves out the lyrics block, which
// scrolls, and the gesture reloads through the shell rather than in-page.
var PULL_ZONE = '.np-side, .np-meta, .np-empty';
var PULL_TRIGGER = 72;
var PULL_MAX = 104;
var PULL_SLOP = 8;

var pullBadge = document.getElementById('np-pull');
var pullStartY = 0;
var pullStartX = 0;
var pullTracking = false;
var pullOwned = false;
var pullArmed = false;
var pullBusy = false;

function paintPull(distance) {
    var progress = Math.min(1, distance / PULL_TRIGGER);
    pullBadge.style.setProperty('--np-pull-y', Math.min(distance, PULL_MAX) + 'px');
    pullBadge.style.setProperty('--np-pull-p', progress);
    pullArmed = distance >= PULL_TRIGGER;
    pullBadge.classList.toggle('is-armed', pullArmed);
}

function resetPull() {
    pullTracking = false;
    pullOwned = false;
    pullArmed = false;
    pullBadge.classList.remove('is-dragging', 'is-armed');
    pullBadge.style.setProperty('--np-pull-y', '0px');
    pullBadge.style.setProperty('--np-pull-p', 0);
}

function pullCanStart(e) {
    return !pullBusy && e.touches.length === 1 &&
        (window.scrollY || window.pageYOffset || 0) <= 0 &&
        nowPlaying.scrollTop <= 0 &&
        !!(e.target && e.target.closest && e.target.closest(PULL_ZONE));
}

if (pullBadge && APP_BRIDGE && APP_BRIDGE.reload) {
    nowPlaying.addEventListener('touchstart', function(e) {
        if (!pullCanStart(e)) { return; }
        pullStartY = e.touches[0].clientY;
        pullStartX = e.touches[0].clientX;
        pullTracking = true;
        pullOwned = false;
    }, { passive: true });

    nowPlaying.addEventListener('touchmove', function(e) {
        if (!pullTracking || !e.touches.length) { return; }
        var moved = e.touches[0].clientY - pullStartY;
        var sideways = Math.abs(e.touches[0].clientX - pullStartX);
        if (!pullOwned) {
            // Anything but a downward drag stays the page's for the rest of the gesture.
            if (Math.abs(moved) <= PULL_SLOP && sideways <= PULL_SLOP) { return; }
            if (moved <= PULL_SLOP || sideways > moved) { pullTracking = false; return; }
            pullOwned = true;
            pullBadge.classList.add('is-dragging');
        }
        // Non-passive listener: preventDefault is what suppresses the overscroll.
        e.preventDefault();
        paintPull(moved - PULL_SLOP);
    }, { passive: false });

    nowPlaying.addEventListener('touchend', function() {
        if (pullOwned && pullArmed) {
            pullBusy = true;
            pullBadge.classList.remove('is-dragging');
            pullBadge.classList.add('is-busy');
            paintPull(PULL_TRIGGER);
            APP_BRIDGE.reload();
            return;
        }
        resetPull();
    }, { passive: true });

    nowPlaying.addEventListener('touchcancel', resetPull, { passive: true });
}

var coverZoom = {
    root: document.getElementById('cover-zoom'),
    figure: document.getElementById('cover-zoom-figure'),
    img: document.getElementById('cover-zoom-img'),
    meta: document.querySelector('.cover-zoom-meta'),
    progressBar: document.getElementById('cover-zoom-progress-bar'),
    title: document.getElementById('cover-zoom-title'),
    artist: document.getElementById('cover-zoom-artist'),
    album: document.getElementById('cover-zoom-album'),
    button: document.getElementById('np-cover-button'),
    panel: document.querySelector('.left-panel'),
};

var ZOOM_MS = 260;
var zoomAnims = [];

function zoomOpts(closing) {
    return {
        duration: ZOOM_MS,
        easing: 'cubic-bezier(0.2, 0, 0.2, 1)',
        fill: closing ? 'both' : 'backwards',
    };
}

// Dropping ?size= asks the same route for the original artwork; the remote
// URL carries a per-track cache buster instead, so it keeps its query.
function fullCoverSrc(src) {
    return src.indexOf('/cover/remote.jpg') === 0 ? src : src.split('?')[0];
}

function setCoverRatio(img) {
    if (img.naturalWidth && img.naturalHeight) {
        coverZoom.figure.style.setProperty('--cover-r', img.naturalWidth / img.naturalHeight);
    }
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
    // Read off the card's copy, which is already decoded: the enlarged one may
    // still be loading when the opening animation measures its box.
    setCoverRatio(el.cover);
    coverZoom.title.textContent = el.title.textContent;
    coverZoom.artist.textContent = el.artist.textContent;
    coverZoom.album.textContent = el.album.textContent;
}

function stopZoomAnims() {
    for (var i = 0; i < zoomAnims.length; i++) { zoomAnims[i].cancel(); }
    zoomAnims = [];
}

// Both boxes are measured per run: the panel's height follows the lyrics, and
// the enlarged picture is laid out from the artwork's ratio.
function animateZoom(from, closing) {
    var big = coverZoom.figure.getBoundingClientRect();
    if (!from.width || !big.width ||
        window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
        return null;
    }
    var small = {
        transform: 'translate(' + (from.left - big.left) + 'px, ' + (from.top - big.top) +
            'px) scale(' + (from.width / big.width) + ')',
    };
    var grown = { transform: 'none' };
    // The caption arrives once the picture is nearly in place and leaves
    // first: shrunk to the card cover's size it would be illegible.
    var caption = closing
        ? [{ opacity: 1, offset: 0 }, { opacity: 0, offset: 0.45 }, { opacity: 0, offset: 1 }]
        : [{ opacity: 0, offset: 0 }, { opacity: 0, offset: 0.55 }, { opacity: 1, offset: 1 }];
    // Opening fills backwards only: once it ends the enlarged state comes from
    // the stylesheet, never from an animation left holding its last frame.
    var opts = zoomOpts(closing);
    zoomAnims = [
        coverZoom.figure.animate(closing ? [grown, small] : [small, grown], opts),
        coverZoom.meta.animate(caption, opts),
        coverZoom.root.animate({ opacity: closing ? [1, 0] : [0, 1] }, opts),
    ];
    return zoomAnims[0];
}

// Squaring the panel off moves everything below it, so its height is animated
// alongside the picture.
function animateCard(from, to, closing) {
    if (Math.abs(from - to) < 1 ||
        window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
        return;
    }
    zoomAnims.push(nowPlaying.animate(
        [{ height: from + 'px' }, { height: to + 'px' }], zoomOpts(closing)));
}

// The card's content clears out under the enlarged cover, on the picture's beat.
function animateCardContent(closing) {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) { return; }
    var frames = closing
        ? [{ opacity: 0 }, { opacity: 1 }]
        : [{ opacity: 1 }, { opacity: 0 }];
    for (var i = 0; i < nowPlaying.children.length; i++) {
        zoomAnims.push(nowPlaying.children[i].animate(frames, zoomOpts(closing)));
    }
}

function openCoverZoom() {
    if (!coverZoom.root || !el.cover.getAttribute('src')) { return; }
    var from = el.cover.getBoundingClientRect();
    var cardHeight = nowPlaying.getBoundingClientRect().height;
    stopZoomAnims();
    coverZoom.root.hidden = false;
    coverZoom.panel.classList.add('is-zoomed');
    coverZoom.button.setAttribute('aria-expanded', 'true');
    syncCoverZoom();
    animateZoom(from, false);
    animateCardContent(false);
    animateCard(cardHeight, nowPlaying.getBoundingClientRect().height, false);
}

function endCoverZoom() {
    stopZoomAnims();
    coverZoom.root.hidden = true;
    coverZoom.panel.classList.remove('is-zoomed');
}

function closeCoverZoom() {
    if (!coverZoom.root || coverZoom.root.hidden) { return; }
    coverZoom.button.setAttribute('aria-expanded', 'false');
    stopZoomAnims();
    var squared = nowPlaying.getBoundingClientRect().height;
    // Measured with the class off and put back at once, in the same frame:
    // the panel keeps clipping its content while it grows back.
    coverZoom.panel.classList.remove('is-zoomed');
    var natural = nowPlaying.getBoundingClientRect().height;
    coverZoom.panel.classList.add('is-zoomed');
    var shrink = animateZoom(el.cover.getBoundingClientRect(), true);
    animateCardContent(true);
    animateCard(squared, natural, true);
    if (shrink) {
        shrink.onfinish = endCoverZoom;
    } else {
        endCoverZoom();
    }
}

if (coverZoom.button && coverZoom.root) {
    // On a track change the card's copy still carries the previous artwork's
    // dimensions, so the enlarged one settles the ratio when it loads.
    coverZoom.img.addEventListener('load', function() {
        setCoverRatio(coverZoom.img);
    });
    coverZoom.button.addEventListener('click', openCoverZoom);
    coverZoom.root.addEventListener('click', closeCoverZoom);
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') { closeCoverZoom(); }
    });
}

function fitCardCover() {
    el.cover.closest('.np-cover').style.setProperty('--np-cover-r', coverRatio(el.cover));
}

el.cover.addEventListener('load', function() {
    fitCardCover();
    sampleCoverTint();
});

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
// A request the OS suspended mid-flight (network handover, doze) can hang
// without ever failing.
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
    // data.time is read mid-trip, so render() back-dates it by half the round trip.
    var sentAt = Date.now();
    // ?known skips the lyrics lookup while the track on screen is unchanged;
    // ?player sends this device's pin.
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
            // Text nodes, never innerHTML, mirroring the server-rendered structure.
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
// Extrapolates the position, and drives the karaoke, between network polls.
setInterval(paintProgress, 250);
