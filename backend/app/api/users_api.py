#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import annotations

from flask import Blueprint, request

from app.api.auth_guard import require_current_user
from app.core.response import success_response
from app.services.governance_service import governance_service


users_api_bp = Blueprint("users_api", __name__)


@users_api_bp.get("/users")
def get_users():
    require_current_user(roles=["admin"])
    data = governance_service.list_users()
    return success_response(data=data, message="用户列表获取成功")


@users_api_bp.post("/users")
def create_user():
    current_user = require_current_user(roles=["admin"])
    payload = request.get_json(silent=True) or {}
    data = governance_service.create_user(payload, current_user)
    return success_response(data=data, message="用户创建成功")


@users_api_bp.patch("/users/<user_id>")
def update_user(user_id: str):
    current_user = require_current_user(roles=["admin"])
    payload = request.get_json(silent=True) or {}
    data = governance_service.update_user(user_id, payload, current_user)
    return success_response(data=data, message="用户资料更新成功")


@users_api_bp.post("/users/<user_id>/reset-password")
def reset_password(user_id: str):
    current_user = require_current_user(roles=["admin"])
    data = governance_service.reset_user_password(user_id, current_user)
    return success_response(data=data, message="用户密码已重置")


@users_api_bp.post("/users/<user_id>/toggle-status")
def toggle_user_status(user_id: str):
    current_user = require_current_user(roles=["admin"])
    data = governance_service.toggle_user_status(user_id, current_user)
    return success_response(data=data, message="用户状态已更新")
