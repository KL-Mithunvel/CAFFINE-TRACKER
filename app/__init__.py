"""Flask application factory."""
from flask import Flask

from app import db as db_module


def create_app() -> Flask:
    app = Flask(__name__)

    db_module.init_db()
    app.teardown_appcontext(db_module.close_connection)

    from app.routes import bp

    app.register_blueprint(bp)
    return app
