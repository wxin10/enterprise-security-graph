#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
文件路径：backend/app/middleware/__init__.py

文件作用：
1. 统一导出当前后端可复用的轻量中间件工具。
2. 当前阶段仅暴露 WEB_BLOCKLIST 真实阻断中间件与 blocklist 读写工具。
"""

from app.middleware.ip_blocklist import (
    add_ip_to_blocklist,
    ensure_blocklist_file,
    query_blocked_ip,
    register_ip_blocklist_middleware,
    remove_ip_from_blocklist,
)

__all__ = [
    "add_ip_to_blocklist",
    "ensure_blocklist_file",
    "query_blocked_ip",
    "register_ip_blocklist_middleware",
    "remove_ip_from_blocklist",
]
