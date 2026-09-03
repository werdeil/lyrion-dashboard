[English](development.md) | [Français](development.fr.md) — back to the [README](../README.md)

# Development

Three ways to run something other than the released image, from the lightest to the closest to production.

## From the sources

The loop to write code in: templates and static files are re-read on every request under `DEV=1`, so an HTML or CSS edit shows up on a page refresh.

```bash
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your values
source .env
DEV=1 python app.py
```

The app is available at `http://localhost:1111`. This is also the way to run the dashboard on a host where Docker is not wanted — drop `DEV=1` there.

`.env` is what feeds the app here (`config.py` reads the environment once at start-up), and `scripts/embed_lyrics.py` loads the same file through python-dotenv. Every variable is documented on the [Configuration](configuration.md) page.

## The `dev` image

`ghcr.io/werdeil/lyrion-dashboard:dev` is rebuilt on every merge to `master`, so it carries code that is in no release yet. Use it to try a fix before it ships or to reproduce a bug against the current code, and point `image:` back at a version tag afterwards — nothing guarantees `dev` is in a working state.

## Building the image from a checkout

`docker-compose.yml` carries a commented `build: .`. Uncomment it and Compose builds the image locally instead of pulling it:

```bash
docker compose up -d --build
```

This is how to check a change to the `Dockerfile` itself. It is a poor loop for application code: the image ships its own copy of the sources, so every edit needs a rebuild.

## Checks

The test suite, the linters and the security scanners are the same ones CI runs; `CLAUDE.md` lists each command and how to reproduce it.

```bash
python -m unittest discover
```
