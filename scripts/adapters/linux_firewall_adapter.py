#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
文件路径：scripts/adapters/linux_firewall_adapter.py

文件作用：
1. 解析 Linux / iptables / ufw 通用防火墙日志。
2. 兼容常见 syslog 形式的 key=value 防火墙记录。
3. 将解析结果统一映射为系统中间字段。

当前支持的最小可运行格式：
1. UFW BLOCK / UFW ALLOW
2. iptables DROP / ACCEPT / REJECT
3. 含有 SRC= / DST= / PROTO= / SPT= / DPT= 等键值对的内核日志
"""

from __future__ import annotations

import re
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


ADAPTER_NAME = "linux_firewall_adapter"
SOURCE_KEY = "linux_firewall"


KEY_VALUE_PATTERN = re.compile(r"([A-Z]+)=([^ ]+)")


def parse_file(file_path: Path) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    解析 Linux 防火墙日志文件。
    """
    records: List[Dict[str, Any]] = []
    errors: List[str] = []

    with file_path.open("r", encoding="utf-8") as file_obj:
        for line_number, raw_line in enumerate(file_obj, start=1):
            stripped_line = raw_line.strip()
            if not stripped_line:
                continue

            try:
                # 日志行开头优先尝试解析 ISO 时间；若不存在则保留空值。
                time_candidate = stripped_line.split(" ", 1)[0]
                event_time = normalize_iso_datetime(time_candidate)

                key_values = {match.group(1): match.group(2) for match in KEY_VALUE_PATTERN.finditer(stripped_line)}
                src_ip = normalize_text(key_values.get("SRC"))
                dst_ip = normalize_text(key_values.get("DST"))
                src_port = safe_int(key_values.get("SPT"))
                dst_port = safe_int(key_values.get("DPT"))
                protocol = normalize_upper_text(key_values.get("PROTO")) or infer_protocol_from_port(dst_port)
                hostname = normalize_upper_text(_extract_hostname(stripped_line))

                if "UFW BLOCK" in stripped_line.upper() or "DROP" in stripped_line.upper() or "REJECT" in stripped_line.upper():
                    status = "BLOCKED"
                    action = "DROP"
                    event_type = "FIREWALL_DROP"
                else:
                    status = "ALLOWED"
                    action = "ALLOW"
                    event_type = "FIREWALL_ALLOW"

                severity = infer_severity_from_status(status, "HIGH")
                username = build_synthetic_username(SOURCE_KEY, src_ip)
                raw_log_id = build_raw_log_id(SOURCE_KEY, file_path, line_number, event_time or f"line-{line_number}")
                session_hint = build_session_hint(SOURCE_KEY, event_time, src_ip, dst_ip, dst_port or "", username)

                records.append(
                    build_unified_record(
                        {
                            "raw_log_id": raw_log_id,
                            "session_hint": session_hint,
                            "log_source": "LINUX_FIREWALL",
                            "log_type": "FIREWALL",
                            "source_type": "firewall",
                            "event_time": event_time,
                            "username": username,
                            "user": username,
                            "src_ip": src_ip,
                            "src_port": src_port or "",
                            "dst_ip": dst_ip,
                            "dst_port": dst_port or "",
                            "asset": hostname,
                            "hostname": hostname,
                            "protocol": protocol,
                            "action": action,
                            "event_type": event_type,
                            "attack_type": event_type,
                            "rule_name": "Linux Firewall",
                            "severity": severity,
                            "status": status,
                            "raw_log": stripped_line,
                            "raw_message": stripped_line,
                            "risk_score": severity_to_risk_score(severity, status, event_type),
                            "risk_score_hint": severity_to_risk_score(severity, status, event_type),
                            "confidence": 0.84,
                            "can_block": status == "BLOCKED",
                        }
                    )
                )
            except Exception as exc:
                errors.append(f"{file_path.name} 第 {line_number} 行解析失败：{exc}")

    return records, errors


def _extract_hostname(log_line: str) -> str:
    """
    从 syslog 风格日志中提取主机名。

    示例：
    2026-03-15T12:31:05+08:00 linux-fw-01 kernel: [UFW BLOCK] ...
    上述情况下会返回 linux-fw-01。
    """
    parts = log_line.split()
    if len(parts) >= 2 and "T" in parts[0]:
        return parts[1]
    return ""
