from flask import Blueprint, current_app, send_from_directory

custom_bp = Blueprint("custom", __name__)


@custom_bp.route("/files/")
@custom_bp.route("/files/<path:filepath>")
def serve_file(filepath=""):
    """Serve static files from the custom data directory.

    These files are written by other services (e.g. JSON exports consumed by
    a Homepage widget), not by this app, so they are served sandboxed: should
    an HTML file ever land in the directory, it renders in an opaque origin
    and cannot script the dashboard or call its endpoints. Plain data files
    (JSON, images, CSV) are unaffected.
    """
    base_dir = current_app.config["CUSTOM_DATA_DIR"]
    response = send_from_directory(base_dir, filepath)
    # Overrides the app-wide default-src policy for this route (the global
    # after_request only fills the header in when it is absent).
    response.headers["Content-Security-Policy"] = "sandbox"
    return response
