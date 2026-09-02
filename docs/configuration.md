[English](configuration.md) | [Français](configuration.fr.md) — back to the [README](../README.md)

# Configuration

All configuration comes from environment variables, read once at start-up. `.env.example` is the template: copy it to `.env`, fill it in, and Docker Compose (or `source .env`) feeds it to the app.

| Variable | Description | Default |
|---|---|---|
| `LYRION_HOST` | Lyrion server URL (e.g. `https://lyrion.local:9000`) | -- |
| `DB_DIR` | Directory containing Lyrion's `library.db` | -- |
| `DB_PERSIST_DIR` | Directory containing Lyrion's `persist.db` | -- |
| `CUSTOM_DATA_DIR` | Generated files directory | `/opt/scripts/custom_data` |
| `LYRICS_PROVIDERS` | Web lyrics providers, tried in order (`lrclib`, `musixmatch`, `genius`) | `lrclib,musixmatch,genius` |
| `MUSIXMATCH_TOKEN` | Fixed Musixmatch token (otherwise fetched automatically) | -- |
| `LRCLIB_TIMEOUT` | LRCLIB request timeout, in seconds | `15` |
| `LYRICS_VERIFY_DURATION_TOLERANCE` | Max drift (seconds) tolerated by `--verify` in `embed_lyrics.py` | `3` |
| `TZ` | Timezone used to align the listening-velocity windows on local midnight (e.g. `Europe/Paris`) | `UTC` |
| `LOG_LEVEL` | Verbosity of the application logs (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`) | `INFO` (`DEBUG` when `DEV=1`) |
| `DEV` | Set to `1` to live-reload templates and disable static caching (development) | -- |

## Local Docker Compose customization

To add services or local options without polluting Git changes, copy the override template:

```bash
cp docker-compose.override.yml.example docker-compose.override.yml
# Edit docker-compose.override.yml to suit your needs
docker compose up -d
```

Docker Compose automatically loads `docker-compose.override.yml` on top of the main file.

## Logs

Everything the app has to say goes to the container's standard output:

```bash
docker logs -f lyrion-dashboard
```

At start-up it reports the version, the resolved `LYRION_HOST`, the provider order and whether `library.db` / `persist.db` were actually found — the first thing to check when the page stays empty.

At `INFO` (the default), a track that ends up without lyrics tells its whole story: the library lookup, then each provider, then the verdict.

```
track 12345: no lyrics in the library
lyrics: lrclib has no match (312 ms)
lyrics: musixmatch unreachable after 5003 ms (Read timed out)
lyrics: genius has no match (486 ms)
lyrics: 'Hocus Pocus' by 'Focus' -> none (synced=False, plain=False) in 5801 ms
```

A healthy search is a single line, `lyrics: 'Space Debris' by 'Deep Purple' -> lrclib (synced=True, plain=True) in 412 ms`. `source` tells the outcomes apart: a provider name (found), `none` (searched, nothing matched), `rejected` (a candidate came back but was another recording), `unavailable` (no provider answered — the search is not cached and will be retried). Also at `INFO`: a result served from the cache instead of a new search, a search refused by the rate limit or the refresh cooldown, and a stats recompute with its duration.

Set `LOG_LEVEL=DEBUG` and restart the container to also get each provider's HTTP detail, the lookups that succeeded, the player enumeration and every Lyrion JSON-RPC call with its duration. It is verbose — the now-playing poll runs every 2s — so use it while reproducing a problem, then set it back.
