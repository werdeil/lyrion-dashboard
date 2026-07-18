---
name: lyrics
description: >-
  Work on lyrics — the web fallback (LRCLIB, Musixmatch, Genius), the in-memory
  cache, verification, and embedding lyrics into audio file tags. Use this
  whenever a task touches `services/lyrics.py`, `services/tags.py`, the
  `/lyrics.json` route, or `scripts/embed_lyrics.py` / `embed_lyrics_cron.sh` —
  adding or fixing a provider, changing caching/verification, or the batch
  tagger. Covers the provider contract, the synced-vs-plain rule, the read-only
  cache, and why writes only ever store plain text.
---

# Lyrics: web fallback + tag embedding

Two cooperating pieces:

- `services/lyrics.py` — fetch lyrics from the web (used by the `/lyrics.json`
  route and the CLI). **Read-only** with respect to Lyrion.
- `services/tags.py` — write lyrics into an audio file's tags via mutagen
  (used by `scripts/embed_lyrics.py`). Framework-free, no Flask/Lyrion import.

Lyrion's `library.db` is **read-only**, so web lyrics can never be stored back
there — they live in a process-local cache (web app) or get written straight
into the files' tags (CLI), which Lyrion then re-scans.

## Provider contract

Each provider is a function `(artist, title, album, duration) -> result | None`.
A hit is a dict:

```python
{"lyrics": str | None,   # plain text
 "synced": str | None,   # LRC with timestamps, when the provider offers it
 "meta":   {"artist", "title", "album", "duration"} | None}  # for verification
```

Providers live in `services/lyrics.py`: `_provider_lrclib`, `_provider_musixmatch`,
`_provider_genius`, registered in the `PROVIDERS` map. Order comes from the
`LYRICS_PROVIDERS` env var (`_enabled_providers`); **synced-capable providers
first** (LRCLIB, Musixmatch) because display always prefers synced (karaoke)
over plain — Genius is plain-only, so it comes last. Unknown names in the env
list are silently ignored, so an operator can disable a flaky provider by
dropping it.

**Adding a provider:** write `_provider_<name>(artist, title, album, duration)`
returning the dict above (set the `meta` fields you can, leave the rest `None`),
add it to `PROVIDERS`, and — since a provider must never break the chain —
catch its own network/parse exceptions and return `None` on failure. `fetch_lyrics`
already wraps each call in a `try/except`, but keep provider-internal failures
from raising too. Use a browser-like UA where a service blocks default agents
(see `BROWSER_UA`).

## fetch_lyrics: the orchestrator

`fetch_lyrics(track_id, artist, title, album, duration, force, verify)`:

- Tries each enabled provider in order, keeps the **first** non-empty result.
- Returns `{"lyrics", "synced", "source"}`. `source` is the winning provider
  name (preserved across cache hits so the UI can show the origin), `"none"`
  when nothing was found, or `"rejected"` when a candidate came back but failed
  verification.
- **Caching:** an `OrderedDict` LRU behind a lock, bounded to
  `CACHE_MAX_ENTRIES`, with hits kept `TTL_HIT` (24h) and misses `TTL_MISS`
  (1h) — a track with no lyrics online isn't re-queried on every click, but a
  transient failure recovers sooner. The cache key is
  `track_id|artist|title|verify`, **not** track_id alone: streamed "flow"/mix
  sources reuse one playlist track_id while the song changes underneath, which
  would otherwise serve the first song's lyrics for all of them.

## Verification (`verify=True`)

The batch CLI writes lyrics **permanently** into tags, so it opts into
verification: `_matches_request` requires the candidate's normalized title and
artist to equal the request's, and — when both durations are known — to fall
within `VERIFY_DURATION_TOLERANCE` seconds (the surest way to tell the real
recording from a live/remix/cover). `_normalize` folds accents, case,
parenthetical qualifiers, and "feat." credits before comparing. The web route
does **not** verify (lenient recall); the CLI does (precision — a wrong tag is
worse than none).

## Writing tags (`services/tags.py`)

- Handles mp3/aiff/wav (`USLT`), mp4/m4a (`\xa9lyr`), flac/ogg/opus (`LYRICS`).
- **Only plain text is ever stored** — `lrc_to_plain` strips LRC line/word
  timestamps and metadata lines first, for maximum player compatibility. Even
  when a synced result is fetched, the embedded tag is plain.
- `read_metadata`, `has_lyrics`, `write_lyrics`, `clear_lyrics`; failures raise
  `LyricsTagError`.

## The batch CLI (`scripts/embed_lyrics.py`)

Runs outside the web app with `requirements-cli.txt` (no Flask/Lyrion). Walks
files/dirs, fetches with `verify=True`, writes tags; Lyrion picks changes up on
its next scan. Auto-loads the repo-root `.env` (via python-dotenv, **before**
importing `services.lyrics` since its timeout is read at import). Flags:
`--force`, `--clear`, `--no-verify`, `--dry-run`, `--delay`, `--verbose`.
`embed_lyrics_cron.sh` wraps it to only re-tag files whose `ctime` changed
(marker + `find -cnewer`), advancing the marker only on success.

## Checklist

1. New provider → `(artist, title, album, duration)` → result dict; register in
   `PROVIDERS`; swallow its own errors; put synced-capable ones before plain-only.
2. Preserve the cache-key shape and TTL split; don't key on track_id alone.
3. Tag writes store plain text only (run through `lrc_to_plain`).
4. Keep `services/tags.py` free of Flask/Lyrion imports (the CLI reuses it).
5. Add/extend tests: `test_lyrics_cache.py`, `test_lyrics_verify.py`,
   `test_lyrics_route.py`, `test_get_track_lyrics.py`. See the `testing` skill.
