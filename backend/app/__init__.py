#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import annotations

from flask import Flask
from flask_cors import CORS

from app.api import AVAILABLE_API_ENDPOINTS, register_api_blueprints
from app.core.errors import register_error_handlers
from app.core.response import success_response
from app.db import neo4j_client
from app.middleware import register_ip_blocklist_middleware
from config import get_config_class


def create_app(config_name: str | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_object(get_config_class(config_name))
    app.json.ensure_ascii = False

    CORS(
        app,
        resources={r"/api/*": {"origins": app.config["CORS_ORIGINS"]}},
        supports_credentials=False,
    )

    register_ip_blocklist_middleware(app)
    neo4j_client.init_app(app)
    register_api_blueprints(app)
    register_error_handlers(app)

    @app.get("/")
    def index():
        return success_response(
            data={
                "service": app.config["APP_NAME"],
                "available_endpoints": AVAILABLE_API_ENDPOINTS,
            },
            message="后端服务运行正常",
        )

    return app
