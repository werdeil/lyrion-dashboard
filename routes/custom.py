from flask import Blueprint, current_app, send_from_directory

custom_bp = Blueprint("custom", __name__)


@custom_bp.route("/files/")
@custom_bp.route("/files/<path:filepath>")
def serve_file(filepath=""):
    """Serve static files from the custom data directory, sandboxed.

    Other services write these files, so an HTML file landing here renders in an
    opaque origin and cannot script the dashboard or call its endpoints.
    """
    base_dir = current_app.config["CUSTOM_DATA_DIR"]
    response = send_from_directory(base_dir, filepath)
    # Overrides the app-wide default-src policy for this route (the global
    # after_request only fills the header in when it is absent).
    response.headers["Content-Security-Policy"] = "sandbox"
    return response
