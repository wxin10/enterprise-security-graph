#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
文件路径：backend/app/core/response.py

文件作用：
1. 提供统一 JSON 返回工具。
2. 保证所有接口都按照一致结构输出，便于前端消费和后续文档编写。
3. 统一附带时间戳，便于排查问题和论文展示接口结果。
"""

from __future__ import annotations

from datetime import datetime, timezone

from flask import jsonify


def build_timestamp() -> str:
    """
    构造统一时间戳。

    这里使用 ISO 8601 UTC 时间，便于日志排查和跨系统对齐。
    """
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def success_response(data=None, message: str = "请求成功", code: int = 0, http_status: int = 200):
    """
    成功响应统一封装。
    """
    payload = {
        "code": code,
        "message": message,
        "data": data,
        "timestamp": build_timestamp(),
    }
    return jsonify(payload), http_status


def error_response(message: str = "请求失败", code: int = 1, http_status: int = 400, data=None):
    """
    错误响应统一封装。
    """
    payload = {
        "code": code,
        "message": message,
        "data": data,
        "timestamp": build_timestamp(),
    }
    return jsonify(payload), http_status
