#!/usr/bin/env bash
#
# Cron wrapper around scripts/embed_lyrics.py: re-tag only the music files whose
# metadata changed since the last successful run.
#
# It uses ctime (find -cnewer) rather than mtime, so files are picked up not
# only when their contents change but also when their tags/metadata are
# rewritten in place (a tag edit bumps ctime but not always mtime).
#
# Usage:
#     scripts/embed_lyrics_cron.sh /path/to/music [MARKER] [-- EXTRA ARGS]
#
# MARKER defaults to state/embed_lyrics.last_run under the repo root. Anything
# after `--` is forwarded verbatim to embed_lyrics.py (e.g. --clear --delay 1).
#
# Example crontab (daily at 03:30):
#     30 3 * * * /path/to/repo/scripts/embed_lyrics_cron.sh /path/to/music >> /var/log/embed_lyrics.log 2>&1
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="$ROOT/.venv/bin/python"
[ -x "$PYTHON" ] || PYTHON="python3"

if [ "$#" -lt 1 ]; then
    echo "usage: $(basename "$0") /path/to/music [MARKER] [-- EXTRA ARGS]" >&2
    exit 2
fi

MUSIC_DIR="$1"; shift
MARKER="$ROOT/state/embed_lyrics.last_run"
if [ "$#" -gt 0 ] && [ "$1" != "--" ]; then
    MARKER="$1"; shift
fi
[ "${1:-}" = "--" ] && shift   # drop the separator; the rest is forwarded

# A --dry-run pass writes nothing, so the marker must NOT advance, otherwise the
# next real run would skip every file this run only pretended to handle.
DRY_RUN=0
for arg in "$@"; do
    [ "$arg" = "--dry-run" ] && DRY_RUN=1
done

if [ ! -d "$MUSIC_DIR" ]; then
    echo "error: not a directory: $MUSIC_DIR" >&2
    exit 2
fi

mkdir -p "$(dirname "$MARKER")"

# Stamp this run's start time into a temp file. We only promote it to the real
# marker after a successful pass, so a failed run does not advance the window,
# and a file changed *during* the run is still caught next time.
STAMP="$(mktemp "${TMPDIR:-/tmp}/embed_lyrics.XXXXXX")"
LIST="$(mktemp "${TMPDIR:-/tmp}/embed_lyrics.XXXXXX")"
trap 'rm -f "$STAMP" "$LIST"' EXIT

# Collect files whose ctime is newer than the last run. On the first run (no
# marker yet) every file is processed. -print0/-0 keep paths with spaces safe.
if [ -f "$MARKER" ]; then
    find "$MUSIC_DIR" -type f -cnewer "$MARKER" -print0 > "$LIST"
else
    find "$MUSIC_DIR" -type f -print0 > "$LIST"
fi

count="$(tr -dc '\0' < "$LIST" | wc -c | tr -d ' ')"
if [ "$count" -eq 0 ]; then
    echo "no files changed since last run"
    [ "$DRY_RUN" -eq 0 ] && touch -r "$STAMP" "$MARKER"
    exit 0
fi

echo "processing $count changed file(s) since last run"
xargs -0 "$PYTHON" "$ROOT/scripts/embed_lyrics.py" "$@" < "$LIST"

# Success: advance the marker to this run's start time (skipped on --dry-run,
# which wrote nothing, so the window stays open for the next real run).
[ "$DRY_RUN" -eq 0 ] && touch -r "$STAMP" "$MARKER"
