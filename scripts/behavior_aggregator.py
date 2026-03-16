#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
文件路径：scripts/behavior_aggregator.py

文件作用：
1. 在 unified_events 之上提供“攻击行为识别层”。
2. 将同一批次中的统一安全事件按攻击行为进行轻量聚合，生成 attack_behaviors.json / csv。
3. 为下一轮“按攻击行为驱动的告警与封禁”准备稳定、可解释的中间结果，而不改动当前主检测链路。

设计原则：
1. 输入只依赖 unified_events，不再以原始日志目录作为业务判断中心。
2. 聚合规则以启发式规则为主，优先保证可解释、可维护、可答辩演示。
3. 单个高危事件可直接形成行为对象；需要阈值的行为则按时间窗口聚合。
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple


SEVERITY_PRIORITY = {
    "LOW": 1,
    "MEDIUM": 2,
    "HIGH": 3,
    "CRITICAL": 4,
}

ATTACK_BEHAVIOR_FIELDS = [
    "behavior_id",
    "behavior_type",
    "source_type",
    "attacker_ip",
    "target_ip",
    "target_asset",
    "target_port",
    "user",
    "start_time",
    "end_time",
    "event_count",
    "related_event_ids",
    "evidence_count",
    "severity",
    "confidence",
    "risk_score",
    "can_block",
    "block_reason",
    "representative_attack_type",
]


def normalize_text(value: Any) -> str:
    """
    将任意值安全转换为字符串。
    """
    if value is None:
        return ""
    return str(value).strip()


def normalize_upper_text(value: Any) -> str:
    """
    将文本统一转为大写。
    """
    text = normalize_text(value)
    return text.upper() if text else ""


def safe_int(value: Any, default_value: int = 0) -> int:
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


def safe_float(value: Any, default_value: float = 0.0) -> float:
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


def to_bool(value: Any) -> bool:
    """
    将不同形式的布尔值统一转换为 bool。
    """
    if isinstance(value, bool):
        return value
    return normalize_text(value).lower() in {"1", "true", "yes", "y", "on"}


def parse_event_time(value: Any) -> datetime | None:
    """
    解析统一事件中的时间字段。

    说明：
    1. unified_events 当前已经尽量输出 ISO 8601，所以这里优先走 fromisoformat。
    2. 若解析失败，返回 None，并由调用方回退为“无时间窗口”的稳定分组方式。
    """
    text = normalize_text(value)
    if not text:
        return None

    normalized_text = text.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized_text)
    except ValueError:
        return None


def floor_datetime_to_window(event_time: datetime | None, window_minutes: int) -> str:
    """
    将事件时间按固定窗口下取整，生成聚合窗口起点。
    """
    if event_time is None:
        return "no_time_window"

    floored_minute = (event_time.minute // window_minutes) * window_minutes
    floored_time = event_time.replace(minute=floored_minute, second=0, microsecond=0)
    return floored_time.isoformat(timespec="seconds")


def load_unified_events(file_path: Path) -> List[Dict[str, Any]]:
    """
    从 unified_events.json 读取统一安全事件。
    """
    if not file_path.exists():
        return []

    try:
        payload = json.loads(file_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"统一事件文件不是有效 JSON：{file_path}") from exc

    if not isinstance(payload, list):
        raise ValueError(f"统一事件文件格式不正确，期望 JSON 数组：{file_path}")

    return [item for item in payload if isinstance(item, dict)]


def write_json_rows(file_path: Path, rows: Iterable[Dict[str, Any]]) -> None:
    """
    写出 JSON 结果文件。
    """
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(json.dumps(list(rows), ensure_ascii=False, indent=2), encoding="utf-8")


def write_csv_rows(file_path: Path, fieldnames: List[str], rows: Iterable[Dict[str, Any]]) -> None:
    """
    写出 CSV 结果文件。
    """
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with file_path.open("w", encoding="utf-8", newline="") as file_obj:
        writer = csv.DictWriter(file_obj, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def map_event_to_behavior_type(event: Dict[str, Any]) -> str:
    """
    将统一事件映射为候选攻击行为类型。

    说明：
    1. 本轮只做最小可运行版本，先覆盖 5 类高优先级行为。
    2. 若当前事件不属于这几类，则返回空串，表示本轮不聚合为行为对象。
    """
    attack_type = normalize_upper_text(event.get("attack_type"))
    event_type = normalize_upper_text(event.get("event_type"))
    status = normalize_upper_text(event.get("status"))
    action = normalize_upper_text(event.get("action"))
    source_type = normalize_upper_text(event.get("source_type"))

    if attack_type == "SQL_INJECTION":
        return "SQL_INJECTION"
    if attack_type in {"COMMAND_INJECTION", "RCE"}:
        return "COMMAND_INJECTION"
    if attack_type in {"LOGIN_FAIL", "BRUTE_FORCE"}:
        return "BRUTE_FORCE"
    if attack_type in {"SCAN", "PROBE", "PORT_SCAN"}:
        return "SCAN_PROBE"
    if event_type in {"FIREWALL_DROP", "DROP", "DENY", "REJECT"}:
        return "FIREWALL_DROP_ABUSE"
    if source_type == "FIREWALL" and (status in {"BLOCKED", "DENIED"} or action in {"DROP", "DENY", "REJECT"}):
        return "FIREWALL_DROP_ABUSE"

    return ""


def build_group_key(event: Dict[str, Any], behavior_type: str, window_minutes: int) -> Tuple[str, str, str, str, str]:
    """
    构造行为聚合键。

    设计说明：
    1. 以 attacker_ip + 时间窗口为主，符合“按攻击行为驱动”的主线。
    2. 对不同攻击类型增加少量细分字段，避免完全不同目标被聚成一个行为。
    """
    event_time = parse_event_time(event.get("event_time"))
    window_start = floor_datetime_to_window(event_time, window_minutes)
    attacker_ip = normalize_text(event.get("src_ip")) or "unknown_attacker"
    target_asset = normalize_text(event.get("asset")) or normalize_text(event.get("hostname")) or normalize_text(event.get("dst_ip"))
    target_port = normalize_text(event.get("dst_port"))
    user = normalize_text(event.get("user"))

    if behavior_type in {"SQL_INJECTION", "COMMAND_INJECTION"}:
        return behavior_type, attacker_ip, window_start, target_asset, ""
    if behavior_type == "BRUTE_FORCE":
        return behavior_type, attacker_ip, window_start, user or target_asset, ""
    if behavior_type == "SCAN_PROBE":
        return behavior_type, attacker_ip, window_start, "", ""
    if behavior_type == "FIREWALL_DROP_ABUSE":
        return behavior_type, attacker_ip, window_start, target_asset, ""
    return behavior_type, attacker_ip, window_start, target_asset, target_port


def pick_most_common(values: Iterable[Any]) -> str:
    """
    取出现次数最多的非空值。
    """
    normalized_values = [normalize_text(item) for item in values if normalize_text(item)]
    if not normalized_values:
        return ""
    return Counter(normalized_values).most_common(1)[0][0]


def compute_behavior_severity(events: List[Dict[str, Any]]) -> str:
    """
    计算行为级严重程度，优先取最高等级。
    """
    event_severities = [normalize_upper_text(item.get("severity")) for item in events]
    best_severity = "LOW"
    best_priority = 0
    for severity in event_severities:
        if SEVERITY_PRIORITY.get(severity, 0) > best_priority:
            best_severity = severity
            best_priority = SEVERITY_PRIORITY.get(severity, 0)
    return best_severity if best_priority else "MEDIUM"


def compute_behavior_confidence(behavior_type: str, event_count: int, events: List[Dict[str, Any]]) -> float:
    """
    计算行为级置信度。

    规则：
    1. 先给每类行为一个基础置信度。
    2. 再根据事件数量增加少量加分，保证结果稳定且可解释。
    """
    base_confidence = {
        "SQL_INJECTION": 0.92,
        "COMMAND_INJECTION": 0.93,
        "BRUTE_FORCE": 0.82,
        "SCAN_PROBE": 0.76,
        "FIREWALL_DROP_ABUSE": 0.8,
    }.get(behavior_type, 0.7)

    average_confidence = 0.0
    if events:
        average_confidence = sum(safe_float(item.get("confidence"), base_confidence) for item in events) / len(events)

    count_bonus = min(0.15, max(0, event_count - 1) * 0.03)
    return round(min(0.99, max(base_confidence, average_confidence) + count_bonus), 2)


def compute_behavior_risk_score(behavior_type: str, event_count: int, severity: str, events: List[Dict[str, Any]]) -> int:
    """
    计算行为级风险分。

    说明：
    1. 仍然采用启发式打分，不引入复杂模型。
    2. 便于后续在论文中解释“行为驱动”的风险提升逻辑。
    """
    base_score = {
        "SQL_INJECTION": 88,
        "COMMAND_INJECTION": 92,
        "BRUTE_FORCE": 70,
        "SCAN_PROBE": 65,
        "FIREWALL_DROP_ABUSE": 72,
    }.get(behavior_type, 60)

    event_bonus = min(20, max(0, event_count - 1) * 4)
    severity_bonus = {
        "LOW": 0,
        "MEDIUM": 4,
        "HIGH": 8,
        "CRITICAL": 12,
    }.get(severity, 0)

    diversity_bonus = 0
    if behavior_type == "SCAN_PROBE":
        unique_urls = len({normalize_text(item.get("url")) for item in events if normalize_text(item.get("url"))})
        unique_ports = len({normalize_text(item.get("dst_port")) for item in events if normalize_text(item.get("dst_port"))})
        diversity_bonus = min(10, (max(0, unique_urls - 1) + max(0, unique_ports - 1)) * 2)

    return min(100, base_score + event_bonus + severity_bonus + diversity_bonus)


def should_emit_behavior(behavior_type: str, events: List[Dict[str, Any]]) -> bool:
    """
    判断聚合结果是否应输出为行为对象。

    说明：
    1. SQL 注入和命令注入允许单条高危事件直接形成行为。
    2. 其余行为使用轻量阈值，避免把噪声事件过度放大。
    """
    event_count = len(events)
    if behavior_type in {"SQL_INJECTION", "COMMAND_INJECTION"}:
        return event_count >= 1
    if behavior_type == "BRUTE_FORCE":
        return event_count >= 3
    if behavior_type == "SCAN_PROBE":
        unique_urls = len({normalize_text(item.get("url")) for item in events if normalize_text(item.get("url"))})
        unique_ports = len({normalize_text(item.get("dst_port")) for item in events if normalize_text(item.get("dst_port"))})
        return event_count >= 2 or unique_urls >= 2 or unique_ports >= 3
    if behavior_type == "FIREWALL_DROP_ABUSE":
        return event_count >= 2
    return event_count >= 1


def build_block_reason(behavior_type: str, event_count: int, attacker_ip: str, start_time: str, end_time: str) -> str:
    """
    生成可解释的封禁建议说明。
    """
    if behavior_type == "SQL_INJECTION":
        return f"源 IP {attacker_ip} 在 {start_time} - {end_time} 期间触发 {event_count} 次 SQL 注入行为。"
    if behavior_type == "COMMAND_INJECTION":
        return f"源 IP {attacker_ip} 在 {start_time} - {end_time} 期间触发 {event_count} 次命令注入行为。"
    if behavior_type == "BRUTE_FORCE":
        return f"源 IP {attacker_ip} 在 {start_time} - {end_time} 期间出现 {event_count} 次登录失败，疑似暴力破解。"
    if behavior_type == "SCAN_PROBE":
        return f"源 IP {attacker_ip} 在 {start_time} - {end_time} 期间存在探测/扫描行为。"
    if behavior_type == "FIREWALL_DROP_ABUSE":
        return f"源 IP {attacker_ip} 在 {start_time} - {end_time} 期间多次触发防火墙丢弃规则。"
    return f"源 IP {attacker_ip} 在 {start_time} - {end_time} 期间存在可疑攻击行为。"


def build_behavior_id(behavior_type: str, attacker_ip: str, start_time: str, target_asset: str, target_port: str) -> str:
    """
    生成稳定的行为编号。
    """
    seed_text = "|".join([behavior_type, attacker_ip, start_time, target_asset, target_port])
    seed_hash = hashlib.sha1(seed_text.encode("utf-8")).hexdigest()[:12].upper()
    return f"BHV_{behavior_type}_{seed_hash}"


def recognize_attack_behaviors(unified_events: Iterable[Dict[str, Any]], window_minutes: int = 5) -> List[Dict[str, Any]]:
    """
    从 unified_events 识别攻击行为对象。
    """
    grouped_events: Dict[Tuple[str, str, str, str, str], List[Dict[str, Any]]] = defaultdict(list)

    for event in unified_events:
        behavior_type = map_event_to_behavior_type(event)
        if not behavior_type:
            continue
        grouped_events[build_group_key(event, behavior_type, window_minutes)].append(dict(event))

    behavior_results: List[Dict[str, Any]] = []
    for group_key, events in grouped_events.items():
        behavior_type, attacker_ip, _, _, _ = group_key
        if not should_emit_behavior(behavior_type, events):
            continue

        sorted_events = sorted(events, key=lambda item: normalize_text(item.get("event_time")))
        first_event = sorted_events[0]
        last_event = sorted_events[-1]
        event_count = len(sorted_events)
        severity = compute_behavior_severity(sorted_events)
        confidence = compute_behavior_confidence(behavior_type, event_count, sorted_events)
        risk_score = compute_behavior_risk_score(behavior_type, event_count, severity, sorted_events)
        target_asset = pick_most_common(item.get("asset") or item.get("hostname") for item in sorted_events)
        target_ip = pick_most_common(item.get("dst_ip") for item in sorted_events)
        target_port = pick_most_common(item.get("dst_port") for item in sorted_events)
        user = pick_most_common(item.get("user") for item in sorted_events)
        representative_attack_type = pick_most_common(item.get("attack_type") for item in sorted_events)
        source_type = pick_most_common(item.get("source_type") for item in sorted_events)
        related_event_ids = [
            normalize_text(item.get("event_id")) or normalize_text(item.get("raw_log_id")) or f"event_{index + 1}"
            for index, item in enumerate(sorted_events)
        ]
        can_block = (
            behavior_type in {"SQL_INJECTION", "COMMAND_INJECTION"}
            or risk_score >= 80
            or (behavior_type == "BRUTE_FORCE" and event_count >= 3)
            or (behavior_type == "FIREWALL_DROP_ABUSE" and event_count >= 3)
        )

        behavior_results.append(
            {
                "behavior_id": build_behavior_id(
                    behavior_type=behavior_type,
                    attacker_ip=attacker_ip,
                    start_time=normalize_text(first_event.get("event_time")),
                    target_asset=target_asset,
                    target_port=target_port,
                ),
                "behavior_type": behavior_type,
                "source_type": source_type or "unknown",
                "attacker_ip": attacker_ip,
                "target_ip": target_ip,
                "target_asset": target_asset,
                "target_port": target_port,
                "user": user,
                "start_time": normalize_text(first_event.get("event_time")),
                "end_time": normalize_text(last_event.get("event_time")),
                "event_count": event_count,
                "related_event_ids": json.dumps(related_event_ids, ensure_ascii=False),
                "evidence_count": event_count,
                "severity": severity,
                "confidence": confidence,
                "risk_score": risk_score,
                "can_block": can_block,
                "block_reason": build_block_reason(
                    behavior_type=behavior_type,
                    event_count=event_count,
                    attacker_ip=attacker_ip,
                    start_time=normalize_text(first_event.get("event_time")),
                    end_time=normalize_text(last_event.get("event_time")),
                ),
                "representative_attack_type": representative_attack_type or behavior_type,
            }
        )

    return sorted(
        behavior_results,
        key=lambda item: (safe_int(item.get("risk_score"), 0), safe_int(item.get("event_count"), 0)),
        reverse=True,
    )


def summarize_behaviors(behaviors: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    """
    统计攻击行为层摘要，供 status.json 和监控页轻量展示。
    """
    behavior_list = list(behaviors)
    behavior_types = [normalize_upper_text(item.get("behavior_type")) for item in behavior_list if normalize_upper_text(item.get("behavior_type"))]
    type_counter = Counter(behavior_types)
    high_risk_behavior_count = sum(1 for item in behavior_list if safe_int(item.get("risk_score"), 0) >= 80)
    blockable_behavior_count = sum(1 for item in behavior_list if to_bool(item.get("can_block")))

    return {
        "behavior_count": len(behavior_list),
        "behavior_types": sorted(type_counter.keys()),
        "blockable_behavior_count": blockable_behavior_count,
        "high_risk_behavior_count": high_risk_behavior_count,
        "top_behavior_type": type_counter.most_common(1)[0][0] if type_counter else "",
    }


def aggregate_behavior_files(
    unified_event_file: Path,
    output_json_file: Path,
    output_csv_file: Path,
    window_minutes: int = 5,
) -> Dict[str, Any]:
    """
    读取统一安全事件文件并生成攻击行为结果文件。
    """
    unified_events = load_unified_events(unified_event_file)
    behaviors = recognize_attack_behaviors(unified_events, window_minutes=window_minutes)
    summary = summarize_behaviors(behaviors)

    write_json_rows(output_json_file, behaviors)
    write_csv_rows(output_csv_file, ATTACK_BEHAVIOR_FIELDS, behaviors)

    return {
        "behaviors": behaviors,
        "summary": summary,
    }


def build_argument_parser() -> argparse.ArgumentParser:
    """
    构造命令行参数。
    """
    parser = argparse.ArgumentParser(description="从 unified_events 识别攻击行为对象。")
    parser.add_argument("--input", required=True, help="unified_events.json 文件路径")
    parser.add_argument("--output-json", required=True, help="attack_behaviors.json 输出路径")
    parser.add_argument("--output-csv", required=True, help="attack_behaviors.csv 输出路径")
    parser.add_argument("--window-minutes", type=int, default=5, help="时间窗口大小，默认 5 分钟")
    return parser


def main() -> int:
    """
    命令行入口。
    """
    args = build_argument_parser().parse_args()
    result = aggregate_behavior_files(
        unified_event_file=Path(args.input),
        output_json_file=Path(args.output_json),
        output_csv_file=Path(args.output_csv),
        window_minutes=max(1, int(args.window_minutes)),
    )

    summary = result["summary"]
    print("[behavior_aggregator] 攻击行为识别完成")
    print(f"  - 行为数量：{summary['behavior_count']}")
    print(f"  - 行为类型：{', '.join(summary['behavior_types']) or '-'}")
    print(f"  - 可封禁行为数：{summary['blockable_behavior_count']}")
    print(f"  - 高风险行为数：{summary['high_risk_behavior_count']}")
    print(f"  - Top 行为类型：{summary['top_behavior_type'] or '-'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
