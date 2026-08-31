"""Logging setup shared by the web app and the CLI scripts.

Everything goes to stdout as one line per event, so `docker logs
lyrion-dashboard` is the single place to look when something misbehaves.
`LOG_LEVEL` picks the verbosity (DEBUG when `DEV=1`, else INFO): INFO keeps
one line per lyrics search or slow query, DEBUG adds the per-provider and
per-query detail needed to tell "the library has no lyrics" apart from "the
providers were unreachable".
"""

import logging
import os
import sys

LOG_FORMAT = "%(asctime)s %(levelname)-7s %(name)s %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_state = {"configured": False}


def default_level():
    """Log level from `LOG_LEVEL`, falling back to DEBUG under `DEV=1`."""
    name = (os.getenv("LOG_LEVEL") or "").strip().upper()
    if name in ("CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"):
        return name
    return "DEBUG" if os.getenv("DEV") == "1" else "INFO"


def configure_logging(level=None):
    """Send this app's loggers to stdout and return True on the first call.

    Idempotent, so gunicorn's re-import of the app factory (and every test
    building a client) does not stack handlers; the return value lets a caller
    emit its start-up banner exactly once per process.
    """
    if _state["configured"]:
        return False

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT))

    root = logging.getLogger()
    root.addHandler(handler)
    root.setLevel(level or default_level())
    # requests/urllib3 log every connection at DEBUG, which would bury ours.
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    _state["configured"] = True
    return True
