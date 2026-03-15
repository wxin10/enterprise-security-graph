#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
文件路径：scripts/extract_entities.py

脚本职责：
1. 读取 clean_logs.py 输出的标准化日志文件。
2. 按第一阶段定义的图模型，抽取用户、主机、IP、会话、事件、规则、告警和封禁动作等节点。
3. 生成 Neo4j 导入所需的节点 CSV 与关系 CSV，输出到 data/processed/。

设计说明：
1. 真实企业环境中，实体抽取通常会结合 CMDB、账号台账、威胁情报等外部数据。
2. 为了保证毕业设计样例完整且可运行，本脚本内置了少量“参考主数据”，用于补全用户、主机、规则和 IP 的属性。
3. 这样既能保留“从原始日志抽取行为链路”的核心过程，也能让最终导入结果更接近真实安全平台的数据形态。
"""

from __future__ import annotations

import argparse
import csv
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple


BASE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_PROCESSED_DIR = BASE_DIR / "data" / "processed"


# 清洗阶段的中间文件名定义。
CLEANED_LOGIN_FILE = "cleaned_login_logs.csv"
CLEANED_HOST_FILE = "cleaned_host_logs.csv"
CLEANED_ALERT_FILE = "cleaned_alert_logs.csv"


# 参考用户主数据。
USER_REFERENCE: Dict[str, Dict[str, object]] = {
    "zhangsan": {
        "user_id": "U001",
        "username": "zhangsan",
        "display_name": "张三",
        "department": "运维部",
        "role": "运维工程师",
        "privilege_level": 4,
        "status": "ACTIVE",
        "is_whitelisted": False,
        "risk_score": 88,
        "created_at": "2026-03-01T09:00:00+08:00",
    },
    "lisi": {
        "user_id": "U002",
        "username": "lisi",
        "display_name": "李四",
        "department": "财务部",
        "role": "财务专员",
        "privilege_level": 2,
        "status": "ACTIVE",
        "is_whitelisted": False,
        "risk_score": 40,
        "created_at": "2026-03-01T09:05:00+08:00",
    },
    "sec_admin": {
        "user_id": "U003",
        "username": "sec_admin",
        "display_name": "安全管理员",
        "department": "安全部",
        "role": "安全管理员",
        "privilege_level": 5,
        "status": "ACTIVE",
        "is_whitelisted": True,
        "risk_score": 5,
        "created_at": "2026-03-01T09:10:00+08:00",
    },
}


# 参考主机主数据。
HOST_REFERENCE: Dict[str, Dict[str, object]] = {
    "WIN10-001": {
        "host_id": "H001",
        "hostname": "WIN10-001",
        "asset_type": "WORKSTATION",
        "os_name": "Windows 10",
        "critical_level": 2,
        "owner_department": "办公网络",
        "status": "ONLINE",
        "risk_score": 25,
        "created_at": "2026-03-01T09:00:00+08:00",
    },
    "FILE-SRV-01": {
        "host_id": "H002",
        "hostname": "FILE-SRV-01",
        "asset_type": "FILE_SERVER",
        "os_name": "Windows Server 2019",
        "critical_level": 5,
        "owner_department": "基础设施部",
        "status": "ONLINE",
        "risk_score": 72,
        "created_at": "2026-03-01T09:05:00+08:00",
    },
    "DB-SRV-01": {
        "host_id": "H003",
        "hostname": "DB-SRV-01",
        "asset_type": "DATABASE_SERVER",
        "os_name": "CentOS 7",
        "critical_level": 5,
        "owner_department": "数据平台部",
        "status": "ONLINE",
        "risk_score": 90,
        "created_at": "2026-03-01T09:10:00+08:00",
    },
}


# 参考 IP 主数据。
IP_REFERENCE: Dict[str, Dict[str, object]] = {
    "10.10.1.23": {
        "ip_id": "IP001",
        "ip_address": "10.10.1.23",
        "ip_type": "INTERNAL",
        "geo_location": "华东办公区",
        "reputation_level": "LOW",
        "is_blocked": False,
        "risk_score": 15,
        "created_at": "2026-03-01T09:00:00+08:00",
    },
    "10.10.9.99": {
        "ip_id": "IP002",
        "ip_address": "10.10.9.99",
        "ip_type": "INTERNAL",
        "geo_location": "VPN接入区",
        "reputation_level": "HIGH",
        "is_blocked": True,
        "risk_score": 85,
        "created_at": "2026-03-01T09:05:00+08:00",
    },
    "183.62.211.45": {
        "ip_id": "IP003",
        "ip_address": "183.62.211.45",
        "ip_type": "EXTERNAL",
        "geo_location": "境外节点",
        "reputation_level": "HIGH",
        "is_blocked": True,
        "risk_score": 92,
        "created_at": "2026-03-01T09:10:00+08:00",
    },
}


# 原始日志编号与事件编号的稳定映射。
EVENT_REFERENCE: Dict[str, Dict[str, object]] = {
    "RAW202603150001": {
        "event_id": "E001",
        "event_type": "LOGIN_FAIL",
        "event_level": "HIGH",
        "confidence": 0.91,
        "risk_score": 82,
    },
    "RAW202603150002": {
        "event_id": "E002",
        "event_type": "LATERAL_MOVE",
        "event_level": "CRITICAL",
        "confidence": 0.96,
        "risk_score": 95,
    },
    "RAW202603150003": {
        "event_id": "E003",
        "event_type": "HIGH_FREQ_ACCESS",
        "event_level": "HIGH",
        "confidence": 0.87,
        "risk_score": 75,
    },
}


# 为了与第一阶段样例保持一致，这里使用固定演示风险分值。
SESSION_RISK_REFERENCE = {
    "S001": 78,
    "S002": 90,
    "S003": 82,
}


USERS_FIELDS = [
    "user_id",
    "username",
    "display_name",
    "department",
    "role",
    "privilege_level",
    "status",
    "is_whitelisted",
    "risk_score",
    "created_at",
]

HOSTS_FIELDS = [
    "host_id",
    "hostname",
    "asset_type",
    "os_name",
    "critical_level",
    "owner_department",
    "status",
    "risk_score",
    "created_at",
]

IPS_FIELDS = [
    "ip_id",
    "ip_address",
    "ip_type",
    "geo_location",
    "reputation_level",
    "is_blocked",
    "risk_score",
    "created_at",
]

SESSIONS_FIELDS = [
    "session_id",
    "protocol",
    "login_result",
    "start_time",
    "end_time",
    "duration_seconds",
    "auth_method",
    "src_port",
    "dst_port",
    "risk_score",
]

EVENTS_FIELDS = [
    "event_id",
    "event_type",
    "event_level",
    "event_time",
    "action",
    "result",
    "log_source",
    "raw_log_id",
    "confidence",
    "risk_score",
    "detail",
]

RULES_FIELDS = [
    "rule_id",
    "rule_name",
    "rule_category",
    "rule_level",
    "threshold_desc",
    "description",
    "enabled",
]

ALERTS_FIELDS = [
    "alert_id",
    "alert_name",
    "severity",
    "score",
    "status",
    "first_seen",
    "last_seen",
    "description",
    "suggestion",
]

BLOCK_ACTIONS_FIELDS = [
    "action_id",
    "action_type",
    "target_type",
    "status",
    "executed_at",
    "executor",
    "ticket_no",
    "rollback_supported",
    "remark",
]

REL_SIMPLE_FIELDS = ["relation_time"]


def read_csv_rows(file_path: Path) -> List[Dict[str, str]]:
    """
    读取 CSV 字典行。
    """
    if not file_path.exists():
        raise FileNotFoundError(f"未找到输入文件：{file_path}，请先执行 clean_logs.py。")

    with file_path.open("r", encoding="utf-8", newline="") as file_obj:
        reader = csv.DictReader(file_obj)
        return [dict(row) for row in reader]


def write_csv_rows(file_path: Path, fieldnames: List[str], rows: Iterable[Dict[str, object]]) -> None:
    """
    写出 CSV 文件，并保证列顺序稳定。
    """
    file_path.parent.mkdir(parents=True, exist_ok=True)

    with file_path.open("w", encoding="utf-8", newline="") as file_obj:
        writer = csv.DictWriter(file_obj, fieldnames=fieldnames)
        writer.writeheader()

        for row in rows:
            normalized_row = {}
            for field in fieldnames:
                value = row.get(field, "")
                normalized_row[field] = format_csv_value(value)

            writer.writerow(normalized_row)


def format_csv_value(value: object) -> str:
    """
    将 Python 值转换为 CSV 字符串。
    """
    if value is None:
        return ""

    if isinstance(value, bool):
        return "true" if value else "false"

    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))
        return str(value)

    return str(value)


def parse_int(value: str) -> Optional[int]:
    """
    将字符串解析为整数，空值返回 None。
    """
    if value is None or str(value).strip() == "":
        return None
    return int(float(str(value).strip()))


def parse_float(value: str) -> Optional[float]:
    """
    将字符串解析为浮点数，空值返回 None。
    """
    if value is None or str(value).strip() == "":
        return None
    return float(str(value).strip())


def parse_bool(value: str) -> Optional[bool]:
    """
    将字符串解析为布尔值，空值返回 None。
    """
    if value is None or str(value).strip() == "":
        return None

    normalized = str(value).strip().lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False

    raise ValueError(f"无法解析布尔值：{value}")


def normalize_session_result(raw_result: str) -> str:
    """
    会话层的登录结果使用 SUCCESS / FAILURE。
    """
    if raw_result == "FAILED":
        return "FAILURE"
    return raw_result


def calculate_duration_seconds(start_time: str, end_time: str) -> Optional[int]:
    """
    根据开始时间和结束时间计算会话持续秒数。
    """
    if not start_time or not end_time:
        return None

    start_dt = datetime.fromisoformat(start_time)
    end_dt = datetime.fromisoformat(end_time)
    return int((end_dt - start_dt).total_seconds())


def ensure_reference_user(username: str) -> Dict[str, object]:
    """
    获取用户参考数据。

    若日志中出现了参考表中没有的新用户，则自动生成一个最小可用用户记录，
    保证脚本具备一定扩展性。
    """
    if username in USER_REFERENCE:
        return USER_REFERENCE[username]

    generated_id = f"U9{len(USER_REFERENCE) + 1:02d}"
    USER_REFERENCE[username] = {
        "user_id": generated_id,
        "username": username,
        "display_name": username,
        "department": "未知部门",
        "role": "未知角色",
        "privilege_level": 1,
        "status": "ACTIVE",
        "is_whitelisted": False,
        "risk_score": 10,
        "created_at": "2026-03-01T09:30:00+08:00",
    }
    return USER_REFERENCE[username]


def ensure_reference_host(hostname: str) -> Dict[str, object]:
    """
    获取主机参考数据。
    """
    if hostname in HOST_REFERENCE:
        return HOST_REFERENCE[hostname]

    generated_id = f"H9{len(HOST_REFERENCE) + 1:02d}"
    HOST_REFERENCE[hostname] = {
        "host_id": generated_id,
        "hostname": hostname,
        "asset_type": "UNKNOWN",
        "os_name": "Unknown",
        "critical_level": 1,
        "owner_department": "未知业务域",
        "status": "ONLINE",
        "risk_score": 10,
        "created_at": "2026-03-01T09:30:00+08:00",
    }
    return HOST_REFERENCE[hostname]


def ensure_reference_ip(ip_address: str, blocked_ips: Set[str]) -> Dict[str, object]:
    """
    获取 IP 参考数据。
    """
    if ip_address in IP_REFERENCE:
        ip_record = dict(IP_REFERENCE[ip_address])
        ip_record["is_blocked"] = ip_record["is_blocked"] or (ip_address in blocked_ips)
        return ip_record

    generated_id = f"IP9{len(IP_REFERENCE) + 1:02d}"
    generated_record = {
        "ip_id": generated_id,
        "ip_address": ip_address,
        "ip_type": "UNKNOWN",
        "geo_location": "未知区域",
        "reputation_level": "MEDIUM",
        "is_blocked": ip_address in blocked_ips,
        "risk_score": 50 if ip_address in blocked_ips else 20,
        "created_at": "2026-03-01T09:30:00+08:00",
    }
    IP_REFERENCE[ip_address] = dict(generated_record)
    return generated_record


def deduplicate_rows(rows: Iterable[Dict[str, object]], key_fields: List[str]) -> List[Dict[str, object]]:
    """
    根据关键字段去重。
    """
    unique_map: Dict[Tuple[object, ...], Dict[str, object]] = {}
    for row in rows:
        key = tuple(row.get(field) for field in key_fields)
        unique_map[key] = row
    return list(unique_map.values())


def build_users() -> List[Dict[str, object]]:
    """
    输出用户节点。

    当前策略：
    不仅保留日志中出现的用户，也输出参考账号主数据，便于展示企业账号基线。
    """
    users = list(USER_REFERENCE.values())
    return sorted(users, key=lambda item: str(item["user_id"]))


def build_hosts() -> List[Dict[str, object]]:
    """
    输出主机节点。
    """
    hosts = list(HOST_REFERENCE.values())
    return sorted(hosts, key=lambda item: str(item["host_id"]))


def build_ips(login_rows: List[Dict[str, str]], alert_rows: List[Dict[str, str]]) -> Tuple[List[Dict[str, object]], Dict[str, str]]:
    """
    从日志和告警中收集 IP 节点，并返回 IP 地址到 ip_id 的映射。
    """
    observed_ips: Set[str] = set()
    blocked_ips: Set[str] = set()

    for row in login_rows:
        if row.get("src_ip"):
            observed_ips.add(row["src_ip"])
        if row.get("dst_ip"):
            observed_ips.add(row["dst_ip"])

    for row in alert_rows:
        if row.get("target_ip"):
            observed_ips.add(row["target_ip"])
            if row.get("action_id"):
                blocked_ips.add(row["target_ip"])

    ip_rows: List[Dict[str, object]] = []
    ip_id_map: Dict[str, str] = {}

    for ip_address in sorted(observed_ips):
        ip_record = ensure_reference_ip(ip_address, blocked_ips)
        ip_rows.append(ip_record)
        ip_id_map[ip_address] = str(ip_record["ip_id"])

    return sorted(ip_rows, key=lambda item: str(item["ip_id"])), ip_id_map


def build_sessions(login_rows: List[Dict[str, str]]) -> List[Dict[str, object]]:
    """
    从登录日志中构建 Session 节点。
    """
    sessions: Dict[str, Dict[str, object]] = {}

    for row in login_rows:
        session_id = row["session_hint"]
        start_time = row.get("start_time", "")
        end_time = row.get("end_time", "")
        duration_seconds = calculate_duration_seconds(start_time, end_time)

        sessions[session_id] = {
            "session_id": session_id,
            "protocol": row.get("protocol", ""),
            "login_result": normalize_session_result(row.get("result", "")),
            "start_time": start_time,
            "end_time": end_time,
            "duration_seconds": duration_seconds,
            "auth_method": row.get("auth_method", ""),
            "src_port": parse_int(row.get("src_port")),
            "dst_port": parse_int(row.get("dst_port")),
            "risk_score": SESSION_RISK_REFERENCE.get(session_id, 20),
        }

    return sorted(sessions.values(), key=lambda item: str(item["session_id"]))


def build_auto_event_id(raw_log_id: str) -> str:
    """
    为自动接入的新日志生成稳定事件编号。

    设计原因：
    1. 原有样例数据使用 EVENT_REFERENCE 中的固定事件编号。
    2. 自动接入日志不可能全部预先写入参考表，因此需要一个稳定的回退方案。
    3. 使用 raw_log_id 派生事件编号，可以保证重复导入同一日志时仍然幂等。
    """
    normalized = "".join(char if char.isalnum() else "_" for char in raw_log_id.upper()).strip("_")
    return f"E_AUTO_{normalized}" if normalized else "E_AUTO_UNKNOWN"


def infer_event_level_from_score(risk_score: Optional[float]) -> str:
    """
    根据风险分提示推断事件等级。
    """
    if risk_score is None:
        return "MEDIUM"
    if risk_score >= 90:
        return "CRITICAL"
    if risk_score >= 75:
        return "HIGH"
    if risk_score >= 55:
        return "MEDIUM"
    return "LOW"


def resolve_login_event_type(row: Dict[str, str]) -> str:
    """
    根据登录日志推断事件类型。

    当前只对失败认证重点建事件，避免为每条普通访问都生成过多低价值事件。
    """
    action = row.get("action", "")
    result = row.get("result", "")

    if result in {"FAILED", "FAILURE"}:
        return "LOGIN_FAIL"
    if action == "LOGIN" and result == "SUCCESS":
        return "LOGIN_SUCCESS"
    return "GENERIC_LOGIN_EVENT"


def resolve_event_reference(
    raw_log_id: str,
    event_type: str,
    risk_score_hint: Optional[float],
    confidence_hint: Optional[float],
) -> Dict[str, object]:
    """
    解析事件参考信息。

    兼容策略：
    1. 若命中原有 EVENT_REFERENCE，则继续使用既有样例编号和风险分。
    2. 若未命中，则为自动接入日志生成回退事件编号和风险等级。
    """
    if raw_log_id in EVENT_REFERENCE:
        reference = dict(EVENT_REFERENCE[raw_log_id])
        if event_type:
            reference["event_type"] = event_type
        return reference

    resolved_risk_score = risk_score_hint if risk_score_hint is not None else 60
    return {
        "event_id": build_auto_event_id(raw_log_id),
        "event_type": event_type or "GENERIC_EVENT",
        "event_level": infer_event_level_from_score(resolved_risk_score),
        "confidence": confidence_hint if confidence_hint is not None else 0.8,
        "risk_score": resolved_risk_score,
    }


def build_events(
    login_rows: List[Dict[str, str]],
    host_rows: List[Dict[str, str]],
) -> Tuple[List[Dict[str, object]], Dict[str, str], List[Dict[str, object]]]:
    """
    从登录日志和主机日志中构建 Event 节点，并返回：
    1. 事件列表
    2. 原始日志编号到事件编号的映射
    3. Session -> Event 关系列表
    """
    event_rows: List[Dict[str, object]] = []
    raw_to_event_id: Dict[str, str] = {}
    session_event_rows: List[Dict[str, object]] = []

    for row in login_rows:
        if row.get("result") not in {"FAILED", "FAILURE"}:
            continue

        inferred_event_type = resolve_login_event_type(row)
        reference = resolve_event_reference(
            raw_log_id=row["raw_log_id"],
            event_type=inferred_event_type,
            risk_score_hint=82,
            confidence_hint=0.9,
        )

        event_id = str(reference["event_id"])
        raw_to_event_id[row["raw_log_id"]] = event_id

        event_rows.append(
            {
                "event_id": event_id,
                "event_type": reference["event_type"],
                "event_level": reference["event_level"],
                "event_time": row.get("event_time", ""),
                "action": row.get("action", ""),
                "result": row.get("result", ""),
                "log_source": row.get("log_source", ""),
                "raw_log_id": row.get("raw_log_id", ""),
                "confidence": reference["confidence"],
                "risk_score": reference["risk_score"],
                "detail": row.get("message", ""),
            }
        )

        session_event_rows.append(
            {
                "session_id": row["session_hint"],
                "event_id": event_id,
                "relation_time": row.get("event_time", ""),
            }
        )

    for row in host_rows:
        inferred_event_type = row.get("event_type_hint") or "GENERIC_EVENT"
        reference = resolve_event_reference(
            raw_log_id=row["raw_log_id"],
            event_type=inferred_event_type,
            risk_score_hint=parse_float(row.get("risk_score_hint")),
            confidence_hint=parse_float(row.get("confidence")),
        )

        event_id = str(reference["event_id"])
        raw_to_event_id[row["raw_log_id"]] = event_id

        event_rows.append(
            {
                "event_id": event_id,
                "event_type": row.get("event_type_hint") or reference["event_type"],
                "event_level": reference["event_level"],
                "event_time": row.get("event_time", ""),
                "action": row.get("action", ""),
                "result": row.get("result", ""),
                "log_source": row.get("log_source", ""),
                "raw_log_id": row.get("raw_log_id", ""),
                "confidence": parse_float(row.get("confidence")) or reference["confidence"],
                "risk_score": parse_float(row.get("risk_score_hint")) or reference["risk_score"],
                "detail": row.get("message", ""),
            }
        )

        session_event_rows.append(
            {
                "session_id": row["session_hint"],
                "event_id": event_id,
                "relation_time": row.get("event_time", ""),
            }
        )

    event_rows = deduplicate_rows(event_rows, ["event_id"])
    session_event_rows = deduplicate_rows(session_event_rows, ["session_id", "event_id"])

    return (
        sorted(event_rows, key=lambda item: str(item["event_id"])),
        raw_to_event_id,
        sorted(session_event_rows, key=lambda item: (str(item["session_id"]), str(item["event_id"]))),
    )


def build_rules(alert_rows: List[Dict[str, str]]) -> List[Dict[str, object]]:
    """
    从告警日志中构建 Rule 节点。
    """
    rules: List[Dict[str, object]] = []

    for row in alert_rows:
        rules.append(
            {
                "rule_id": row.get("rule_id", ""),
                "rule_name": row.get("rule_name", ""),
                "rule_category": row.get("rule_category", ""),
                "rule_level": row.get("rule_level", ""),
                "threshold_desc": row.get("threshold_desc", ""),
                "description": build_rule_description(row),
                "enabled": True,
            }
        )

    rules = deduplicate_rows(rules, ["rule_id"])
    return sorted(rules, key=lambda item: str(item["rule_id"]))


def build_rule_description(alert_row: Dict[str, str]) -> str:
    """
    根据规则编号生成更贴近论文描述的规则说明。
    """
    rule_id = alert_row.get("rule_id", "")
    if rule_id == "R001":
        return "检测外部来源对单主机的暴力破解行为"
    if rule_id == "R002":
        return "检测同一账号短时间访问多台关键主机"
    if rule_id == "R003":
        return "检测脚本化或异常自动化访问行为"
    return "根据安全告警日志抽取的检测规则"


def build_alerts(alert_rows: List[Dict[str, str]]) -> List[Dict[str, object]]:
    """
    构建 Alert 节点。
    """
    alerts = []

    for row in alert_rows:
        alerts.append(
            {
                "alert_id": row.get("alert_id", ""),
                "alert_name": row.get("alert_name", ""),
                "severity": row.get("severity", ""),
                "score": parse_float(row.get("score")),
                "status": row.get("status", ""),
                "first_seen": row.get("first_seen", ""),
                "last_seen": row.get("last_seen", ""),
                "description": row.get("description", ""),
                "suggestion": row.get("suggestion", ""),
            }
        )

    alerts = deduplicate_rows(alerts, ["alert_id"])
    return sorted(alerts, key=lambda item: str(item["alert_id"]))


def build_block_actions(alert_rows: List[Dict[str, str]]) -> List[Dict[str, object]]:
    """
    从告警联动日志中构建 BlockAction 节点。
    """
    actions = []

    for row in alert_rows:
        if not row.get("action_id"):
            continue

        actions.append(
            {
                "action_id": row.get("action_id", ""),
                "action_type": row.get("action_type", ""),
                "target_type": row.get("target_type", ""),
                "status": row.get("action_status", ""),
                "executed_at": row.get("executed_at", ""),
                "executor": row.get("executor", ""),
                "ticket_no": row.get("ticket_no", ""),
                "rollback_supported": parse_bool(row.get("rollback_supported")),
                "remark": row.get("remark", ""),
            }
        )

    actions = deduplicate_rows(actions, ["action_id"])
    return sorted(actions, key=lambda item: str(item["action_id"]))


def build_user_session_relations(login_rows: List[Dict[str, str]]) -> List[Dict[str, object]]:
    """
    构建 User -> Session 关系。
    """
    rows = []
    for row in login_rows:
        user_record = ensure_reference_user(row["username"])
        rows.append(
            {
                "user_id": user_record["user_id"],
                "session_id": row["session_hint"],
                "relation_time": row.get("start_time") or row.get("event_time", ""),
            }
        )

    rows = deduplicate_rows(rows, ["user_id", "session_id"])
    return sorted(rows, key=lambda item: (str(item["user_id"]), str(item["session_id"])))


def build_session_ip_relations(login_rows: List[Dict[str, str]], ip_id_map: Dict[str, str]) -> List[Dict[str, object]]:
    """
    构建 Session -> IP 关系。
    """
    rows = []
    for row in login_rows:
        src_ip = row.get("src_ip", "")
        if not src_ip:
            continue

        rows.append(
            {
                "session_id": row["session_hint"],
                "ip_id": ip_id_map[src_ip],
                "relation_time": row.get("start_time") or row.get("event_time", ""),
            }
        )

    rows = deduplicate_rows(rows, ["session_id", "ip_id"])
    return sorted(rows, key=lambda item: (str(item["session_id"]), str(item["ip_id"])))


def build_session_host_relations(login_rows: List[Dict[str, str]]) -> List[Dict[str, object]]:
    """
    构建 Session -> Host 关系。
    """
    rows = []
    for row in login_rows:
        host_record = ensure_reference_host(row["hostname"])
        rows.append(
            {
                "session_id": row["session_hint"],
                "host_id": host_record["host_id"],
                "relation_time": row.get("event_time", ""),
            }
        )

    rows = deduplicate_rows(rows, ["session_id", "host_id"])
    return sorted(rows, key=lambda item: (str(item["session_id"]), str(item["host_id"])))


def build_event_alert_relations(
    alert_rows: List[Dict[str, str]],
    raw_to_event_id: Dict[str, str],
) -> List[Dict[str, object]]:
    """
    构建 Event -> Alert 关系。
    """
    rows = []
    for row in alert_rows:
        event_id = raw_to_event_id.get(row.get("related_raw_log_id", ""))
        if not event_id:
            continue

        rows.append(
            {
                "event_id": event_id,
                "alert_id": row.get("alert_id", ""),
                "relation_time": row.get("event_time", ""),
            }
        )

    rows = deduplicate_rows(rows, ["event_id", "alert_id"])
    return sorted(rows, key=lambda item: (str(item["event_id"]), str(item["alert_id"])))


def build_alert_rule_relations(alert_rows: List[Dict[str, str]]) -> List[Dict[str, object]]:
    """
    构建 Alert -> Rule 关系。
    """
    rows = []
    for row in alert_rows:
        rows.append(
            {
                "alert_id": row.get("alert_id", ""),
                "rule_id": row.get("rule_id", ""),
                "relation_time": row.get("event_time", ""),
            }
        )

    rows = deduplicate_rows(rows, ["alert_id", "rule_id"])
    return sorted(rows, key=lambda item: (str(item["alert_id"]), str(item["rule_id"])))


def build_action_alert_relations(alert_rows: List[Dict[str, str]]) -> List[Dict[str, object]]:
    """
    构建 BlockAction -> Alert 关系。
    """
    rows = []
    for row in alert_rows:
        if not row.get("action_id"):
            continue

        rows.append(
            {
                "action_id": row.get("action_id", ""),
                "alert_id": row.get("alert_id", ""),
                "relation_time": row.get("executed_at") or row.get("event_time", ""),
            }
        )

    rows = deduplicate_rows(rows, ["action_id", "alert_id"])
    return sorted(rows, key=lambda item: (str(item["action_id"]), str(item["alert_id"])))


def build_action_ip_relations(alert_rows: List[Dict[str, str]], ip_id_map: Dict[str, str]) -> List[Dict[str, object]]:
    """
    构建 BlockAction -> IP 关系。
    """
    rows = []
    for row in alert_rows:
        if not row.get("action_id") or not row.get("target_ip"):
            continue

        rows.append(
            {
                "action_id": row.get("action_id", ""),
                "ip_id": ip_id_map[row["target_ip"]],
                "relation_time": row.get("executed_at") or row.get("event_time", ""),
            }
        )

    rows = deduplicate_rows(rows, ["action_id", "ip_id"])
    return sorted(rows, key=lambda item: (str(item["action_id"]), str(item["ip_id"])))


def build_argument_parser() -> argparse.ArgumentParser:
    """
    构造命令行参数。
    """
    parser = argparse.ArgumentParser(description="从清洗后的日志中抽取图谱实体和关系。")
    parser.add_argument(
        "--processed-dir",
        default=str(DEFAULT_PROCESSED_DIR),
        help="输入清洗日志和输出节点/关系 CSV 的目录，默认使用项目下的 data/processed。",
    )
    return parser


def main() -> int:
    """
    程序主入口。
    """
    parser = build_argument_parser()
    args = parser.parse_args()

    processed_dir = Path(args.processed_dir).resolve()

    try:
        login_rows = read_csv_rows(processed_dir / CLEANED_LOGIN_FILE)
        host_rows = read_csv_rows(processed_dir / CLEANED_HOST_FILE)
        alert_rows = read_csv_rows(processed_dir / CLEANED_ALERT_FILE)

        for row in login_rows:
            ensure_reference_user(row["username"])
            ensure_reference_host(row["hostname"])

        for row in host_rows:
            ensure_reference_user(row["username"])
            ensure_reference_host(row["hostname"])

        users = build_users()
        hosts = build_hosts()
        ips, ip_id_map = build_ips(login_rows, alert_rows)
        sessions = build_sessions(login_rows)
        events, raw_to_event_id, rel_session_generates_event = build_events(login_rows, host_rows)
        rules = build_rules(alert_rows)
        alerts = build_alerts(alert_rows)
        block_actions = build_block_actions(alert_rows)

        rel_user_initiates_session = build_user_session_relations(login_rows)
        rel_session_uses_source_ip = build_session_ip_relations(login_rows, ip_id_map)
        rel_session_accesses_host = build_session_host_relations(login_rows)
        rel_event_triggers_alert = build_event_alert_relations(alert_rows, raw_to_event_id)
        rel_alert_hit_rule = build_alert_rule_relations(alert_rows)
        rel_block_disposes_alert = build_action_alert_relations(alert_rows)
        rel_block_targets_ip = build_action_ip_relations(alert_rows, ip_id_map)

        write_csv_rows(processed_dir / "users.csv", USERS_FIELDS, users)
        write_csv_rows(processed_dir / "hosts.csv", HOSTS_FIELDS, hosts)
        write_csv_rows(processed_dir / "ips.csv", IPS_FIELDS, ips)
        write_csv_rows(processed_dir / "sessions.csv", SESSIONS_FIELDS, sessions)
        write_csv_rows(processed_dir / "events.csv", EVENTS_FIELDS, events)
        write_csv_rows(processed_dir / "rules.csv", RULES_FIELDS, rules)
        write_csv_rows(processed_dir / "alerts.csv", ALERTS_FIELDS, alerts)
        write_csv_rows(processed_dir / "block_actions.csv", BLOCK_ACTIONS_FIELDS, block_actions)

        write_csv_rows(
            processed_dir / "rel_user_initiates_session.csv",
            ["user_id", "session_id", *REL_SIMPLE_FIELDS],
            rel_user_initiates_session,
        )
        write_csv_rows(
            processed_dir / "rel_session_uses_source_ip.csv",
            ["session_id", "ip_id", *REL_SIMPLE_FIELDS],
            rel_session_uses_source_ip,
        )
        write_csv_rows(
            processed_dir / "rel_session_accesses_host.csv",
            ["session_id", "host_id", *REL_SIMPLE_FIELDS],
            rel_session_accesses_host,
        )
        write_csv_rows(
            processed_dir / "rel_session_generates_event.csv",
            ["session_id", "event_id", *REL_SIMPLE_FIELDS],
            rel_session_generates_event,
        )
        write_csv_rows(
            processed_dir / "rel_event_triggers_alert.csv",
            ["event_id", "alert_id", *REL_SIMPLE_FIELDS],
            rel_event_triggers_alert,
        )
        write_csv_rows(
            processed_dir / "rel_alert_hit_rule.csv",
            ["alert_id", "rule_id", *REL_SIMPLE_FIELDS],
            rel_alert_hit_rule,
        )
        write_csv_rows(
            processed_dir / "rel_block_disposes_alert.csv",
            ["action_id", "alert_id", *REL_SIMPLE_FIELDS],
            rel_block_disposes_alert,
        )
        write_csv_rows(
            processed_dir / "rel_block_targets_ip.csv",
            ["action_id", "ip_id", *REL_SIMPLE_FIELDS],
            rel_block_targets_ip,
        )
    except Exception as exc:
        print(f"[extract_entities] 执行失败：{exc}", file=sys.stderr)
        return 1

    print("[extract_entities] 实体与关系抽取完成。")
    print(f"[extract_entities] User 节点：{len(users)}")
    print(f"[extract_entities] Host 节点：{len(hosts)}")
    print(f"[extract_entities] IP 节点：{len(ips)}")
    print(f"[extract_entities] Session 节点：{len(sessions)}")
    print(f"[extract_entities] Event 节点：{len(events)}")
    print(f"[extract_entities] Alert 节点：{len(alerts)}")
    print(f"[extract_entities] BlockAction 节点：{len(block_actions)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
