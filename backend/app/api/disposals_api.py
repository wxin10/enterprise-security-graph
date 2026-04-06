#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import annotations

from flask import Blueprint, request

from app.api.auth_guard import require_current_user
from app.core.response import success_response
from app.services.governance_service import governance_service


disposals_api_bp = Blueprint("disposals_api", __name__)


@disposals_api_bp.get("/disposals")
def get_disposals():
    current_user = require_current_user(roles=["admin"])
    data = governance_service.list_disposals(current_user, own_only=False)
    return success_response(data=data, message="处置申请列表获取成功")


@disposals_api_bp.post("/disposals")
def create_disposal():
    current_user = require_current_user()
    payload = request.get_json(silent=True) or {}
    data = governance_service.create_disposal(payload, current_user)
    return success_response(data=data, message="处置申请提交成功")


@disposals_api_bp.get("/disposals/my")
def get_my_disposals():
    current_user = require_current_user()
    data = governance_service.list_disposals(current_user, own_only=True)
    return success_response(data=data, message="个人处置记录获取成功")


@disposals_api_bp.patch("/disposals/<request_id>")
def update_disposal(request_id: str):
    current_user = require_current_user(roles=["admin"])
    payload = request.get_json(silent=True) or {}
    data = governance_service.update_disposal(request_id, payload, current_user)
    return success_response(data=data, message="处置申请状态已更新")
