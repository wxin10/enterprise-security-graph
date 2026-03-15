#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
文件路径：backend/app/api/alert_api.py

文件作用：
1. 提供告警相关接口蓝图。
2. 复用 graph_service 中已有的告警查询逻辑。
3. 对外暴露告警列表接口。
"""

from __future__ import annotations

from flask import Blueprint, request

from app.core.errors import ValidationError
from app.core.response import success_response
from app.services import graph_service


alert_api_bp = Blueprint("alert_api", __name__)


def parse_positive_int(value: str | None, default_value: int, field_name: str) -> int:
    """
    解析分页参数。

    设计原因：
    1. 告警列表接口支持分页查询。
    2. 如果请求参数非法，统一抛出 ValidationError，交给全局异常处理返回 JSON。
    """
    if value in (None, ""):
        return default_value

    try:
        parsed_value = int(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"参数 {field_name} 必须是整数") from exc

    if parsed_value <= 0:
        raise ValidationError(f"参数 {field_name} 必须大于 0")

    return parsed_value


@alert_api_bp.get("/alerts")
def get_alerts():
    """
    接口：GET /api/alerts

    作用：
    1. 返回告警列表。
    2. 支持按状态、严重等级、关键字查询。
    3. 适合后续告警列表页、告警中心、表格展示。
    """
    page = parse_positive_int(request.args.get("page"), 1, "page")
    size = parse_positive_int(request.args.get("size"), 10, "size")

    # 为保证最小可运行版本的稳定性，这里限制最大分页大小，避免一次查询过大。
    size = min(size, 100)

    alerts_data = graph_service.list_alerts(
        page=page,
        size=size,
        status=request.args.get("status"),
        severity=request.args.get("severity"),
        keyword=request.args.get("keyword"),
    )
    return success_response(data=alerts_data, message="告警列表获取成功")
