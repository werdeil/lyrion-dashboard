import os


def _read_version():
    # Kept in sync with the Android versionName by the release workflow.
    version_file = os.path.join(os.path.dirname(__file__), "VERSION")
    try:
        with open(version_file, encoding="utf-8") as handle:
            return handle.read().strip()
    except OSError:
        return "unknown"


def _db_dir(override_var, subdir):
    # Lyrion keeps `prefs/` and `cache/` side by side under one data directory;
    # an override names whichever of the two was moved out of it.
    override = os.getenv(override_var)
    if override:
        return override
    data_dir = os.getenv("LYRION_DATA_DIR")
    return os.path.join(data_dir, subdir) if data_dir else ""


class Config:
    VERSION = _read_version()

    LYRION_HOST = os.getenv("LYRION_HOST")

    DB_PATH = os.path.join(_db_dir("DB_DIR", "cache"), "library.db")
    DB_PERSIST_PATH = os.path.join(_db_dir("DB_PERSIST_DIR", "prefs"), "persist.db")

    # "lyrion" forces Lyrion's own counters over the Alternative Play Count plugin.
    PLAY_COUNTS_SOURCE = os.getenv("PLAY_COUNTS_SOURCE", "auto").strip().lower()

    CUSTOM_DATA_DIR = os.getenv("CUSTOM_DATA_DIR", "/opt/scripts/custom_data")

    # DEV=1: templates reload from disk and static files are served uncached.
    DEV = os.getenv("DEV") == "1"
    TEMPLATES_AUTO_RELOAD = DEV
    SEND_FILE_MAX_AGE_DEFAULT = 0 if DEV else None
