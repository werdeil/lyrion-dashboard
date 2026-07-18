# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Flask web app that displays a live "now playing" dashboard for a
[Lyrion Music Server](https://github.com/LMS-Community/slimserver) (formerly
Logitech Media Server / Squeezebox). It reads the currently playing track,
recent plays, synced lyrics and library statistics, and serves them on a
glanceable page. A thin Android WebView wrapper lives in `android/`.

It is designed for a **trusted home LAN and has no authentication by design**
— never add auth flows, login pages, or public-exposure features unless the
user explicitly asks. The security posture is deliberate; the full review is
[PR #15](https://github.com/werdeil/lyrion-dashboard/pull/15), referenced in
code as "audit S1", "P8", etc.

## Commands

The app targets **Python 3.12**. There is no build step — dependencies install
at container start.

```bash
# Run locally (needs a reachable Lyrion + its SQLite files; see .env.example)
pip install -r requirements.txt
cp .env.example .env      # then edit
source .env
python app.py             # http://localhost:1111

# Live-reload templates/static while developing
DEV=1 python app.py

# Docker (how it actually deploys)
docker compose up -d
```

### Tests, lint, security — the CI gates

CI (`.github/workflows/`) must stay green. Reproduce each job locally:

```bash
# Unit tests (unittest, discovered from repo root) — python-ci.yml
python -m unittest discover

# A single test file / case / method
python -m unittest tests.test_now_playing_route
python -m unittest tests.test_now_playing_route.NowPlayingKnownTest
python -m unittest tests.test_now_playing_route.NowPlayingKnownTest.test_no_known_includes_lyrics

# Syntax check (also part of python-ci.yml)
python -m compileall .

# Lint (pylint) — install both requirements files + playwright so imports resolve
pip install -r requirements.txt -r requirements-cli.txt playwright pylint
pylint app.py config.py i18n.py routes services scripts tests

# Security (security job) — accepted findings carry an inline `# nosec`; new ones fail
pip install pip-audit bandit
pip-audit
bandit -r . -x ./tests

# Frontend/shell lint — web-ci.yml
npx --yes eslint@9 static/*.js
shellcheck scripts/*.sh
```

Pylint config (`.pylintrc`) intentionally disables the docstring-required
checks and `broad-exception-caught`, caps line length at 130, and allows
`fetch_lyrics`' 7-arg signature. Match those norms rather than fighting them.

When opening a PR, follow `.github/pull_request_template.md`: fill in what/why
and how it was tested, and work through its checklist (it mirrors the CI gates
above plus the FR/EN string parity, README lockstep, and no-auth-by-design
rules).

## Architecture

### Request layering (strict)

**routes → services → (Lyrion | SQLite | web providers).** Routes parse the
request and shape the response; they never build JSON-RPC payloads or open the
DB inline. All real work lives in `services/`. Keep handlers thin — if a
handler grows domain logic, that logic belongs in a service.

- `app.py` — the app factory (`create_app`). Registers blueprints, the
  `/health` endpoint, and one `after_request` that sets app-wide security
  headers (`CSP default-src 'self'`, `nosniff`, `SAMEORIGIN`) via `setdefault`,
  so a route only sets a header itself to **override** the default for one
  route (as `/files/` does with `CSP: sandbox`).
- `config.py` — all configuration from env vars, read once at import (the
  source tree is mounted read-only). `DEV=1` enables template auto-reload and
  disables static caching. `VERSION` is read from the `VERSION` file.
- `routes/nowplaying.py` (`nowplaying_bp`) — the dashboard page and its JSON
  endpoints. `routes/custom.py` (`custom_bp`) — the sandboxed `/files/` server.

### Services

- `services/lyrion.py` — JSON-RPC client for the music server. Every call goes
  through `lyrion_request` (tolerant of Lyrion's empty non-JSON bodies).
  `status` queries request only the fields they need via a `tags:` string.
  Covers are proxied same-origin so the page can sample pixels for the accent
  tint. `get_active_now_playing` caches a snapshot of all playing players for
  `NOW_PLAYING_TTL` (2s) behind a lock and ages the playback position by
  wall-clock time, so many polling clients cost Lyrion one enumeration per TTL.
  `verify=False` is used **only** for the self-signed local host (audit S1),
  never for public CDN URLs. **See the `lyrion-api` skill.**
- `services/database.py` — read-only SQLite access. Opens Lyrion's `library.db`
  in RO mode and `ATTACH`es `persist.db` (also RO) per request via a context
  manager. The app never writes to these DBs — they belong to Lyrion.
- `services/lyrics.py` — web lyrics fallback (LRCLIB, Musixmatch, Genius, tried
  in `LYRICS_PROVIDERS` order; synced-capable providers first). Results live in
  a process-local in-memory cache (single gunicorn worker + threads means all
  requests share it); hits are cached longer (`TTL_HIT`) than misses
  (`TTL_MISS`). Cannot be persisted — `library.db` is read-only.
- `services/ratelimit.py` — dependency-free `RateLimiter` (per-IP sliding
  window) and `Cooldown` (once per interval), used to fuse the outbound lyrics
  searches. Idle entries are swept on every call so the maps stay bounded.
- `services/tags.py` — framework-free lyrics-into-file-tags writer (mutagen),
  shared by the web app and the CLI script. Only plain text is stored.

### Frontend

Vanilla JS/CSS, no framework or bundler. `static/nowplaying.js` +
`static/style.css`; `static/lib/` holds vendored `fast-average-color` and
`vibrant` (used to derive the accent color from the cover). `templates/` has
the Jinja page plus `_icons.html` (reusable inline-SVG icon macros).

### i18n (FR/EN)

The UI is fully bilingual. `i18n.py` is the single source of truth for UI
strings (`TRANSLATIONS` with `fr`/`en` sub-dicts sharing identical keys); the
language is chosen per request from `Accept-Language`. The whole chosen dict is
passed to the template as `t` and serialized to JS. **A user-facing string
never exists in only one language, and `README.md` (EN) and `README.fr.md`
(FR) are kept in lockstep.** JSON endpoints are not localized. **See the
`i18n` skill.**

### Scripts (`scripts/`)

Run outside the web app with `requirements-cli.txt` (no Flask/Lyrion). They
operate directly on audio files; Lyrion picks up changes on its next scan.
`embed_lyrics.py` embeds web lyrics into file tags; `embed_lyrics_cron.sh` is a
cron wrapper that only re-tags files whose `ctime` changed;
`generate_screenshots.py` regenerates the README images with mocked
Lyrion/DB layers and headless Chromium.

## Code style & comments

The codebase has a deliberate comment culture — match it rather than stripping
it or padding it out:

- **Comment the _why_, not the _what_.** Existing comments and docstrings
  explain reasoning and trade-offs (why a cache ages by wall-clock time, why the
  cache key isn't `track_id` alone, why a search retries without the album), not
  what the next line obviously does. Add a comment when a choice would puzzle
  the next reader; skip it when the code speaks for itself.
- **Comments are timeless — describe the _state_, not the _change_.** A comment
  documents how the code is now, as if it had always been that way, not the edit
  that produced it. Write "the cache ages by wall-clock time so shared clients
  stay accurate", never "changed this to age by wall-clock time" or "was 5s, now
  2s". Anything about _why it changed_ belongs in the commit message and the PR,
  not in a comment that the next reader will meet with no memory of the old code.
- **Docstrings where they add something, not everywhere.** `.pylintrc` disables
  the docstring-required checks on purpose. Public service functions carry rich
  docstrings that document the contract and the intent (`get_active_now_playing`,
  `fetch_lyrics`, `lyrion_request` are good models); trivial helpers don't need
  one.
- **Reference the audit tags for accepted risks.** Security/performance
  decisions that were reviewed and accepted cite their tag from the audit
  ([PR #15](https://github.com/werdeil/lyrion-dashboard/pull/15)) — "audit S1",
  "P8", etc. Keep that reference in the comment when you touch such code, and
  keep the inline `# nosec` (with its justification) that pairs with it, so the
  bandit trail and the audit stay connected.
- **Broad `except Exception` is intentional** around web providers and tag
  writers, where any single failure must not break the chain; `.pylintrc`
  disables `broad-exception-caught` for this reason. Don't narrow those without
  cause, and don't add new broad catches where a specific one belongs.

## Testing conventions

Tests use `unittest` + `unittest.mock.patch`. Each `tests/test_*.py` is
standalone: it sets `LYRION_HOST`, `DB_DIR`, `DB_PERSIST_DIR` via
`os.environ.setdefault` **before importing `app`** (config reads env at
import), then builds a client with `create_app().test_client()`. Patch the
**service functions a route imports**, at the route module path (e.g.
`@patch("routes.nowplaying.get_track_lyrics")`) — never hit a real Lyrion
server or a real DB. This env scaffolding is duplicated per file on purpose
(`# pylint: disable=duplicate-code`). `tests/test_now_playing_route.py` is the
reference example. **See the `add-route` skill.**

## Versioning & releases

`VERSION` (repo root) is the single source of truth for the web app version,
exposed on `/health` and kept in sync with the Android `versionName` by the
release workflow. Releases are cut manually via the `Release` workflow
(`workflow_dispatch`), which tags and opens a draft GitHub release; publishing
it fires `android.yml` to build and attach the signed APK.

## Repo-specific skills

Project skills live in `.claude/skills/` (tracked in git, shared with
contributors). Consult them when a task matches:

- **`lyrion-api`** — querying Lyrion over JSON-RPC (tags, caching, TLS rules).
- **`add-route`** — adding a Flask endpoint (route → service → test layering).
- **`i18n`** — adding/translating UI strings and keeping the READMEs in sync.
- **`testing`** — the `unittest`/`mock.patch` conventions (standalone files,
  env-before-import, where to patch, testing caches/clock).
- **`frontend`** — the vanilla JS/CSS page (accent tint, karaoke sync, polling,
  i18n wiring, the Android bridge, the ESLint gate).
- **`lyrics`** — the web fallback providers, cache/verification, and embedding
  lyrics into audio file tags.
- **`release`** — cutting a version (the `VERSION`/gradle mirrors, the manual
  Release → publish → `android.yml` chain).
- **`android`** — the WebView wrapper (shell-only principle, signing split,
  static F-Droid versioning, discovery, the JS↔native bridge).
