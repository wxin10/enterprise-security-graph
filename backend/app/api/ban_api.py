#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
文件路径：backend/app/api/ban_api.py

文件作用：
1. 提供封禁管理相关接口蓝图。
2. 暴露封禁列表、封禁详情、放行 / 解封、重新封禁接口。
3. 通过 ban_service 统一处理当前状态切换与历史动作审计逻辑，避免把业务逻辑堆在路由层。
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


def parse_action_payload(default_reason: str) -> dict:
    """
    解析状态切换请求体。

    当前阶段统一支持：
    1. reason：操作原因，允许前端用 release_reason / block_reason / reason 任一字段传入。
    2. operator：执行人，允许前端用 released_by / blocked_by / operator 任一字段传入。
    """
    request_payload = request.get_json(silent=True) or {}

    reason = str(
        request_payload.get("reason")
        or request_payload.get("release_reason")
        or request_payload.get("block_reason")
        or ""
    ).strip()
    operator = str(
        request_payload.get("operator")
        or request_payload.get("released_by")
        or request_payload.get("blocked_by")
        or ""
    ).strip()

    return {
        "reason": reason or default_reason,
        "operator": operator or "security_console",
    }


@ban_api_bp.get("/bans")
def get_bans():
    """
    接口：GET /api/bans

    作用：
    1. 返回封禁目标的当前状态列表。
    2. 同时附带最近动作与历史动作摘要，便于前端做“状态管理 + 审计展示”。
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
    2. 包含当前状态、最近动作和完整历史动作列表，供详情抽屉复用。
    """
    ban_detail = ban_service.get_ban_detail(ban_id)
    return success_response(data=ban_detail, message="封禁记录详情获取成功")


@ban_api_bp.post("/bans/<ban_id>/unban")
def unban_ban(ban_id: str):
    """
    接口：POST /api/bans/<ban_id>/unban

    作用：
    1. 将当前已封禁目标切换为已放行。
    2. 若目标已经处于放行状态，则返回幂等提示。
    """
    payload = parse_action_payload(default_reason="人工复核后确认放行")
    result = ban_service.unban(
        ban_id=ban_id,
        release_reason=payload["reason"],
        released_by=payload["operator"],
    )
    return success_response(data=result, message=result.get("message") or "放行操作已完成")


@ban_api_bp.post("/bans/<ban_id>/reblock")
def reblock_ban(ban_id: str):
    """
    接口：POST /api/bans/<ban_id>/reblock

    作用：
    1. 将当前已放行目标切换为重新封禁。
    2. 若目标已经处于封禁状态，则返回幂等提示。
    """
    payload = parse_action_payload(default_reason="人工复核后重新封禁")
    result = ban_service.reblock(
        ban_id=ban_id,
        block_reason=payload["reason"],
        blocked_by=payload["operator"],
    )
    return success_response(data=result, message=result.get("message") or "重新封禁操作已完成")
