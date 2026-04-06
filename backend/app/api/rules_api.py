#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import annotations

from flask import Blueprint, request

from app.api.auth_guard import require_current_user
from app.core.response import success_response
from app.services.governance_service import governance_service


rules_api_bp = Blueprint("rules_api", __name__)


@rules_api_bp.get("/rules")
def get_rules():
    require_current_user(roles=["admin"])
    data = governance_service.list_rules()
    return success_response(data=data, message="规则列表获取成功")


@rules_api_bp.post("/rules")
def create_rule():
    current_user = require_current_user(roles=["admin"])
    payload = request.get_json(silent=True) or {}
    data = governance_service.create_rule(payload, current_user)
    return success_response(data=data, message="规则创建成功")


@rules_api_bp.patch("/rules/<rule_id>")
def update_rule(rule_id: str):
    current_user = require_current_user(roles=["admin"])
    payload = request.get_json(silent=True) or {}
    data = governance_service.update_rule(rule_id, payload, current_user)
    return success_response(data=data, message="规则更新成功")


@rules_api_bp.post("/rules/<rule_id>/gray-release")
def gray_release_rule(rule_id: str):
    current_user = require_current_user(roles=["admin"])
    payload = request.get_json(silent=True) or {}
    data = governance_service.gray_release_rule(rule_id, payload, current_user)
    return success_response(data=data, message="规则已进入灰度发布")


@rules_api_bp.post("/rules/<rule_id>/toggle-status")
def toggle_rule_status(rule_id: str):
    current_user = require_current_user(roles=["admin"])
    data = governance_service.toggle_rule_status(rule_id, current_user)
    return success_response(data=data, message="规则状态已更新")
