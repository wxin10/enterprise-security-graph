#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
文件路径：backend/app/api/auth_api.py

文件作用：
1. 提供控制台登录和当前用户查询接口。
2. 复用 auth_service 的后端持久化会话能力，补齐真实登录闭环。
3. 为前端刷新恢复登录态与后端重启后的会话续用提供稳定接口入口。
"""

from __future__ import annotations

from flask import Blueprint, request

from app.core.response import success_response
from app.services.auth_service import auth_service
from app.core.errors import ValidationError


auth_api_bp = Blueprint("auth_api", __name__)


def parse_login_payload() -> dict:
    """
    解析登录请求体。

    说明：
    1. 当前接口只接受 JSON 请求体。
    2. 若字段缺失或为空，统一抛出 ValidationError，由全局异常处理返回标准 JSON。
    """
    request_payload = request.get_json(silent=True)
    if not isinstance(request_payload, dict):
        raise ValidationError("登录请求体必须为 JSON 对象")

    username = str(request_payload.get("username") or "").strip()
    password = str(request_payload.get("password") or "").strip()

    if not username:
        raise ValidationError("username 不能为空", data={"field": "username"})

    if not password:
        raise ValidationError("password 不能为空", data={"field": "password"})

    return {
        "username": username,
        "password": password,
    }


def resolve_session_token() -> str:
    """
    从请求头中提取当前会话令牌。

    当前支持两种传递方式：
    1. Authorization: Bearer <token>
    2. X-Session-Token: <token>

    这样做的原因：
    1. 兼容后续前端按标准 Bearer 方式接入。
    2. 也便于当前阶段用简单请求工具直接联调。
    """
    authorization_value = str(request.headers.get("Authorization") or "").strip()
    x_session_token = str(request.headers.get("X-Session-Token") or "").strip()

    if authorization_value.lower().startswith("bearer "):
        return authorization_value[7:].strip()

    return x_session_token


@auth_api_bp.post("/auth/login")
def login():
    """
    接口：POST /api/auth/login

    作用：
    1. 接收 username、password。
    2. 在后端校验账号口径并创建当前阶段的会话令牌。
    3. 返回 session_token 和兼容前端结构的 user 数据。
    """
    login_payload = parse_login_payload()
    login_result = auth_service.login(
        username=login_payload["username"],
        password=login_payload["password"],
    )
    return success_response(data=login_result, message="控制台登录成功")


@auth_api_bp.get("/auth/me")
def get_current_user():
    """
    接口：GET /api/auth/me

    作用：
    1. 根据请求头中的 token 返回当前登录用户。
    2. 为下一轮前端“刷新页面后恢复登录态”提供真实后端接口基础。
    """
    session_token = resolve_session_token()
    session_payload = auth_service.get_current_session(session_token)
    return success_response(data=session_payload, message="当前登录用户获取成功")
