---
name: database
description: >-
  Read data from Lyrion's SQLite databases — library stats, stored lyrics,
  album covers, recent plays. Use this whenever a task queries `library.db` or
  `persist.db`, adds or changes a statistic, or touches `services/database.py`.
  Covers the read-only connection model (RO open + `ATTACH persist.db`), the
  key tables and the Alternative Play Count plugin, the single-flight stats
  cache, and why the app must never write to these DBs. Reach for it before
  writing any SQL against the Lyrion databases.
---

# Reading Lyrion's SQLite databases

All DB access lives in `services/database.py`. These databases belong to
**Lyrion**, not to this app — the app opens them **read-only** and never
writes. (Web lyrics can't be persisted here for exactly this reason; they go to
a cache or into file tags — see the `lyrics` skill.)

## The connection model

Use the `get_db_conn()` context manager for every query — don't open sqlite
inline in a route or elsewhere:

```python
with get_db_conn() as conn:
    row = conn.execute("SELECT lyrics FROM tracks WHERE id = ?", (track_id,)).fetchone()
```

It opens `library.db` in read-only URI mode (`file:...?mode=ro`), **`ATTACH`es**
`persist.db` (also RO) as the `persist` schema, sets `row_factory = sqlite3.Row`
(access columns by name), applies read-tuning pragmas (mmap/cache/temp), and
wraps the work in `BEGIN DEFERRED` … `COMMIT`. Two databases, one connection:

- **`library.db`** (default schema) — the music library: `tracks`, `albums`,
  `contributor_track`, `genres`, and the Alternative Play Count table
  `alternativeplaycount`.
- **`persist.db`** (referenced as `persist.<table>`) — persistent per-track
  state: `persist.tracks_persistent` (ratings, `lastplayed`, …).

The DB paths come from config (`DB_PATH`, `DB_PERSIST_PATH`), derived from
`DB_DIR`/`DB_PERSIST_DIR` env vars.

## Key tables and columns

- `tracks` — one row per track. `id` (the Lyrion track id used everywhere,
  e.g. lyrics lookup), `url`, `urlmd5` (join key to `alternativeplaycount`),
  `album` (→ `albums.id`), `audio` (filter `audio = 1` for real tracks),
  `lyrics`, `year`, `coverid`.
- `albums` — `id`, `artwork` (the **coverid** of the album's artwork track, the
  same id `/cover/<coverid>.jpg` serves).
- `contributor_track` — track↔artist links with a `role`: **role 5 = ALBUMARTIST**,
  **role 1 = ARTIST** (track artist). "Album artists" filter `role = 5`; "track
  artists" filter `role IN (1, 5)`.
- `persist.tracks_persistent` — `rating`, `lastplayed` (unix seconds; **bumped
  on skips too**, so don't use it to mean "really played").

## Alternative Play Count (the plugin that matters)

Real listening data comes from the `alternativeplaycount` table (the
[Alternative Play Count](https://github.com/AF-1/lms-alternativeplaycount)
plugin, a project requirement), joined on `tracks.urlmd5 = apc.urlmd5`. It keeps
**plays separate from skips**, which `tracks_persistent.lastplayed` does not:

- `playcount` / `lastplayed` — genuine plays. "Played" means `playcount > 0`.
- `skipcount` / `lastskipped` — skips.

That's why `get_recent_album_covers` orders by `MAX(apc.lastplayed)` filtered on
`playcount > 0` — using `tracks_persistent.lastplayed` would surface albums that
were only skipped past. Prefer `alternativeplaycount` for anything about what
was actually played.

## The stats cache (single-flight)

`get_stats()` returns library statistics cached for `STATS_TTL` (60s) behind
`_stats_lock`. The lock makes the recompute **single-flight**: when the cache
expires, simultaneous clients wait for one computation instead of each firing
their own set of full-library aggregations. It returns a **copy** so callers
can't mutate the cached dict. Keep both properties if you touch it — the stats
are four full-library scans and the page polls them from every open client.

`_compute_stats()` runs **four queries** (albums+songs, album artists, track
artists, misc) using CTEs to scan `tracks JOIN alternativeplaycount` once each,
then derives percentages via the local `pct()` helper. Every count coalesces to
0 (`row[...] or 0`) so an empty library yields zeros, not `None`.

## Adding or changing a statistic

1. Add the aggregation to the right query in `_compute_stats` (reuse the
   `track_play` CTE pattern; scan once, don't add a query per number).
2. Add the key to the `stats` dict (coalesce to `0`); add a `_pct` via `pct()`
   if it's a proportion.
3. Surface it: the `/stats.json` route returns the whole dict, and the template
   renders named fields — a new stat shown on the page needs an `i18n.py` label
   (both `fr` and `en`) and a README **Configuration/stats** mention if it's
   part of the documented surface (see the `i18n` and `add-route` skills).
4. Test it: build a small temp SQLite DB with the tables/rows you need and
   assert the computed number (see `tests/test_get_recent_album_covers.py`,
   `tests/test_stats_cache.py`, `tests/test_get_track_lyrics.py`). Don't hit a
   real Lyrion DB. See the `testing` skill.

## Rules

- **Read-only, always.** No `INSERT`/`UPDATE`/`DELETE`/`CREATE`; the app must
  never write to Lyrion's databases.
- Always go through `get_db_conn()`; parameterize queries (`?` placeholders),
  never string-format user input into SQL.
- Filter real tracks with `audio = 1`; join play data via `urlmd5`.
- Reach for `alternativeplaycount` (not `tracks_persistent.lastplayed`) when you
  mean "actually played".
