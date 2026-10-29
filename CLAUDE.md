# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Flask web app that displays a live "now playing" dashboard for a [Lyrion Music Server](https://github.com/LMS-Community/slimserver) (formerly Logitech Media Server / Squeezebox). It reads the currently playing track, recent plays, synced lyrics and library statistics, and serves them on a glanceable page. A thin Android WebView wrapper lives in `android/`.

It is designed for a **trusted home LAN and has no authentication by design** — never add auth flows, login pages, or public-exposure features unless the user explicitly asks. The security posture is deliberate; the full review is [PR #15](https://github.com/werdeil/lyrion-dashboard/pull/15), referenced in code as "audit S1", "P8", etc.

## Commands

The app targets **Python 3.12** and ships as a container image built by `docker.yml`, which installs the pinned dependencies into it. The frontend has no build step — no bundler, no transpiler.

```bash
# Run locally (needs a reachable Lyrion + its SQLite files, and a hand-written
# .env: LYRION_HOST and LYRION_DATA_DIR are enough — see docs/development.md)
pip install -r requirements.txt
set -a; source .env; set +a
python app.py             # http://localhost:1111

# Live-reload templates/static while developing
DEV=1 python app.py

# Docker (how it actually deploys: the published image; see docs/development.md to build one)
docker compose up -d
```

### Tests, lint, security — the CI gates

CI (`.github/workflows/`) must stay green. Reproduce each job locally:

```bash
# Unit tests (unittest, discovered from repo root) — python-ci.yml
python -m unittest discover

# Syntax check (also part of python-ci.yml)
python -m compileall .

# Lint (pylint) — install the requirements + playwright so imports resolve
pip install -r requirements.txt playwright pylint
pylint app.py config.py i18n.py logsetup.py routes services scripts tests

# Security (security job) — accepted findings carry an inline `# nosec`; new ones fail
pip install pip-audit bandit
pip-audit
bandit -r . -x ./tests

# Frontend/shell lint — web-ci.yml
npx --yes eslint@9 static/*.js
shellcheck .claude/hooks/*.sh
```

Pylint config (`.pylintrc`) intentionally disables the docstring-required checks and `broad-exception-caught`, caps line length at 130, and allows `fetch_lyrics`' 6-arg signature. Match those norms rather than fighting them.

In Claude Code on the web, `.claude/hooks/session-start.sh` installs these into a project `.venv` at session start (put first on `PATH`), so tests, pylint, pip-audit and bandit run without manual setup. Locally it's a no-op — manage your own venv.

PR titles and commit subjects follow Conventional Commits `type(scope): summary`; see the `pull-request` skill before opening or updating a PR. PR titles and descriptions are written in **English**, like commit messages — only the user-facing UI and the READMEs are bilingual.

**Markdown is never hard-wrapped: one paragraph is one line, however long.** That holds for the files in this repo — CLAUDE.md, the skills, the READMEs, the PR template — and for PR, issue and review bodies alike. In a file, a wrapped paragraph has to be reflowed the moment a sentence changes, so a two-word edit lands as a ten-line diff and the reviewer hunts for what actually moved; on GitHub, those bodies render with GFM line breaks on, so every newline inside a paragraph becomes a visible `<br>` and a body wrapped at 80 columns comes out ragged. Only prose joins up: code fences, tables, list items (each on its own single line) and raw HTML blocks — an image row, a comment — keep the line breaks they are written with. Keep angle brackets out of prose (`{id}`, not `<id>`; the sanitizer eats the latter). The commit message is the exception: it stays wrapped at ~72 columns because git shows it verbatim.

**Never post progress commentary on a PR.** A comment is for something the maintainer has to act on or could not get from the branch — not "pushed a follow-up", "fixed the regression", "sorry, I misread". Pushing more commits is how progress is reported; the commit messages carry the reasoning, and the description carries the current state. A review round that reshapes the branch leaves the PR with a rewritten description, not a trail of replies.

**Assign every PR to its author as soon as it is opened** — the GitHub account that opened it, read from the PR itself rather than assumed. When the tool that opens the PR takes no assignee, set it straight after through the issue API (a PR is an issue).

**Never subscribe to / watch a PR for activity** (CI results, review comments) on this repo — don't auto-monitor or auto-fix. Report status when asked and let the maintainer drive the PR.

**Never merge a PR** on this repo — merging is the maintainer's call, always. Prepare and push the branch, open or update the PR, but leave the merge to a human.

## Architecture

### Request layering (strict)

**routes → services → (Lyrion | SQLite | web providers).** Routes parse the request and shape the response; they never build JSON-RPC payloads or open the DB inline. All real work lives in `services/`. Keep handlers thin — if a handler grows domain logic, that logic belongs in a service.

- `app.py` — the app factory (`create_app`). Registers blueprints, the `/health` endpoint, and one `after_request` that sets app-wide security headers (`CSP default-src 'self'`, `nosniff`, `SAMEORIGIN`) via `setdefault`, so a route only sets a header itself to **override** the default for one route (as `/files/` does with `CSP: sandbox`).
- `config.py` — all configuration from env vars, read once at import (the image ships the source tree). `DEV=1` enables template auto-reload and disables static caching. `VERSION` is read from the `VERSION` file.
- `logsetup.py` — `configure_logging()` (called once by `create_app`) points the root logger at stdout, so `docker logs` is the single place to look; `LOG_LEVEL` sets the level (`DEBUG` under `DEV=1`, else `INFO`). Modules log through `logging.getLogger(__name__)` with lazy `%s` formatting. The rule of thumb: **INFO for an outcome the operator would ask about** (a lyrics search and each provider's verdict, a track with no lyrics in the library, a throttled request, a stats recompute), **WARNING/ERROR for a degraded dependency** (a provider down, Lyrion unreachable, a DB that won't open), **DEBUG for detail that only matters once you're already looking** (HTTP statuses, cache internals, per-call timings). The ceiling is repetition, not importance: **anything that repeats on the 2s now-playing poll stays DEBUG** (the Lyrion calls, the player enumeration), while a per-track-change line may be INFO. Never log lyrics or cover bodies, only their size and provenance.
- `routes/nowplaying.py` (`nowplaying_bp`) — the dashboard page and its JSON endpoints. `routes/custom.py` (`custom_bp`) — the sandboxed `/files/` server.

### Services

- `services/lyrion.py` — JSON-RPC client for the music server. Every call goes through `lyrion_request` (tolerant of Lyrion's empty non-JSON bodies). `status` queries request only the fields they need via a `tags:` string. Covers are proxied same-origin so the page can sample pixels for the accent tint. `get_active_now_playing` caches a snapshot of all playing or paused players for `NOW_PLAYING_TTL` (2s) behind a lock (a paused one drops out after `PAUSE_TIMEOUT`) and ages the playback position by wall-clock time, so many polling clients cost Lyrion one enumeration per TTL. `verify=False` is used **only** for the self-signed local host (audit S1), never for public CDN URLs. **See the `lyrion-api` skill.**
- `services/database.py` — read-only SQLite access. Opens Lyrion's `library.db` in RO mode and `ATTACH`es `persist.db` (also RO) per request via a context manager. The app never writes to these DBs — they belong to Lyrion. Stats are cached single-flight for `STATS_TTL`. **See the `database` skill.**
- `services/lyrics.py` — web lyrics fallback (LRCLIB, Musixmatch, NetEase, Genius, tried in `LYRICS_PROVIDERS` order; synced-capable providers first). Results live in a process-local in-memory cache (single gunicorn worker + threads means all requests share it); hits are cached longer (`TTL_HIT`) than misses (`TTL_MISS`). Cannot be persisted — `library.db` is read-only.

### i18n (FR/EN)

The UI is fully bilingual. `i18n.py` is the single source of truth for UI strings (`TRANSLATIONS` with `fr`/`en` sub-dicts sharing identical keys); the language is chosen per request from `Accept-Language`. The whole chosen dict is passed to the template as `t` and serialized to JS. **A user-facing string never exists in only one language, and every documentation page ships as an EN/FR pair kept in lockstep — `README.md` / `README.fr.md`, and each `docs/*.md` / `docs/*.fr.md`.** `android/README.md` is the exception: it documents the Gradle build, the CI and the F-Droid packaging, so it stays English like commit messages and PRs, and every link to it from the FR README is flagged "(en anglais)". JSON endpoints are not localized. **See the `i18n` skill.**

### Scripts (`scripts/`)

`generate_screenshots.py` regenerates the images under `docs/screenshots/` — the README header and the demo gallery — with mocked Lyrion/DB layers and headless Chromium. It needs `requirements.txt` plus playwright.

## Code style & comments

**Comments are the exception, not the norm.** The default is no comment: intent belongs in naming and small functions, not in prose. Parts of the codebase are still over-commented from an earlier, chattier culture — that density is a legacy, not a licence: never match it, and when you touch a block, delete the comments in it that the rules below don't justify.

A comment (or docstring) must earn its place. The only things that justify one:

- **A constraint the code cannot show** — a locking/ordering rule, a cache subtlety, an invariant that a refactor could silently break.
- **An external quirk** — Lyrion returning empty non-JSON bodies, a provider blocking default user agents. Things no amount of local reading would reveal.
- **An accepted risk** — security/performance decisions reviewed in the audit ([PR #15](https://github.com/werdeil/lyrion-dashboard/pull/15)) cite their tag ("audit S1", "P8", …) and keep the paired inline `# nosec` justification, so the bandit trail and the audit stay connected. These are mandatory, not optional.
- **A public contract** — per PEP 257, public functions carry a docstring stating the contract: arguments, return shape, side effects (caching, rate limits). One summary line when that's enough (`get_track_lyrics`), a few more when the contract has real subtleties (`fetch_lyrics`). Private and trivial helpers don't get one; `.pylintrc` disables the docstring-required checks so this stays judgment, not ceremony.

Rules for the comments that do survive:

- **Two lines max** for any code comment — Python, CSS and JS alike, block or inline. If the rationale needs a paragraph, it belongs in the commit message or the PR description, not in the code. Contract docstrings may run longer, but stay lean: document the contract, not the implementation.
- **No motivation, no problem-story in the code.** State the surviving constraint in a clause and stop — never the symptom it fixes, the before/after heights, the reflow it prevents, or why the value is what it is. That is the commit message's job. Litmus test: if the comment would read as a sentence in your PR description, it is a commit message in the wrong place — cut it to the constraint or delete it. (This rule is the one most often broken; hold it hard.)
- **Timeless — describe the _state_, not the _change_.** Write "the cache ages by wall-clock time", never "changed this to age by wall-clock time" or "was 5s, now 2s". Why it changed goes in the commit, which the next reader — who has no memory of the old code — can dig up if they care.
- **Never narrate the obvious** — what the next line does, section banners, restating a name. If the code says it, the comment is noise: delete it.
- **Re-read every comment in the diff before committing** — for each one you added, cut it unless it names a constraint, an external quirk, an accepted risk or a public contract. They get written while the reasoning is still warm, which is precisely when a motivation comment feels indispensable; the pass a few minutes later is what catches it. In Claude Code, `.claude/hooks/review-comments.sh` enforces the pass: it refuses a `git commit` once, listing the comment lines it adds, and lets the same commit through when it is run again with those comments unchanged.

**Broad `except Exception` is intentional** around web providers, where any single failure must not break the chain; `.pylintrc` disables `broad-exception-caught` for this reason. Don't narrow those without cause, and don't add new broad catches where a specific one belongs.

## Testing conventions

Tests use `unittest` + `unittest.mock.patch`. Each `tests/test_*.py` is standalone: it sets `LYRION_HOST`, `DB_DIR`, `DB_PERSIST_DIR` via `os.environ.setdefault` **before importing `app`** (config reads env at import), then builds a client with `create_app().test_client()`. Patch the **service functions a route imports**, at the route module path (e.g. `@patch("routes.nowplaying.get_track_lyrics")`) — never hit a real Lyrion server or a real DB. This env scaffolding is duplicated per file on purpose (`# pylint: disable=duplicate-code`). `tests/test_now_playing_route.py` is the reference example. **See the `add-route` skill.**

`tests/__init__.py` pins `LOG_LEVEL=CRITICAL` so the suite's output stays readable; a test that asserts on a log line uses `assertLogs`, which raises the level of the logger it watches (`tests/test_logging.py`).

## Repo-specific skills

Project skills live in `.claude/skills/` (tracked in git, shared with contributors). Consult them when a task matches:

- **`lyrion-api`** — querying Lyrion over JSON-RPC (tags, caching, TLS rules).
- **`database`** — reading Lyrion's read-only SQLite DBs (tables, Alternative Play Count, the stats cache, adding a statistic).
- **`add-route`** — adding a Flask endpoint (route → service → test layering).
- **`i18n`** — adding/translating UI strings and keeping the READMEs in sync.
- **`testing`** — the `unittest`/`mock.patch` conventions (standalone files, env-before-import, where to patch, testing caches/clock).
- **`frontend`** — the vanilla JS/CSS page (accent tint, karaoke sync, polling, i18n wiring, the Android bridge, the ESLint gate).
- **`lyrics`** — the web fallback providers, their match rule, and the cache.
- **`release`** — cutting a version (the `VERSION`/gradle mirrors, the manual Release → publish → `android.yml` chain).
- **`pull-request`** — the PR title form, template and body budget, and re-checking the body against the diff.
- **`android`** — the WebView wrapper (shell-only principle, signing split, static F-Droid versioning, discovery, the JS↔native bridge).

**A skill that describes what a PR changes moves with it, in the same PR.** The trigger is the code, not the user: a refactor nobody can see — an rAF loop becoming a timer — leaves the skill confidently wrong, and unlike a stale README nobody reads it again until the next task has already trusted it.
