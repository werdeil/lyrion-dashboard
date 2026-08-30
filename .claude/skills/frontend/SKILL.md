---
name: frontend
description: >-
  Work on the dashboard's frontend — the vanilla JS/CSS page with no framework
  or bundler. Use this whenever a task touches `static/nowplaying.js`,
  `static/style.css`, the Jinja templates (`templates/nowplaying.html`,
  `_icons.html`), the accent-color tinting, the karaoke lyrics sync, the
  now-playing poll, or the empty-state mosaic / recent-plays pile. Covers how
  the page is wired, how it reads i18n and data from the server, the ESLint
  gate, and the Android bridge, so changes match the existing patterns.
---

# Frontend (vanilla JS/CSS, no framework)

The page is plain ES5-ish JavaScript and hand-written CSS — **no framework, no bundler, no build step, no npm dependencies**. Two vendored libraries in `static/lib/` (`fast-average-color`, `vibrant`) are loaded via `<script>` tags. Keep it that way: don't introduce a framework, a bundler, or a package.json.

- `static/nowplaying.js` — all page behaviour (~1300 lines, one file).
- `static/style.css` — all styling.
- `templates/nowplaying.html` — the Jinja page. `templates/_icons.html` — reusable inline-SVG icon macros (`{% import "_icons.html" as icons %}`).
- `DEV=1 python app.py` live-reloads templates and disables static caching, so HTML/CSS/JS edits show on a plain refresh (see `config.py`).

## Lint gate

ESLint (flat config `eslint.config.mjs`, dependency-free) runs in CI on `static/*.js` (`.github/workflows/web-ci.yml`):

```bash
npx --yes eslint@9 static/*.js
```

Match the existing style: `var`, small named `function`s, `try/catch` around `localStorage`, defensive null checks (`if (!el.retry) { return; }`).

## How the page gets its data

Nothing is hardcoded in the JS that the server already knows:

- **i18n** — the template serializes the chosen-language dict into a `<script id="i18n-data" type="application/json">` block; the JS reads it once as `I18N` and uses `I18N.some_key` for every dynamic string. Never hardcode a display string in JS — add a key in `i18n.py` (both `fr` and `en`) and read it from `I18N`. See the `i18n` skill.
- **Server host** — `document.body.dataset.lyrionHost` (`LYRION_HOST`).
- **Live state** — the JSON endpoints: `/now-playing.json` (polled), `/stats.json`, `/lyrics.json`, `/mosaic-covers.json`, `/recent-covers.json`.
- **DOM handles** — collected once into the `el = { ... }` object by id; reuse those, don't re-query.

## The polling loop

`poll()` fetches `/now-playing.json` every `POLL_INTERVAL_MS` (2000ms) and calls `render(data)`. Two efficiency contracts to preserve when editing:

- The page sends `?known=<track key>` (the `id|title|artist|album` it already shows); the server omits `lyrics` when it matches, so a steady-state poll skips the DB. Keep the key format in sync with the route.
- `?player=<id>` pins the switcher's pick (persisted in `localStorage`); a malformed id is dropped server-side.

`catchUp()` re-syncs after the tab was backgrounded. Stats poll separately (`pollStats`).

## Accent color from the cover

The signature visual: the page samples the cover art (served **same-origin** via `/cover/...` precisely so the canvas isn't tainted) to derive two colors — a **tint** (the average color, `FastAverageColor`) and an **accent** (the dominant vibrant swatch, `Vibrant`, normalized in HSV via `rgb2Hsv`/`hsv2Rgb`: fixed brightness `ACCENT_V`, saturation clamped into `[ACCENT_SAT_FLOOR, ACCENT_SAT_MAX]`, and swatches under `ACCENT_SAT_MIN` — greyscale covers — falling back to `ACCENT_DEFAULT`). `SWATCH_ORDER` sets swatch preference. `setTint`/`setAccent`/`resetColors` push them into CSS custom properties. If you change how covers are served, keep them same-origin or the tint breaks.

## Karaoke lyrics sync

`parseLRC` turns timestamped LRC into `[{time, text}]`; `syncLyrics` (driven off the aged playback `time` from the poll) highlights the current line via `paintLine` and auto-scrolls, unless the user scrolled away (`setAutoFollow`, `updateScrollReset`, the resume-scroll button). Plain (un-timed) lyrics render as static text. The web-search switch (`setAuto`) is `off`/`auto`, persisted in `localStorage`; display always prefers synced over plain — it's never a user choice.

## Enlarged cover

The card's artwork is a button (`#np-cover-button`) opening `#cover-zoom`, an overlay holding the artwork with the track's title/artist/album over its lower edge. It covers `.left-panel` — the now-playing card only, leaving the stats panel readable — and is a sibling of the card rather than a child, because the card's `backdrop-filter` would make it the containing block of any `position: fixed` descendant. Narrow landscape is the one configuration where the card outgrows the screen, so there the overlay switches to `position: fixed` and takes the viewport.

There is no close button: a click anywhere on the overlay closes it, as does Escape, and `render()` closes it when playback stops. Focus never leaves the trigger, which carries `aria-expanded`.

The overlay has no surface of its own — the panel keeps its card background, and the card's content is what clears out under it (`.left-panel.is-zoomed .now-playing > *`, faded by `animateCardContent`). Only the narrow-landscape fallback, which covers the whole viewport, carries a backdrop. On the stacked layouts the overlay drops its padding so the picture runs edge to edge, the same width as the stats panel under it; `--cover-zoom-radius` keeps the picture's corners on the card's.

`.cover-zoom-figure` is sized as the largest box of the artwork's ratio that fits the panel — `--cover-r` (set from the card image's `naturalWidth/naturalHeight`, already decoded when the view opens, and settled again when the enlarged image loads — on a track change the card's copy still carries the previous artwork's dimensions) plus a `100cqh` width off the overlay's container query. The picture fills that box, upscaled when the panel is bigger than the artwork, and the rounded edge, shadow and caption hug the picture rather than a letterboxed box. On the stacked layouts the card grows with the lyrics far past its own width, so `.left-panel.is-zoomed` squares it off.

The caption (`.cover-zoom-meta`) is a plaque hugging its text near the picture's lower edge, not a band across it: absolutely positioned with `width: fit-content` and auto margins, tinted and `backdrop-filter`-blurred so it reads over any artwork.

`paintProgress` paints the playback position into the bar on the artwork's bottom edge along with the card's own, so the two never drift.

Opening is a FLIP: `animateZoom` measures the card cover's box and the enlarged figure's box at run time — the panel's height follows the lyrics, so neither is fixed — and animates the figure from one to the other while the card's content fades out and the caption arrives late; `animateCard` animates the card's height over the same beat so the stats below slide rather than jump. Closing plays it backwards and only then sets `hidden`. Opening fills backwards only (`zoomOpts`): once it ends the enlarged state comes from the stylesheet rather than an animation holding its last frame. Everything is skipped under `prefers-reduced-motion`.

The card shows a 512px thumbnail; the overlay paints that cached thumbnail first and swaps in the original artwork (the same `/cover/` URL without `?size=`) once it has loaded, so it never shows a blank frame.

## Mosaic and recent-plays pile

The empty-state background mosaic (`loadMosaic`/`layoutMosaic`/`stepMosaic`) and the recent-plays sleeve pile (`loadRecent`/`renderRecent`) are decorative, desktop-driven layouts. They pull cover ids from `/mosaic-covers.json` and `/recent-covers.json`.

The mosaic's belt **steps rather than flows**: one cover every `MOSAIC_STEP_MS`, glided by the tiles' CSS transform transition, and nothing scheduled in between. Continuous motion is what costs — every frame recomposites the whole backdrop, a full core against 2.7% for a still collage — and the cost scales with the step rate, so that constant is the only knob worth turning. A cover only ever glides one slot along its row; anywhere the belt is discontinuous it is placed outright, which stays invisible because those breaks are all off the card.

## Measuring the page

Two traps, both of which quietly yield wrong numbers rather than an error:

- The app's `CSP default-src 'self'` blocks a `<style>` injected at runtime, so a probe that overrides CSS that way measures nothing at all — the override never applies. CSSOM writes (`el.style.foo = …`) and the Web Animations API are unaffected.
- `getBoundingClientRect()` on a mosaic tile returns the bounding box of the 3°-rotated square, ~10px wider than the cover itself. Read the CSS width when the number matters.

## Android bridge

Inside the Android WebView a native object `window.LyrionApp` is injected. The JS detects it (kept in `APP_BRIDGE`), adds `body.in-app`, reveals the header menu button, and wires it to `bridge.openMenu()` / `openSettings()`. Pull-to-refresh is app-only too: a downward drag starting in the card's cover/meta zone (`PULL_ZONE`, so never the scrolling lyrics box) rides the `#np-pull` badge down from the card's top edge and calls `bridge.reload()` past `PULL_TRIGGER`, which reloads through the shell so a server that has gone away lands on the native error view. The gesture only starts with the page and the card both at their top, and the `touchmove` listener is non-passive because suppressing the WebView's overscroll needs `preventDefault()`. On Android, the "open in Lyrion" links become `intent://` URLs targeting the LMS Material app. Guard any app-only behaviour behind the presence of the bridge, as the existing code does.

## Regenerate the README screenshots after a visual change

The README images (`docs/screenshots/`) are checked in and embedded in `README.md` (EN, `dashboard-en.png`), `README.fr.md` (FR, `dashboard-fr.png`), plus `dashboard-mobile.png` and `dashboard-app.png`. **If your change alters what the dashboard looks like** — layout, styling, colors, the empty state, the lyrics/stats panels, an icon, anything a user would see — regenerate them so the docs don't drift from the app:

```bash
pip install -r requirements.txt playwright
playwright install chromium        # once
python scripts/generate_screenshots.py
```

The script runs the real app with the Lyrion/DB layers mocked (fake track, synced LRC, generated cover art, canned stats) and captures every image with headless Chromium — desktop in **both** languages, the mobile view, and the Android app view. No Lyrion server or database is needed. Commit the updated PNGs alongside the code change, and keep both language shots in sync (they're regenerated together). Skip this only for changes with no visual effect (pure refactors, endpoint-only tweaks).

## Checklist

1. No new framework/bundler/npm dep; stay vanilla and edit the single JS file.
2. Every user-facing string comes from `I18N` (key added to `i18n.py` FR+EN).
3. Read server data from the existing endpoints / `data-*` attributes.
4. Keep covers same-origin so tinting works.
5. Run `npx --yes eslint@9 static/*.js` — it gates CI.
6. Visual change? Regenerate `docs/screenshots/` (see above) and commit the PNGs.
