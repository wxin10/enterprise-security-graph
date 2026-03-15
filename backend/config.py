#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
文件路径：backend/config.py

文件作用：
1. 统一管理 Flask 应用配置。
2. 统一管理 Neo4j 连接配置。
3. 为开发环境和默认环境提供可扩展的配置入口。

说明：
1. 当前阶段暂不实现登录鉴权，因此这里只保留系统运行所需的基础配置。
2. Neo4j 的用户名、密码、数据库名建议通过环境变量覆盖，便于不同机器部署。
"""

from __future__ import annotations

import os
from typing import Dict, Type


def parse_cors_origins(raw_value: str):
    """
    解析跨域来源配置。

    设计原因：
    1. 当前阶段前后端尚未联调，因此默认放开所有来源，方便接口测试。
    2. 后续如果需要限制来源，只需将环境变量 CORS_ORIGINS 设置为逗号分隔的域名列表。
    """
    if not raw_value or raw_value.strip() == "*":
        return "*"

    origins = [item.strip() for item in raw_value.split(",") if item.strip()]
    return origins if origins else "*"


class BaseConfig:
    """
    基础配置类。

    所有环境共享的默认配置都放在这里，后续如果需要测试环境、生产环境，
    只需在该类基础上继续继承即可。
    """

    APP_NAME = "enterprise-security-graph-backend"
    DEBUG = False
    TESTING = False
    SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "enterprise-security-graph-dev-secret")
    JSON_AS_ASCII = False
    JSON_SORT_KEYS = False

    HOST = os.getenv("FLASK_HOST", "0.0.0.0")
    PORT = int(os.getenv("FLASK_PORT", "5000"))

    CORS_ORIGINS = parse_cors_origins(os.getenv("CORS_ORIGINS", "*"))

    NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
    NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")
    NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")
    NEO4J_VERIFY_CONNECTIVITY = os.getenv("NEO4J_VERIFY_CONNECTIVITY", "false").lower() == "true"
    NEO4J_CONNECTION_TIMEOUT = int(os.getenv("NEO4J_CONNECTION_TIMEOUT", "15"))
    NEO4J_MAX_CONNECTION_LIFETIME = int(os.getenv("NEO4J_MAX_CONNECTION_LIFETIME", "3600"))
    NEO4J_MAX_CONNECTION_POOL_SIZE = int(os.getenv("NEO4J_MAX_CONNECTION_POOL_SIZE", "50"))


class DevelopmentConfig(BaseConfig):
    """
    开发环境配置。

    当前毕业设计阶段主要以本地开发演示为主，因此默认启用调试模式。
    """

    DEBUG = True


CONFIG_MAPPING: Dict[str, Type[BaseConfig]] = {
    "default": DevelopmentConfig,
    "development": DevelopmentConfig,
}


def get_config_class(config_name: str | None = None) -> Type[BaseConfig]:
    """
    根据配置名称返回配置类。

    参数优先级：
    1. create_app 传入的 config_name
    2. 环境变量 FLASK_ENV
    3. 默认 development
    """
    resolved_name = (config_name or os.getenv("FLASK_ENV", "development")).lower()
    return CONFIG_MAPPING.get(resolved_name, DevelopmentConfig)
