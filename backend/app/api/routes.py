#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import annotations

from flask import Flask

from app.api.alert_api import alert_api_bp
from app.api.audit_api import audit_api_bp
from app.api.auth_api import auth_api_bp
from app.api.ban_api import ban_api_bp
from app.api.disposals_api import disposals_api_bp
from app.api.graph_api import graph_api_bp
from app.api.monitor_api import monitor_api_bp
from app.api.profile_api import profile_api_bp
from app.api.rules_api import rules_api_bp
from app.api.users_api import users_api_bp


AVAILABLE_API_ENDPOINTS = [
    "POST /api/auth/login",
    "GET /api/auth/me",
    "GET /api/graph/overview",
    "GET /api/graph/stats",
    "GET /api/alerts",
    "GET /api/alerts/<alert_id>/attack-chain",
    "GET /api/bans",
    "GET /api/bans/<ban_id>",
    "POST /api/bans/<ban_id>/unban",
    "POST /api/bans/<ban_id>/reblock",
    "POST /api/bans/<ban_id>/verify",
    "GET /api/graph/user/<user_id>",
    "POST /api/monitor/start",
    "POST /api/monitor/stop",
    "GET /api/monitor/status",
    "GET /api/monitor/config",
    "GET /api/monitor/topology",
    "GET /api/users",
    "POST /api/users",
    "PATCH /api/users/<user_id>",
    "POST /api/users/<user_id>/reset-password",
    "POST /api/users/<user_id>/toggle-status",
    "GET /api/rules",
    "POST /api/rules",
    "PATCH /api/rules/<rule_id>",
    "POST /api/rules/<rule_id>/gray-release",
    "POST /api/rules/<rule_id>/toggle-status",
    "GET /api/audit/logs",
    "GET /api/audit/logs/<audit_id>",
    "GET /api/disposals",
    "POST /api/disposals",
    "GET /api/disposals/my",
    "PATCH /api/disposals/<request_id>",
    "GET /api/profile",
    "PATCH /api/profile",
]

API_BLUEPRINTS = [
    auth_api_bp,
    graph_api_bp,
    alert_api_bp,
    ban_api_bp,
    monitor_api_bp,
    users_api_bp,
    rules_api_bp,
    audit_api_bp,
    disposals_api_bp,
    profile_api_bp,
]


def register_api_blueprints(app: Flask) -> None:
    for blueprint in API_BLUEPRINTS:
        app.register_blueprint(blueprint, url_prefix="/api")
