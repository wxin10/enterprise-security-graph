#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
文件路径：scripts/adapters/windows_firewall_adapter.py

文件作用：
1. 解析 Windows 防火墙日志。
2. 兼容标准 pfirewall.log 样式以及少量演示增强注释。
3. 将原始字段统一映射为系统内部标准中间格式。

已支持的要点：
1. 解析 #Fields: 指定的列顺序。
2. 支持通过自定义注释传入主机名和事件等级：
   - #hostname: DB-SRV-01
   - #severity: HIGH
3. 对单行异常解析进行容错，不影响其它记录继续处理。
"""

from __future__ import annotations

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
    safe_int,
    severity_to_risk_score,
)


ADAPTER_NAME = "windows_firewall_adapter"
SOURCE_KEY = "windows_firewall"


def parse_file(file_path: Path) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    解析 Windows 防火墙日志文件。
    """
    records: List[Dict[str, Any]] = []
    errors: List[str] = []
    field_names: List[str] = []
    metadata: Dict[str, str] = {}

    with file_path.open("r", encoding="utf-8") as file_obj:
        for line_number, raw_line in enumerate(file_obj, start=1):
            stripped_line = raw_line.strip()
            if not stripped_line:
                continue

            if stripped_line.startswith("#"):
                lowered_line = stripped_line.lower()
                if lowered_line.startswith("#fields:"):
                    field_names = stripped_line.split(":", 1)[1].strip().split()
                elif lowered_line.startswith("#hostname:"):
                    metadata["hostname"] = normalize_upper_text(stripped_line.split(":", 1)[1])
                elif lowered_line.startswith("#severity:"):
                    metadata["severity"] = normalize_upper_text(stripped_line.split(":", 1)[1])
                continue

            if not field_names:
                errors.append(f"{file_path.name} 第 {line_number} 行缺少 #Fields 头部，无法解析。")
                continue

            try:
                parts = stripped_line.split()
                record_map = {field_names[index]: parts[index] if index < len(parts) else "" for index in range(len(field_names))}

                date_text = normalize_text(record_map.get("date"))
                time_text = normalize_text(record_map.get("time"))
                event_time = normalize_iso_datetime(f"{date_text} {time_text}".strip())

                src_ip = normalize_text(record_map.get("src-ip"))
                dst_ip = normalize_text(record_map.get("dst-ip"))
                src_port = safe_int(record_map.get("src-port"))
                dst_port = safe_int(record_map.get("dst-port"))
                action = normalize_upper_text(record_map.get("action")) or "ACCESS"
                status = "BLOCKED" if action in {"DROP", "DENY"} else "ALLOWED"
                severity = metadata.get("severity") or infer_severity_from_status(status, "HIGH")
                hostname = metadata.get("hostname", "")
                protocol = normalize_upper_text(record_map.get("protocol")) or infer_protocol_from_port(dst_port)
                username = build_synthetic_username(SOURCE_KEY, src_ip)
                event_type = "FIREWALL_DROP" if status == "BLOCKED" else "FIREWALL_ALLOW"
                info_text = normalize_text(record_map.get("info"))
                path_text = normalize_text(record_map.get("path"))
                raw_message = stripped_line

                raw_log_id = build_raw_log_id(SOURCE_KEY, file_path, line_number, event_time or f"line-{line_number}")
                session_hint = build_session_hint(SOURCE_KEY, event_time, src_ip, dst_ip, dst_port or "", username)

                records.append(
                    build_unified_record(
                        {
                            "raw_log_id": raw_log_id,
                            "session_hint": session_hint,
                            "log_source": "WINDOWS_FIREWALL",
                            "log_type": "FIREWALL",
                            "event_time": event_time,
                            "username": username,
                            "src_ip": src_ip,
                            "src_port": src_port or "",
                            "dst_ip": dst_ip,
                            "dst_port": dst_port or "",
                            "hostname": hostname,
                            "protocol": protocol,
                            "action": action,
                            "event_type": event_type,
                            "severity": severity,
                            "status": status,
                            "raw_message": raw_message,
                            "risk_score_hint": severity_to_risk_score(severity, status, event_type),
                            "confidence": 0.86,
                            "bytes_in": "",
                            "bytes_out": "",
                        }
                    )
                )
            except Exception as exc:
                errors.append(f"{file_path.name} 第 {line_number} 行解析失败：{exc}")

    return records, errors
