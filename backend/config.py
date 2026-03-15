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
from pathlib import Path
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


def parse_monitor_watch_directories(raw_value: str):
    """
    解析监控目录子项配置。

    说明：
    1. 环境变量中使用逗号分隔的目录名称列表。
    2. 若未配置，则回退到当前项目既有的四类 incoming 子目录。
    """
    if not raw_value or not raw_value.strip():
        return ["safeline_waf", "n9e_waf", "windows_firewall", "linux_firewall"]

    directories = [item.strip() for item in raw_value.split(",") if item.strip()]
    return directories or ["safeline_waf", "n9e_waf", "windows_firewall", "linux_firewall"]


def parse_port_list(raw_value: str):
    """
    解析 Windows 防火墙本地端口列表。

    设计说明：
    1. 为了适配答辩演示中的本地靶场，允许仅阻断指定端口，而不是粗暴阻断整台宿主机所有端口。
    2. 环境变量为空时，表示按源 IP 全量阻断入站访问。
    """
    if not raw_value or not raw_value.strip():
        return []

    ports = [item.strip() for item in raw_value.split(",") if item.strip()]
    return ports


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

    PROJECT_ROOT = Path(__file__).resolve().parents[1]
    DATA_ROOT = PROJECT_ROOT / "data"
    MONITOR_INCOMING_ROOT = str(DATA_ROOT / "incoming")
    MONITOR_RUNTIME_ROOT = str(DATA_ROOT / "runtime")
    MONITOR_BATCH_ROOT = str(DATA_ROOT / "runtime" / "batches")
    MONITOR_STATE_FILE = str(DATA_ROOT / "runtime" / "monitor_state.json")
    MONITOR_WATCHER_LOG_FILE = str(DATA_ROOT / "runtime" / "monitor_watcher.log")
    MONITOR_DEFAULT_INTERVAL_SECONDS = int(os.getenv("MONITOR_DEFAULT_INTERVAL_SECONDS", "5"))
    MONITOR_RECENT_RECORD_LIMIT = int(os.getenv("MONITOR_RECENT_RECORD_LIMIT", "10"))
    MONITOR_WATCH_DIRECTORIES = parse_monitor_watch_directories(
        os.getenv(
            "MONITOR_WATCH_DIRECTORIES",
            "safeline_waf,n9e_waf,windows_firewall,linux_firewall",
        )
    )

    BAN_ENFORCEMENT_MODE = os.getenv("BAN_ENFORCEMENT_MODE", "MOCK").upper()
    BAN_WINDOWS_FIREWALL_RULE_PREFIX = os.getenv("BAN_WINDOWS_FIREWALL_RULE_PREFIX", "ESG")
    BAN_WINDOWS_FIREWALL_DIRECTION = os.getenv("BAN_WINDOWS_FIREWALL_DIRECTION", "Inbound")
    BAN_WINDOWS_FIREWALL_PROTOCOL = os.getenv("BAN_WINDOWS_FIREWALL_PROTOCOL", "TCP").upper()
    BAN_WINDOWS_FIREWALL_LOCAL_PORTS = parse_port_list(os.getenv("BAN_WINDOWS_FIREWALL_LOCAL_PORTS", ""))


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
