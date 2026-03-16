#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
文件路径：scripts/event_normalizer.py

文件作用：
1. 在现有多源适配器解析结果之上，提供“统一安全事件标准化层”。
2. 将不同来源日志统一映射为后续更容易复用的标准安全事件结构。
3. 为下一轮“按攻击行为驱动的检测与封禁”提供统一输入基础，但本轮不改检测主逻辑。

设计原则：
1. 适配器负责解析原始日志，事件标准化层负责统一语义。
2. 本轮只做最小可运行版本，因此优先保留高价值字段并落盘为文件。
3. 标准化结果既用于调试排查，也用于后续逐步替代“按目录来源驱动”的思路。
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Set

from adapters.common import normalize_text, normalize_upper_text, safe_float, safe_int, severity_to_risk_score


UNIFIED_EVENT_FIELDS = [
    "event_id",
    "raw_log_id",
    "session_hint",
    "event_time",
    "source_type",
    "log_source",
    "log_type",
    "src_ip",
    "src_port",
    "dst_ip",
    "dst_port",
    "asset",
    "hostname",
    "user",
    "user_id",
    "url",
    "method",
    "protocol",
    "action",
    "status",
    "event_type",
    "attack_type",
    "rule_name",
    "severity",
    "confidence",
    "risk_score",
    "can_block",
    "raw_log",
    "source_file",
]


BLOCKABLE_ATTACK_TYPES = {
    "SQL_INJECTION",
    "COMMAND_INJECTION",
    "RCE",
    "FIREWALL_DROP",
    "LOGIN_FAIL",
    "SCAN",
    "PROBE",
    "PORT_SCAN",
    "BRUTE_FORCE",
}


AUTH_KEYWORDS = [
    "login failed",
    "authentication failed",
    "invalid password",
    "user auth failed",
    "登录失败",
]


URL_PATTERN = re.compile(r"(/\S+)")
HTTP_METHOD_PATTERN = re.compile(r"\b(GET|POST|PUT|DELETE|HEAD|OPTIONS|PATCH)\b", re.IGNORECASE)


def _to_bool(value: Any) -> bool:
    """
    将不同形式的布尔值安全转换为 Python bool。
    """
    if isinstance(value, bool):
        return value
    text = normalize_text(value).lower()
    return text in {"1", "true", "yes", "y", "on"}


def _infer_source_type(record: Dict[str, Any], classifier_result: Dict[str, Any]) -> str:
    """
    推导统一事件的 source_type。
    """
    source_type = normalize_text(record.get("source_type")) or normalize_text(classifier_result.get("source_type"))
    return source_type or "unknown"


def _infer_user(record: Dict[str, Any]) -> str:
    """
    推导统一事件中的用户字段。
    """
    return normalize_text(record.get("user")) or normalize_text(record.get("username"))


def _infer_asset(record: Dict[str, Any]) -> str:
    """
    推导统一事件中的资产字段。
    """
    return normalize_text(record.get("asset")) or normalize_text(record.get("hostname"))


def _extract_url(raw_log: str, record: Dict[str, Any]) -> str:
    """
    从结构化字段或原始日志文本中提取 URL / 目标资源。
    """
    for candidate_key in ("url", "uri", "path", "request_uri", "target_resource"):
        candidate_value = normalize_text(record.get(candidate_key))
        if candidate_value:
            return candidate_value

    match = URL_PATTERN.search(raw_log)
    return match.group(1) if match else ""


def _extract_method(raw_log: str, record: Dict[str, Any]) -> str:
    """
    从结构化字段或原始文本中提取 HTTP 方法。
    """
    for candidate_key in ("method", "http_method"):
        candidate_value = normalize_upper_text(record.get(candidate_key))
        if candidate_value:
            return candidate_value

    match = HTTP_METHOD_PATTERN.search(raw_log)
    return normalize_upper_text(match.group(1)) if match else ""


def _infer_attack_type(record: Dict[str, Any], raw_log: str) -> str:
    """
    推导攻击行为类型。

    优先级：
    1. 适配器已给出的 attack_type
    2. event_type
    3. 原始日志中的关键字启发式识别
    """
    direct_attack_type = normalize_upper_text(record.get("attack_type"))
    if direct_attack_type:
        return direct_attack_type

    event_type = normalize_upper_text(record.get("event_type"))
    if event_type:
        return event_type

    lowered_log = raw_log.lower()
    if "sql_injection" in lowered_log or "sql injection" in lowered_log:
        return "SQL_INJECTION"
    if "command_injection" in lowered_log or "command injection" in lowered_log:
        return "COMMAND_INJECTION"
    if any(keyword in lowered_log for keyword in AUTH_KEYWORDS):
        return "LOGIN_FAIL"
    if "scan" in lowered_log or "probe" in lowered_log:
        return "SCAN"

    return "GENERIC_SECURITY_EVENT"


def _infer_rule_name(record: Dict[str, Any]) -> str:
    """
    推导命中规则名称。
    """
    for candidate_key in ("rule_name", "rule", "threat_rule"):
        candidate_value = normalize_text(record.get(candidate_key))
        if candidate_value:
            return candidate_value
    return ""


def _infer_confidence(record: Dict[str, Any], attack_type: str) -> float:
    """
    推导统一事件置信度。
    """
    confidence = safe_float(record.get("confidence"))
    if confidence is not None:
        return max(0.0, min(1.0, confidence))

    if attack_type in {"SQL_INJECTION", "COMMAND_INJECTION", "RCE"}:
        return 0.92
    if attack_type in {"FIREWALL_DROP", "LOGIN_FAIL", "SCAN"}:
        return 0.85
    return 0.7


def _infer_risk_score(record: Dict[str, Any], severity: str, status: str, attack_type: str) -> int:
    """
    推导统一事件风险分。
    """
    explicit_risk_score = safe_int(record.get("risk_score"))
    if explicit_risk_score is not None:
        return max(0, min(100, explicit_risk_score))

    hinted_risk_score = safe_float(record.get("risk_score_hint"))
    if hinted_risk_score is not None:
        return max(0, min(100, int(round(hinted_risk_score))))

    return severity_to_risk_score(severity, status, attack_type)


def _infer_can_block(attack_type: str, severity: str, risk_score: int) -> bool:
    """
    推导事件是否具备封禁候选资格。

    说明：
    1. 本轮只做统一事件层，不直接改自动封禁主逻辑。
    2. 这里先把可封禁倾向写入统一事件文件，供下一轮行为驱动封禁复用。
    """
    if attack_type in BLOCKABLE_ATTACK_TYPES:
        return True
    return severity in {"HIGH", "CRITICAL"} and risk_score >= 80


def normalize_records_to_events(
    records: Iterable[Dict[str, Any]],
    classifier_result: Dict[str, Any],
    source_file: Path,
) -> List[Dict[str, Any]]:
    """
    将适配器输出记录列表统一标准化为安全事件列表。
    """
    normalized_events: List[Dict[str, Any]] = []

    for record in records:
        raw_log = normalize_text(record.get("raw_log")) or normalize_text(record.get("raw_message"))
        source_type = _infer_source_type(record, classifier_result)
        attack_type = _infer_attack_type(record, raw_log)
        severity = normalize_upper_text(record.get("severity")) or "MEDIUM"
        status = normalize_upper_text(record.get("status")) or "OBSERVED"
        confidence = _infer_confidence(record, attack_type)
        risk_score = _infer_risk_score(record, severity, status, attack_type)
        can_block = _infer_can_block(attack_type, severity, risk_score)

        normalized_events.append(
            {
                "event_id": normalize_text(record.get("raw_log_id")),
                "raw_log_id": normalize_text(record.get("raw_log_id")),
                "session_hint": normalize_text(record.get("session_hint")),
                "event_time": normalize_text(record.get("event_time")),
                "source_type": source_type,
                "log_source": normalize_text(record.get("log_source")),
                "log_type": normalize_text(record.get("log_type")),
                "src_ip": normalize_text(record.get("src_ip")),
                "src_port": safe_int(record.get("src_port"), "") or "",
                "dst_ip": normalize_text(record.get("dst_ip")),
                "dst_port": safe_int(record.get("dst_port"), "") or "",
                "asset": _infer_asset(record),
                "hostname": normalize_text(record.get("hostname")),
                "user": _infer_user(record),
                "user_id": normalize_text(record.get("user_id")),
                "url": _extract_url(raw_log, record),
                "method": _extract_method(raw_log, record),
                "protocol": normalize_upper_text(record.get("protocol")),
                "action": normalize_upper_text(record.get("action")),
                "status": status,
                "event_type": normalize_upper_text(record.get("event_type")),
                "attack_type": attack_type,
                "rule_name": _infer_rule_name(record),
                "severity": severity,
                "confidence": confidence,
                "risk_score": risk_score,
                "can_block": can_block,
                "raw_log": raw_log,
                "source_file": str(source_file),
            }
        )

    return normalized_events


def summarize_events(events: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    """
    统计统一事件摘要，供 status.json 与监控页展示。
    """
    event_list = list(events)
    attack_type_set: Set[str] = {
        normalize_upper_text(item.get("attack_type"))
        for item in event_list
        if normalize_upper_text(item.get("attack_type"))
    }
    blockable_event_count = sum(1 for item in event_list if _to_bool(item.get("can_block")))

    return {
        "unified_event_count": len(event_list),
        "detected_attack_types": sorted(attack_type_set),
        "blockable_event_count": blockable_event_count,
    }

