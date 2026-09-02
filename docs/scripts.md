[English](scripts.md) | [Français](scripts.fr.md) — back to the [README](../README.md)

# Scripts

The scripts in `scripts/` run outside the web app, on `requirements-cli.txt` alone. They write to the audio files directly; Lyrion is never contacted and picks the changes up on its next scan.

## Embed lyrics into files (`scripts/embed_lyrics.py`)

Walks a folder (or files), fetches lyrics from web providers and writes them into the *lyrics* tag of each track. Configuration (`.env`) is read automatically.

```bash
python scripts/embed_lyrics.py /path/to/music [options]
# Shell globs work, even when quoted:
python scripts/embed_lyrics.py "/path/to/music/A*" /path/to/music/B*
```

| Option | Description |
|---|---|
| <code>&#8209;&#8209;force</code> | Rewrites the tag even if lyrics are already present. |
| <code>&#8209;&#8209;clear</code> | Erases the existing tag when nothing is found online, to reflect what the providers offer. Also processes already-tagged files (so one web request per file); combinable with `--force`. |
| <code>&#8209;&#8209;no&#8209;verify</code> | Accepts a provider's lyrics even when its own title/artist/duration don't match the file. Off by default: since tags are written permanently, a mismatched result is worse than no lyrics. |
| <code>&#8209;&#8209;dry&#8209;run</code> | Prints what would be done, without writing anything. |
| <code>&#8209;&#8209;delay&nbsp;0.5</code> | Delay (seconds) between web requests (default: 0.5). |
| <code>&#8209;&#8209;verbose</code> | Logs every file, including skipped ones. |

### Cron: only re-tag changed files (`scripts/embed_lyrics_cron.sh`)

A cron-oriented wrapper that only feeds `embed_lyrics.py` the files whose `ctime` changed since the last successful pass (`find -cnewer`), via a marker file.

```bash
scripts/embed_lyrics_cron.sh /path/to/music [MARKER] [-- OPTIONS]
```

- `MARKER`: timestamp file (default: `state/embed_lyrics.last_run` at the repo root). Missing → the whole library is processed (first pass).
- The marker is stamped at the **start** of the pass and only advances **on success**: a failure does not move the window forward, and a file modified during the pass is picked up on the next run. `--dry-run` does not advance the marker.
- Everything after `--` is forwarded as-is to `embed_lyrics.py` (e.g. `-- --clear --delay 1`).

```cron
30 3 * * * /path/to/custom_data/scripts/embed_lyrics_cron.sh \
  /path/to/music >> /tmp/embed_lyrics.log 2>&1
```

> `ctime` (not `mtime`) is used on purpose: it also catches in-place tag rewrites and files copied while preserving their `mtime` (`rsync -a`, `cp -p`).

## Embed cover art into files (`scripts/embed_covers.py`)

Walks album folders and writes each folder's cover file into the *artwork* tag of its tracks, wherever that file is sharper than what the tags already carry. Lyrion displays the embedded artwork and ignores `folder.jpg` entirely, so an album with a 1500 px sleeve on disk and a 300 px one in its tags keeps showing the small one until this runs.

```bash
python scripts/embed_covers.py /path/to/music [options]
# Shell globs work, even when quoted:
python scripts/embed_covers.py "/path/to/music/A*" /path/to/music/B*
```

| Option | Description |
|---|---|
| <code>&#8209;&#8209;name&nbsp;folder.jpg</code> | Name of the cover file to look for in each album folder (default: `folder.jpg`), matched without regard to case. |
| <code>&#8209;&#8209;dry&#8209;run</code> | Prints which albums would be re-tagged, without writing anything. |
| <code>&#8209;&#8209;verbose</code> | Logs every album, including skipped ones. |

Covers are compared on their **shortest side**, the one that decides how sharp a sleeve looks on screen: only a bigger file is embedded, and an album whose tags carry no artwork at all is always filled in. The image is stored as it is, never re-encoded. Embedding rewrites every track of the album, so the run reports how much the audio files grow — a 2 MB sleeve across a twelve-track album adds 24 MB that then has to resync and back up.

### Cron: only re-check changed folders (`scripts/embed_covers_cron.sh`)

Same marker mechanism as the lyrics wrapper, except the unit is the album folder: `find -cnewer` lists the files whose `ctime` changed, and it is their folders that `embed_covers.py` is handed. A replaced `folder.jpg` therefore queues its album just as a new track does.

```bash
scripts/embed_covers_cron.sh /path/to/music [MARKER] [-- OPTIONS]
```

- `MARKER`: timestamp file (default: `state/embed_covers.last_run` at the repo root). Missing → the whole library is processed (first pass).
- Same rules as above: stamped at the **start** of the pass, advanced only **on success**, left where it is by `--dry-run`.
- Everything after `--` is forwarded as-is to `embed_covers.py` (e.g. `-- --name cover.jpg`).

```cron
0 5 * * * /path/to/repo/scripts/embed_covers_cron.sh \
  /path/to/music >> /tmp/embed_covers.log 2>&1
```

> Embedding a cover bumps every track's `ctime`, so the album shows up again in the next pass — which then finds the tags already right and moves on.

## Regenerate the screenshots (`scripts/generate_screenshots.py`)

Runs the real app with the Lyrion/database layers mocked (fake now-playing track, synced LRC lyrics, generated cover art, a fake recent-plays history, canned stats) and captures every image under `docs/screenshots/` with headless Chromium: the desktop dashboard in both languages, the responsive mobile view, the Android app in a device frame, and the demo gallery (enlarged cover, karaoke lyrics, the recent-plays pile, the statistics panel, the empty state's mosaic). Each capture uses a different cover on purpose, to show the accent color adapting to the artwork. No Lyrion server, database or network is needed.

```bash
pip install -r requirements.txt playwright
playwright install chromium   # once, or set CHROMIUM_PATH
python scripts/generate_screenshots.py
```

A capture is one `Shot` entry in the script's `SHOTS` map: the scenario to serve, the viewport and locale, optionally some JS to run first (opening the enlarged cover) and an element to crop to.
