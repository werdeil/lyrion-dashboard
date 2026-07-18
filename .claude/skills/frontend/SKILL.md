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

The page is plain ES5-ish JavaScript and hand-written CSS — **no framework, no
bundler, no build step, no npm dependencies**. Two vendored libraries in
`static/lib/` (`fast-average-color`, `vibrant`) are loaded via `<script>` tags.
Keep it that way: don't introduce a framework, a bundler, or a package.json.

- `static/nowplaying.js` — all page behaviour (~1300 lines, one file).
- `static/style.css` — all styling.
- `templates/nowplaying.html` — the Jinja page. `templates/_icons.html` —
  reusable inline-SVG icon macros (`{% import "_icons.html" as icons %}`).
- `DEV=1 python app.py` live-reloads templates and disables static caching, so
  HTML/CSS/JS edits show on a plain refresh (see `config.py`).

## Lint gate

ESLint (flat config `eslint.config.mjs`, dependency-free) runs in CI on
`static/*.js` (`.github/workflows/web-ci.yml`):

```bash
npx --yes eslint@9 static/*.js
```

Match the existing style: `var`, small named `function`s, `try/catch` around
`localStorage`, defensive null checks (`if (!el.retry) { return; }`).

## How the page gets its data

Nothing is hardcoded in the JS that the server already knows:

- **i18n** — the template serializes the chosen-language dict into a
  `<script id="i18n-data" type="application/json">` block; the JS reads it once
  as `I18N` and uses `I18N.some_key` for every dynamic string. Never hardcode a
  display string in JS — add a key in `i18n.py` (both `fr` and `en`) and read
  it from `I18N`. See the `i18n` skill.
- **Server host** — `document.body.dataset.lyrionHost` (`LYRION_HOST`).
- **Live state** — the JSON endpoints: `/now-playing.json` (polled),
  `/stats.json`, `/lyrics.json`, `/mosaic-covers.json`, `/recent-covers.json`.
- **DOM handles** — collected once into the `el = { ... }` object by id; reuse
  those, don't re-query.

## The polling loop

`poll()` fetches `/now-playing.json` every `POLL_INTERVAL_MS` (2000ms) and calls
`render(data)`. Two efficiency contracts to preserve when editing:

- The page sends `?known=<track key>` (the `id|title|artist|album` it already
  shows); the server omits `lyrics` when it matches, so a steady-state poll
  skips the DB. Keep the key format in sync with the route.
- `?player=<id>` pins the switcher's pick (persisted in `localStorage`); a
  malformed id is dropped server-side.

`catchUp()` re-syncs after the tab was backgrounded. Stats poll separately
(`pollStats`).

## Accent color from the cover

The signature visual: the page samples the cover art (served **same-origin**
via `/cover/...` precisely so the canvas isn't tainted) to derive two colors —
a **tint** (the average color, `FastAverageColor`) and an **accent** (the
dominant vibrant swatch, `Vibrant`, normalized in HSV via `rgb2Hsv`/`hsv2Rgb`,
with `isGrey` guarding dull swatches). `SWATCH_ORDER` sets swatch preference.
`setTint`/`setAccent`/`resetColors` push them into CSS custom properties. If you
change how covers are served, keep them same-origin or the tint breaks.

## Karaoke lyrics sync

`parseLRC` turns timestamped LRC into `[{time, text}]`; `syncLyrics` (driven off
the aged playback `time` from the poll) highlights the current line via
`paintLine` and auto-scrolls, unless the user scrolled away (`setAutoFollow`,
`updateScrollReset`, the resume-scroll button). Plain (un-timed) lyrics render
as static text. The web-search switch (`setAuto`) is `off`/`auto`, persisted in
`localStorage`; display always prefers synced over plain — it's never a user
choice.

## Mosaic and recent-plays pile

The empty-state background mosaic (`loadMosaic`/`layoutMosaic`/`stepMosaic`,
animated via `requestAnimationFrame`) and the recent-plays sleeve pile
(`loadRecent`/`renderRecent`) are decorative, desktop-driven layouts. They pull
cover ids from `/mosaic-covers.json` and `/recent-covers.json`.

## Android bridge

Inside the Android WebView a native object `window.LyrionApp` is injected. The
JS detects it, adds `body.in-app`, reveals the header menu button, and wires it
to `bridge.openMenu()` / `openSettings()`. On Android, the "open in Lyrion"
links become `intent://` URLs targeting the LMS Material app. Guard any
app-only behaviour behind the presence of the bridge, as the existing code does.

## Checklist

1. No new framework/bundler/npm dep; stay vanilla and edit the single JS file.
2. Every user-facing string comes from `I18N` (key added to `i18n.py` FR+EN).
3. Read server data from the existing endpoints / `data-*` attributes.
4. Keep covers same-origin so tinting works.
5. Run `npx --yes eslint@9 static/*.js` — it gates CI.
