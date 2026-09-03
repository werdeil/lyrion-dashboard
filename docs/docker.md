[English](docker.md) | [Français](docker.fr.md) — back to the [README](../README.md)

# Docker

The dashboard ships as a container image on the GitHub Container Registry: `ghcr.io/werdeil/lyrion-dashboard`. Installing it needs no clone of this repository — a `docker-compose.yml`, a filled-in `.env`, and `docker compose up -d`.

That compose file is yours once downloaded: change the port, the volumes, the restart policy, drop the service into a larger stack. Nothing has to stay in sync with this repository.

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

`docker-compose.yml` carries a commented `build: .`. Uncomment it in a checkout of this repository and Compose builds the image locally instead of pulling it:

```bash
docker compose up -d --build
```

For development, running the app directly with `DEV=1` reloads templates and static files on a page refresh — a built image cannot, since it ships its own copy of the sources.

## Filesystem permissions

The container runs as uid 1000, not root. If Lyrion's `library.db` and `persist.db` are not world-readable, the dashboard starts but logs that it cannot open them; run it as the user owning those files instead:

```yaml
services:
  lyrion-dashboard:
    user: "0:0"
```
