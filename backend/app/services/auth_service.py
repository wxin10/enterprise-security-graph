#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import annotations

import json
import os
import secrets
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import RLock
from typing import Any

from app.core.errors import APIError, ValidationError
from app.services.governance_service import governance_service


class AuthenticationError(APIError):
    def __init__(self, message: str = "登录状态无效或已过期", code: int = 4010, data=None, http_status: int = 401):
        super().__init__(message=message, code=code, http_status=http_status, data=data)


class AuthService:
    SESSION_TTL_SECONDS = 8 * 60 * 60
    DEFAULT_SESSION_FILE_PATH = Path(__file__).resolve().parents[1] / "data" / "session_state.json"
    SESSION_FILE_PATH = DEFAULT_SESSION_FILE_PATH
    SESSION_FILE_ENV = "SESSION_STATE_FILE"

    def __init__(self) -> None:
        self._lock = RLock()
        self._ensure_session_file()
        self._session_store: dict[str, dict[str, Any]] = self._load_session_store()

    def login(self, username: str, password: str) -> dict[str, Any]:
        normalized_username = self._normalize_username(username)
        normalized_password = self._normalize_password(password)

        if not normalized_username:
            raise ValidationError("username 不能为空", data={"field": "username"})
        if not normalized_password:
            raise ValidationError("password 不能为空", data={"field": "password"})

        account_profile = governance_service.get_login_user(normalized_username)
        if not account_profile:
            raise AuthenticationError(
                message="账号不存在或当前账号无权进入系统",
                code=4011,
                data={"field": "username"},
            )

        if account_profile.get("status") != "启用":
            raise AuthenticationError(
                message="当前账号未启用，暂时无法登录",
                code=4015,
                data={"field": "username"},
            )

        if not governance_service.verify_password(normalized_password, account_profile):
            raise AuthenticationError(
                message="账号或密码错误",
                code=4012,
                data={"field": "password"},
            )

        self._cleanup_expired_sessions()

        issued_at = self._now()
        expires_at = issued_at + timedelta(seconds=self.SESSION_TTL_SECONDS)
        session_token = self._build_session_token()
        current_user = governance_service.mark_user_login(
            account_profile["user_id"],
            self._serialize_local_datetime(issued_at),
        )
        auth_user = governance_service.get_auth_user_by_id(current_user["user_id"]) or account_profile

        session_payload = {
            "session_token": session_token,
            "user_id": current_user["user_id"],
            "username": auth_user.get("username") or normalized_username,
            "password_updated_at": self._resolve_password_version(auth_user),
            "user": deepcopy(current_user),
            "issued_at": self._serialize_datetime(issued_at),
            "expires_at": self._serialize_datetime(expires_at),
        }

        with self._lock:
            self._session_store[session_token] = session_payload
            self._save_session_store()

        return {
            "session_token": session_token,
            "token_type": "Bearer",
            "expires_in": self.SESSION_TTL_SECONDS,
            "issued_at": session_payload["issued_at"],
            "expires_at": session_payload["expires_at"],
            "user": deepcopy(current_user),
        }

    def get_current_session(self, session_token: str) -> dict[str, Any]:
        normalized_token = self._normalize_token(session_token)
        if not normalized_token:
            raise AuthenticationError(message="未提供登录令牌", code=4013)

        self._cleanup_expired_sessions()

        with self._lock:
            session_payload = deepcopy(self._session_store.get(normalized_token))

        if not session_payload:
            raise AuthenticationError(message="登录状态无效或已过期", code=4014)

        auth_user = governance_service.get_auth_user_by_id(session_payload["user_id"])
        if not auth_user or auth_user.get("status") != "启用":
            self._invalidate_session(normalized_token)
            raise AuthenticationError(message="当前账号已停用或不存在", code=4016)

        current_password_version = self._resolve_password_version(auth_user)
        if session_payload.get("password_updated_at") != current_password_version:
            self._invalidate_session(normalized_token)
            raise AuthenticationError(message="登录状态已失效，请重新登录", code=4017)

        current_user = governance_service.get_public_user_by_id(session_payload["user_id"])
        if not current_user:
            self._invalidate_session(normalized_token)
            raise AuthenticationError(message="当前账号已停用或不存在", code=4016)

        return {
            "session_token": session_payload["session_token"],
            "token_type": "Bearer",
            "issued_at": session_payload["issued_at"],
            "expires_at": session_payload["expires_at"],
            "user": deepcopy(current_user),
        }

    def _cleanup_expired_sessions(self) -> None:
        now = self._now()
        expired_tokens: list[str] = []

        with self._lock:
            for token, session_payload in self._session_store.items():
                expires_at = self._parse_datetime(session_payload.get("expires_at"))
                if expires_at <= now:
                    expired_tokens.append(token)

            if not expired_tokens:
                return

            for token in expired_tokens:
                self._session_store.pop(token, None)

            self._save_session_store()

    def _invalidate_session(self, session_token: str) -> None:
        with self._lock:
            if session_token not in self._session_store:
                return

            self._session_store.pop(session_token, None)
            self._save_session_store()

    def _ensure_session_file(self) -> None:
        session_file_path = self._get_session_file_path()
        with self._lock:
            session_file_path.parent.mkdir(parents=True, exist_ok=True)
            if session_file_path.exists():
                return

            session_file_path.write_text(
                json.dumps({"sessions": []}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

    def _load_session_store(self) -> dict[str, dict[str, Any]]:
        session_file_path = self._get_session_file_path()
        with self._lock:
            self._ensure_session_file()
            raw_text = session_file_path.read_text(encoding="utf-8").strip() or '{"sessions": []}'
            payload = json.loads(raw_text)
            sessions = payload.get("sessions") or []

            return {
                str(item.get("session_token") or "").strip(): deepcopy(item)
                for item in sessions
                if str(item.get("session_token") or "").strip()
            }

    def _save_session_store(self) -> None:
        session_file_path = self._get_session_file_path()
        data = {
            "sessions": sorted(
                [deepcopy(item) for item in self._session_store.values()],
                key=lambda item: str(item.get("issued_at") or ""),
                reverse=True,
            )
        }
        temp_path = session_file_path.with_suffix(".tmp")
        temp_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        temp_path.replace(session_file_path)

    def _resolve_password_version(self, user: dict[str, Any]) -> str:
        return str(user.get("password_updated_at") or user.get("updated_at") or user.get("created_at") or "").strip()

    def _build_session_token(self) -> str:
        return f"esg_{secrets.token_urlsafe(24)}"

    def _normalize_username(self, username: Any) -> str:
        return str(username or "").strip().lower()

    def _normalize_password(self, password: Any) -> str:
        return str(password or "").strip()

    def _normalize_token(self, session_token: Any) -> str:
        return str(session_token or "").strip()

    def _get_session_file_path(self) -> Path:
        env_value = str(os.getenv(self.SESSION_FILE_ENV, "") or "").strip()
        if env_value:
            return Path(env_value)
        return Path(self.SESSION_FILE_PATH or self.DEFAULT_SESSION_FILE_PATH)

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def _serialize_datetime(self, value: datetime) -> str:
        return value.isoformat(timespec="seconds")

    def _serialize_local_datetime(self, value: datetime) -> str:
        return value.astimezone().strftime("%Y-%m-%d %H:%M:%S")

    def _parse_datetime(self, value: Any) -> datetime:
        try:
            return datetime.fromisoformat(str(value))
        except (TypeError, ValueError) as exc:
            raise AuthenticationError(message="后端会话时间格式异常", code=5002) from exc


auth_service = AuthService()
