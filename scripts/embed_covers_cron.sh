#!/usr/bin/env bash
#
# Cron wrapper around scripts/embed_covers.py: re-check only the album folders
# whose contents changed since the last successful run.
#
# It uses ctime (find -cnewer) rather than mtime, so a folder is picked up when
# a track is added, when its tags are rewritten in place, and when the cover
# file itself is replaced — all three are reasons to look at the album again.
#
# Usage:
#     scripts/embed_covers_cron.sh /path/to/music [MARKER] [-- EXTRA ARGS]
#
# MARKER defaults to state/embed_covers.last_run under the repo root. Anything
# after `--` is forwarded verbatim to embed_covers.py (e.g. --name cover.jpg).
#
# Example crontab (daily at 05:00):
#     0 5 * * * /path/to/repo/scripts/embed_covers_cron.sh /path/to/music >> /var/log/embed_covers.log 2>&1
#
# Needs GNU find and sort (-printf, sort -z), as shipped on the Linux hosts this
# runs on.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="$ROOT/.venv/bin/python"
[ -x "$PYTHON" ] || PYTHON="python3"

if [ "$#" -lt 1 ]; then
    echo "usage: $(basename "$0") /path/to/music [MARKER] [-- EXTRA ARGS]" >&2
    exit 2
fi

MUSIC_DIR="$1"; shift
MARKER="$ROOT/state/embed_covers.last_run"
if [ "$#" -gt 0 ] && [ "$1" != "--" ]; then
    MARKER="$1"; shift
fi
[ "${1:-}" = "--" ] && shift   # drop the separator; the rest is forwarded

# A --dry-run pass writes nothing, so the marker must NOT advance, otherwise the
# next real run would skip every album this run only pretended to handle.
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
STAMP="$(mktemp "${TMPDIR:-/tmp}/embed_covers.XXXXXX")"
LIST="$(mktemp "${TMPDIR:-/tmp}/embed_covers.XXXXXX")"
trap 'rm -f "$STAMP" "$LIST"' EXIT

# Collect the folders holding a file whose ctime is newer than the last run. On
# the first run (no marker yet) the whole library is processed. %h prints each
# file's directory, so an album is queued once however many of its files moved.
if [ -f "$MARKER" ]; then
    find "$MUSIC_DIR" -type f -cnewer "$MARKER" -printf '%h\0' | sort -zu > "$LIST"
else
    printf '%s\0' "$MUSIC_DIR" > "$LIST"
fi

count="$(tr -dc '\0' < "$LIST" | wc -c | tr -d ' ')"
if [ "$count" -eq 0 ]; then
    echo "no folder changed since last run"
    [ "$DRY_RUN" -eq 0 ] && touch -r "$STAMP" "$MARKER"
    exit 0
fi

# Embedding a cover rewrites every track, bumping their ctime, so those albums
# reappear in the next run's list; the pass then finds the tags already right.
echo "checking $count changed folder(s) since last run"
xargs -0 "$PYTHON" "$ROOT/scripts/embed_covers.py" "$@" < "$LIST"

# Success: advance the marker to this run's start time (skipped on --dry-run,
# which wrote nothing, so the window stays open for the next real run).
[ "$DRY_RUN" -eq 0 ] && touch -r "$STAMP" "$MARKER"
