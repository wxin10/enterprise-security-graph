#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
文件路径：backend/app/services/auth_service.py

文件作用：
1. 提供控制台登录与当前会话查询的后端服务能力。
2. 维护当前阶段的后端内存态会话，为前端切换到真实登录接口提供最小闭环。
3. 统一复用当前前端既有账号口径和用户结构，避免前后端账号模型再次分叉。

当前阶段说明：
1. 本服务不接数据库，也不引入完整权限中心。
2. 当前阶段采用“固定账号映射 + 后端内存态会话”的轻量实现。
3. 该实现的目标是补齐真实后端登录接口闭环，而不是直接替代未来的生产级统一鉴权系统。
"""

from __future__ import annotations

import secrets
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from app.core.errors import APIError, ValidationError


class AuthenticationError(APIError):
    """
    登录鉴权异常。

    设计原因：
    1. 登录失败、令牌缺失、令牌过期都属于鉴权失败场景。
    2. 继续复用全局异常处理器，保证返回结构与现有接口风格一致。
    """

    def __init__(self, message: str = "登录状态无效或已过期", code: int = 4010, data=None, http_status: int = 401):
        super().__init__(message=message, code=code, http_status=http_status, data=data)


class AuthService:
    """
    控制台登录服务。

    当前阶段支持的最小能力：
    1. 账号密码登录。
    2. 生成后端会话令牌。
    3. 根据会话令牌查询当前登录用户。
    """

    SESSION_TTL_SECONDS = 8 * 60 * 60

    # 账号模板严格复用当前前端 auth.js 的用户结构口径。
    # 这样下一轮前端切换到后端登录时，不需要再额外改用户字段映射。
    ACCOUNT_TEMPLATES = {
        "admin": {
            "password": "123456",
            "user": {
                "user_id": "ADMIN-001",
                "username": "admin",
                "display_name": "平台管理员",
                "department": "安全运营中心",
                "title": "高权限运维负责人",
                "role": "admin",
            },
        },
        "analyst": {
            "password": "123456",
            "user": {
                "user_id": "OPS-001",
                "username": "analyst",
                "display_name": "值班分析员",
                "department": "安全运营中心",
                "title": "一线运维 / 安全分析员",
                "role": "user",
            },
        },
        "user": {
            "password": "123456",
            "user": {
                "user_id": "OPS-002",
                "username": "user",
                "display_name": "一线运维人员",
                "department": "安全运营中心",
                "title": "一线运维 / 安全分析员",
                "role": "user",
            },
        },
    }

    def __init__(self):
        # 当前阶段会话仅保存在后端进程内存中。
        # 这意味着服务重启后令牌会失效，这是当前“最小真实闭环”允许接受的边界。
        self._session_store: Dict[str, Dict[str, Any]] = {}

    def login(self, username: str, password: str) -> Dict[str, Any]:
        """
        执行登录并生成后端会话。
        """
        normalized_username = self._normalize_username(username)
        normalized_password = self._normalize_password(password)

        if not normalized_username:
            raise ValidationError("username 不能为空", data={"field": "username"})

        if not normalized_password:
            raise ValidationError("password 不能为空", data={"field": "password"})

        account_profile = self.ACCOUNT_TEMPLATES.get(normalized_username)
        if not account_profile:
            raise AuthenticationError(
                message="账号不存在或当前账号无权限进入系统",
                code=4011,
                data={"field": "username"},
            )

        if normalized_password != account_profile["password"]:
            raise AuthenticationError(
                message="账号或密码错误",
                code=4012,
                data={"field": "password"},
            )

        self._cleanup_expired_sessions()

        issued_at = self._now()
        expires_at = issued_at + timedelta(seconds=self.SESSION_TTL_SECONDS)
        session_token = self._build_session_token()
        current_user = self._build_login_user(account_profile["user"], issued_at)

        self._session_store[session_token] = {
            "session_token": session_token,
            "user": deepcopy(current_user),
            "issued_at": self._serialize_datetime(issued_at),
            "expires_at": self._serialize_datetime(expires_at),
        }

        return {
            "session_token": session_token,
            "token_type": "Bearer",
            "expires_in": self.SESSION_TTL_SECONDS,
            "issued_at": self._serialize_datetime(issued_at),
            "expires_at": self._serialize_datetime(expires_at),
            "user": deepcopy(current_user),
        }

    def get_current_session(self, session_token: str) -> Dict[str, Any]:
        """
        根据令牌返回当前登录会话。
        """
        normalized_token = self._normalize_token(session_token)
        if not normalized_token:
            raise AuthenticationError(message="未提供登录令牌", code=4013)

        self._cleanup_expired_sessions()

        session_payload = self._session_store.get(normalized_token)
        if not session_payload:
            raise AuthenticationError(message="登录状态无效或已过期", code=4014)

        return {
            "session_token": session_payload["session_token"],
            "token_type": "Bearer",
            "issued_at": session_payload["issued_at"],
            "expires_at": session_payload["expires_at"],
            "user": deepcopy(session_payload["user"]),
        }

    def _cleanup_expired_sessions(self) -> None:
        """
        清理已过期的内存态会话。

        设计说明：
        1. 当前阶段不用单独引入定时任务。
        2. 在登录和查询当前用户时顺带清理即可，足以满足最小闭环需求。
        """
        now = self._now()
        expired_tokens = []

        for token, session_payload in self._session_store.items():
            expires_at = self._parse_datetime(session_payload.get("expires_at"))
            if expires_at <= now:
                expired_tokens.append(token)

        for token in expired_tokens:
            self._session_store.pop(token, None)

    def _build_login_user(self, account_user: Dict[str, Any], issued_at: datetime) -> Dict[str, Any]:
        """
        构造登录成功后的用户对象。

        说明：
        1. 返回字段与前端现有会话结构保持兼容。
        2. 额外补充 login_at，便于前端后续直接复用当前展示逻辑。
        """
        return {
            **deepcopy(account_user),
            "login_at": self._serialize_datetime(issued_at),
        }

    def _build_session_token(self) -> str:
        """
        生成当前阶段的轻量会话令牌。
        """
        return f"esg_{secrets.token_urlsafe(24)}"

    def _normalize_username(self, username: Any) -> str:
        """
        统一规范化账号名。
        """
        return str(username or "").strip().lower()

    def _normalize_password(self, password: Any) -> str:
        """
        统一规范化密码字符串。
        """
        return str(password or "").strip()

    def _normalize_token(self, session_token: Any) -> str:
        """
        统一规范化会话令牌。
        """
        return str(session_token or "").strip()

    def _now(self) -> datetime:
        """
        返回当前 UTC 时间。
        """
        return datetime.now(timezone.utc)

    def _serialize_datetime(self, value: datetime) -> str:
        """
        序列化时间，统一使用 ISO 8601 字符串。
        """
        return value.isoformat(timespec="seconds")

    def _parse_datetime(self, value: Any) -> datetime:
        """
        解析已序列化的时间字符串。
        """
        try:
            return datetime.fromisoformat(str(value))
        except (TypeError, ValueError) as exc:
            raise AuthenticationError(message="后端会话时间格式异常", code=5002) from exc


auth_service = AuthService()
