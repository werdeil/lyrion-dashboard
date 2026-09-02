[English](endpoints.md) | [Français](endpoints.fr.md) — back to the [README](../README.md)

# Endpoints

| Method | Route | Description |
|---|---|---|
| GET | `/` | Main dashboard (now playing + stats) |
| GET | `/health` | Health check |
| GET | `/stats.json` | Library statistics (JSON) |
| GET | `/now-playing.json` | Live state of the currently playing track, auto-detected (JSON) |
| GET | `/cover/{coverid}.jpg` | Proxies an album cover from Lyrion, same-origin |
| GET | `/cover/remote.jpg` | Proxies the artwork of the currently playing remote/streaming track |
| GET | `/mosaic-covers.json` | Album cover ids for the empty-state mosaic, recently played first (JSON) |
| GET | `/recent-covers.json` | Recently played album cover ids, newest first (JSON) |
| GET | `/lyrics.json` | Fetches lyrics from the web for a track, on demand |
| GET | `/files/{path}` | Serves a file from the custom data directory |

The JSON endpoints are not localized: they return raw values, which the page formats.

## Homepage widget

`/stats.json` returns plain JSON, so it plugs directly into a [Homepage](https://gethomepage.dev) [`customapi`](https://gethomepage.dev/widgets/services/customapi/) widget to surface library stats on your dashboard:

```yaml
- Lyrion Dashboard:
    href: http://lyrion-dashboard:1111
    widget:
      type: customapi
      url: http://lyrion-dashboard:1111/stats.json
      mappings:
        - field: albums_total
          label: Albums
        - field: songs_total
          label: Tracks
        - field: velocity_30d
          label: Played (30 d)
```

Any key from the JSON works as a `field` — check `/stats.json` in a browser to pick the ones you want.
