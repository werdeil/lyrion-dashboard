from flask import Flask

from config import Config
from routes.nowplaying import nowplaying_bp
from routes.custom import custom_bp


def create_app():
    flask_app = Flask(__name__)
    flask_app.config.from_object(Config)

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
    # Only reached via `python app.py` for quick local dev. In Docker the app is
    # served by gunicorn (see docker-compose.yml), which binds via its own -b
    # flag and never runs this block — so there's nothing to configure here.
    app.run(host="0.0.0.0", port=1111)  # nosec
