[English](docker.md) | [Français](docker.fr.md) — back to the [README](../README.md)

# Docker

The dashboard ships as a container image on the GitHub Container Registry: `ghcr.io/werdeil/lyrion-dashboard`. Installing it needs no clone of this repository — one `docker-compose.yml` carrying your Lyrion URL and data directory, and `docker compose up -d`.

That compose file is yours once downloaded: change the port, the volumes, the restart policy, drop the service into a larger stack. Nothing has to stay in sync with this repository.

## Image tags

| Tag | Points to | Rebuilt |
|---|---|---|
| `latest` | the most recent release | on every release |
| `X.Y` | the latest patch of that minor (e.g. `0.2`) | on every release in that series |
| `X.Y.Z` | that exact release (e.g. `0.2.6`) | never — the digest is immutable |
| `dev` | the `master` branch | on every merge — unreleased code, in no release yet |

Images are built for `linux/amd64` and `linux/arm64`, so a Raspberry Pi or an ARM NAS pulls the same tag as a PC. Pin `X.Y.Z` for a deployment that only ever changes when you say so; `latest` follows the releases. No released tag is ever rebuilt, so a security fix in the Debian base image reaches you with the next release rather than under the tag you already run.

`dev` is there to try a fix before it ships or to reproduce a bug against the current code. It is unstable by definition — do not point a dashboard you rely on at it.

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

The container runs as uid 1000, not root. If Lyrion's files under the directory you mount on `/lyrion` are not readable by it, the dashboard starts but logs that it cannot open the databases; run it as the user owning them instead:

```yaml
services:
  lyrion-dashboard:
    user: "0:0"
```
