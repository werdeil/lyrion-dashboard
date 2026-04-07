from flask import Flask

from config import Config
from routes.suggester import suggester_bp
from routes.custom import custom_bp


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Register blueprints
    app.register_blueprint(suggester_bp)
    app.register_blueprint(custom_bp)

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(
        host=app.config["HOST"],
        port=app.config["PORT"],
    )
