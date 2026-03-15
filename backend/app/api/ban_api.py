#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
文件路径：backend/app/api/ban_api.py

文件作用：
1. 提供封禁管理相关接口蓝图。
2. 暴露封禁列表、封禁详情和放行 / 解封接口。
3. 通过 ban_service 统一处理状态查询与放行逻辑，避免将业务逻辑直接写在路由层。
"""

from __future__ import annotations

from flask import Blueprint, request

from app.core.errors import ValidationError
from app.core.response import success_response
from app.services import ban_service


ban_api_bp = Blueprint("ban_api", __name__)


def parse_positive_int(value: str | None, default_value: int, field_name: str) -> int:
    """
    解析分页参数。
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


def parse_release_payload() -> dict:
    """
    解析放行请求体。

    当前最小版本支持：
    1. release_reason：放行原因。
    2. released_by：放行执行人。
    """
    request_payload = request.get_json(silent=True) or {}
    release_reason = str(request_payload.get("release_reason") or "").strip()
    released_by = str(request_payload.get("released_by") or "").strip()

    return {
        "release_reason": release_reason or "人工复核后确认放行",
        "released_by": released_by or "security_console",
    }


@ban_api_bp.get("/bans")
def get_bans():
    """
    接口：GET /api/bans

    作用：
    1. 返回封禁 / 放行记录列表。
    2. 支持按状态和目标 IP 进行筛选。
    3. 返回结果兼容当前前端封禁管理页，同时补充放行所需新字段。
    """
    page = parse_positive_int(request.args.get("page"), 1, "page")
    size = parse_positive_int(request.args.get("size"), 10, "size")
    size = min(size, 100)

    bans_data = ban_service.list_bans(
        page=page,
        size=size,
        status=request.args.get("status"),
        target_ip=request.args.get("target_ip"),
    )
    return success_response(data=bans_data, message="封禁处置列表获取成功")


@ban_api_bp.get("/bans/<ban_id>")
def get_ban_detail(ban_id: str):
    """
    接口：GET /api/bans/<ban_id>

    作用：
    1. 返回单条封禁记录详情。
    2. 供前端未来扩展详情弹窗或审计页复用。
    """
    ban_detail = ban_service.get_ban_detail(ban_id)
    return success_response(data=ban_detail, message="封禁记录详情获取成功")


@ban_api_bp.post("/bans/<ban_id>/unban")
def unban_ban(ban_id: str):
    """
    接口：POST /api/bans/<ban_id>/unban

    作用：
    1. 对指定封禁记录执行放行 / 解封。
    2. 重复放行具备幂等性，不直接抛出 500。
    3. 返回最新记录，便于前端操作成功后立即刷新页面状态。
    """
    payload = parse_release_payload()
    result = ban_service.unban(
        ban_id=ban_id,
        release_reason=payload["release_reason"],
        released_by=payload["released_by"],
    )

    response_message = result.get("message") or "放行操作已完成"
    return success_response(data=result, message=response_message)
