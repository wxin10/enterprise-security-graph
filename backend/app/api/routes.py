#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
文件路径：backend/app/api/routes.py

文件作用：
1. 作为 app/api 目录下所有蓝图的统一注册入口。
2. 不创建 routes 目录，保持当前项目的平铺式 API 结构。
3. 统一维护当前阶段已开放接口列表，供 app/__init__.py 复用。
"""

from __future__ import annotations

from flask import Flask

from app.api.alert_api import alert_api_bp
from app.api.ban_api import ban_api_bp
from app.api.graph_api import graph_api_bp
from app.api.monitor_api import monitor_api_bp


# 当前阶段已开放接口列表。
# 这个列表会被应用根路径说明接口复用，避免写两份接口清单。
AVAILABLE_API_ENDPOINTS = [
    "GET /api/graph/overview",
    "GET /api/graph/stats",
    "GET /api/alerts",
    "GET /api/bans",
    "GET /api/graph/user/<user_id>",
    "POST /api/monitor/start",
    "POST /api/monitor/stop",
    "GET /api/monitor/status",
    "GET /api/monitor/config",
]


# 当前阶段的 API 蓝图集合。
# 后续如果增加审计日志、封禁执行等接口，只需要继续在这里补充蓝图即可。
API_BLUEPRINTS = [
    graph_api_bp,
    alert_api_bp,
    ban_api_bp,
    monitor_api_bp,
]


def register_api_blueprints(app: Flask) -> None:
    """
    向 Flask 应用注册所有 API 蓝图。

    说明：
    1. 所有蓝图统一挂载到 /api 前缀下。
    2. 这样可以保持接口路径统一，也便于未来扩展版本化路径。
    """
    for blueprint in API_BLUEPRINTS:
        app.register_blueprint(blueprint, url_prefix="/api")
