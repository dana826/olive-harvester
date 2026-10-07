"""Flask application factory for the Olive Harvester dashboard MVP."""

from __future__ import annotations

import hmac
import os

from flask import Flask, Response, render_template, request

from .config import AppConfig
from .core.harvest_controller import HarvestController
from .storage.db import Database


def create_app(config: AppConfig | None = None) -> Flask:
    config = config or AppConfig()

    app = Flask(__name__, static_folder="static", template_folder="templates")
    app.config["APP_CONFIG"] = config

    db = Database(config.db_path, config.schema_path)
    controller = HarvestController(
        capture_dir=config.capture_dir,
        profiles_path=config.vibration_profiles_path,
        db=db,
        branches=config.branches,
    )

    app.extensions["controller"] = controller
    app.extensions["capture_dir"] = config.capture_dir

    from .api.routes import api_bp

    app.register_blueprint(api_bp, url_prefix="/api")

    # Optional access password for public hosting. If the OLIVE_PASSWORD
    # environment variable is set, every page and API call requires it
    # (browser shows a login box; the username can be anything).
    password = os.environ.get("OLIVE_PASSWORD")
    if password:

        @app.before_request
        def require_password():
            auth = request.authorization
            supplied = (auth.password or "") if auth else ""
            if not hmac.compare_digest(supplied.encode(), password.encode()):
                return Response(
                    "Password required.",
                    401,
                    {"WWW-Authenticate": 'Basic realm="Olive Harvester"'},
                )

    @app.route("/")
    def index():
        return render_template("index.html")

    return app
