<p align="center"><a href="README.md">English</a> | <a href="README.fr.md">Français</a></p>

<p align="center"><img src="static/favicon.svg" alt="" width="56"></p>

<h1 align="center">Lyrion Dashboard</h1>

<p align="center">A Flask web app for <a href="https://github.com/LMS-Community/slimserver">Lyrion Music Server</a> (formerly Logitech Media Server / Squeezebox Server): a glanceable "now playing" page with synced lyrics, recent plays and library statistics, in a browser or through its companion <a href="https://f-droid.org/packages/com.werdeil.lyriondashboard/">Android app</a>.</p>

<p align="center">
  <img src="docs/screenshots/dashboard-en.png" alt="Dashboard" width="600">
  <img src="docs/screenshots/dashboard-app.png" alt="Android app" width="179">
</p>

## Features

- **Now Playing** -- The player currently playing is detected automatically and its track shown live (cover art, title, artist, album), with the accent color sampled from the cover. Clicking the cover grows it over the panel.
- **Recent plays** -- On wide screens the recently played albums stack up as a pile of sleeves under the cover, newest on top. Built from the play history, one cover per album; with the Alternative Play Count plugin installed, skips are excluded.
- **Synced lyrics** -- Lyrics with LRC timestamps scroll line by line in time with playback, karaoke-style.
- **Web lyrics fallback** -- An auto-search switch queries LRCLIB, Musixmatch and Genius for every playing track: it fills in what the library is missing and upgrades plain text to a synced version when one exists.
- **Library statistics** -- Albums, artists, played/unplayed tracks, genres, ratings, lyrics, 30-day listening velocity.
- **File server** -- Serves files from a configurable directory.
- **Android app** -- A thin WebView wrapper (same principle as [lms-material-app](https://github.com/CDrummond/lms-material-app)) with LMS auto-discovery, published on [F-Droid](https://f-droid.org/packages/com.werdeil.lyriondashboard/), see [`android/`](android/README.md).

## Demo

<p>
  <a href="docs/screenshots/demo-cover-zoom.png"><img src="docs/screenshots/demo-cover-zoom.png" alt="Enlarged cover" title="Click the cover: it fills the panel, playback progress on its bottom edge" width="210"></a>
  <a href="docs/screenshots/demo-empty.png"><img src="docs/screenshots/demo-empty.png" alt="Empty state" title="Nothing playing: a slow mosaic of the albums played recently" width="210"></a>
  <a href="docs/screenshots/demo-lyrics.png"><img src="docs/screenshots/demo-lyrics.png" alt="Synced lyrics" title="Karaoke lyrics: the current line is highlighted, the source tinted when synced" width="135"></a>
  <a href="docs/screenshots/dashboard-mobile.png"><img src="docs/screenshots/dashboard-mobile.png" alt="Mobile view" title="The responsive mobile layout" width="85"></a>
  <a href="docs/screenshots/demo-recent.png"><img src="docs/screenshots/demo-recent.png" alt="Recent plays" title="The pile of recently played sleeves" width="85"></a>
  <a href="docs/screenshots/demo-stats.png"><img src="docs/screenshots/demo-stats.png" alt="Library statistics" title="The library statistics panel" width="85"></a>
</p>

Left to right, click any of them for the full-size image: the enlarged cover, the empty state's mosaic of recently played albums, the karaoke lyrics, the mobile layout, the pile of recent sleeves and the statistics panel.

## Requirements

- An accessible Lyrion Music Server
- Docker and Docker Compose
- Recommended: the [Alternative Play Count](https://github.com/AF-1/lms-alternativeplaycount) plugin on Lyrion. Without it the dashboard reads Lyrion's own play counters instead: the skip count disappears from the statistics, and since Lyrion bumps a track's last-played time on a skip too, an album that was only skipped past can surface in the recent plays.

## Installation

### With Docker (recommended)

Fetch [`docker-compose.yml`](docker-compose.yml), set your Lyrion URL and the path to its data directory in it, then start it:

```bash
curl -O https://raw.githubusercontent.com/werdeil/lyrion-dashboard/master/docker-compose.yml
$EDITOR docker-compose.yml
docker compose up -d
```

This pulls `ghcr.io/werdeil/lyrion-dashboard:latest`, built for amd64 and arm64 on every release. The app is then available at `http://localhost:1111`. Pinning a version and updating are on the [Docker](docs/docker.md) page.

Running from the sources instead — to develop, or on a host where Docker is not wanted — is on the [Development](docs/development.md) page.

### Android app

The companion app is published on F-Droid:

[<img src="https://fdroid.gitlab.io/artwork/badge/get-it-on.png" alt="Get it on F-Droid" height="70">](https://f-droid.org/packages/com.werdeil.lyriondashboard/)

A signed APK is also attached to each [GitHub release](https://github.com/werdeil/lyrion-dashboard/releases). On first launch, let it discover the Lyrion server on the local network or enter the dashboard URL yourself — see [`android/`](android/README.md).

## Documentation

- [Configuration](docs/configuration.md) — environment variables.
- [Docker](docs/docker.md) — image tags, updating, filesystem permissions.
- [Development](docs/development.md) — running from the sources, the `dev` image, building the image locally.
- [Logs](docs/logs.md) — what the app prints at each level, and how to read a lyrics search that found nothing.
- [Endpoints](docs/endpoints.md) — the HTTP routes, and the Homepage widget fed by `/stats.json`.
- [Scripts](docs/scripts.md) — embedding lyrics and cover art into audio file tags, their cron wrappers, and regenerating these screenshots.
- [Android app](android/README.md) — the WebView wrapper: install, build, discovery.

## Security

The dashboard has **no authentication, by design**: it is a glanceable, always-on display meant for a **trusted home LAN**. Anyone who can reach the port can see what is playing in real time (presence information), read the library statistics and download everything under `CUSTOM_DATA_DIR` (`/files/`).

- Never expose the port directly to the Internet (no port forwarding, no public reverse proxy).
- For remote access, join the LAN instead of opening the dashboard up: a VPN such as WireGuard or Tailscale keeps it LAN-only while your devices connect from anywhere.

## Sponsor

If this dashboard is useful to you, you can support its development through [GitHub Sponsors](https://github.com/sponsors/werdeil). It is entirely optional: the project stays free and MIT-licensed either way.

## License

This project is distributed under the MIT license — see the [LICENSE](LICENSE) file.
