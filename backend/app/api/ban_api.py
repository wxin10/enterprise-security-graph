#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
文件路径：backend/app/api/ban_api.py

文件作用：
1. 提供封禁与处置相关接口蓝图。
2. 复用 graph_service 中已有的封禁动作查询逻辑。
3. 对外暴露封禁处置列表接口。
"""

from __future__ import annotations

from flask import Blueprint, request

from app.core.errors import ValidationError
from app.core.response import success_response
from app.services import graph_service


ban_api_bp = Blueprint("ban_api", __name__)


def parse_positive_int(value: str | None, default_value: int, field_name: str) -> int:
    """
    解析分页参数。

    设计原因：
    1. 封禁动作列表接口支持分页。
    2. 参数错误时统一进入全局异常处理，保持 JSON 返回结构一致。
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


@ban_api_bp.get("/bans")
def get_bans():
    """
    接口：GET /api/bans

    作用：
    1. 返回封禁或处置动作列表。
    2. 支持按动作状态和目标 IP 查询。
    3. 适合后续封禁管理页、联动处置页和审计展示。
    """
    page = parse_positive_int(request.args.get("page"), 1, "page")
    size = parse_positive_int(request.args.get("size"), 10, "size")
    size = min(size, 100)

    bans_data = graph_service.list_bans(
        page=page,
        size=size,
        status=request.args.get("status"),
        target_ip=request.args.get("target_ip"),
    )
    return success_response(data=bans_data, message="封禁处置列表获取成功")
