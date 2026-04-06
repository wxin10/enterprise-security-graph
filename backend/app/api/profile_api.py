#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import annotations

from flask import Blueprint, request

from app.api.auth_guard import require_current_user
from app.core.response import success_response
from app.services.governance_service import governance_service


profile_api_bp = Blueprint("profile_api", __name__)


@profile_api_bp.get("/profile")
def get_profile():
    current_user = require_current_user()
    data = governance_service.get_profile(current_user["user_id"])
    return success_response(data=data, message="个人资料获取成功")


@profile_api_bp.patch("/profile")
def update_profile():
    current_user = require_current_user()
    payload = request.get_json(silent=True) or {}
    data = governance_service.update_profile(current_user["user_id"], payload)
    return success_response(data=data, message="个人资料更新成功")
