#!/usr/bin/env python3
"""Embed each album folder's cover file into the tags of its tracks.

Lyrion displays the artwork embedded in the files and ignores a folder's cover
file entirely, so an album whose folder.jpg is sharper than its own tags shows
the worse of the two. This walks album folders and, wherever the file beats the
tags, writes it into every track of that album. Lyrion picks the change up on
its next scan.

Usage:
    python scripts/embed_covers.py /path/to/music [--dry-run] [--name folder.jpg]
                                   [--verbose]

Several targets are accepted, and shell-style wildcards work even when quoted
(or when the shell finds no match and passes the pattern through literally):
    python scripts/embed_covers.py /path/to/music/A*
    python scripts/embed_covers.py "/path/to/music/A*" /path/to/music/B*
Each target is a directory, scanned recursively for folders holding music.

Nothing is written with --dry-run. Either way the run reports how much the
audio files grow: embedding a cover rewrites every track, so a 2 MB sleeve
across a twelve-track album adds 24 MB that then has to resync and back up.

Only a bigger cover is embedded, measured on the shortest side — the side that
decides how sharp a sleeve looks on screen. An album whose tags carry no
artwork at all is always filled in.
"""

import argparse
import glob
import os
import sys

# Allow running both as a script (python scripts/embed_covers.py) and as a
# module (python -m scripts.embed_covers) by putting the repo root on the path.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

# pylint: disable=wrong-import-position
from services import artwork, tags  # noqa: E402


def album_folders(patterns):
    """Yield (folder, [music files]) for every album folder under `patterns`.

    Returns them through a generator, so the walk and the work interleave.
    Patterns the shell already expanded arrive as plain paths; literal ones
    (quoted, or left untouched because the shell found no match) are expanded
    here. Folders without music are skipped, which leaves artwork-only
    subfolders (Scans/, Artwork/) alone.
    """
    seen = set()
    for pattern in patterns:
        matches = sorted(glob.glob(pattern)) if glob.has_magic(pattern) else [pattern]
        if not matches:
            print(f"warning: no match for pattern: {pattern}", file=sys.stderr)
        for match in matches:
            if not os.path.isdir(match):
                print(f"warning: not a directory: {match}", file=sys.stderr)
                continue
            for dirpath, _dirs, names in os.walk(match):
                # macOS leaves AppleDouble stubs (._track.mp3) beside the real
                # files; they carry the extension but none of the content.
                music = sorted(n for n in names if tags.is_music_file(n) and not n.startswith("."))
                if music and dirpath not in seen:
                    seen.add(dirpath)
                    yield dirpath, [os.path.join(dirpath, n) for n in music]


def label(folder):
    """The album's last two path components, so a disc subfolder still names its
    album in the log rather than showing up as a bare CD1."""
    return os.sep.join(folder.rstrip(os.sep).split(os.sep)[-2:])


def read_folder_cover(folder, name):
    """Return (bytes, shortest side) for the folder's cover file, or None.

    The name is matched without regard to case, so a Folder.jpg written by a
    Windows tagger is found too.
    """
    try:
        entries = {n.lower(): n for n in os.listdir(folder)}
    except OSError:
        return None
    real = entries.get(name.lower())
    if not real:
        return None
    try:
        with open(os.path.join(folder, real), "rb") as handle:
            data = handle.read()
    except OSError:
        return None
    side = artwork.smallest_side(data)
    return (data, side) if side else None


def embedded_side(files):
    """Shortest side of the artwork already in the album's tags, 0 if none.

    Three tracks are enough to tell what an album carries; the write still
    covers every one of them.
    """
    for path in files[:3]:
        data = tags.read_cover(path)
        if data:
            side = artwork.smallest_side(data)
            if side:
                return side
    return 0


def process(folder, files, data, side, current):
    """Write `data` into every track, returning the failures as text lines."""
    failures = []
    for path in files:
        try:
            tags.write_cover(path, data)
        except tags.CoverTagError as exc:
            failures.append(f"{os.path.basename(path)}: {exc}")
    rel = label(folder)
    if failures:
        print(f"[fail]      {rel}: {len(failures)}/{len(files)} tracks failed")
        for line in failures[:3]:
            print(f"              {line}")
    else:
        print(f"[written]   {rel}  {current or 'none'} -> {side}px on {len(files)} tracks")
    return failures


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Embed each album folder's cover file into the tags of its tracks."
    )
    parser.add_argument(
        "targets", nargs="+",
        help="Directories to process. Shell-style wildcards (e.g. A*) are accepted, even quoted.",
    )
    parser.add_argument(
        "--name", default="folder.jpg",
        help="Name of the cover file to look for in each album folder (default folder.jpg).",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Report which albums would be re-tagged, without writing anything.",
    )
    parser.add_argument(
        "--verbose", action="store_true",
        help="Log every album, including those skipped.",
    )
    args = parser.parse_args(argv)

    counts = {"scanned": 0, "written": 0, "no_cover": 0, "up_to_date": 0, "failed": 0}
    added = 0
    dry = " (dry-run)" if args.dry_run else ""

    for folder, files in album_folders(args.targets):
        counts["scanned"] += 1
        rel = label(folder)

        cover = read_folder_cover(folder, args.name)
        if not cover:
            counts["no_cover"] += 1
            if args.verbose:
                print(f"[skip:none] {rel}")
            continue

        data, side = cover
        current = embedded_side(files)
        if current >= side:
            counts["up_to_date"] += 1
            if args.verbose:
                print(f"[skip:has]  {rel}  (tags {current}px, file {side}px)")
            continue

        added += len(data) * len(files)
        if args.dry_run:
            counts["written"] += 1
            print(f"[would]     {rel}  {current or 'none'} -> {side}px on {len(files)} tracks")
            continue

        counts["failed" if process(folder, files, data, side, current) else "written"] += 1

    print(
        f"\nDone{dry}: {counts['scanned']} albums scanned, {counts['written']} re-tagged, "
        f"{counts['up_to_date']} already good, {counts['no_cover']} without {args.name}, "
        f"{counts['failed']} failed"
    )
    if added:
        print(f"Audio files grow by about {added / 1024 / 1024:.0f} MB")
    return 1 if counts["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
