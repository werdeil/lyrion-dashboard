import logging
import os

from flask import Flask

from config import Config
from logsetup import configure_logging
from routes.nowplaying import nowplaying_bp
from routes.custom import custom_bp

log = logging.getLogger(__name__)


def _log_startup(flask_app):
    """Report the effective configuration once, so a `docker logs` dump opens
    with what the container actually resolved rather than what .env intended."""
    log.info(
        "lyrion-dashboard %s starting (lyrion=%s, providers=%s, dev=%s, log_level=%s)",
        flask_app.config["VERSION"],
        flask_app.config["LYRION_HOST"] or "UNSET",
        os.getenv("LYRICS_PROVIDERS", "lrclib,musixmatch,genius"),
        flask_app.config["DEV"],
        logging.getLevelName(logging.getLogger().level),
    )
    if not flask_app.config["LYRION_HOST"]:
        log.error("LYRION_HOST is not set: no player, cover or now-playing data will load")
    for label, path in (
        ("library.db", flask_app.config["DB_PATH"]),
        ("persist.db", flask_app.config["DB_PERSIST_PATH"]),
    ):
        if not os.path.isfile(path):
            log.error("%s not found at %s: check LYRION_DATA_DIR (or DB_DIR/DB_PERSIST_DIR) and the volume mounts",
                      label, path)
        elif not os.access(path, os.R_OK):
            log.error("%s at %s is not readable by the container user", label, path)
        else:
            log.info("%s found at %s", label, path)


def create_app():
    flask_app = Flask(__name__)
    flask_app.config.from_object(Config)

    if configure_logging():
        _log_startup(flask_app)

    @flask_app.route("/health", methods=["GET"])
    def healthcheck():
        return {"status": "ok", "version": flask_app.config["VERSION"]}, 200

    @flask_app.after_request
    def set_security_headers(response):
        # Everything the page needs is same-origin, so a tight CSP costs
        # nothing; nosniff stops the browser from second-guessing content
        # types (which matters for whatever lands in /files/), and the frame
        # header keeps the dashboard out of third-party iframes.
        response.headers.setdefault("Content-Security-Policy", "default-src 'self'")
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        return response

    flask_app.register_blueprint(nowplaying_bp)
    flask_app.register_blueprint(custom_bp)

    return flask_app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=1111)  # nosec
