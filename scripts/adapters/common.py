#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
文件路径：scripts/adapters/common.py

文件作用：
1. 提供多源日志适配器共享的统一字段定义与通用工具函数。
2. 统一处理时间、数值、枚举、会话编号和原始日志编号生成逻辑。
3. 保证不同日志适配器最终输出一致的中间格式，便于 log_watcher.py 继续桥接现有处理链路。
"""

from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


UNIFIED_LOG_FIELDS = [
    "raw_log_id",
    "session_hint",
    "log_source",
    "log_type",
    "event_time",
    "user_id",
    "username",
    "src_ip",
    "src_port",
    "dst_ip",
    "dst_port",
    "host_id",
    "hostname",
    "protocol",
    "action",
    "event_type",
    "severity",
    "status",
    "raw_message",
    "bytes_in",
    "bytes_out",
    "confidence",
    "risk_score_hint",
]


# 为了和当前项目已有资产参考保持一致，这里为常见演示主机提供默认属性。
HOST_PROFILE_REFERENCE: Dict[str, Dict[str, Any]] = {
    "WIN10-001": {
        "asset_type": "WORKSTATION",
        "os_name": "Windows 10",
        "owner_department": "办公网络",
        "critical_level": 2,
    },
    "FILE-SRV-01": {
        "asset_type": "FILE_SERVER",
        "os_name": "Windows Server 2019",
        "owner_department": "基础设施部",
        "critical_level": 5,
    },
    "DB-SRV-01": {
        "asset_type": "DATABASE_SERVER",
        "os_name": "CentOS 7",
        "owner_department": "数据平台部",
        "critical_level": 5,
    },
}


def normalize_text(value: Any) -> str:
    """
    将任意值安全转换为字符串。
    """
    if value is None:
        return ""
    return str(value).strip()


def normalize_upper_text(value: Any) -> str:
    """
    将文本统一转大写，适合枚举字段。
    """
    text = normalize_text(value)
    return text.upper() if text else ""


def safe_int(value: Any, default_value: Optional[int] = None) -> Optional[int]:
    """
    安全转换整数。
    """
    text = normalize_text(value)
    if not text:
        return default_value

    try:
        return int(float(text))
    except (TypeError, ValueError):
        return default_value


def safe_float(value: Any, default_value: Optional[float] = None) -> Optional[float]:
    """
    安全转换浮点数。
    """
    text = normalize_text(value)
    if not text:
        return default_value

    try:
        return float(text)
    except (TypeError, ValueError):
        return default_value


def normalize_iso_datetime(value: Any) -> str:
    """
    将不同格式时间统一为 ISO 8601 字符串。
    """
    text = normalize_text(value)
    if not text:
        return ""

    normalized_text = text.replace("Z", "+00:00")
    candidate_formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y/%m/%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S.%f",
    ]

    try:
        parsed_datetime = datetime.fromisoformat(normalized_text)
    except ValueError:
        parsed_datetime = None
        for item_format in candidate_formats:
            try:
                parsed_datetime = datetime.strptime(normalized_text, item_format)
                break
            except ValueError:
                continue

        if parsed_datetime is None:
            return text

    if parsed_datetime.tzinfo is None:
        return parsed_datetime.strftime("%Y-%m-%dT%H:%M:%S+08:00")

    return parsed_datetime.isoformat(timespec="seconds")


def parse_json_records(file_path: Path) -> List[Dict[str, Any]]:
    """
    解析 JSON / JSONL 文件。

    支持两种常见形态：
    1. 整个文件是一个 JSON 数组。
    2. 每一行是一个 JSON 对象。
    """
    content = file_path.read_text(encoding="utf-8").strip()
    if not content:
        return []

    # 先尝试把整个文件视为 JSON 对象或数组。
    try:
        parsed = json.loads(content)
        if isinstance(parsed, list):
            return [item for item in parsed if isinstance(item, dict)]
        if isinstance(parsed, dict):
            return [parsed]
    except json.JSONDecodeError:
        pass

    # 若整体解析失败，则按 JSON Lines 逐行解析。
    records: List[Dict[str, Any]] = []
    for line in content.splitlines():
        stripped_line = line.strip()
        if not stripped_line:
            continue
        try:
            parsed_line = json.loads(stripped_line)
        except json.JSONDecodeError:
            # 为满足“单条记录解析失败不影响整文件”的要求，
            # 这里对单行坏数据直接跳过，由上层适配器继续处理其余记录。
            continue
        if isinstance(parsed_line, dict):
            records.append(parsed_line)

    return records


def parse_csv_records(file_path: Path) -> List[Dict[str, Any]]:
    """
    解析 CSV 文件为字典列表。
    """
    with file_path.open("r", encoding="utf-8", newline="") as file_obj:
        reader = csv.DictReader(file_obj)
        return [dict(row) for row in reader]


def severity_to_risk_score(severity: str, status: str = "", event_type: str = "") -> int:
    """
    根据严重等级和状态推导风险分。

    设计说明：
    1. 适配器层只负责给出一个“初始事件风险提示值”。
    2. 真正的总风险分仍由 detection_service.py 再次计算。
    """
    normalized_severity = normalize_upper_text(severity)
    normalized_status = normalize_upper_text(status)
    normalized_event_type = normalize_upper_text(event_type)

    base_score_map = {
        "LOW": 35,
        "MEDIUM": 60,
        "HIGH": 80,
        "CRITICAL": 95,
    }
    risk_score = base_score_map.get(normalized_severity, 55)

    if normalized_status in {"BLOCKED", "DENIED", "DROP", "DROPPED"}:
        risk_score += 5

    if normalized_event_type in {"SQL_INJECTION", "COMMAND_INJECTION", "RCE", "LATERAL_MOVE"}:
        risk_score += 5

    return min(100, risk_score)


def infer_severity_from_status(status: str, default_value: str = "MEDIUM") -> str:
    """
    根据动作结果推断严重等级。
    """
    normalized_status = normalize_upper_text(status)
    if normalized_status in {"BLOCKED", "DENIED", "DROP", "DROPPED"}:
        return "HIGH"
    if normalized_status in {"ALLOWED", "ALLOW", "ACCEPT", "PASSED"}:
        return "MEDIUM"
    return normalize_upper_text(default_value) or "MEDIUM"


def infer_protocol_from_port(dst_port: Any, default_value: str = "TCP") -> str:
    """
    根据目标端口推断协议。
    """
    port_number = safe_int(dst_port)
    protocol_map = {
        22: "SSH",
        80: "HTTP",
        443: "HTTPS",
        445: "SMB",
        3389: "RDP",
        1433: "MSSQL",
        3306: "MYSQL",
        5432: "POSTGRESQL",
    }
    if port_number in protocol_map:
        return protocol_map[port_number]
    return normalize_upper_text(default_value) or "TCP"


def build_raw_log_id(source_key: str, file_path: Path, line_number: int, event_time: str) -> str:
    """
    生成原始日志编号。

    这里采用“来源目录 + 文件名 + 行号 + 时间”的组合生成稳定哈希，
    这样同一个文件重复解析时可以得到相同 raw_log_id，便于去重和幂等导入。
    """
    raw_seed = f"{source_key}|{file_path.name}|{line_number}|{event_time}"
    digest = hashlib.md5(raw_seed.encode("utf-8")).hexdigest()[:12].upper()
    return f"RAW_AUTO_{digest}"


def build_session_hint(
    source_key: str,
    event_time: str,
    src_ip: str,
    dst_ip: str,
    dst_port: Any,
    username: str,
) -> str:
    """
    生成会话编号提示。

    设计原因：
    1. 自动接入日志不一定天然带有 session_id。
    2. 这里使用来源、用户、源 IP、目标地址和时间生成稳定编号，便于后续建模。
    """
    raw_seed = f"{source_key}|{event_time}|{src_ip}|{dst_ip}|{dst_port}|{username}"
    digest = hashlib.md5(raw_seed.encode("utf-8")).hexdigest()[:10].upper()
    return f"S_AUTO_{digest}"


def build_synthetic_username(source_key: str, src_ip: str) -> str:
    """
    当日志中缺少用户名时，基于来源和源 IP 生成一个稳定的伪用户名。

    这样做的意义：
    1. 便于当前图模型继续保留 User -> Session 关系。
    2. 避免因为缺失用户名而让整个实体抽取链路中断。
    3. 同一来源、同一源 IP 会稳定映射到同一个伪用户，便于规则聚合。
    """
    normalized_ip = normalize_text(src_ip).replace(".", "_").replace(":", "_")
    normalized_source = normalize_text(source_key).lower()
    if not normalized_ip:
        normalized_ip = "unknown"
    return f"{normalized_source}_{normalized_ip}"


def build_unified_record(record: Dict[str, Any]) -> Dict[str, Any]:
    """
    将适配器解析结果填充为统一字段结构。
    """
    unified_record = {field_name: "" for field_name in UNIFIED_LOG_FIELDS}
    for field_name, field_value in record.items():
        if field_name not in unified_record:
            continue
        unified_record[field_name] = field_value
    return unified_record
