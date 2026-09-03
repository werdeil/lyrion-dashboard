[English](docker.md) | [Français](docker.fr.md) — back to the [README](../README.md)

# Docker

The dashboard ships as a container image on the GitHub Container Registry: `ghcr.io/werdeil/lyrion-dashboard`. Installing it needs no clone of this repository — a `docker-compose.yml`, a filled-in `.env`, and `docker compose up -d`.

## Image tags

| Tag | Points to | Rebuilt |
|---|---|---|
| `latest` | the most recent release | on every release, plus weekly for base image fixes |
| `X.Y` | the latest patch of that minor (e.g. `0.2`) | on every release in that series |
| `X.Y.Z` | that exact release (e.g. `0.2.6`) | never — the digest is immutable |

Images are built for `linux/amd64` and `linux/arm64`, so a Raspberry Pi or an ARM NAS pulls the same tag as a PC. Pin `X.Y.Z` if you want a deployment that only ever changes when you say so; `latest` also picks up the weekly rebuild that carries Debian security fixes into the image.

## Updating

```bash
docker compose pull
docker compose up -d
```

## Building from source

Copy the override template and let Compose build this checkout instead of pulling:

```bash
cp docker-compose.override.yml.example docker-compose.override.yml
docker compose up -d --build
```

The template also mounts the sources read-only and sets `DEV=1`, so template and CSS edits show up on a page refresh — that is the development setup. Drop those lines if you only want a locally built image.

## Local Compose customization

`docker-compose.override.yml` is where local changes belong — an auxiliary service, an extra volume, a different port — so that `git pull` never conflicts with them. Compose loads it automatically on top of `docker-compose.yml`, and `.gitignore` keeps it out of the repository.

## Filesystem permissions

The container runs as uid 1000, not root. If Lyrion's `library.db` and `persist.db` are not world-readable, the dashboard starts but logs that it cannot open them; run it as the user owning those files instead:

```yaml
services:
  lyrion-dashboard:
    user: "0:0"
```
