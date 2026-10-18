[English](scripts.md) | [Français](scripts.fr.md) — back to the [README](../README.md)

# Scripts

`scripts/` holds the tooling that runs outside the web app.

## Regenerate the screenshots (`scripts/generate_screenshots.py`)

Runs the real app with the Lyrion/database layers mocked (fake now-playing track, synced LRC lyrics, generated cover art, a fake recent-plays history, canned stats) and captures every image under `docs/screenshots/` with headless Chromium: the desktop dashboard in both languages, the responsive mobile view, the Android app in a device frame, and the demo gallery (enlarged cover, karaoke lyrics, the recent-plays pile, the statistics panel, the empty state's mosaic). Each capture uses a different cover on purpose, to show the accent color adapting to the artwork. No Lyrion server, database or network is needed.

```bash
pip install -r requirements.txt playwright
playwright install chromium   # once, or set CHROMIUM_PATH
python scripts/generate_screenshots.py
```

A capture is one `Shot` entry in the script's `SHOTS` map: the scenario to serve, the viewport and locale, optionally some JS to run first (opening the enlarged cover) and an element to crop to.
