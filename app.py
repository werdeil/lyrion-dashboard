from flask import Flask

from config import Config
from routes.nowplaying import nowplaying_bp
from routes.custom import custom_bp


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    @app.route("/health", methods=["GET"])
    def healthcheck():
        return {"status": "ok"}, 200

    app.register_blueprint(nowplaying_bp)
    app.register_blueprint(custom_bp)

    return app


app = create_app()

if __name__ == "__main__":
    app.run(
        host=app.config["HOST"],
        port=app.config["PORT"],
    )
