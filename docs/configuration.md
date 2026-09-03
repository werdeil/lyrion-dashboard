[English](configuration.md) | [Français](configuration.fr.md) — back to the [README](../README.md)

# Configuration

All configuration comes from environment variables, read once at start-up. `.env.example` is the template: copy it to `.env`, fill it in, and Docker Compose (or `source .env`) feeds it to the app.

| Variable | Description | Default |
|---|---|---|
| `LYRION_HOST` | Lyrion server URL (e.g. `https://lyrion.local:9000`) | -- |
| `LYRION_DATA_DIR` | Lyrion's data directory, the one holding its `prefs/` and `cache/` | -- |
| `DB_DIR` | Directory containing Lyrion's `library.db`, when its cache sits outside `LYRION_DATA_DIR` | `LYRION_DATA_DIR/cache` |
| `DB_PERSIST_DIR` | Directory containing Lyrion's `persist.db`, when its prefs sit outside `LYRION_DATA_DIR` | `LYRION_DATA_DIR/prefs` |
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

Lyrion lets its cache be relocated (to an SSD, a larger volume). If yours was moved, set `DB_DIR` — or `DB_PERSIST_DIR` for a relocated prefs directory — to the real path; each overrides only its own derived path. The container needs to reach it too, so add a read-only mount for it in `docker-compose.override.yml`.

Upgrading from a `.env` that only set `DB_DIR` and `DB_PERSIST_DIR`: Compose now mounts `LYRION_DATA_DIR` and refuses to start without it, so add it — usually the parent of the two directories you already had.

## Local Docker Compose customization

To add services or local options without polluting Git changes, copy the override template:

```bash
cp docker-compose.override.yml.example docker-compose.override.yml
# Edit docker-compose.override.yml to suit your needs
docker compose up -d
```

Docker Compose automatically loads `docker-compose.override.yml` on top of the main file.
