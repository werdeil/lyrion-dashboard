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

What each `LOG_LEVEL` actually prints is on the [Logs](logs.md) page.

## Local Docker Compose customization

To add services or local options without polluting Git changes, copy the override template:

```bash
cp docker-compose.override.yml.example docker-compose.override.yml
# Edit docker-compose.override.yml to suit your needs
docker compose up -d
```

Docker Compose automatically loads `docker-compose.override.yml` on top of the main file.
