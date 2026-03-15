#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
文件路径：scripts/adapters/safe_line_waf_adapter.py

文件作用：
1. 解析雷池 WAF 导出的日志文件。
2. 将雷池日志字段映射为系统统一中间字段。
3. 对单条解析失败的记录进行容错，避免整个文件处理失败。

当前支持的最小可运行格式：
1. JSON Lines（推荐）
2. JSON 数组

样例字段兼容范围：
1. timestamp / time / event_time
2. src_ip / client_ip / remote_addr
3. dst_ip / server_ip / local_addr
4. dst_port / server_port / local_port
5. hostname / host / target_host / site
6. event_type / attack_type / rule / threat_type
7. severity
8. status / disposition / action_result
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

from adapters.common import (
    build_raw_log_id,
    build_session_hint,
    build_synthetic_username,
    build_unified_record,
    infer_protocol_from_port,
    infer_severity_from_status,
    normalize_iso_datetime,
    normalize_text,
    normalize_upper_text,
    parse_json_records,
    safe_float,
    safe_int,
    severity_to_risk_score,
)


ADAPTER_NAME = "safe_line_waf_adapter"
SOURCE_KEY = "safeline_waf"


def _resolve_field(raw_record: Dict[str, Any], *candidate_keys: str) -> Any:
    """
    从多个候选字段中取第一个非空值。
    """
    for key_name in candidate_keys:
        if key_name in raw_record and normalize_text(raw_record.get(key_name)):
            return raw_record.get(key_name)
    return ""


def parse_file(file_path: Path) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    解析雷池 WAF 日志文件。

    返回值：
    1. records：统一格式记录列表
    2. errors：单条记录解析错误信息列表
    """
    records: List[Dict[str, Any]] = []
    errors: List[str] = []

    try:
        raw_records = parse_json_records(file_path)
    except Exception as exc:
        raise ValueError(f"雷池 WAF 日志解析失败：{exc}") from exc

    for index, raw_record in enumerate(raw_records, start=1):
        try:
            event_time = normalize_iso_datetime(
                _resolve_field(raw_record, "timestamp", "time", "event_time", "@timestamp")
            )
            src_ip = normalize_text(_resolve_field(raw_record, "src_ip", "client_ip", "remote_addr", "client"))
            dst_ip = normalize_text(_resolve_field(raw_record, "dst_ip", "server_ip", "local_addr", "server"))
            dst_port = safe_int(_resolve_field(raw_record, "dst_port", "server_port", "local_port", "port"))
            src_port = safe_int(_resolve_field(raw_record, "src_port", "client_port", "remote_port"))
            hostname = normalize_upper_text(_resolve_field(raw_record, "hostname", "host", "target_host", "site"))
            event_type = normalize_upper_text(
                _resolve_field(raw_record, "event_type", "attack_type", "rule", "threat_type", "attack")
            )
            status = normalize_upper_text(
                _resolve_field(raw_record, "status", "disposition", "action_result", "blocked")
            )
            severity = normalize_upper_text(_resolve_field(raw_record, "severity", "level")) or infer_severity_from_status(
                status,
                "HIGH",
            )
            username = normalize_text(_resolve_field(raw_record, "username", "user", "account"))
            if not username:
                username = build_synthetic_username(SOURCE_KEY, src_ip)

            action = normalize_upper_text(_resolve_field(raw_record, "action", "method", "http_method")) or "HTTP_REQUEST"
            protocol = normalize_upper_text(_resolve_field(raw_record, "protocol")) or infer_protocol_from_port(dst_port, "HTTP")
            raw_message = normalize_text(raw_record.get("raw_message"))
            if not raw_message:
                raw_message = json.dumps(raw_record, ensure_ascii=False)

            raw_log_id = build_raw_log_id(SOURCE_KEY, file_path, index, event_time or f"line-{index}")
            session_hint = build_session_hint(SOURCE_KEY, event_time, src_ip, dst_ip, dst_port or "", username)

            unified_record = build_unified_record(
                {
                    "raw_log_id": raw_log_id,
                    "session_hint": session_hint,
                    "log_source": "SAFELINE_WAF",
                    "log_type": "WAF",
                    "event_time": event_time,
                    "username": username,
                    "src_ip": src_ip,
                    "src_port": src_port or "",
                    "dst_ip": dst_ip,
                    "dst_port": dst_port or "",
                    "hostname": hostname,
                    "protocol": protocol,
                    "action": action,
                    "event_type": event_type or "WAF_ATTACK",
                    "severity": severity,
                    "status": status or "BLOCKED",
                    "raw_message": raw_message,
                    "confidence": safe_float(_resolve_field(raw_record, "confidence", "score_confidence"), 0.9),
                    "risk_score_hint": severity_to_risk_score(severity, status, event_type),
                }
            )
            records.append(unified_record)
        except Exception as exc:
            errors.append(f"{file_path.name} 第 {index} 条记录解析失败：{exc}")

    return records, errors
