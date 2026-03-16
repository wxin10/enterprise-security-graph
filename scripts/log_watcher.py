#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
文件路径：scripts/log_watcher.py

脚本职责：
1. 轮询 `data/incoming/` 下的多源日志目录，自动发现新日志文件。
2. 对统一入口 `data/incoming/unified/` 中的文件先做轻量日志类型识别，再路由到现有适配器。
3. 将解析结果桥接为当前项目已有脚本可直接消费的原始样例格式。
4. 自动触发以下既有处理链路：
   - clean_logs.py
   - extract_entities.py
   - import_to_neo4j.py
   - run_detection.py
5. 处理成功后归档原始文件，处理失败后移动到 failed 目录，并写入失败原因与状态文件。

设计说明：
1. 本轮只做“第一阶段最小改造”，不重写检测主逻辑，也不重构导入链路。
2. 统一入口的自动识别只负责选择解析器，不参与告警或封禁决策。
3. 旧目录 `safeline_waf / n9e_waf / windows_firewall / linux_firewall` 保持兼容可用。
"""

from __future__ import annotations

import argparse
import csv
import json
import locale
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple


BASE_DIR = Path(__file__).resolve().parents[1]
SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_ENV_FILE = BASE_DIR / "backend" / ".env"

INCOMING_ROOT = BASE_DIR / "data" / "incoming"
ARCHIVE_ROOT = BASE_DIR / "data" / "archive"
FAILED_ROOT = BASE_DIR / "data" / "failed"
RUNTIME_ROOT = BASE_DIR / "data" / "runtime"
BATCH_ROOT = RUNTIME_ROOT / "batches"

SOURCE_DIRECTORIES = [
    "unified",
    "safeline_waf",
    "n9e_waf",
    "windows_firewall",
    "linux_firewall",
]
SUPPORTED_EXTENSIONS = {".json", ".jsonl", ".csv", ".log", ".txt"}


# 将 scripts 目录加入搜索路径，方便脚本直接导入本地适配器与分类器。
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))


from adapters import ADAPTER_REGISTRY  # noqa: E402
from adapters.common import (  # noqa: E402
    HOST_PROFILE_REFERENCE,
    UNIFIED_LOG_FIELDS,
    build_synthetic_username,
    infer_protocol_from_port,
    normalize_text,
    normalize_upper_text,
    safe_float,
    safe_int,
    severity_to_risk_score,
)
from log_classifier import classify_log_file  # noqa: E402
from event_normalizer import (  # noqa: E402
    UNIFIED_EVENT_FIELDS,
    normalize_records_to_events,
    summarize_events,
)
from behavior_aggregator import (  # noqa: E402
    ATTACK_BEHAVIOR_FIELDS,
    recognize_attack_behaviors,
    summarize_behaviors,
)


LOGIN_RAW_FIELDS = [
    "raw_log_id",
    "session_hint",
    "log_source",
    "log_type",
    "event_time",
    "start_time",
    "end_time",
    "username",
    "display_name",
    "department",
    "role",
    "privilege_level",
    "src_ip",
    "dst_ip",
    "src_port",
    "dst_port",
    "hostname",
    "protocol",
    "action",
    "result",
    "auth_method",
    "message",
]

HOST_RAW_FIELDS = [
    "raw_log_id",
    "session_hint",
    "log_source",
    "log_type",
    "event_time",
    "username",
    "src_ip",
    "hostname",
    "asset_type",
    "os_name",
    "owner_department",
    "critical_level",
    "protocol",
    "action",
    "result",
    "bytes_in",
    "bytes_out",
    "event_type_hint",
    "confidence",
    "risk_score_hint",
    "message",
]

ALERT_RAW_FIELDS = [
    "alert_id",
    "related_raw_log_id",
    "session_hint",
    "event_type_hint",
    "event_time",
    "rule_id",
    "rule_name",
    "rule_category",
    "rule_level",
    "threshold_desc",
    "alert_name",
    "severity",
    "score",
    "status",
    "first_seen",
    "last_seen",
    "description",
    "suggestion",
    "action_id",
    "action_type",
    "target_type",
    "target_ip",
    "action_status",
    "executed_at",
    "executor",
    "ticket_no",
    "rollback_supported",
    "remark",
]


def load_env_file(env_file: Path) -> None:
    """
    读取 `backend/.env` 并注入环境变量。

    这样 log_watcher 触发 import_to_neo4j.py 与 run_detection.py 时，
    可以自动继承 Neo4j 连接配置，而不需要每次手工传参。
    """
    if not env_file.exists():
        return

    for line in env_file.read_text(encoding="utf-8").splitlines():
        stripped_line = line.strip()
        if not stripped_line or stripped_line.startswith("#") or "=" not in stripped_line:
            continue

        key, value = stripped_line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def build_argument_parser() -> argparse.ArgumentParser:
    """
    构造命令行参数解析器。
    """
    parser = argparse.ArgumentParser(description="自动扫描 incoming 目录并触发日志导入与检测链路。")
    parser.add_argument(
        "--once",
        action="store_true",
        help="只扫描并处理一轮，适合本地测试。",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=5,
        help="轮询模式下的扫描间隔秒数，默认 5 秒。",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只打印将要处理的文件与识别结果，不真正导入。",
    )
    return parser


def ensure_directories() -> None:
    """
    确保自动接入相关目录存在。
    """
    for source_dir in SOURCE_DIRECTORIES:
        (INCOMING_ROOT / source_dir).mkdir(parents=True, exist_ok=True)
        (ARCHIVE_ROOT / source_dir).mkdir(parents=True, exist_ok=True)
        (FAILED_ROOT / source_dir).mkdir(parents=True, exist_ok=True)

    BATCH_ROOT.mkdir(parents=True, exist_ok=True)


def sanitize_filename(value: str) -> str:
    """
    将任意文本安全转换为文件名片段。
    """
    cleaned_text = re.sub(r"[^0-9A-Za-z_\-.]+", "_", normalize_text(value))
    return cleaned_text.strip("_") or "unknown"


def format_csv_value(value: Any) -> str:
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


def write_csv_rows(file_path: Path, fieldnames: List[str], rows: Iterable[Dict[str, Any]]) -> None:
    """
    写出 CSV 文件。
    """
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with file_path.open("w", encoding="utf-8", newline="") as file_obj:
        writer = csv.DictWriter(file_obj, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field_name: format_csv_value(row.get(field_name, "")) for field_name in fieldnames})


def write_json_rows(file_path: Path, rows: Iterable[Dict[str, Any]]) -> None:
    """
    写出 JSON 文件。

    设计说明：
    1. 统一安全事件层需要显式落盘，便于答辩演示和后续行为驱动改造复用。
    2. 当前以 JSON 数组形式保存，方便人工阅读与脚本再次消费。
    """
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(
        json.dumps(list(rows), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def discover_files() -> List[Path]:
    """
    扫描 incoming 目录并返回待处理文件列表。
    """
    discovered_files: List[Path] = []
    for source_dir in SOURCE_DIRECTORIES:
        source_path = INCOMING_ROOT / source_dir
        if not source_path.exists():
            continue

        for file_path in sorted(source_path.iterdir()):
            if not file_path.is_file():
                continue
            if file_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                continue
            discovered_files.append(file_path)

    return discovered_files


def resolve_host_profile(hostname: str) -> Dict[str, Any]:
    """
    根据主机名获取资产属性。
    若未命中已有参考，则生成一个最小可运行默认值。
    """
    normalized_hostname = normalize_upper_text(hostname)
    if normalized_hostname in HOST_PROFILE_REFERENCE:
        return dict(HOST_PROFILE_REFERENCE[normalized_hostname])

    return {
        "asset_type": "UNKNOWN",
        "os_name": "Unknown",
        "owner_department": "自动接入资产",
        "critical_level": 2,
    }


def resolve_hostname(record: Dict[str, Any]) -> str:
    """
    获取统一记录中的主机名。
    如果源日志没有主机名，则基于目标 IP 生成占位主机名。
    """
    hostname = normalize_upper_text(record.get("hostname"))
    if hostname:
        return hostname

    dst_ip = normalize_text(record.get("dst_ip"))
    if dst_ip:
        return f"AUTOHOST_{dst_ip.replace('.', '_').replace(':', '_')}".upper()

    return "AUTOHOST_UNKNOWN"


def resolve_username(record: Dict[str, Any], source_key: str) -> str:
    """
    获取统一记录中的用户名。
    若为空，则按来源和源 IP 生成稳定伪用户名。
    """
    username = normalize_text(record.get("username")).lower()
    if username:
        return username
    return build_synthetic_username(source_key, normalize_text(record.get("src_ip"))).lower()


def build_login_raw_rows(records: List[Dict[str, Any]], source_key: str) -> List[Dict[str, Any]]:
    """
    将统一中间记录转换为 `login_logs_sample.csv` 兼容格式。

    说明：
    1. 这里的“login”并不严格等于真实登录行为，而是用于复用当前 Session 抽取链路。
    2. 即使是 WAF / firewall 日志，也会生成一条“访问会话型”桥接记录。
    """
    rows: List[Dict[str, Any]] = []

    for item in records:
        username = resolve_username(item, source_key)
        hostname = resolve_hostname(item)
        event_time = normalize_text(item.get("event_time"))
        protocol = normalize_upper_text(item.get("protocol")) or infer_protocol_from_port(item.get("dst_port"), "TCP")
        action = normalize_upper_text(item.get("action")) or "ACCESS"
        status = normalize_upper_text(item.get("status")) or "OBSERVED"

        rows.append(
            {
                "raw_log_id": normalize_text(item.get("raw_log_id")),
                "session_hint": normalize_upper_text(item.get("session_hint")),
                "log_source": normalize_upper_text(item.get("log_source")),
                "log_type": normalize_upper_text(item.get("log_type")) or "NETWORK_ACCESS",
                "event_time": event_time,
                "start_time": event_time,
                "end_time": event_time,
                "username": username,
                "display_name": username,
                "department": "自动接入",
                "role": "自动接入主体",
                "privilege_level": 1,
                "src_ip": normalize_text(item.get("src_ip")),
                "dst_ip": normalize_text(item.get("dst_ip")),
                "src_port": safe_int(item.get("src_port"), "") or "",
                "dst_port": safe_int(item.get("dst_port"), "") or "",
                "hostname": hostname,
                "protocol": protocol,
                "action": action,
                "result": status,
                "auth_method": "NETWORK",
                "message": normalize_text(item.get("raw_message")),
            }
        )

    return rows


def build_host_raw_rows(records: List[Dict[str, Any]], source_key: str) -> List[Dict[str, Any]]:
    """
    将统一中间记录转换为 `host_logs_sample.csv` 兼容格式。
    """
    rows: List[Dict[str, Any]] = []

    for item in records:
        username = resolve_username(item, source_key)
        hostname = resolve_hostname(item)
        host_profile = resolve_host_profile(hostname)
        severity = normalize_upper_text(item.get("severity")) or "MEDIUM"
        status = normalize_upper_text(item.get("status")) or "OBSERVED"
        event_type = normalize_upper_text(item.get("event_type")) or "GENERIC_EVENT"
        risk_score_hint = safe_float(item.get("risk_score_hint"))
        if risk_score_hint is None:
            risk_score_hint = float(severity_to_risk_score(severity, status, event_type))

        rows.append(
            {
                "raw_log_id": normalize_text(item.get("raw_log_id")),
                "session_hint": normalize_upper_text(item.get("session_hint")),
                "log_source": normalize_upper_text(item.get("log_source")),
                "log_type": normalize_upper_text(item.get("log_type")) or "HOST_ACCESS",
                "event_time": normalize_text(item.get("event_time")),
                "username": username,
                "src_ip": normalize_text(item.get("src_ip")),
                "hostname": hostname,
                "asset_type": host_profile["asset_type"],
                "os_name": host_profile["os_name"],
                "owner_department": host_profile["owner_department"],
                "critical_level": host_profile["critical_level"],
                "protocol": normalize_upper_text(item.get("protocol")) or infer_protocol_from_port(item.get("dst_port"), "TCP"),
                "action": normalize_upper_text(item.get("action")) or "ACCESS",
                "result": status,
                "bytes_in": safe_int(item.get("bytes_in"), "") or "",
                "bytes_out": safe_int(item.get("bytes_out"), "") or "",
                "event_type_hint": event_type,
                "confidence": safe_float(item.get("confidence"), 0.85),
                "risk_score_hint": risk_score_hint,
                "message": normalize_text(item.get("raw_message")),
            }
        )

    return rows


def build_alert_raw_rows() -> List[Dict[str, Any]]:
    """
    自动接入阶段暂不直接生成原始联动告警日志。

    当前兼容策略：
    1. 先输出空表头文件，保持 clean_logs.py 与 extract_entities.py 链路不报错。
    2. 真正的告警仍由后续 run_detection.py 基于图数据自动生成。
    """
    return []


def write_status_json(file_path: Path, payload: Dict[str, Any]) -> None:
    """
    写出批次状态文件，便于前端监控页与答辩演示。
    """
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def create_batch_directory(source_key: str, file_path: Path, create_on_disk: bool = True) -> Path:
    """
    为单个原始日志文件创建独立处理批次目录。
    """
    timestamp_text = datetime.now().strftime("%Y%m%d_%H%M%S")
    batch_name = f"{timestamp_text}_{source_key}_{sanitize_filename(file_path.stem)}"
    batch_dir = BATCH_ROOT / batch_name
    if create_on_disk:
        batch_dir.mkdir(parents=True, exist_ok=True)
    return batch_dir


def run_subprocess(command: List[str], env_mapping: Dict[str, str]) -> Tuple[bool, str]:
    """
    执行子脚本，并返回是否成功及控制台输出。

    兼容说明：
    1. Windows 下优先使用系统首选编码，避免中文输出导致 UnicodeDecodeError。
    2. 极端情况下用 replace 兜底，避免单次输出异常中断整条链路。
    """
    preferred_encoding = locale.getpreferredencoding(False) or "utf-8"

    completed = subprocess.run(
        command,
        cwd=str(BASE_DIR),
        capture_output=True,
        text=True,
        encoding=preferred_encoding,
        errors="replace",
        env=env_mapping,
    )

    combined_output = ""
    if completed.stdout:
        combined_output += completed.stdout.strip()
    if completed.stderr:
        if combined_output:
            combined_output += "\n"
        combined_output += completed.stderr.strip()

    return completed.returncode == 0, combined_output


def move_file_to_directory(source_file: Path, target_root: Path, source_key: str) -> Path:
    """
    将原始日志移动到 archive / failed 对应目录。
    """
    target_dir = target_root / source_key
    target_dir.mkdir(parents=True, exist_ok=True)
    timestamp_text = datetime.now().strftime("%Y%m%d_%H%M%S")
    target_path = target_dir / f"{timestamp_text}__{source_file.name}"
    shutil.move(str(source_file), str(target_path))
    return target_path


def write_failure_reason(failed_file_path: Path, reason_text: str) -> Path:
    """
    为失败日志生成原因说明文件。
    """
    reason_file_path = failed_file_path.with_suffix(f"{failed_file_path.suffix}.error.txt")
    reason_file_path.write_text(reason_text, encoding="utf-8")
    return reason_file_path


def derive_source_type_from_adapter(adapter_key: str) -> str:
    """
    根据适配器键名推导统一 source_type。
    """
    source_type_mapping = {
        "safeline_waf": "waf",
        "n9e_waf": "waf",
        "windows_firewall": "firewall",
        "linux_firewall": "firewall",
    }
    return source_type_mapping.get(adapter_key, "unknown")


def build_status_payload(
    *,
    status: str,
    source_file: Path,
    source_directory_name: str,
    source_type: str,
    classifier_result: Dict[str, Any],
    selected_adapter_key: str,
    selected_adapter_name: str,
    parse_error_count: int = 0,
    failed_step: str = "",
    outputs: Dict[str, str] | None = None,
    archived_file: Path | None = None,
    failed_file: Path | None = None,
    reason_file: Path | None = None,
    normalized_file: Path | None = None,
    unified_event_json_file: Path | None = None,
    unified_event_csv_file: Path | None = None,
    attack_behavior_json_file: Path | None = None,
    attack_behavior_csv_file: Path | None = None,
    raw_files: List[Path] | None = None,
    processed_dir: Path | None = None,
    parse_warning_file: Path | None = None,
    unified_event_count: int = 0,
    detected_attack_types: List[str] | None = None,
    blockable_event_count: int = 0,
    behavior_count: int = 0,
    behavior_types: List[str] | None = None,
    blockable_behavior_count: int = 0,
    high_risk_behavior_count: int = 0,
    top_behavior_type: str = "",
) -> Dict[str, Any]:
    """
    统一构造批次 status.json 结构。
    """
    return {
        "status": status,
        "source_file": str(source_file),
        "source_directory_name": source_directory_name,
        "source_type": source_type,
        "classifier_result": classifier_result,
        "selected_adapter_key": selected_adapter_key,
        "selected_adapter_name": selected_adapter_name,
        "archived_file": str(archived_file) if archived_file else "",
        "failed_file": str(failed_file) if failed_file else "",
        "reason_file": str(reason_file) if reason_file else "",
        "normalized_file": str(normalized_file) if normalized_file else "",
        "unified_event_json_file": str(unified_event_json_file) if unified_event_json_file else "",
        "unified_event_csv_file": str(unified_event_csv_file) if unified_event_csv_file else "",
        "attack_behavior_json_file": str(attack_behavior_json_file) if attack_behavior_json_file else "",
        "attack_behavior_csv_file": str(attack_behavior_csv_file) if attack_behavior_csv_file else "",
        "raw_files": [str(item) for item in (raw_files or [])],
        "processed_dir": str(processed_dir) if processed_dir else "",
        "parse_error_count": parse_error_count,
        "parse_warning_file": str(parse_warning_file) if parse_warning_file else "",
        "unified_event_count": unified_event_count,
        "detected_attack_types": detected_attack_types or [],
        "blockable_event_count": blockable_event_count,
        "behavior_count": behavior_count,
        "behavior_types": behavior_types or [],
        "blockable_behavior_count": blockable_behavior_count,
        "high_risk_behavior_count": high_risk_behavior_count,
        "top_behavior_type": top_behavior_type,
        "failed_step": failed_step,
        "outputs": outputs or {},
    }


def resolve_file_routing(file_path: Path) -> Dict[str, Any]:
    """
    对文件执行目录兼容 + unified 自动识别的最小路由决策。

    路由规则：
    1. 旧目录继续优先按目录映射，保持兼容。
    2. unified 目录先做内容识别，再选择最接近的现有适配器。
    3. 当前第一阶段尚未支持的类型只做识别，不强行导入。
    """
    source_directory_name = file_path.parent.name
    classifier_result = classify_log_file(file_path, directory_hint=source_directory_name)
    route_mode = "directory_mapping"
    selected_adapter_key = source_directory_name if source_directory_name in ADAPTER_REGISTRY else ""

    if source_directory_name == "unified":
        route_mode = "classifier_mapping"
        selected_adapter_key = str(classifier_result.get("adapter_key", "") or "")
    elif not selected_adapter_key:
        route_mode = "classifier_fallback"
        selected_adapter_key = str(classifier_result.get("adapter_key", "") or "")

    source_type = str(classifier_result.get("source_type", "") or derive_source_type_from_adapter(selected_adapter_key))
    adapter_info = ADAPTER_REGISTRY.get(selected_adapter_key) if selected_adapter_key else None
    selected_adapter_name = adapter_info["adapter_name"] if adapter_info else "unknown_adapter"
    classifier_payload = {
        **classifier_result,
        "route_mode": route_mode,
        "selected_adapter_key": selected_adapter_key,
        "selected_adapter_name": selected_adapter_name,
    }

    if source_directory_name == "unified" and adapter_info is None:
        unsupported_message = (
            f"统一入口已识别为 {source_type or 'unknown'}，"
            "但当前第一阶段尚未接入对应解析器，请先使用已支持的 WAF / firewall 日志样例进行演示。"
        )
    else:
        unsupported_message = ""

    return {
        "source_directory_name": source_directory_name,
        "source_type": source_type or "unknown",
        "classifier_result": classifier_payload,
        "selected_adapter_key": selected_adapter_key,
        "selected_adapter_name": selected_adapter_name,
        "adapter_info": adapter_info,
        "unsupported_message": unsupported_message,
    }


def process_file(file_path: Path, dry_run: bool, env_mapping: Dict[str, str]) -> None:
    """
    处理单个原始日志文件。
    """
    route_info = resolve_file_routing(file_path)
    source_key = route_info["source_directory_name"]
    source_type = route_info["source_type"]
    classifier_result = route_info["classifier_result"]
    selected_adapter_key = route_info["selected_adapter_key"]
    selected_adapter_name = route_info["selected_adapter_name"]
    adapter_info = route_info["adapter_info"]

    batch_dir = create_batch_directory(source_key, file_path, create_on_disk=not dry_run)
    normalized_file_path = batch_dir / "normalized_logs.csv"
    runtime_raw_dir = batch_dir / "raw"
    runtime_processed_dir = batch_dir / "processed"
    warnings_file_path = batch_dir / "parse_warnings.txt"
    status_file_path = batch_dir / "status.json"
    unified_events_json_path = batch_dir / "unified_events.json"
    unified_events_csv_path = batch_dir / "unified_events.csv"
    attack_behaviors_json_path = batch_dir / "attack_behaviors.json"
    attack_behaviors_csv_path = batch_dir / "attack_behaviors.csv"

    print(f"[log_watcher] 发现文件：{file_path}")
    print(f"[log_watcher] 目录来源：{source_key}")
    print(f"[log_watcher] 自动识别结果：source_type={source_type}，adapter={selected_adapter_key or 'unknown'}")
    print(f"[log_watcher] 识别说明：{classifier_result.get('reason', '-')}")

    if adapter_info is None:
        reason_text = route_info["unsupported_message"] or "当前文件无法匹配到可用解析器。"
        print(f"[log_watcher] {reason_text}")
        if dry_run:
            return

        failed_file_path = move_file_to_directory(file_path, FAILED_ROOT, source_key)
        reason_file_path = write_failure_reason(failed_file_path, reason_text)
        write_status_json(
            status_file_path,
            build_status_payload(
                status="FAILED",
                source_file=file_path,
                source_directory_name=source_key,
                source_type=source_type,
                classifier_result=classifier_result,
                selected_adapter_key=selected_adapter_key,
                selected_adapter_name=selected_adapter_name,
                failed_step="classify_or_route",
                failed_file=failed_file_path,
                reason_file=reason_file_path,
            ),
        )
        print(f"[log_watcher] 已移动到失败目录：{failed_file_path}")
        print(f"[log_watcher] 失败原因文件：{reason_file_path}")
        return

    parse_file_func = adapter_info["parse_file"]
    print(f"[log_watcher] 使用适配器：{selected_adapter_name}")

    try:
        records, parse_errors = parse_file_func(file_path)
    except Exception as exc:
        reason_text = f"适配器解析失败：{exc}"
        print(f"[log_watcher] {reason_text}")
        if dry_run:
            return

        failed_file_path = move_file_to_directory(file_path, FAILED_ROOT, source_key)
        reason_file_path = write_failure_reason(failed_file_path, reason_text)
        write_status_json(
            status_file_path,
            build_status_payload(
                status="FAILED",
                source_file=file_path,
                source_directory_name=source_key,
                source_type=source_type,
                classifier_result=classifier_result,
                selected_adapter_key=selected_adapter_key,
                selected_adapter_name=selected_adapter_name,
                failed_step="parse_file",
                failed_file=failed_file_path,
                reason_file=reason_file_path,
            ),
        )
        print(f"[log_watcher] 已移动到失败目录：{failed_file_path}")
        print(f"[log_watcher] 失败原因文件：{reason_file_path}")
        return

    if not records:
        reason_text = "适配器未解析出任何有效记录。"
        print(f"[log_watcher] {reason_text}")
        if dry_run:
            return

        failed_file_path = move_file_to_directory(file_path, FAILED_ROOT, source_key)
        reason_file_path = write_failure_reason(failed_file_path, reason_text)
        write_status_json(
            status_file_path,
            build_status_payload(
                status="FAILED",
                source_file=file_path,
                source_directory_name=source_key,
                source_type=source_type,
                classifier_result=classifier_result,
                selected_adapter_key=selected_adapter_key,
                selected_adapter_name=selected_adapter_name,
                parse_error_count=len(parse_errors),
                failed_step="parse_file",
                failed_file=failed_file_path,
                reason_file=reason_file_path,
            ),
        )
        print(f"[log_watcher] 已移动到失败目录：{failed_file_path}")
        print(f"[log_watcher] 失败原因文件：{reason_file_path}")
        return

    print(f"[log_watcher] 解析成功记录数：{len(records)}")
    if parse_errors:
        print(f"[log_watcher] 解析警告数：{len(parse_errors)}，将继续处理有效记录。")

    unified_events = normalize_records_to_events(records, classifier_result, file_path)
    unified_event_summary = summarize_events(unified_events)
    attack_behaviors = recognize_attack_behaviors(unified_events)
    behavior_summary = summarize_behaviors(attack_behaviors)

    print(f"[log_watcher] 将生成统一中间文件：{normalized_file_path}")
    print(f"[log_watcher] 将生成统一安全事件文件：{unified_events_json_path}")
    print(f"[log_watcher] 将生成统一安全事件文件：{unified_events_csv_path}")
    print(f"[log_watcher] 将生成攻击行为文件：{attack_behaviors_json_path}")
    print(f"[log_watcher] 将生成攻击行为文件：{attack_behaviors_csv_path}")
    print(f"[log_watcher] 将生成批次原始目录：{runtime_raw_dir}")
    print(f"[log_watcher] 将生成批次处理目录：{runtime_processed_dir}")
    print(
        "[log_watcher] 统一安全事件统计："
        f"count={unified_event_summary['unified_event_count']}，"
        f"attack_types={','.join(unified_event_summary['detected_attack_types']) or '-'}，"
        f"blockable={unified_event_summary['blockable_event_count']}"
    )
    print(
        "[log_watcher] 攻击行为统计："
        f"count={behavior_summary['behavior_count']}，"
        f"types={','.join(behavior_summary['behavior_types']) or '-'}，"
        f"blockable={behavior_summary['blockable_behavior_count']}，"
        f"high_risk={behavior_summary['high_risk_behavior_count']}"
    )

    if dry_run:
        return

    write_csv_rows(normalized_file_path, UNIFIED_LOG_FIELDS, records)
    write_json_rows(unified_events_json_path, unified_events)
    write_csv_rows(unified_events_csv_path, UNIFIED_EVENT_FIELDS, unified_events)
    write_json_rows(attack_behaviors_json_path, attack_behaviors)
    write_csv_rows(attack_behaviors_csv_path, ATTACK_BEHAVIOR_FIELDS, attack_behaviors)
    if parse_errors:
        warnings_file_path.write_text("\n".join(parse_errors), encoding="utf-8")

    login_rows = build_login_raw_rows(records, source_key)
    host_rows = build_host_raw_rows(records, source_key)
    alert_rows = build_alert_raw_rows()

    login_raw_file = runtime_raw_dir / "login_logs_sample.csv"
    host_raw_file = runtime_raw_dir / "host_logs_sample.csv"
    alert_raw_file = runtime_raw_dir / "alert_logs_sample.csv"

    write_csv_rows(login_raw_file, LOGIN_RAW_FIELDS, login_rows)
    write_csv_rows(host_raw_file, HOST_RAW_FIELDS, host_rows)
    write_csv_rows(alert_raw_file, ALERT_RAW_FIELDS, alert_rows)

    print(f"[log_watcher] 已生成原始桥接文件：{login_raw_file}")
    print(f"[log_watcher] 已生成原始桥接文件：{host_raw_file}")
    print(f"[log_watcher] 已生成原始桥接文件：{alert_raw_file}")

    commands = [
        {
            "name": "clean_logs",
            "command": [
                sys.executable,
                str(BASE_DIR / "scripts" / "clean_logs.py"),
                "--raw-dir",
                str(runtime_raw_dir),
                "--processed-dir",
                str(runtime_processed_dir),
            ],
        },
        {
            "name": "extract_entities",
            "command": [
                sys.executable,
                str(BASE_DIR / "scripts" / "extract_entities.py"),
                "--processed-dir",
                str(runtime_processed_dir),
            ],
        },
        {
            "name": "import_to_neo4j",
            "command": [
                sys.executable,
                str(BASE_DIR / "scripts" / "import_to_neo4j.py"),
                "--processed-dir",
                str(runtime_processed_dir),
                "--skip-schema",
            ],
        },
        {
            "name": "run_detection",
            "command": [
                sys.executable,
                str(BASE_DIR / "scripts" / "run_detection.py"),
            ],
        },
    ]

    execution_outputs: Dict[str, str] = {}
    for item in commands:
        print(f"[log_watcher] 开始执行：{item['name']}")
        is_success, output_text = run_subprocess(item["command"], env_mapping)
        execution_outputs[item["name"]] = output_text
        if output_text:
            print(output_text)

        if not is_success:
            reason_text = f"处理链路在步骤 {item['name']} 失败。\n{output_text}"
            failed_file_path = move_file_to_directory(file_path, FAILED_ROOT, source_key)
            reason_file_path = write_failure_reason(failed_file_path, reason_text)
            write_status_json(
                status_file_path,
                build_status_payload(
                    status="FAILED",
                    source_file=file_path,
                    source_directory_name=source_key,
                    source_type=source_type,
                    classifier_result=classifier_result,
                    selected_adapter_key=selected_adapter_key,
                    selected_adapter_name=selected_adapter_name,
                    parse_error_count=len(parse_errors),
                    failed_step=item["name"],
                    outputs=execution_outputs,
                    failed_file=failed_file_path,
                    reason_file=reason_file_path,
                    normalized_file=normalized_file_path,
                    unified_event_json_file=unified_events_json_path,
                    unified_event_csv_file=unified_events_csv_path,
                    attack_behavior_json_file=attack_behaviors_json_path,
                    attack_behavior_csv_file=attack_behaviors_csv_path,
                    raw_files=[login_raw_file, host_raw_file, alert_raw_file],
                    processed_dir=runtime_processed_dir,
                    parse_warning_file=warnings_file_path if parse_errors else None,
                    unified_event_count=unified_event_summary["unified_event_count"],
                    detected_attack_types=unified_event_summary["detected_attack_types"],
                    blockable_event_count=unified_event_summary["blockable_event_count"],
                    behavior_count=behavior_summary["behavior_count"],
                    behavior_types=behavior_summary["behavior_types"],
                    blockable_behavior_count=behavior_summary["blockable_behavior_count"],
                    high_risk_behavior_count=behavior_summary["high_risk_behavior_count"],
                    top_behavior_type=behavior_summary["top_behavior_type"],
                ),
            )
            print(f"[log_watcher] 处理失败，已移动到失败目录：{failed_file_path}")
            print(f"[log_watcher] 失败原因文件：{reason_file_path}")
            return

    archived_file_path = move_file_to_directory(file_path, ARCHIVE_ROOT, source_key)
    write_status_json(
        status_file_path,
        build_status_payload(
            status="SUCCESS",
            source_file=file_path,
            source_directory_name=source_key,
            source_type=source_type,
            classifier_result=classifier_result,
            selected_adapter_key=selected_adapter_key,
            selected_adapter_name=selected_adapter_name,
            archived_file=archived_file_path,
            normalized_file=normalized_file_path,
            unified_event_json_file=unified_events_json_path,
            unified_event_csv_file=unified_events_csv_path,
            attack_behavior_json_file=attack_behaviors_json_path,
            attack_behavior_csv_file=attack_behaviors_csv_path,
            raw_files=[login_raw_file, host_raw_file, alert_raw_file],
            processed_dir=runtime_processed_dir,
            parse_error_count=len(parse_errors),
            parse_warning_file=warnings_file_path if parse_errors else None,
            unified_event_count=unified_event_summary["unified_event_count"],
            detected_attack_types=unified_event_summary["detected_attack_types"],
            blockable_event_count=unified_event_summary["blockable_event_count"],
            behavior_count=behavior_summary["behavior_count"],
            behavior_types=behavior_summary["behavior_types"],
            blockable_behavior_count=behavior_summary["blockable_behavior_count"],
            high_risk_behavior_count=behavior_summary["high_risk_behavior_count"],
            top_behavior_type=behavior_summary["top_behavior_type"],
            outputs=execution_outputs,
        ),
    )

    print(f"[log_watcher] 已成功导入并完成检测：{file_path.name}")
    print(f"[log_watcher] 原始文件已归档到：{archived_file_path}")


def main() -> int:
    """
    程序主入口。
    """
    load_env_file(BACKEND_ENV_FILE)
    ensure_directories()

    parser = build_argument_parser()
    args = parser.parse_args()

    env_mapping = os.environ.copy()
    print("[log_watcher] 自动日志接入模块已启动")
    print(f"[log_watcher] 监听目录：{INCOMING_ROOT}")
    print(f"[log_watcher] 运行模式：{'单次执行' if args.once else '轮询模式'}")
    print(f"[log_watcher] Dry Run：{'是' if args.dry_run else '否'}")

    try:
        while True:
            pending_files = discover_files()
            if pending_files:
                print(f"[log_watcher] 本轮发现待处理文件 {len(pending_files)} 个。")
                for file_path in pending_files:
                    process_file(file_path, args.dry_run, env_mapping)
            else:
                if args.once:
                    print("[log_watcher] 当前没有发现待处理日志文件。")
                else:
                    print("[log_watcher] 当前未发现新文件，继续等待。")

            if args.once:
                break

            time.sleep(max(1, args.interval))
    except KeyboardInterrupt:
        print("[log_watcher] 已收到终止信号，监听结束。")
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
