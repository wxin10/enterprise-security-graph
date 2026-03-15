#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
文件路径：scripts/log_watcher.py

脚本职责：
1. 轮询 data/incoming/ 下的多源日志目录，自动发现新日志文件。
2. 根据来源目录选择对应适配器，将原始日志解析为统一中间格式。
3. 将统一中间格式桥接为当前项目现有脚本可直接消费的批次文件。
4. 自动触发以下处理链路：
   - clean_logs.py
   - extract_entities.py
   - import_to_neo4j.py
   - run_detection.py
5. 处理成功后归档原始日志；处理失败后移动到 failed 目录并记录失败原因。

设计说明：
1. 本脚本优先复用项目现有脚本，不另起一套平行导入流程。
2. 采用“扫描目录 + 批次桥接 + 子脚本调用”的最小可运行方案，便于答辩演示。
3. 当前阶段优先支持文件级自动接入，暂不接入第三方在线 API 或流式消息队列。
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
    "safeline_waf",
    "n9e_waf",
    "windows_firewall",
    "linux_firewall",
]
SUPPORTED_EXTENSIONS = {".json", ".jsonl", ".csv", ".log", ".txt"}


# 将 scripts 目录加入搜索路径，便于直接导入 adapters 包。
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
    读取 backend/.env 并注入环境变量。

    这样 log_watcher 触发 import_to_neo4j.py 和 run_detection.py 时，
    可以自动继承 Neo4j 连接配置，不需要每次手工传参。
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
        help="只打印将要处理的文件和计划生成的中间文件，不真正导入。",
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
        "owner_department": "未知业务域",
        "critical_level": 2,
    }


def resolve_hostname(record: Dict[str, Any]) -> str:
    """
    获取统一记录中的主机名。

    如果源日志没有主机名，则基于目标 IP 生成一个可用占位名称，
    确保现有实体抽取脚本仍能建立 Session -> Host 关系。
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
    """
    username = normalize_text(record.get("username")).lower()
    if username:
        return username
    return build_synthetic_username(source_key, normalize_text(record.get("src_ip"))).lower()


def build_login_raw_rows(records: List[Dict[str, Any]], source_key: str) -> List[Dict[str, Any]]:
    """
    将统一中间记录转换为现有 login_logs_sample.csv 兼容格式。

    设计说明：
    1. 这里的“login”并不严格等于真实登录行为，而是作为当前系统会话建模的桥接输入。
    2. 对于防火墙/WAF 日志，仍然会生成一条“访问会话”型记录，以复用现有 Session 抽取链路。
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
    将统一中间记录转换为现有 host_logs_sample.csv 兼容格式。

    这一步是自动接入链路的关键桥接层：
    1. 新日志源先统一落成 normalized CSV。
    2. 再桥接成现有脚本已经支持的 host_logs_sample.csv 结构。
    3. 这样 extract_entities.py 无需被整套推翻。
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

    兼容策略：
    1. 这里先输出空表头文件，保证 clean_logs.py 和 extract_entities.py 链路正常运行。
    2. 真正的告警由后续 run_detection.py 基于图数据自动生成并写回 Neo4j。
    """
    return []


def write_status_json(file_path: Path, payload: Dict[str, Any]) -> None:
    """
    写出批次状态文件，便于排查和答辩展示。
    """
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def create_batch_directory(source_key: str, file_path: Path) -> Path:
    """
    为单个原始日志文件创建一个独立处理批次目录。
    """
    timestamp_text = datetime.now().strftime("%Y%m%d_%H%M%S")
    batch_name = f"{timestamp_text}_{source_key}_{sanitize_filename(file_path.stem)}"
    batch_dir = BATCH_ROOT / batch_name
    batch_dir.mkdir(parents=True, exist_ok=True)
    return batch_dir


def run_subprocess(command: List[str], env_mapping: Dict[str, str]) -> Tuple[bool, str]:
    """
    执行子脚本，并返回执行是否成功及控制台输出。
    """
    # 在 Windows 终端环境下，子进程标准输出往往会使用本机首选编码而不是固定 UTF-8。
    # 如果这里强制按 UTF-8 解码，遇到中文输出时可能抛出 UnicodeDecodeError，
    # 从而影响自动接入链路的可观测性。为保证演示与实际运行稳定，这里优先使用系统首选编码，
    # 同时在极端情况下以 replace 模式兜底，避免单次输出解码异常中断整个流程。
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


def process_file(file_path: Path, dry_run: bool, env_mapping: Dict[str, str]) -> None:
    """
    处理单个原始日志文件。
    """
    source_key = file_path.parent.name
    adapter_info = ADAPTER_REGISTRY.get(source_key)
    if adapter_info is None:
        print(f"[log_watcher] 未找到目录 {source_key} 对应的适配器，跳过文件：{file_path}")
        return

    adapter_name = adapter_info["adapter_name"]
    parse_file_func = adapter_info["parse_file"]
    print(f"[log_watcher] 发现文件：{file_path}")
    print(f"[log_watcher] 使用适配器：{adapter_name}")

    try:
        records, parse_errors = parse_file_func(file_path)
    except Exception as exc:
        reason_text = f"适配器解析失败：{exc}"
        print(f"[log_watcher] {reason_text}")
        if dry_run:
            return
        failed_file_path = move_file_to_directory(file_path, FAILED_ROOT, source_key)
        reason_file_path = write_failure_reason(failed_file_path, reason_text)
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
        print(f"[log_watcher] 已移动到失败目录：{failed_file_path}")
        print(f"[log_watcher] 失败原因文件：{reason_file_path}")
        return

    batch_dir = create_batch_directory(source_key, file_path)
    normalized_file_path = batch_dir / "normalized_logs.csv"
    runtime_raw_dir = batch_dir / "raw"
    runtime_processed_dir = batch_dir / "processed"
    warnings_file_path = batch_dir / "parse_warnings.txt"
    status_file_path = batch_dir / "status.json"

    print(f"[log_watcher] 解析成功记录数：{len(records)}")
    if parse_errors:
        print(f"[log_watcher] 解析警告数：{len(parse_errors)}，将继续处理有效记录。")

    print(f"[log_watcher] 将生成统一中间文件：{normalized_file_path}")
    print(f"[log_watcher] 将生成批次原始目录：{runtime_raw_dir}")
    print(f"[log_watcher] 将生成批次处理目录：{runtime_processed_dir}")

    if dry_run:
        return

    write_csv_rows(normalized_file_path, UNIFIED_LOG_FIELDS, records)
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
                {
                    "status": "FAILED",
                    "source_file": str(file_path),
                    "failed_file": str(failed_file_path),
                    "reason_file": str(reason_file_path),
                    "failed_step": item["name"],
                    "parse_error_count": len(parse_errors),
                    "outputs": execution_outputs,
                },
            )
            print(f"[log_watcher] 处理失败，已移动到失败目录：{failed_file_path}")
            print(f"[log_watcher] 失败原因文件：{reason_file_path}")
            return

    archived_file_path = move_file_to_directory(file_path, ARCHIVE_ROOT, source_key)
    write_status_json(
        status_file_path,
        {
            "status": "SUCCESS",
            "source_file": str(file_path),
            "archived_file": str(archived_file_path),
            "normalized_file": str(normalized_file_path),
            "raw_files": [str(login_raw_file), str(host_raw_file), str(alert_raw_file)],
            "processed_dir": str(runtime_processed_dir),
            "parse_error_count": len(parse_errors),
            "parse_warning_file": str(warnings_file_path) if parse_errors else "",
            "outputs": execution_outputs,
        },
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
