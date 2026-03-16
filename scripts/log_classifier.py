#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
文件路径：scripts/log_classifier.py

文件作用：
1. 为统一入口 `data/incoming/unified/` 提供轻量级日志类型自动识别能力。
2. 识别结果只用于选择最接近的现有解析器，不直接参与告警或封禁决策。
3. 保持当前项目“多源适配器继续可用”的兼容策略，不推翻现有目录与适配器设计。

当前最小支持的 source_type：
1. waf
2. firewall
3. web_access
4. middleware
5. auth
6. unknown
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List


# 目录提示映射。
# 说明：
# 1. 对已经明确分类的旧目录，优先直接返回稳定结果。
# 2. 对 unified 目录则继续走内容识别逻辑。
DIRECTORY_HINT_MAPPING = {
    "safeline_waf": {
        "source_type": "waf",
        "adapter_key": "safeline_waf",
        "confidence": 1.0,
        "reason": "目录提示已明确指定为雷池 WAF 日志",
    },
    "n9e_waf": {
        "source_type": "waf",
        "adapter_key": "n9e_waf",
        "confidence": 1.0,
        "reason": "目录提示已明确指定为通用 WAF 日志",
    },
    "windows_firewall": {
        "source_type": "firewall",
        "adapter_key": "windows_firewall",
        "confidence": 1.0,
        "reason": "目录提示已明确指定为 Windows 防火墙日志",
    },
    "linux_firewall": {
        "source_type": "firewall",
        "adapter_key": "linux_firewall",
        "confidence": 1.0,
        "reason": "目录提示已明确指定为 Linux 防火墙日志",
    },
}


WAF_FIELD_KEYWORDS = {
    "attack_type",
    "rule",
    "rule_name",
    "uri",
    "url",
    "path",
    "request_uri",
    "method",
    "http_method",
    "remote_addr",
    "client_ip",
}
WAF_TEXT_KEYWORDS = [
    "sql_injection",
    "command_injection",
    "xss",
    "path_traversal",
    "waf",
    "safeline",
]
WINDOWS_FIREWALL_KEYWORDS = [
    "#fields:",
    "src-ip",
    "dst-ip",
    "src-port",
    "dst-port",
]
LINUX_FIREWALL_KEYWORDS = [
    "ufw ",
    "src=",
    "dst=",
    "proto=",
    "dpt=",
    "spt=",
]
WEB_ACCESS_KEYWORDS = [
    "http/1.1",
    "http/1.0",
    "\"get ",
    "\"post ",
    "\"put ",
    "\"delete ",
]
MIDDLEWARE_KEYWORDS = [
    "exception",
    "traceback",
    "spring",
    "tomcat",
    "java.lang",
    "upstream",
    "stack trace",
]
AUTH_KEYWORDS = [
    "login failed",
    "authentication failed",
    "invalid password",
    "user auth failed",
    "failed password",
    "登录失败",
]


def _normalize_text(value: Any) -> str:
    """
    将任意值安全转换为文本。
    """
    if value is None:
        return ""
    return str(value).strip()


def _read_preview_text(file_path: Path, max_chars: int = 12000) -> str:
    """
    读取日志文件前若干字符，用于快速内容识别。

    设计说明：
    1. 第一阶段只做轻量识别，不做全文深度分析。
    2. 优先保证 unified 目录里的文件能快速路由到现有适配器。
    """
    return file_path.read_text(encoding="utf-8", errors="ignore")[:max_chars]


def _extract_preview_json_objects(preview_text: str, max_records: int = 3) -> List[Dict[str, Any]]:
    """
    从预览文本中尝试提取少量 JSON / JSONL 对象。

    说明：
    1. 如果 unified 日志是 JSON 数组、JSON 对象或 JSON Lines，都尽量识别。
    2. 单条 JSON 解析失败不会中断整个分类流程。
    """
    stripped_text = preview_text.strip()
    if not stripped_text:
        return []

    preview_objects: List[Dict[str, Any]] = []

    try:
        parsed_payload = json.loads(stripped_text)
        if isinstance(parsed_payload, dict):
            return [parsed_payload]
        if isinstance(parsed_payload, list):
            return [item for item in parsed_payload if isinstance(item, dict)][:max_records]
    except json.JSONDecodeError:
        pass

    for raw_line in stripped_text.splitlines():
        raw_line = raw_line.strip()
        if not raw_line:
            continue
        try:
            parsed_line = json.loads(raw_line)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed_line, dict):
            preview_objects.append(parsed_line)
        if len(preview_objects) >= max_records:
            break

    return preview_objects


def _contains_any(text: str, keywords: List[str]) -> bool:
    """
    判断文本中是否包含任一关键字。
    """
    lowered_text = text.lower()
    return any(keyword in lowered_text for keyword in keywords)


def _looks_like_windows_firewall(preview_text: str) -> bool:
    """
    判断是否像 Windows 防火墙日志。
    """
    lowered_text = preview_text.lower()
    return all(keyword in lowered_text for keyword in WINDOWS_FIREWALL_KEYWORDS)


def _looks_like_linux_firewall(preview_text: str) -> bool:
    """
    判断是否像 Linux / iptables / ufw 防火墙日志。
    """
    lowered_text = preview_text.lower()
    hit_count = sum(1 for keyword in LINUX_FIREWALL_KEYWORDS if keyword in lowered_text)
    return hit_count >= 2


def _looks_like_waf(preview_text: str, preview_json_objects: List[Dict[str, Any]]) -> bool:
    """
    判断是否像 WAF 或 Web 攻击日志。
    """
    lowered_text = preview_text.lower()
    if _contains_any(lowered_text, WAF_TEXT_KEYWORDS):
        return True

    for preview_object in preview_json_objects:
        field_names = {str(item).lower() for item in preview_object.keys()}
        if len(field_names.intersection(WAF_FIELD_KEYWORDS)) >= 2:
            return True

    return False


def _looks_like_web_access(preview_text: str) -> bool:
    """
    判断是否像 Web 访问日志。
    """
    lowered_text = preview_text.lower()
    if _contains_any(lowered_text, WEB_ACCESS_KEYWORDS):
        return True

    access_log_pattern = re.compile(r"\b(GET|POST|PUT|DELETE|HEAD)\s+/\S*\s+HTTP/\d\.\d", re.IGNORECASE)
    return bool(access_log_pattern.search(preview_text))


def _looks_like_middleware(preview_text: str) -> bool:
    """
    判断是否像中间件 / 应用日志。
    """
    lowered_text = preview_text.lower()
    return _contains_any(lowered_text, MIDDLEWARE_KEYWORDS)


def _looks_like_auth(preview_text: str) -> bool:
    """
    判断是否像认证 / 登录日志。

    说明：
    1. 本轮只做轻量识别，不额外引入新的认证专用解析器。
    2. 先把认证类日志标记为 auth，便于下一轮继续接入统一事件层。
    """
    lowered_text = preview_text.lower()
    return _contains_any(lowered_text, AUTH_KEYWORDS)


def classify_log_file(file_path: Path, directory_hint: str = "") -> Dict[str, Any]:
    """
    对日志文件做最小可运行的类型识别。

    返回字段说明：
    1. source_type：统一后的大类标识，供后续展示与审计。
    2. adapter_key：建议使用的现有适配器键名。
    3. is_supported：当前项目是否已有可直接复用的解析器。
    4. reason：识别原因，便于 status.json 和答辩演示解释。
    """
    normalized_directory_hint = _normalize_text(directory_hint)
    if normalized_directory_hint in DIRECTORY_HINT_MAPPING:
        mapping = DIRECTORY_HINT_MAPPING[normalized_directory_hint]
        return {
            "classifier_name": "heuristic_classifier_v1",
            "directory_hint": normalized_directory_hint,
            "source_type": mapping["source_type"],
            "adapter_key": mapping["adapter_key"],
            "confidence": mapping["confidence"],
            "reason": mapping["reason"],
            "matched_signatures": [normalized_directory_hint],
            "is_supported": True,
        }

    preview_text = _read_preview_text(file_path)
    preview_json_objects = _extract_preview_json_objects(preview_text)
    matched_signatures: List[str] = []

    if _looks_like_windows_firewall(preview_text):
        matched_signatures.append("windows_firewall_fields")
        return {
            "classifier_name": "heuristic_classifier_v1",
            "directory_hint": normalized_directory_hint,
            "source_type": "firewall",
            "adapter_key": "windows_firewall",
            "confidence": 0.96,
            "reason": "检测到 Windows 防火墙 #Fields 头部与标准字段",
            "matched_signatures": matched_signatures,
            "is_supported": True,
        }

    if _looks_like_linux_firewall(preview_text):
        matched_signatures.append("linux_firewall_kv")
        return {
            "classifier_name": "heuristic_classifier_v1",
            "directory_hint": normalized_directory_hint,
            "source_type": "firewall",
            "adapter_key": "linux_firewall",
            "confidence": 0.93,
            "reason": "检测到 UFW / iptables 常见键值对日志特征",
            "matched_signatures": matched_signatures,
            "is_supported": True,
        }

    if _looks_like_waf(preview_text, preview_json_objects):
        matched_signatures.append("waf_attack_signature")
        return {
            "classifier_name": "heuristic_classifier_v1",
            "directory_hint": normalized_directory_hint,
            "source_type": "waf",
            "adapter_key": "n9e_waf",
            "confidence": 0.92,
            "reason": "检测到 Web 攻击字段、规则字段或攻击类型关键字",
            "matched_signatures": matched_signatures,
            "is_supported": True,
        }

    if _looks_like_web_access(preview_text):
        matched_signatures.append("web_access_request_line")
        return {
            "classifier_name": "heuristic_classifier_v1",
            "directory_hint": normalized_directory_hint,
            "source_type": "web_access",
            "adapter_key": "",
            "confidence": 0.75,
            "reason": "识别为 Web 访问日志，但当前第一阶段尚未接入专用 access 解析器",
            "matched_signatures": matched_signatures,
            "is_supported": False,
        }

    if _looks_like_middleware(preview_text):
        matched_signatures.append("middleware_runtime_keywords")
        return {
            "classifier_name": "heuristic_classifier_v1",
            "directory_hint": normalized_directory_hint,
            "source_type": "middleware",
            "adapter_key": "",
            "confidence": 0.7,
            "reason": "识别为应用 / 中间件运行日志，当前第一阶段仅完成来源识别",
            "matched_signatures": matched_signatures,
            "is_supported": False,
        }

    if _looks_like_auth(preview_text):
        matched_signatures.append("auth_keywords")
        return {
            "classifier_name": "heuristic_classifier_v1",
            "directory_hint": normalized_directory_hint,
            "source_type": "auth",
            "adapter_key": "",
            "confidence": 0.68,
            "reason": "识别为认证 / 登录日志，当前第一阶段仅完成类型识别与统一入口接入",
            "matched_signatures": matched_signatures,
            "is_supported": False,
        }

    return {
        "classifier_name": "heuristic_classifier_v1",
        "directory_hint": normalized_directory_hint,
        "source_type": "unknown",
        "adapter_key": "",
        "confidence": 0.3,
        "reason": "未识别出稳定日志特征，已标记为 unknown",
        "matched_signatures": matched_signatures,
        "is_supported": False,
    }
