import os


class Config:
    # Lyrion Music Server
    LYRION_HOST = os.getenv("LYRION_HOST")

    # Database paths
    DB_PATH = os.path.join(os.getenv("DB_DIR", ""), "library.db")
    DB_PERSIST_PATH = os.path.join(os.getenv("DB_PERSIST_DIR", ""), "persist.db")

    # Custom data directory
    CUSTOM_DATA_DIR = os.getenv("CUSTOM_DATA_DIR", "/opt/scripts/custom_data")

    # Wear OS companion install (routes/wear.py): adb binary on the server
    # host, where the watch APK is cached/dropped, and which repo's releases
    # to fetch it from when the file is absent.
    ADB_PATH = os.getenv("ADB_PATH") or "adb"
    WEAR_APK_PATH = os.getenv("WEAR_APK_PATH") or os.path.join(
        CUSTOM_DATA_DIR, "lyrion-wear.apk"
    )
    GITHUB_REPO = os.getenv("GITHUB_REPO") or "werdeil/lyrion-dashboard"

    # Server
    # Binds all interfaces on purpose (Docker); set HOST to bind narrower.
    HOST = os.getenv("HOST", "0.0.0.0")  # nosec
    PORT = int(os.getenv("PORT", "1111"))

    # Development helpers: when DEV=1, Jinja re-reads templates from disk on
    # every request and static files are served with no cache, so HTML/CSS
    # edits show up on a simple page refresh (no worker/container restart).
    DEV = os.getenv("DEV", "").lower() in ("1", "true", "yes")
    TEMPLATES_AUTO_RELOAD = DEV
    SEND_FILE_MAX_AGE_DEFAULT = 0 if DEV else None
