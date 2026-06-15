"""Read music metadata and embed plain-text lyrics into a file's tags.

Framework-free so it can be reused from a CLI or the web app. Lyrion is never
touched here: this works directly on the audio files via mutagen, and Lyrion
picks any change up on its next scan. Only plain text is stored (timestamps from
synced LRC are stripped) for maximum player compatibility.
"""

import os
import re

import mutagen
from mutagen.id3 import USLT
from mutagen.flac import FLAC
from mutagen.mp4 import MP4
from mutagen.mp3 import MP3
from mutagen.aiff import AIFF
from mutagen.wave import WAVE
from mutagen.oggvorbis import OggVorbis
from mutagen.oggopus import OggOpus


MUSIC_EXTENSIONS = {
    ".mp3", ".flac", ".ogg", ".opus", ".m4a", ".mp4", ".aiff", ".aif", ".wav",
}

# LRC timing tags: line timestamps [mm:ss.xx], enhanced word timestamps
# <mm:ss.xx>, and metadata lines like [ar:...] / [length:...].
_LINE_TS = re.compile(r"\[\d{1,2}:\d{2}(?:[.:]\d{1,3})?\]")
_WORD_TS = re.compile(r"<\d{1,2}:\d{2}(?:[.:]\d{1,3})?>")
_META_LINE = re.compile(r"^\[[a-zA-Z#]+:.*\]$")


class LyricsTagError(Exception):
    """A user-facing failure while reading or writing tags."""


def lrc_to_plain(text):
    """Strip LRC line/word timestamps and metadata lines, leaving plain text."""
    lines = []
    for line in text.splitlines():
        if _META_LINE.match(line.strip()):
            continue
        line = _WORD_TS.sub("", _LINE_TS.sub("", line)).strip()
        lines.append(line)
    return "\n".join(lines).strip()


def is_music_file(path):
    """True if the path's extension is one we know how to tag."""
    return os.path.splitext(path)[1].lower() in MUSIC_EXTENSIONS


def read_metadata(path):
    """Return {artist, title, album, duration} for a file, or None if unreadable.

    Uses mutagen's "easy" interface so the same key names work across formats.
    """
    try:
        audio = mutagen.File(path, easy=True)
    except Exception:
        return None
    if audio is None:
        return None

    def first(key):
        value = audio.get(key)
        return value[0] if value else None

    duration = getattr(getattr(audio, "info", None), "length", None)
    return {
        "artist": first("artist"),
        "title": first("title"),
        "album": first("album"),
        "duration": duration,
    }


def _read_lyrics(audio):
    """Return the existing lyrics tag of an opened mutagen file, or None."""
    if isinstance(audio, (MP3, AIFF, WAVE)):
        if audio.tags is None:
            return None
        frames = audio.tags.getall("USLT")
        return str(frames[0].text) if frames else None
    if isinstance(audio, MP4):
        values = audio.get("\xa9lyr")
        return values[0] if values else None
    if isinstance(audio, (FLAC, OggVorbis, OggOpus)):
        values = audio.get("LYRICS") or audio.get("UNSYNCEDLYRICS")
        return values[0] if values else None
    return None


def has_lyrics(path):
    """True if the file already carries a non-empty lyrics tag."""
    audio = mutagen.File(path)
    if audio is None:
        return False
    return bool(_read_lyrics(audio))


def write_lyrics(path, text):
    """Write plain-text `text` into the lyrics tag of `path`.

    Raises LyricsTagError on unrecognised/unsupported format or write failure.
    """
    if not text:
        raise LyricsTagError("empty lyrics")

    audio = mutagen.File(path)
    if audio is None:
        raise LyricsTagError("unrecognised file format")

    if isinstance(audio, (MP3, AIFF, WAVE)):
        if audio.tags is None:
            audio.add_tags()
        audio.tags.delall("USLT")
        audio.tags.add(USLT(encoding=3, lang="eng", desc="", text=text))
    elif isinstance(audio, MP4):
        audio["\xa9lyr"] = text
    elif isinstance(audio, (FLAC, OggVorbis, OggOpus)):
        audio["LYRICS"] = text
    else:
        raise LyricsTagError("unsupported format for lyrics")

    try:
        audio.save()
    except Exception as exc:
        raise LyricsTagError(f"write failed: {exc}")
