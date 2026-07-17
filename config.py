import os


def _read_version():
    # Single source of truth for the web app's version, kept in sync with the
    # Android versionName by the release workflow. Read once at import; the
    # source tree is mounted read-only in the container so this never changes
    # under a running process.
    version_file = os.path.join(os.path.dirname(__file__), "VERSION")
    try:
        with open(version_file, encoding="utf-8") as handle:
            return handle.read().strip()
    except OSError:
        return "unknown"


class Config:
    # Application version, exposed on /health for support and debugging.
    VERSION = _read_version()

    # Lyrion Music Server
    LYRION_HOST = os.getenv("LYRION_HOST")

    # Database paths
    DB_PATH = os.path.join(os.getenv("DB_DIR", ""), "library.db")
    DB_PERSIST_PATH = os.path.join(os.getenv("DB_PERSIST_DIR", ""), "persist.db")

    # Custom data directory
    CUSTOM_DATA_DIR = os.getenv("CUSTOM_DATA_DIR", "/opt/scripts/custom_data")

    # Development helpers: when DEV=1, Jinja re-reads templates from disk on
    # every request and static files are served with no cache, so HTML/CSS
    # edits show up on a simple page refresh (no worker/container restart).
    DEV = os.getenv("DEV", "").lower() in ("1", "true", "yes")
    TEMPLATES_AUTO_RELOAD = DEV
    SEND_FILE_MAX_AGE_DEFAULT = 0 if DEV else None
