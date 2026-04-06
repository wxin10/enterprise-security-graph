#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import annotations

from flask import request

from app.core.errors import APIError
from app.services.auth_service import auth_service


def resolve_request_session_token() -> str:
    authorization_value = str(request.headers.get("Authorization") or "").strip()
    x_session_token = str(request.headers.get("X-Session-Token") or "").strip()

    if authorization_value.lower().startswith("bearer "):
        return authorization_value[7:].strip()

    return x_session_token


def require_current_user(*, roles: list[str] | None = None) -> dict:
    session_payload = auth_service.get_current_session(resolve_request_session_token())
    current_user = session_payload["user"]

    if roles and current_user.get("role") not in roles:
        raise APIError(message="当前账号无权执行该操作", code=4030, http_status=403)

    return current_user
