#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
文件路径：scripts/adapters/generic_waf_adapter.py

文件作用：
1. 解析通用 WAF 或 N9E 采集导出的日志文件。
2. 支持 JSON、JSON Lines 和 CSV 三类常见格式。
3. 将不同字段名称映射为系统统一中间格式。

说明：
1. 用户需求允许实现 n9e_waf_adapter.py 或 generic_waf_adapter.py。
2. 为了减少重复代码，本项目采用更通用的 generic_waf_adapter.py，
   并在 log_watcher.py 中把 data/incoming/n9e_waf/ 映射到该适配器。
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
    parse_csv_records,
    parse_json_records,
    safe_float,
    safe_int,
    severity_to_risk_score,
)


ADAPTER_NAME = "generic_waf_adapter"
SOURCE_KEY = "generic_waf"


def _resolve_field(raw_record: Dict[str, Any], *candidate_keys: str) -> Any:
    """
    从多个候选字段中取第一个非空值。
    """
    for key_name in candidate_keys:
        if key_name in raw_record and normalize_text(raw_record.get(key_name)):
            return raw_record.get(key_name)
    return ""


def _load_records(file_path: Path) -> List[Dict[str, Any]]:
    """
    根据文件后缀自动选择解析方式。
    """
    suffix = file_path.suffix.lower()
    if suffix == ".csv":
        return parse_csv_records(file_path)
    return parse_json_records(file_path)


def parse_file(file_path: Path) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    解析通用 WAF 日志文件。
    """
    records: List[Dict[str, Any]] = []
    errors: List[str] = []

    try:
        raw_records = _load_records(file_path)
    except Exception as exc:
        raise ValueError(f"通用 WAF 日志解析失败：{exc}") from exc

    for index, raw_record in enumerate(raw_records, start=1):
        try:
            event_time = normalize_iso_datetime(
                _resolve_field(raw_record, "timestamp", "time", "event_time", "@timestamp")
            )
            src_ip = normalize_text(_resolve_field(raw_record, "src_ip", "client_ip", "remote_addr"))
            dst_ip = normalize_text(_resolve_field(raw_record, "dst_ip", "server_ip", "local_addr"))
            dst_port = safe_int(_resolve_field(raw_record, "dst_port", "port", "server_port", "local_port"))
            src_port = safe_int(_resolve_field(raw_record, "src_port", "client_port", "remote_port"))
            hostname = normalize_upper_text(_resolve_field(raw_record, "hostname", "host", "target_host"))
            username = normalize_text(_resolve_field(raw_record, "username", "user", "account"))
            if not username:
                username = build_synthetic_username("generic_waf", src_ip)

            status = normalize_upper_text(_resolve_field(raw_record, "status", "disposition", "action_result"))
            severity = normalize_upper_text(_resolve_field(raw_record, "severity", "level")) or infer_severity_from_status(
                status,
                "MEDIUM",
            )
            event_type = normalize_upper_text(
                _resolve_field(raw_record, "event_type", "attack_type", "rule", "threat_type", "attack")
            ) or "WAF_ATTACK"
            action = normalize_upper_text(_resolve_field(raw_record, "action", "method", "http_method")) or "HTTP_REQUEST"
            protocol = normalize_upper_text(_resolve_field(raw_record, "protocol")) or infer_protocol_from_port(dst_port, "HTTP")
            log_source = normalize_upper_text(_resolve_field(raw_record, "log_source", "source", "vendor")) or "GENERIC_WAF"
            raw_message = normalize_text(raw_record.get("raw_message"))
            if not raw_message:
                raw_message = json.dumps(raw_record, ensure_ascii=False)

            raw_log_id = build_raw_log_id(log_source.lower(), file_path, index, event_time or f"line-{index}")
            session_hint = build_session_hint(log_source.lower(), event_time, src_ip, dst_ip, dst_port or "", username)

            records.append(
                build_unified_record(
                    {
                        "raw_log_id": raw_log_id,
                        "session_hint": session_hint,
                        "log_source": log_source,
                        "log_type": "WAF",
                        "source_type": "waf",
                        "event_time": event_time,
                        "username": username,
                        "user": username,
                        "src_ip": src_ip,
                        "src_port": src_port or "",
                        "dst_ip": dst_ip,
                        "dst_port": dst_port or "",
                        "asset": hostname,
                        "hostname": hostname,
                        "url": normalize_text(_resolve_field(raw_record, "url", "uri", "path", "request_uri")),
                        "method": normalize_upper_text(_resolve_field(raw_record, "method", "http_method")),
                        "protocol": protocol,
                        "action": action,
                        "event_type": event_type,
                        "attack_type": event_type,
                        "rule_name": normalize_text(_resolve_field(raw_record, "rule_name", "rule", "threat_type")),
                        "severity": severity,
                        "status": status or "ALLOWED",
                        "raw_log": raw_message,
                        "raw_message": raw_message,
                        "confidence": safe_float(_resolve_field(raw_record, "confidence"), 0.8),
                        "risk_score": severity_to_risk_score(severity, status, event_type),
                        "risk_score_hint": severity_to_risk_score(severity, status, event_type),
                        "can_block": severity in {"HIGH", "CRITICAL"},
                    }
                )
            )
        except Exception as exc:
            errors.append(f"{file_path.name} 第 {index} 条记录解析失败：{exc}")

    return records, errors
