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

- `services/lyrics.py` — fetch lyrics from the web (used by the `/lyrics.json` route and the CLI). **Read-only** with respect to Lyrion.
- `services/tags.py` — write lyrics into an audio file's tags via mutagen (used by `scripts/embed_lyrics.py`). Framework-free, no Flask/Lyrion import.

Lyrion's `library.db` is **read-only**, so web lyrics can never be stored back there — they live in a process-local cache (web app) or get written straight into the files' tags (CLI), which Lyrion then re-scans.

## Provider contract

Each provider is a function `(artist, title, album, duration) -> result | None`. A hit is a dict:

```python
{"lyrics": str | None,   # plain text
 "synced": str | None,   # LRC with timestamps, when the provider offers it
 "meta":   {"artist", "title", "album", "duration"} | None}  # for verification
```

Providers live in `services/lyrics.py`: `_provider_lrclib`, `_provider_musixmatch`, `_provider_genius`, registered in the `PROVIDERS` map. Order comes from the `LYRICS_PROVIDERS` env var (`_enabled_providers`); **synced-capable providers first** (LRCLIB, Musixmatch) because display always prefers synced (karaoke) over plain — Genius is plain-only, so it comes last. Unknown names in the env list are silently ignored, so an operator can disable a flaky provider by dropping it.

**A provider that can return either form must prefer the synced one, inside itself.** LRCLIB stores lyrics per upload: the record `/get` matches on the exact artist/title/album/duration signature may be plain-only while another upload of the same track carries an LRC, so `_provider_lrclib` keeps a plain-only hit as a fallback and still runs `/search`, scanning the candidates for one with `syncedLyrics` instead of taking `results[0]`. The chain above it can't fix this: `_search_providers` returns the first provider with *anything*, so a plain-only answer ends the search (`tests/test_lyrics_lrclib.py`).

**A name the two sides spell differently finds nothing.** LRCLIB matches names as it stores them, so `_lrclib_attempts` builds the `/search` queries in two passes: each name album-filtered first for precision then without it, then the whole set again with the leading articles dropped — the one word a library and a catalogue routinely disagree on (`Les Fatals Picards` tagged as `Fatals Picards`).

**But a synced record only counts if it is the same recording.** An LRC's timestamps belong to the upload they were made for, so a live or extended version scrolls against the wrong timeline — the karaoke sits idle, then jumps. `_duration_close` (the same tolerance `_matches_request` verifies with) filters the `/search` candidates before the synced preference applies, and a record of another length still serves its `plainLyrics`: right words with no karaoke beat a karaoke that's wrong.

**A fuzzy matcher's own answer has to be checked inside the provider.** Musixmatch's `matcher.track.get` always returns its nearest hit, so a track absent from its catalogue comes back as a different song — often in another language, since that is what "nearest" reaches for once the title stops matching. `_provider_musixmatch` runs the matched track through `_matches_request` and returns `None` when it doesn't line up, whatever the caller's `verify` setting: unlike LRCLIB's signature `/get`, there is no upstream "no match" to fall back on. It also picks the subtitle by language (`_mxm_subtitle`) rather than taking `subtitle_list[0]`, since a translation among the subtitles would swap out the words; when only translations are on offer the plain lyrics stand alone.

**Adding a provider:** write `_provider_<name>(artist, title, album, duration)` returning the dict above (set the `meta` fields you can, leave the rest `None`), add it to `PROVIDERS`, and — since a provider must never break the chain — catch its own network/parse exceptions and return `None` on failure. `fetch_lyrics` already wraps each call in a `try/except`, but keep provider-internal failures from raising too. Use a browser-like UA where a service blocks default agents (see `BROWSER_UA`).

## fetch_lyrics: the orchestrator

`fetch_lyrics(track_id, artist, title, album, duration, force, verify)`:

- Tries each enabled provider in order, keeps the **first** non-empty result.
- Returns `{"lyrics", "synced", "source"}`. `source` is the winning provider name (preserved across cache hits so the UI can show the origin), `"none"` when nothing was found, or `"rejected"` when a candidate came back but failed verification.
- **Caching:** an `OrderedDict` LRU behind a lock, bounded to `CACHE_MAX_ENTRIES`, with hits kept `TTL_HIT` (24h) and misses `TTL_MISS` (1h) — a track with no lyrics online isn't re-queried on every click, but a transient failure recovers sooner. The cache key is `track_id|artist|title|verify`, **not** track_id alone: streamed "flow"/mix sources reuse one playlist track_id while the song changes underneath, which would otherwise serve the first song's lyrics for all of them.

## Diagnosing a track without lyrics

The chain logs its own reasoning (see `logsetup.py`), so `docker logs` answers "why no lyrics" without a debugger:

- `INFO` — the whole story of one track: the library miss from `get_track_lyrics` (which separates "the library has no lyrics" from "the web fallback found nothing"), each provider's verdict (`has no match`, unreachable, rejected-with-the-candidate), the closing `lyrics: <title> by <artist> -> <source> (synced=…, plain=…) in N ms`, a cache hit served instead of a search, and throttling. A provider whose own shortlist explains the verdict says so here too: each LRCLIB `/search` attempt reports the artist name and album filter it used, how many candidates came back, how many carry an LRC and how many are of this track's length — which separates "nothing on LRCLIB" from "a synced upload exists but for another recording". Two LRCLIB lines carry a browsable URL so the catalogue can be checked by hand: a lookup that found no record at all logs the site's search page for the same artist and title (`_lrclib_search_url`), and a synced record dropped for its length logs `lrclib.net/tracks/<id>` with both durations. That search does not filter on duration the way `_duration_close` does, so it lists records the app refuses — the gap is the diagnosis.
- `DEBUG` — the HTTP detail behind those verdicts, the lookups that succeeded, the search inputs (album, duration, verify), and the LRCLIB record finally chosen, which opens at `lrclib.net/tracks/<id>`.

A new provider raises `ProviderUnavailable` for unreachability — `_search_providers` logs the warning with the cause, so don't log it twice — and keeps its own dead ends at DEBUG, except a non-200 that is not part of a normal fallback (LRCLIB's `/get` 404s routinely before `/search`, so that one stays DEBUG).

## Verification (`verify=True`)

The batch CLI writes lyrics **permanently** into tags, so it opts into verification: `_matches_request` requires the candidate's normalized title and artist to equal the request's, and — when both durations are known — to fall within `VERIFY_DURATION_TOLERANCE` seconds (the surest way to tell the real recording from a live/remix/cover). `_fold_name` does the comparing: `_normalize` (accents, case, parenthetical qualifiers, "feat." credits), then the leading article dropped and plural words trimmed, so a library tagged "Fatal Picards" still matches the catalogue's "Les Fatals Picards". It folds both sides, so distinct acts stay apart, and the duration is what tells two recordings of one song apart. The web route does **not** verify (lenient recall); the CLI does (precision — a wrong tag is worse than none). The flag governs the chain in `_search_providers`; `_provider_musixmatch` applies the same rule to itself unconditionally (see above), so the lenient path still never shows another song's lyrics.

## Writing tags (`services/tags.py`)

- Handles mp3/aiff/wav (`USLT`), mp4/m4a (`\xa9lyr`), flac/ogg/opus (`LYRICS`).
- **Only plain text is ever stored** — `lrc_to_plain` strips LRC line/word timestamps and metadata lines first, for maximum player compatibility. Even when a synced result is fetched, the embedded tag is plain.
- `read_metadata`, `has_lyrics`, `write_lyrics`, `clear_lyrics`; failures raise `LyricsTagError`.

## The batch CLI (`scripts/embed_lyrics.py`)

Runs outside the web app with `requirements-cli.txt` (no Flask/Lyrion). Walks files/dirs, fetches with `verify=True`, writes tags; Lyrion picks changes up on its next scan. Auto-loads the repo-root `.env` (via python-dotenv, **before** importing `services.lyrics` since its timeout is read at import). Flags: `--force`, `--clear`, `--no-verify`, `--dry-run`, `--delay`, `--verbose`. `embed_lyrics_cron.sh` wraps it to only re-tag files whose `ctime` changed (marker + `find -cnewer`), advancing the marker only on success.

## Checklist

1. New provider → `(artist, title, album, duration)` → result dict; register in `PROVIDERS`; swallow its own errors; put synced-capable ones before plain-only.
2. Preserve the cache-key shape and TTL split; don't key on track_id alone.
3. Tag writes store plain text only (run through `lrc_to_plain`).
4. Keep `services/tags.py` free of Flask/Lyrion imports (the CLI reuses it).
5. Add/extend tests: `test_lyrics_cache.py`, `test_lyrics_verify.py`, `test_lyrics_musixmatch.py`, `test_lyrics_route.py`, `test_get_track_lyrics.py`. See the `testing` skill.
