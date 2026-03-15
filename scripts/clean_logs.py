#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
文件路径：scripts/clean_logs.py

脚本职责：
1. 读取 data/raw/ 下的三类原始日志样例文件。
2. 对原始日志进行基础标准化清洗，包括时间格式、大小写、空值、数字字段和布尔字段处理。
3. 输出中间清洗结果到 data/processed/，供 extract_entities.py 继续抽取实体和关系。

设计说明：
1. 本脚本只做“日志标准化”，不直接生成 Neo4j 节点和关系文件。
2. 这样可以把“数据清洗”和“图谱建模抽取”拆成两个独立步骤，便于论文描述分层流程。
3. 当前脚本使用 Python 标准库实现，不依赖 pandas，便于在教学和答辩环境中直接运行。
"""

from __future__ import annotations

import argparse
import csv
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List


# 通过脚本所在路径反推项目根目录，避免在不同工作目录下执行时出现相对路径错误。
BASE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_RAW_DIR = BASE_DIR / "data" / "raw"
DEFAULT_PROCESSED_DIR = BASE_DIR / "data" / "processed"


# 原始输入文件名定义，集中管理更便于后续维护。
LOGIN_INPUT_FILE = "login_logs_sample.csv"
HOST_INPUT_FILE = "host_logs_sample.csv"
ALERT_INPUT_FILE = "alert_logs_sample.csv"


# 清洗后输出文件名定义。
CLEANED_LOGIN_OUTPUT_FILE = "cleaned_login_logs.csv"
CLEANED_HOST_OUTPUT_FILE = "cleaned_host_logs.csv"
CLEANED_ALERT_OUTPUT_FILE = "cleaned_alert_logs.csv"


# 登录日志清洗后的标准字段顺序。
LOGIN_OUTPUT_FIELDS = [
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


# 主机行为日志清洗后的标准字段顺序。
HOST_OUTPUT_FIELDS = [
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


# 告警联动日志清洗后的标准字段顺序。
ALERT_OUTPUT_FIELDS = [
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


def read_csv_rows(file_path: Path) -> List[Dict[str, str]]:
    """
    读取 CSV 文件并返回字典列表。

    这里统一使用 UTF-8 编码，保证中文日志摘要和中文规则名称不会出现乱码。
    """
    if not file_path.exists():
        raise FileNotFoundError(f"未找到输入文件：{file_path}")

    with file_path.open("r", encoding="utf-8", newline="") as file_obj:
        reader = csv.DictReader(file_obj)
        return [dict(row) for row in reader]


def write_csv_rows(file_path: Path, fieldnames: List[str], rows: List[Dict[str, str]]) -> None:
    """
    将清洗后的结果写入 CSV 文件。

    这里显式传入 fieldnames，确保输出列顺序稳定，后续脚本和 Neo4j 导入过程就能直接复用。
    """
    file_path.parent.mkdir(parents=True, exist_ok=True)

    with file_path.open("w", encoding="utf-8", newline="") as file_obj:
        writer = csv.DictWriter(file_obj, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def normalize_text(value: str) -> str:
    """
    清理普通文本字段。

    处理逻辑：
    1. 空值统一转为空字符串。
    2. 去掉首尾空格，减少由于日志采集格式不一致造成的重复值。
    """
    if value is None:
        return ""

    return str(value).strip()


def normalize_upper_text(value: str) -> str:
    """
    将枚举类字段统一为大写，便于后续规则匹配和 CSV 导入。
    """
    text = normalize_text(value)
    return text.upper() if text else ""


def normalize_username(value: str) -> str:
    """
    用户名统一转小写。

    原因：
    不同系统中用户名可能混用大小写，统一转小写可避免同一账号被错误识别为多个节点。
    """
    text = normalize_text(value)
    return text.lower() if text else ""


def normalize_hostname(value: str) -> str:
    """
    主机名统一转大写，便于与资产清单匹配。
    """
    text = normalize_text(value)
    return text.upper() if text else ""


def normalize_integer_text(value: str) -> str:
    """
    将整数文本标准化为纯数字字符串。

    如果输入为空，则保持为空字符串，避免后续数值转换报错。
    """
    text = normalize_text(value)
    if not text:
        return ""

    return str(int(float(text)))


def normalize_float_text(value: str) -> str:
    """
    将浮点数字段标准化为字符串形式，保留原始数值语义。
    """
    text = normalize_text(value)
    if not text:
        return ""

    number = float(text)

    # 为了让生成的 CSV 更易读，如果是整数形式则不保留多余小数位。
    if number.is_integer():
        return str(int(number))

    return str(number)


def normalize_boolean_text(value: str) -> str:
    """
    将布尔字段统一为 true / false 小写字符串。
    """
    text = normalize_text(value).lower()
    if not text:
        return ""

    if text in {"true", "1", "yes", "y"}:
        return "true"

    if text in {"false", "0", "no", "n"}:
        return "false"

    raise ValueError(f"无法识别的布尔值：{value}")


def normalize_datetime_text(value: str) -> str:
    """
    统一时间字段为 ISO 8601 字符串。

    当前样例数据已经是 ISO 格式，但这里仍保留标准化逻辑，方便后续接入其他原始日志格式。
    """
    text = normalize_text(value)
    if not text:
        return ""

    normalized = text.replace("Z", "+00:00")

    try:
        dt_value = datetime.fromisoformat(normalized)
    except ValueError:
        candidate_formats = [
            "%Y-%m-%d %H:%M:%S",
            "%Y/%m/%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S",
        ]

        for date_format in candidate_formats:
            try:
                dt_value = datetime.strptime(normalized, date_format)
                return dt_value.strftime("%Y-%m-%dT%H:%M:%S+08:00")
            except ValueError:
                continue

        raise ValueError(f"无法识别的时间格式：{value}")

    if dt_value.tzinfo is None:
        return dt_value.strftime("%Y-%m-%dT%H:%M:%S+08:00")

    return dt_value.isoformat(timespec="seconds")


def clean_login_row(row: Dict[str, str]) -> Dict[str, str]:
    """
    清洗登录日志。
    """
    return {
        "raw_log_id": normalize_text(row.get("raw_log_id")),
        "session_hint": normalize_upper_text(row.get("session_hint")),
        "log_source": normalize_upper_text(row.get("log_source")),
        "log_type": normalize_upper_text(row.get("log_type")),
        "event_time": normalize_datetime_text(row.get("event_time")),
        "start_time": normalize_datetime_text(row.get("start_time")),
        "end_time": normalize_datetime_text(row.get("end_time")),
        "username": normalize_username(row.get("username")),
        "display_name": normalize_text(row.get("display_name")),
        "department": normalize_text(row.get("department")),
        "role": normalize_text(row.get("role")),
        "privilege_level": normalize_integer_text(row.get("privilege_level")),
        "src_ip": normalize_text(row.get("src_ip")),
        "dst_ip": normalize_text(row.get("dst_ip")),
        "src_port": normalize_integer_text(row.get("src_port")),
        "dst_port": normalize_integer_text(row.get("dst_port")),
        "hostname": normalize_hostname(row.get("hostname")),
        "protocol": normalize_upper_text(row.get("protocol")),
        "action": normalize_upper_text(row.get("action")),
        "result": normalize_upper_text(row.get("result")),
        "auth_method": normalize_upper_text(row.get("auth_method")),
        "message": normalize_text(row.get("message")),
    }


def clean_host_row(row: Dict[str, str]) -> Dict[str, str]:
    """
    清洗主机行为日志。
    """
    return {
        "raw_log_id": normalize_text(row.get("raw_log_id")),
        "session_hint": normalize_upper_text(row.get("session_hint")),
        "log_source": normalize_upper_text(row.get("log_source")),
        "log_type": normalize_upper_text(row.get("log_type")),
        "event_time": normalize_datetime_text(row.get("event_time")),
        "username": normalize_username(row.get("username")),
        "src_ip": normalize_text(row.get("src_ip")),
        "hostname": normalize_hostname(row.get("hostname")),
        "asset_type": normalize_upper_text(row.get("asset_type")),
        "os_name": normalize_text(row.get("os_name")),
        "owner_department": normalize_text(row.get("owner_department")),
        "critical_level": normalize_integer_text(row.get("critical_level")),
        "protocol": normalize_upper_text(row.get("protocol")),
        "action": normalize_upper_text(row.get("action")),
        "result": normalize_upper_text(row.get("result")),
        "bytes_in": normalize_integer_text(row.get("bytes_in")),
        "bytes_out": normalize_integer_text(row.get("bytes_out")),
        "event_type_hint": normalize_upper_text(row.get("event_type_hint")),
        "confidence": normalize_float_text(row.get("confidence")),
        "risk_score_hint": normalize_float_text(row.get("risk_score_hint")),
        "message": normalize_text(row.get("message")),
    }


def clean_alert_row(row: Dict[str, str]) -> Dict[str, str]:
    """
    清洗告警联动日志。
    """
    return {
        "alert_id": normalize_upper_text(row.get("alert_id")),
        "related_raw_log_id": normalize_text(row.get("related_raw_log_id")),
        "session_hint": normalize_upper_text(row.get("session_hint")),
        "event_type_hint": normalize_upper_text(row.get("event_type_hint")),
        "event_time": normalize_datetime_text(row.get("event_time")),
        "rule_id": normalize_upper_text(row.get("rule_id")),
        "rule_name": normalize_text(row.get("rule_name")),
        "rule_category": normalize_upper_text(row.get("rule_category")),
        "rule_level": normalize_upper_text(row.get("rule_level")),
        "threshold_desc": normalize_text(row.get("threshold_desc")),
        "alert_name": normalize_text(row.get("alert_name")),
        "severity": normalize_upper_text(row.get("severity")),
        "score": normalize_float_text(row.get("score")),
        "status": normalize_upper_text(row.get("status")),
        "first_seen": normalize_datetime_text(row.get("first_seen")),
        "last_seen": normalize_datetime_text(row.get("last_seen")),
        "description": normalize_text(row.get("description")),
        "suggestion": normalize_text(row.get("suggestion")),
        "action_id": normalize_upper_text(row.get("action_id")),
        "action_type": normalize_upper_text(row.get("action_type")),
        "target_type": normalize_upper_text(row.get("target_type")),
        "target_ip": normalize_text(row.get("target_ip")),
        "action_status": normalize_upper_text(row.get("action_status")),
        "executed_at": normalize_datetime_text(row.get("executed_at")),
        "executor": normalize_text(row.get("executor")),
        "ticket_no": normalize_text(row.get("ticket_no")),
        "rollback_supported": normalize_boolean_text(row.get("rollback_supported")),
        "remark": normalize_text(row.get("remark")),
    }


def build_argument_parser() -> argparse.ArgumentParser:
    """
    构造命令行参数解析器。
    """
    parser = argparse.ArgumentParser(description="清洗原始安全日志并生成标准化中间文件。")
    parser.add_argument(
        "--raw-dir",
        default=str(DEFAULT_RAW_DIR),
        help="原始日志目录，默认使用项目下的 data/raw。",
    )
    parser.add_argument(
        "--processed-dir",
        default=str(DEFAULT_PROCESSED_DIR),
        help="清洗结果输出目录，默认使用项目下的 data/processed。",
    )
    return parser


def main() -> int:
    """
    程序主入口。
    """
    parser = build_argument_parser()
    args = parser.parse_args()

    raw_dir = Path(args.raw_dir).resolve()
    processed_dir = Path(args.processed_dir).resolve()

    try:
        login_rows = [clean_login_row(row) for row in read_csv_rows(raw_dir / LOGIN_INPUT_FILE)]
        host_rows = [clean_host_row(row) for row in read_csv_rows(raw_dir / HOST_INPUT_FILE)]
        alert_rows = [clean_alert_row(row) for row in read_csv_rows(raw_dir / ALERT_INPUT_FILE)]

        write_csv_rows(processed_dir / CLEANED_LOGIN_OUTPUT_FILE, LOGIN_OUTPUT_FIELDS, login_rows)
        write_csv_rows(processed_dir / CLEANED_HOST_OUTPUT_FILE, HOST_OUTPUT_FIELDS, host_rows)
        write_csv_rows(processed_dir / CLEANED_ALERT_OUTPUT_FILE, ALERT_OUTPUT_FIELDS, alert_rows)
    except Exception as exc:
        print(f"[clean_logs] 执行失败：{exc}", file=sys.stderr)
        return 1

    print("[clean_logs] 清洗完成。")
    print(f"[clean_logs] 登录日志输出：{processed_dir / CLEANED_LOGIN_OUTPUT_FILE}，共 {len(login_rows)} 行。")
    print(f"[clean_logs] 主机日志输出：{processed_dir / CLEANED_HOST_OUTPUT_FILE}，共 {len(host_rows)} 行。")
    print(f"[clean_logs] 告警日志输出：{processed_dir / CLEANED_ALERT_OUTPUT_FILE}，共 {len(alert_rows)} 行。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
