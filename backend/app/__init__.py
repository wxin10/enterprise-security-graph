#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
文件路径：backend/app/__init__.py

文件作用：
1. 提供 Flask 应用工厂 create_app。
2. 初始化 CORS、Neo4j 连接封装、蓝图和异常处理。
3. 作为整个后端工程的装配入口。
"""

from __future__ import annotations

from flask import Flask
from flask_cors import CORS

from config import get_config_class
from app.api import AVAILABLE_API_ENDPOINTS, register_api_blueprints
from app.core.errors import register_error_handlers
from app.core.response import success_response
from app.db import neo4j_client
from app.middleware import register_ip_blocklist_middleware


def create_app(config_name: str | None = None) -> Flask:
    """
    创建并配置 Flask 应用实例。

    这里采用应用工厂模式，主要有两个好处：
    1. 后续如果增加测试环境或生产环境配置，可以更方便地切换。
    2. 有利于后续继续扩展为更完整的工程化结构。
    """
    app = Flask(__name__)
    app.config.from_object(get_config_class(config_name))
    app.json.ensure_ascii = False

    CORS(
        app,
        resources={r"/api/*": {"origins": app.config["CORS_ORIGINS"]}},
        supports_credentials=False,
    )

    # 在最小真实阻断版本中，只有 WEB_BLOCKLIST 模式才会真正拦截请求。
    # 这里统一注册中间件，由中间件内部自行判断当前模式是否需要启用拦截。
    register_ip_blocklist_middleware(app)
    neo4j_client.init_app(app)
    register_api_blueprints(app)
    register_error_handlers(app)

    @app.get("/")
    def index():
        """
        根路径说明接口。

        作用：
        1. 用于快速确认 Flask 服务已经启动。
        2. 返回当前阶段已开放的核心接口列表。
        """
        return success_response(
            data={
                "service": app.config["APP_NAME"],
                "stage": "第四阶段：后端接口开发",
                "available_endpoints": AVAILABLE_API_ENDPOINTS,
            },
            message="后端服务启动成功",
        )

    return app
