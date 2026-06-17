// UI strings for the dynamic (JS-rendered) bits, resolved server-side from the
// browser language and embedded in the page as JSON. Static markup is
// translated via Jinja in the template.
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

var nowPlaying = document.getElementById('now-playing');
var el = {
    player: document.getElementById('np-player'),
    title:  document.getElementById('np-title'),
    artist: document.getElementById('np-artist'),
    album:  document.getElementById('np-album'),
    lyrics: document.getElementById('np-lyrics'),
    source: document.getElementById('np-lyrics-source'),
    cover:  document.getElementById('np-cover-img'),
    fetch:  document.getElementById('np-fetch-lyrics'),
    progressBar: document.getElementById('np-progress-bar'),
    lyrionLink: document.getElementById('lyrion-link'),
};

// "Open in Lyrion" button. On desktop it opens the Material web skin,
// deep-linked to the active player. On Android it opens the native LMS
// Material app (com.craigd.lmsmaterial.app) via an intent URL, falling
// back to the web skin when the app isn't installed.
// NB: the native app loads its own configured server + default player,
// so the ?player= hint only affects the web (skin / fallback), not the
// app — there is no supported way to deep-link a player into the app.
var MATERIAL_BASE = LYRION_HOST ? LYRION_HOST + '/material/' : '#';
var IS_ANDROID = /Android/i.test(navigator.userAgent || '');
var MATERIAL_APP_PKG = 'com.craigd.lmsmaterial.app';
function setLyrionLink(playerId) {
    if (!el.lyrionLink) { return; }
    if (!LYRION_HOST) { el.lyrionLink.href = '#'; return; }
    var web = MATERIAL_BASE + (playerId ? '?player=' + encodeURIComponent(playerId) : '');
    if (IS_ANDROID) {
        el.lyrionLink.href = 'intent://' + web.replace(/^https?:\/\//, '') +
            '#Intent;scheme=https;type=text/html;package=' + MATERIAL_APP_PKG +
            ';S.browser_fallback_url=' + encodeURIComponent(web) + ';end';
    } else {
        el.lyrionLink.href = web;
    }
}
var lastTrackId = null;
var currentTrack = null;
var lyricsTried = false;

// Background tint, Material-skin style: neutral grey-blue when idle,
// the cover's dominant colour while playing. The cover is served
// same-origin (via /cover/<id>.jpg) so we can read its pixels.
var TINT_NEUTRAL = '#8b94a8';
// Default accent for when there's no usable cover hue (idle screen,
// greyscale covers, sampling failures): a soft Lyrion-like blue that
// stays calm on the dark UI, matching Lyrion's current default.
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

function hslToRgb(h, s, l) {
    function hue(p, q, t) {
        if (t < 0) t += 1;
        if (t > 1) t -= 1;
        if (t < 1 / 6) return p + (q - p) * 6 * t;
        if (t < 1 / 2) return q;
        if (t < 2 / 3) return p + (q - p) * (2 / 3 - t) * 6;
        return p;
    }
    var q = l < 0.5 ? l * (1 + s) : l + s - l * s;
    var p = 2 * l - q;
    return 'rgb(' +
        Math.round(hue(p, q, h + 1 / 3) * 255) + ',' +
        Math.round(hue(p, q, h) * 255) + ',' +
        Math.round(hue(p, q, h - 1 / 3) * 255) + ')';
}

// Average the cover, then push saturation/lightness into a readable
// mid-range so even muted artwork yields a visible — but not garish — tint.
function sampleCoverTint() {
    try {
        var img = el.cover;
        if (!img.naturalWidth) { return; }
        var s = 32;
        var canvas = document.createElement('canvas');
        canvas.width = s;
        canvas.height = s;
        var ctx = canvas.getContext('2d');
        ctx.drawImage(img, 0, 0, s, s);
        var d = ctx.getImageData(0, 0, s, s).data;
        var r = 0, g = 0, b = 0, n = 0;
        for (var i = 0; i < d.length; i += 4) {
            if (d[i + 3] < 125) { continue; }
            r += d[i]; g += d[i + 1]; b += d[i + 2]; n++;
        }
        if (!n) { resetColors(); return; }
        r = r / n / 255; g = g / n / 255; b = b / n / 255;
        var max = Math.max(r, g, b), min = Math.min(r, g, b);
        var l = (max + min) / 2, h = 0, sat = 0;
        if (max !== min) {
            var dd = max - min;
            sat = l > 0.5 ? dd / (2 - max - min) : dd / (max + min);
            if (max === r) { h = (g - b) / dd + (g < b ? 6 : 0); }
            else if (max === g) { h = (b - r) / dd + 2; }
            else { h = (r - g) / dd + 4; }
            h /= 6;
        }
        // Background tint: muted mid-range so it stays a backdrop.
        setTint(hslToRgb(h, Math.min(1, Math.max(sat, 0.45)),
                            Math.min(0.62, Math.max(0.42, l))));
        // Accents: brighter and more saturated to stay legible on the
        // dark UI. A near-greyscale cover has no meaningful hue, so we
        // fall back to the default blue rather than inventing a colour.
        if (sat < 0.08) {
            setAccent(ACCENT_DEFAULT);
        } else {
            setAccent(hslToRgb(h, Math.min(1, Math.max(sat, 0.55)), 0.6));
        }
    } catch (e) {
        // Tainted canvas or other failure: fall back to the neutral look.
        resetColors();
    }
}

// Authoritative transport state from the last poll. We interpolate
// locally between polls so the bar advances smoothly instead of
// jumping every 5s; each poll resyncs to the server's time.
var progress = { time: 0, duration: 0, playing: false, syncedAt: 0 };

function paintProgress() {
    var t = progress.time;
    if (progress.playing) {
        t += (Date.now() - progress.syncedAt) / 1000;
    }
    var pct = progress.duration > 0
        ? Math.max(0, Math.min(100, (t / progress.duration) * 100))
        : 0;
    el.progressBar.style.width = pct + '%';
}

// Friendly labels for the provider keys returned by /lyrics.json.
// Only "library" is translated; the web providers are proper nouns.
var SOURCE_LABELS = {
    library:    I18N.source_library,
    lrclib:     'LRCLIB',
    musixmatch: 'Musixmatch',
    genius:     'Genius',
};

function setLyrics(text, isEmpty) {
    el.lyrics.textContent = text;
    el.lyrics.classList.toggle('empty', !!isEmpty);
    // Reset scroll so a new track's lyrics start from the top.
    el.lyrics.scrollTop = 0;
}

function setLyricsSource(source) {
    var label = source && SOURCE_LABELS[source];
    el.source.textContent = label ? I18N.source_prefix + ' ' + label : '';
}

function render(data) {
    if (!data || !data.track_id) {
        nowPlaying.classList.add('is-empty');
        el.player.textContent = '';
        el.cover.removeAttribute('src');
        setLyrionLink(null);
        resetColors();
        lastTrackId = null;
        currentTrack = null;
        progress = { time: 0, duration: 0, playing: false, syncedAt: 0 };
        el.progressBar.style.width = '0';
        return;
    }

    nowPlaying.classList.remove('is-empty');

    progress = {
        time: data.time || 0,
        duration: data.duration || 0,
        playing: !!data.playing,
        syncedAt: Date.now(),
    };
    paintProgress();
    setLyrionLink(data.player_id);
    el.player.textContent = data.player_name || '';
    el.title.textContent = data.title || '';
    el.artist.textContent = data.artist || '';
    el.album.textContent = data.album || '';

    // Only repaint cover + lyrics when the track actually changes,
    // so polling doesn't flicker the image or reset lyric scroll.
    if (data.track_id !== lastTrackId) {
        lastTrackId = data.track_id;
        currentTrack = data;
        el.cover.src = '/cover/' + (data.coverid || 0) + '.jpg';
        setLyrics(data.lyrics || I18N.no_lyrics, !data.lyrics);
        setLyricsSource(data.lyrics ? 'library' : null);
        // Offer the web lookup only when the library has no lyrics.
        el.fetch.style.display = data.lyrics ? 'none' : '';
        el.fetch.disabled = false;
        el.fetch.textContent = '🔍 ' + I18N.fetch_lyrics;
        lyricsTried = false;
    }
}

el.fetch.addEventListener('click', function() {
    if (!currentTrack) { return; }
    el.fetch.disabled = true;
    el.fetch.textContent = I18N.searching;
    var params = new URLSearchParams({
        track_id: currentTrack.track_id || '',
        artist:   currentTrack.artist || '',
        title:    currentTrack.title || '',
        album:    currentTrack.album || '',
        duration: currentTrack.duration || '',
        // A retry forces a fresh LRCLIB lookup, bypassing the server cache.
        refresh:  lyricsTried ? '1' : '',
    });
    lyricsTried = true;
    fetch('/lyrics.json?' + params.toString(), { cache: 'no-store' })
        .then(function(r) { return r.json(); })
        .then(function(res) {
            var lyrics = res.lyrics || res.synced;
            if (lyrics) {
                setLyrics(lyrics, false);
                setLyricsSource(res.source);
                el.fetch.style.display = 'none';
            } else {
                setLyrics(I18N.no_lyrics_web, true);
                el.fetch.disabled = false;
                el.fetch.textContent = '🔍 ' + I18N.retry;
            }
        })
        .catch(function() {
            el.fetch.disabled = false;
            el.fetch.textContent = '🔍 ' + I18N.retry;
        });
});

// Re-tint whenever a new cover finishes loading.
el.cover.addEventListener('load', sampleCoverTint);

function poll() {
    fetch('/now-playing.json')
        .then(function(r) { return r.json(); })
        .then(render)
        .catch(function() { /* keep last render on transient errors */ });
}

// Stats change only when playcounts move, so refresh them less often
// than now-playing. Elements carry data-stat (and optional data-stat-pct)
// so we update text in place without reloading the page.
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

// Dim second-level breakdown rows whose count is zero. Reads the
// leading integer of each .sub row's value (e.g. "0 (0%)" -> 0).
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
        .catch(function() { /* keep last render on transient errors */ });
}

dimZeroSubRows();
poll();
setInterval(poll, 5000);
setInterval(pollStats, 60000);
setInterval(paintProgress, 1000);
