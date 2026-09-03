[English](configuration.md) | [Français](configuration.fr.md) — back to the [README](../README.md)

# Configuration

All configuration comes from environment variables, read once at start-up. `.env.example` is the template: copy it to `.env`, fill it in, and Docker Compose (or `source .env`) feeds it to the app.

| Variable | Description | Default |
|---|---|---|
| `LYRION_HOST` | Lyrion server URL (e.g. `https://lyrion.local:9000`) | -- |
| `LYRION_DATA_DIR` | Lyrion's data directory, the one holding its `prefs/` and `cache/` | -- |
| `PLAY_COUNTS_SOURCE` | Where play counts come from: `auto` (Alternative Play Count when installed, Lyrion's own counters otherwise) or `lyrion` (always Lyrion's counters) | `auto` |
| `CUSTOM_DATA_DIR` | Generated files directory | `/opt/scripts/custom_data` |
| `LYRICS_PROVIDERS` | Web lyrics providers, tried in order (`lrclib`, `musixmatch`, `genius`) | `lrclib,musixmatch,genius` |
| `MUSIXMATCH_TOKEN` | Fixed Musixmatch token (otherwise fetched automatically) | -- |
| `LRCLIB_TIMEOUT` | LRCLIB request timeout, in seconds | `15` |
| `LYRICS_VERIFY_DURATION_TOLERANCE` | Max drift (seconds) tolerated by `--verify` in `embed_lyrics.py` | `3` |
| `TZ` | Timezone used to align the listening-velocity windows on local midnight (e.g. `Europe/Paris`) | `UTC` |
| `LOG_LEVEL` | Verbosity of the application logs (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`) | `INFO` (`DEBUG` when `DEV=1`) |
| `DEV` | Set to `1` to live-reload templates and disable static caching (development) | -- |

What each `LOG_LEVEL` actually prints is on the [Logs](logs.md) page.

## Where the databases live

The dashboard reads two SQLite files Lyrion keeps side by side under one data directory: `cache/library.db` (the music library) and `prefs/persist.db` (ratings and play history). That directory is `/config` for the Docker image and `/var/lib/squeezeboxserver` for the Debian package — point `LYRION_DATA_DIR` at it and both files are found, and Compose mounts it read-only in one line.

Lyrion lets its cache be relocated (to an SSD, a larger volume). Under Docker, mount it back into place in `docker-compose.yml` and nothing else changes:

```yaml
- /mnt/ssd/cache:${LYRION_DATA_DIR}/cache:ro
```

Running without Docker there is no mount to do that, so name the real path in `DB_DIR` instead — or in `DB_PERSIST_DIR` for a relocated prefs directory. Each replaces only the path it names, and neither is needed by a standard install.

Upgrading from a `.env` that only set `DB_DIR` and `DB_PERSIST_DIR`: Compose now mounts `LYRION_DATA_DIR` and refuses to start without it, so add it — usually the parent of the two directories you already had.

Image tags, updating and building from source are on the [Docker](docker.md) page.
