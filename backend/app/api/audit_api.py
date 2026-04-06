#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import annotations

from flask import Blueprint

from app.api.auth_guard import require_current_user
from app.core.response import success_response
from app.services.governance_service import governance_service


audit_api_bp = Blueprint("audit_api", __name__)


@audit_api_bp.get("/audit/logs")
def get_audit_logs():
    require_current_user(roles=["admin"])
    data = governance_service.list_audit_logs()
    return success_response(data=data, message="审计日志获取成功")


@audit_api_bp.get("/audit/logs/<audit_id>")
def get_audit_log_detail(audit_id: str):
    require_current_user(roles=["admin"])
    data = governance_service.get_audit_log(audit_id)
    return success_response(data=data, message="审计详情获取成功")
