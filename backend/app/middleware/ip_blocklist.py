#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
文件路径：backend/app/middleware/ip_blocklist.py

文件作用：
1. 提供 WEB_BLOCKLIST 模式下的最小真实阻断能力。
2. 维护本地 blocklist.json，用于保存当前被拦截的源 IP。
3. 在 Flask 请求进入时执行 IP 检查，命中 blocklist 时直接返回 403 JSON。

设计说明：
1. 这是一个“最小可运行、最容易验证”的真实阻断方案，不依赖管理员权限，也不依赖系统防火墙。
2. 为了便于本地答辩演示，优先读取 X-Client-IP / X-Forwarded-For，再回退到 remote_addr。
3. blocklist 文件只负责“当前生效阻断列表”，审计历史仍由 Neo4j 中的 BlockAction 维护。
"""

from __future__ import annotations

import ipaddress
import json
from datetime import datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Dict, Optional, Tuple

from flask import Flask, current_app, request

from app.core.response import error_response


def build_now_text() -> str:
    """
    构造本地时区时间字符串。

    说明：
    1. blocklist 文件主要用于本地演示和运行态排查。
    2. 使用本地时区时间更直观，便于和前端展示时间对应。
    """
    return datetime.now().astimezone().isoformat(timespec="seconds")


def normalize_ip_text(value: Any) -> str:
    """
    规范化 IP 文本，并过滤非法输入。

    返回规则：
    1. 合法 IP 返回规范化后的字符串。
    2. 非法值返回空字符串，避免把脏数据写入 blocklist。
    """
    raw_text = str(value or "").strip()
    if not raw_text:
        return ""

    try:
        return str(ipaddress.ip_address(raw_text))
    except ValueError:
        return ""


def ensure_blocklist_file(file_path: str | Path) -> Path:
    """
    确保 blocklist 文件存在。

    初始化结构：
    1. blocked_ips：当前生效的阻断 IP 字典。
    2. updated_at：最后更新时间，便于排查。
    """
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    if not path.exists():
        payload = {
            "blocked_ips": {},
            "updated_at": build_now_text(),
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    return path


def load_blocklist(file_path: str | Path) -> Dict[str, Any]:
    """
    读取 blocklist 文件。

    容错策略：
    1. 文件不存在时自动初始化。
    2. 文件损坏时自动回退到空结构，避免整个后端因单个 JSON 文件损坏而崩溃。
    """
    path = ensure_blocklist_file(file_path)

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        payload = {}

    if not isinstance(payload, dict):
        payload = {}

    blocked_ips = payload.get("blocked_ips")
    if not isinstance(blocked_ips, dict):
        blocked_ips = {}

    return {
        "blocked_ips": blocked_ips,
        "updated_at": str(payload.get("updated_at") or build_now_text()),
    }


def save_blocklist(file_path: str | Path, payload: Dict[str, Any]) -> None:
    """
    原子写回 blocklist 文件。

    设计原因：
    1. 直接覆盖文件时，若中途写入失败，可能导致 blocklist 变成损坏 JSON。
    2. 这里使用临时文件 + replace，尽量降低写入中断导致的数据损坏风险。
    """
    path = ensure_blocklist_file(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    normalized_payload = {
        "blocked_ips": payload.get("blocked_ips") if isinstance(payload.get("blocked_ips"), dict) else {},
        "updated_at": str(payload.get("updated_at") or build_now_text()),
    }

    with NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=str(path.parent)) as temp_file:
        temp_file.write(json.dumps(normalized_payload, ensure_ascii=False, indent=2))
        temp_name = temp_file.name

    Path(temp_name).replace(path)


def add_ip_to_blocklist(file_path: str | Path, target_ip: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    把目标 IP 写入 blocklist。

    返回结果：
    1. blocked：当前是否已处于阻断状态。
    2. existed：本次写入前是否已经存在。
    3. entry：最终写入后的 blocklist 条目。
    """
    normalized_ip = normalize_ip_text(target_ip)
    if not normalized_ip:
        raise ValueError("目标 IP 非法，无法加入 WEB_BLOCKLIST")

    payload = load_blocklist(file_path)
    blocked_ips = payload["blocked_ips"]
    existing_entry = blocked_ips.get(normalized_ip)
    metadata = metadata or {}

    entry = {
        "target_ip": normalized_ip,
        "ban_id": str(metadata.get("ban_id") or ""),
        "blocked_at": str(metadata.get("blocked_at") or build_now_text()),
        "reason": str(metadata.get("reason") or ""),
        "operator": str(metadata.get("operator") or "security_console"),
        "mode": "WEB_BLOCKLIST",
        "updated_at": build_now_text(),
    }
    blocked_ips[normalized_ip] = entry
    payload["updated_at"] = build_now_text()
    save_blocklist(file_path, payload)

    return {
        "blocked": True,
        "existed": existing_entry is not None,
        "entry": entry,
    }


def remove_ip_from_blocklist(file_path: str | Path, target_ip: str) -> Dict[str, Any]:
    """
    把目标 IP 从 blocklist 中移除。

    返回结果：
    1. removed：是否已经按“放行成功”处理。
    2. existed：本次移除前条目是否存在。
    """
    normalized_ip = normalize_ip_text(target_ip)
    if not normalized_ip:
        raise ValueError("目标 IP 非法，无法从 WEB_BLOCKLIST 中移除")

    payload = load_blocklist(file_path)
    blocked_ips = payload["blocked_ips"]
    existed = normalized_ip in blocked_ips
    if existed:
        blocked_ips.pop(normalized_ip, None)
        payload["updated_at"] = build_now_text()
        save_blocklist(file_path, payload)

    return {
        "removed": True,
        "existed": existed,
    }


def query_blocked_ip(file_path: str | Path, target_ip: str) -> Tuple[bool, Dict[str, Any]]:
    """
    查询某个 IP 当前是否处于 blocklist 中。
    """
    normalized_ip = normalize_ip_text(target_ip)
    if not normalized_ip:
        return False, {}

    payload = load_blocklist(file_path)
    entry = payload["blocked_ips"].get(normalized_ip) or {}
    return bool(entry), entry


def resolve_request_ip() -> str:
    """
    从当前请求中解析客户端 IP。

    优先级：
    1. X-Client-IP：便于本地演示时显式模拟攻击源 IP。
    2. X-Forwarded-For：兼容反向代理或多级转发场景。
    3. remote_addr：没有代理头时回退到真实连接地址。
    """
    header_ip = normalize_ip_text(request.headers.get("X-Client-IP"))
    if header_ip:
        return header_ip

    forwarded_for = str(request.headers.get("X-Forwarded-For") or "").strip()
    if forwarded_for:
        first_ip = forwarded_for.split(",")[0].strip()
        normalized_forwarded_ip = normalize_ip_text(first_ip)
        if normalized_forwarded_ip:
            return normalized_forwarded_ip

    return normalize_ip_text(request.remote_addr)


def register_ip_blocklist_middleware(app: Flask) -> None:
    """
    在 Flask 应用上注册 WEB_BLOCKLIST 拦截逻辑。

    行为说明：
    1. 仅当 BAN_ENFORCEMENT_MODE = WEB_BLOCKLIST 时启用。
    2. 命中 blocklist 的请求会在业务路由执行前直接返回 403。
    3. 不中断应用启动；如果 blocklist 初始化失败，由接口侧后续抛出明确错误。
    """
    mode = str(app.config.get("BAN_ENFORCEMENT_MODE") or "MOCK").upper()
    blocklist_file = app.config.get("BAN_WEB_BLOCKLIST_FILE")
    if not blocklist_file:
        return

    ensure_blocklist_file(blocklist_file)
    app.extensions["web_blocklist_file"] = str(blocklist_file)

    if mode != "WEB_BLOCKLIST":
        return

    @app.before_request
    def enforce_web_blocklist():
        """
        在每个请求进入时检查当前来源 IP 是否命中 blocklist。
        """
        client_ip = resolve_request_ip()
        if not client_ip:
            return None

        blocked, entry = query_blocked_ip(current_app.config["BAN_WEB_BLOCKLIST_FILE"], client_ip)
        if not blocked:
            return None

        return error_response(
            message="当前源 IP 已被系统阻断，拒绝访问 Flask 服务",
            code=4033,
            http_status=403,
            data={
                "blocked": True,
                "client_ip": client_ip,
                "enforcement_mode": "WEB_BLOCKLIST",
                "ban_id": str(entry.get("ban_id") or ""),
                "blocked_at": str(entry.get("blocked_at") or ""),
                "reason": str(entry.get("reason") or ""),
            },
        )
