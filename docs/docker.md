[English](docker.md) | [Français](docker.fr.md) — back to the [README](../README.md)

# Docker

The dashboard ships as a container image on the GitHub Container Registry: `ghcr.io/werdeil/lyrion-dashboard`. Installing it needs no clone of this repository — one `docker-compose.yml` carrying your Lyrion URL and data directory, and `docker compose up -d`.

That compose file is yours once downloaded: change the port, the volumes, the restart policy, drop the service into a larger stack. Nothing has to stay in sync with this repository.

## Image tags

| Tag | Points to | Moves when |
|---|---|---|
| `latest` | the most recent stable release | a release is published |
| `X.Y` | the latest patch of that minor (e.g. `0.2`) | a release in that series is published |
| `X.Y.Z` | that exact release (e.g. `0.2.6`) | never — built once, it keeps its digest |
| `dev` | the `master` branch | every merge — unreleased code, see [Development](development.md) |

Images are built for `linux/amd64` and `linux/arm64`, so a Raspberry Pi or an ARM NAS pulls the same tag as a PC. Pin `X.Y.Z` for a deployment that only ever changes when you say so; `latest` follows the releases. No released tag is ever rebuilt, so a security fix in the Debian base image reaches you with the next release rather than under the tag you already run. A release marked as a pre-release publishes its `X.Y.Z` tag alone: `latest` and `X.Y` keep pointing at the last stable one.

## Updating

```bash
docker compose pull
docker compose up -d
```

## Coming from the bind-mounted install

Before this image existed, the compose file ran a bare `python:3.12-slim` over a clone of this repository and read its settings from a `.env` beside it. Neither is used any more. Take the compose file from the [README](../README.md), carry your `LYRION_HOST` into it, and mount on `/lyrion` what `LYRION_DATA_DIR` used to name. The clone can go; keep the `.env` only if you run the [scripts](scripts.md), which still read it.

## Filesystem permissions

The container runs as uid 1000, not root. If Lyrion's files under the directory you mount on `/lyrion` are not readable by it, the dashboard starts but logs that it cannot open the databases; run it as the user owning them instead. `stat -c '%u:%g' /var/lib/squeezeboxserver` prints the pair to use:

```yaml
services:
  lyrion-dashboard:
    user: "999:999"
```

`user: "0:0"` is root and reads anything, which makes it the fix of last resort rather than the first thing to try.
