#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
文件路径：scripts/behavior_alert_mapper.py

文件作用：
1. 在 attack_behaviors 之上提供“行为驱动告警与封禁”的最小接入层。
2. 将每个行为对象映射为兼容当前系统的 Alert 节点，并按可解释阈值生成 BlockAction 记录。
3. 保持现有告警页、封禁页、攻击链图谱和 ban_service 兼容，不重写现有检测与封禁主干。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


BASE_DIR = Path(__file__).resolve().parents[1]
BACKEND_ENV_FILE = BASE_DIR / "backend" / ".env"


def load_graph_database():
    """
    延迟导入官方 Neo4j 驱动，避免项目根目录中的 neo4j/ 文件夹遮蔽官方包。
    """
    original_sys_path = list(sys.path)
    filtered_sys_path: List[str] = []

    for path_item in original_sys_path:
        try:
            resolved_path = Path(path_item).resolve()
        except Exception:
            filtered_sys_path.append(path_item)
            continue

        if resolved_path == BASE_DIR:
            continue

        filtered_sys_path.append(path_item)

    try:
        sys.path[:] = filtered_sys_path
        from neo4j import GraphDatabase  # type: ignore

        return GraphDatabase
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(
            "无法导入官方 neo4j Python 驱动。请先执行 `pip install neo4j`。"
        ) from exc
    finally:
        sys.path[:] = original_sys_path


def load_env_file(env_file: Path) -> None:
    """
    读取 backend/.env，并注入到当前进程环境变量中。
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


def normalize_text(value: Any) -> str:
    """
    将任意值安全转换为字符串。
    """
    if value is None:
        return ""
    return str(value).strip()


def normalize_upper_text(value: Any) -> str:
    """
    将文本统一转换为大写。
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
    将不同形式的布尔值统一转为 bool。
    """
    if isinstance(value, bool):
        return value
    return normalize_text(value).lower() in {"1", "true", "yes", "y", "on"}


def parse_json_list(value: Any) -> List[str]:
    """
    兼容解析 JSON 字符串列表、原生列表和逗号分隔文本。
    """
    if isinstance(value, list):
        return [normalize_text(item) for item in value if normalize_text(item)]

    text = normalize_text(value)
    if not text:
        return []

    if text.startswith("[") and text.endswith("]"):
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            payload = []
        if isinstance(payload, list):
            return [normalize_text(item) for item in payload if normalize_text(item)]

    return [item.strip() for item in text.split(",") if item.strip()]


def build_local_timestamp() -> str:
    """
    生成本地 ISO 时间字符串。
    """
    return datetime.now().astimezone().isoformat(timespec="seconds")


def sanitize_identifier(value: str) -> str:
    """
    将文本转换为适合规则名和主键的安全片段。
    """
    return re.sub(r"[^0-9A-Za-z_-]+", "_", normalize_text(value)).strip("_") or "UNKNOWN"


def load_attack_behaviors(file_path: Path) -> List[Dict[str, Any]]:
    """
    从批次 attack_behaviors.json 读取行为对象。
    """
    if not file_path.exists():
        return []

    payload = json.loads(file_path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"行为识别文件格式不正确，期望 JSON 数组：{file_path}")

    return [item for item in payload if isinstance(item, dict)]


class BehaviorAlertMapper:
    """
    行为驱动映射器。

    核心职责：
    1. 将 attack_behaviors 映射为兼容现有系统的 Alert 节点。
    2. 对满足阈值的行为生成 BlockAction 记录，并同步目标 IP 当前状态。
    3. 尽可能复用 Event / Rule / IP / Host 现有节点，减少对当前图模型的冲击。
    """

    HIGH_PRIORITY_BEHAVIOR_TYPES = {
        "SQL_INJECTION",
        "COMMAND_INJECTION",
        "BRUTE_FORCE",
        "FIREWALL_DROP_ABUSE",
    }

    def __init__(self):
        load_env_file(BACKEND_ENV_FILE)

        graph_database = load_graph_database()
        uri = normalize_text(os.getenv("NEO4J_URI"))
        username = normalize_text(os.getenv("NEO4J_USERNAME"))
        password = normalize_text(os.getenv("NEO4J_PASSWORD"))
        database = normalize_text(os.getenv("NEO4J_DATABASE")) or "neo4j"

        if not uri or not username or not password:
            raise RuntimeError("缺少 Neo4j 连接配置，请检查 backend/.env 或环境变量。")

        self.driver = graph_database.driver(uri, auth=(username, password))
        self.database = database
        self.enforcement_mode = self._resolve_enforcement_mode(os.getenv("BAN_ENFORCEMENT_MODE", "MOCK"))
        self.enforcement_backend = "MOCK" if self.enforcement_mode == "MOCK" else "WINDOWS_FIREWALL"
        self.rule_prefix = normalize_text(os.getenv("BAN_WINDOWS_FIREWALL_RULE_PREFIX")) or "ESG"
        self.local_ports = [
            item.strip()
            for item in normalize_text(os.getenv("BAN_WINDOWS_FIREWALL_LOCAL_PORTS")).split(",")
            if item.strip()
        ]

    def close(self) -> None:
        """
        释放 Neo4j 驱动资源。
        """
        self.driver.close()

    def execute_read(self, query: str, parameters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        执行只读查询。
        """
        with self.driver.session(database=self.database) as session:
            result = session.run(query, parameters or {})
            return [record.data() for record in result]

    def execute_write(self, query: str, parameters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        执行写入查询。
        """
        with self.driver.session(database=self.database) as session:
            result = session.run(query, parameters or {})
            records = [record.data() for record in result]
            result.consume()
            return records

    def apply_behaviors(self, behaviors: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
        """
        将一组行为对象映射为行为级告警与封禁记录。
        """
        behavior_list = [dict(item) for item in behaviors if isinstance(item, dict)]
        results: List[Dict[str, Any]] = []

        for behavior in behavior_list:
            results.append(self._apply_single_behavior(behavior))

        blockable_types = [
            normalize_upper_text(item.get("behavior_type"))
            for item in results
            if item.get("block_candidate")
        ]
        type_counter = Counter([item for item in blockable_types if item])

        return {
            "behavior_driven_enabled": True,
            "behavior_driven_used": len(behavior_list) > 0,
            "alert_count_from_behaviors": sum(1 for item in results if item.get("alert_created")),
            "block_candidate_count_from_behaviors": sum(1 for item in results if item.get("block_candidate")),
            "blocked_behavior_count": sum(1 for item in results if item.get("block_created")),
            "top_blockable_behavior_type": type_counter.most_common(1)[0][0] if type_counter else "",
            "results": results,
        }

    def _apply_single_behavior(self, behavior: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理单个行为对象。
        """
        behavior_type = normalize_upper_text(behavior.get("behavior_type"))
        behavior_id = normalize_text(behavior.get("behavior_id")) or f"BHV_UNKNOWN_{sanitize_identifier(build_local_timestamp())}"
        attacker_ip = normalize_text(behavior.get("attacker_ip"))
        target_ip = normalize_text(behavior.get("target_ip"))
        target_asset = normalize_text(behavior.get("target_asset"))
        target_port = normalize_text(behavior.get("target_port"))
        user = normalize_text(behavior.get("user"))
        severity = normalize_upper_text(behavior.get("severity")) or "MEDIUM"
        confidence = safe_float(behavior.get("confidence"), 0.0)
        risk_score = safe_int(behavior.get("risk_score"), 0)
        source_type = normalize_text(behavior.get("source_type")) or "unknown"
        event_count = safe_int(behavior.get("event_count"), 0)
        block_reason = normalize_text(behavior.get("block_reason"))
        representative_attack_type = normalize_upper_text(behavior.get("representative_attack_type")) or behavior_type
        related_event_ids = parse_json_list(behavior.get("related_event_ids"))
        current_time = build_local_timestamp()

        alert_id = f"BHALT_{sanitize_identifier(behavior_id)}"
        action_id = f"BBA_{sanitize_identifier(behavior_id)}"
        rule_id = f"BRULE_{sanitize_identifier(behavior_type or 'UNKNOWN')}"

        ip_node = self._ensure_ip_node(attacker_ip=attacker_ip, risk_score=risk_score, severity=severity)
        host_node = self._ensure_host_node(target_asset=target_asset, target_ip=target_ip, risk_score=risk_score)

        self._upsert_rule(rule_id=rule_id, behavior_type=behavior_type)
        self._upsert_alert(
            alert_id=alert_id,
            rule_id=rule_id,
            behavior=behavior,
            ip_node=ip_node,
            host_node=host_node,
            current_time=current_time,
            related_event_ids=related_event_ids,
            source_type=source_type,
            severity=severity,
            confidence=confidence,
            risk_score=risk_score,
            event_count=event_count,
            attacker_ip=attacker_ip,
            target_ip=target_ip,
            target_asset=target_asset,
            target_port=target_port,
            user=user,
            block_reason=block_reason,
            representative_attack_type=representative_attack_type,
        )
        self._link_events_to_alert(alert_id=alert_id, related_event_ids=related_event_ids, relation_time=current_time)

        block_candidate, resolved_block_reason = self._evaluate_block_candidate(behavior)
        block_created = False
        if block_candidate and ip_node:
            self._upsert_block_action(
                action_id=action_id,
                alert_id=alert_id,
                behavior=behavior,
                ip_node=ip_node,
                current_time=current_time,
                block_reason=resolved_block_reason,
                severity=severity,
                risk_score=risk_score,
                confidence=confidence,
                event_count=event_count,
                source_type=source_type,
            )
            block_created = True

        return {
            "behavior_id": behavior_id,
            "behavior_type": behavior_type,
            "alert_id": alert_id,
            "action_id": action_id if block_candidate else "",
            "alert_created": True,
            "block_candidate": block_candidate,
            "block_created": block_created,
        }

    def _ensure_ip_node(self, attacker_ip: str, risk_score: int, severity: str) -> Dict[str, Any]:
        """
        确保攻击源 IP 节点存在，并返回其主键信息。
        """
        normalized_ip = normalize_text(attacker_ip)
        if not normalized_ip:
            return {}

        records = self.execute_read(
            """
MATCH (ip:IP)
WHERE ip.ip_address = $ip_address
RETURN ip.ip_id AS ip_id,
       ip.ip_address AS ip_address
LIMIT 1
""",
            {"ip_address": normalized_ip},
        )
        if records:
            ip_id = normalize_text(records[0].get("ip_id"))
            self.execute_write(
                """
MATCH (ip:IP {ip_id: $ip_id})
SET ip.risk_score = CASE
        WHEN coalesce(ip.risk_score, 0) < $risk_score THEN $risk_score
        ELSE ip.risk_score
    END,
    ip.reputation_level = CASE
        WHEN coalesce(ip.reputation_level, '') = '' THEN $severity
        ELSE ip.reputation_level
    END
RETURN ip.ip_id AS ip_id
""",
                {
                    "ip_id": ip_id,
                    "risk_score": risk_score,
                    "severity": severity,
                },
            )
            return {"ip_id": ip_id, "ip_address": normalized_ip}

        ip_id = f"IP_BHV_{sanitize_identifier(normalized_ip.replace('.', '_').replace(':', '_'))}"
        self.execute_write(
            """
MERGE (ip:IP {ip_id: $ip_id})
SET ip.ip_address = $ip_address,
    ip.ip_type = 'ATTACKER',
    ip.geo_location = coalesce(ip.geo_location, 'UNKNOWN'),
    ip.reputation_level = $severity,
    ip.is_blocked = coalesce(ip.is_blocked, false),
    ip.risk_score = $risk_score,
    ip.created_at = coalesce(ip.created_at, $created_at)
RETURN ip.ip_id AS ip_id
""",
            {
                "ip_id": ip_id,
                "ip_address": normalized_ip,
                "severity": severity,
                "risk_score": risk_score,
                "created_at": build_local_timestamp(),
            },
        )
        return {"ip_id": ip_id, "ip_address": normalized_ip}

    def _ensure_host_node(self, target_asset: str, target_ip: str, risk_score: int) -> Dict[str, Any]:
        """
        尽量复用或补充目标资产节点，便于攻击链图谱展示。
        """
        host_name = normalize_text(target_asset) or normalize_text(target_ip)
        if not host_name:
            return {}

        records = self.execute_read(
            """
MATCH (h:Host)
WHERE h.hostname = $hostname OR h.host_id = $hostname
RETURN h.host_id AS host_id,
       h.hostname AS hostname
LIMIT 1
""",
            {"hostname": host_name},
        )
        if records:
            return {
                "host_id": normalize_text(records[0].get("host_id")),
                "hostname": normalize_text(records[0].get("hostname")) or host_name,
            }

        host_id = f"HOST_BHV_{sanitize_identifier(host_name.upper())}"
        self.execute_write(
            """
MERGE (h:Host {host_id: $host_id})
SET h.hostname = $hostname,
    h.asset_type = coalesce(h.asset_type, 'AUTO_DISCOVERED_ASSET'),
    h.os_name = coalesce(h.os_name, 'Unknown'),
    h.critical_level = coalesce(h.critical_level, 3),
    h.owner_department = coalesce(h.owner_department, '自动识别'),
    h.status = coalesce(h.status, 'ACTIVE'),
    h.risk_score = CASE
        WHEN coalesce(h.risk_score, 0) < $risk_score THEN $risk_score
        ELSE h.risk_score
    END,
    h.created_at = coalesce(h.created_at, $created_at)
RETURN h.host_id AS host_id
""",
            {
                "host_id": host_id,
                "hostname": host_name,
                "risk_score": risk_score,
                "created_at": build_local_timestamp(),
            },
        )
        return {"host_id": host_id, "hostname": host_name}

    def _upsert_rule(self, rule_id: str, behavior_type: str) -> None:
        """
        为行为对象补一个轻量规则节点，供告警列表与攻击链图谱复用。
        """
        rule_name_mapping = {
            "SQL_INJECTION": "行为识别规则-SQL 注入",
            "COMMAND_INJECTION": "行为识别规则-命令注入",
            "BRUTE_FORCE": "行为识别规则-暴力破解",
            "SCAN_PROBE": "行为识别规则-扫描探测",
            "FIREWALL_DROP_ABUSE": "行为识别规则-防火墙丢弃滥用",
        }

        self.execute_write(
            """
MERGE (r:Rule {rule_id: $rule_id})
SET r.rule_name = $rule_name,
    r.rule_category = 'BEHAVIOR_DRIVEN',
    r.rule_level = $rule_level,
    r.threshold_desc = '基于 attack_behaviors 的最小行为驱动映射规则',
    r.description = '由行为识别层自动生成的统一行为级规则映射',
    r.enabled = true,
    r.rule_source = 'BEHAVIOR_ENGINE'
RETURN r.rule_id AS rule_id
""",
            {
                "rule_id": rule_id,
                "rule_name": rule_name_mapping.get(behavior_type, f"行为识别规则-{behavior_type or '未知行为'}"),
                "rule_level": "HIGH" if behavior_type in self.HIGH_PRIORITY_BEHAVIOR_TYPES else "MEDIUM",
            },
        )

    def _upsert_alert(
        self,
        *,
        alert_id: str,
        rule_id: str,
        behavior: Dict[str, Any],
        ip_node: Dict[str, Any],
        host_node: Dict[str, Any],
        current_time: str,
        related_event_ids: List[str],
        source_type: str,
        severity: str,
        confidence: float,
        risk_score: int,
        event_count: int,
        attacker_ip: str,
        target_ip: str,
        target_asset: str,
        target_port: str,
        user: str,
        block_reason: str,
        representative_attack_type: str,
    ) -> None:
        """
        将行为对象映射为兼容当前接口的 Alert 节点。
        """
        behavior_id = normalize_text(behavior.get("behavior_id"))
        behavior_type = normalize_upper_text(behavior.get("behavior_type"))
        start_time = normalize_text(behavior.get("start_time"))
        end_time = normalize_text(behavior.get("end_time")) or start_time
        description = (
            f"行为识别层判定源 IP {attacker_ip or '-'} 在 {start_time or '-'} 至 {end_time or '-'} 期间"
            f"触发 {event_count} 次 {behavior_type or '未知'} 行为，风险分 {risk_score}。"
        )
        suggestion = (
            f"建议围绕行为类型 {behavior_type or '-'} 复核相关证据。"
            + (" 当前已满足自动封禁候选条件。" if self._evaluate_block_candidate(behavior)[0] else " 当前建议先观察或人工复核。")
        )
        alert_name = f"行为告警-{behavior_type or 'UNKNOWN'}"
        evidence_ip_ids = [ip_node.get("ip_id")] if ip_node else []
        evidence_host_ids = [host_node.get("host_id")] if host_node else []

        self.execute_write(
            """
MERGE (a:Alert {alert_id: $alert_id})
ON CREATE SET a.status = 'CONFIRMED'
SET a.alert_name = $alert_name,
    a.severity = $severity,
    a.score = $risk_score,
    a.first_seen = CASE
        WHEN coalesce(a.first_seen, '') = '' OR a.first_seen > $start_time THEN $start_time
        ELSE a.first_seen
    END,
    a.last_seen = CASE
        WHEN coalesce(a.last_seen, '') = '' OR a.last_seen < $end_time THEN $end_time
        ELSE a.last_seen
    END,
    a.description = $description,
    a.suggestion = $suggestion,
    a.generated_by = 'BEHAVIOR_ENGINE',
    a.behavior_id = $behavior_id,
    a.behavior_type = $behavior_type,
    a.source_type = $source_type,
    a.attacker_ip = $attacker_ip,
    a.target_ip = $target_ip,
    a.target_asset = $target_asset,
    a.target_port = $target_port,
    a.user = $user,
    a.event_count = $event_count,
    a.evidence_count = $event_count,
    a.confidence = $confidence,
    a.can_block = $can_block,
    a.block_reason = $block_reason,
    a.representative_attack_type = $representative_attack_type,
    a.rule_id = $rule_id,
    a.related_rule_ids = [$rule_id],
    a.evidence_event_ids = $related_event_ids,
    a.evidence_ip_ids = $evidence_ip_ids,
    a.evidence_host_ids = $evidence_host_ids,
    a.updated_at = $updated_at
WITH a
MATCH (r:Rule {rule_id: $rule_id})
MERGE (a)-[hr:HIT_RULE]->(r)
SET hr.relation_time = $updated_at
RETURN a.alert_id AS alert_id
""",
            {
                "alert_id": alert_id,
                "alert_name": alert_name,
                "severity": severity,
                "risk_score": risk_score,
                "start_time": start_time,
                "end_time": end_time,
                "description": description,
                "suggestion": suggestion,
                "behavior_id": behavior_id,
                "behavior_type": behavior_type,
                "source_type": source_type,
                "attacker_ip": attacker_ip,
                "target_ip": target_ip,
                "target_asset": target_asset,
                "target_port": target_port,
                "user": user,
                "event_count": event_count,
                "confidence": confidence,
                "can_block": to_bool(behavior.get("can_block")),
                "block_reason": block_reason,
                "representative_attack_type": representative_attack_type,
                "rule_id": rule_id,
                "related_event_ids": related_event_ids,
                "evidence_ip_ids": evidence_ip_ids,
                "evidence_host_ids": evidence_host_ids,
                "updated_at": current_time,
            },
        )

    def _link_events_to_alert(self, alert_id: str, related_event_ids: List[str], relation_time: str) -> None:
        """
        将行为证据事件轻量挂到 Alert 节点上，保证攻击链图谱可回溯到 Event。
        """
        if not related_event_ids:
            return

        self.execute_write(
            """
MATCH (a:Alert {alert_id: $alert_id})
UNWIND $event_ids AS event_ref
OPTIONAL MATCH (e:Event)
WHERE e.event_id = event_ref OR e.raw_log_id = event_ref
FOREACH (_ IN CASE WHEN e IS NULL THEN [] ELSE [1] END |
    MERGE (e)-[r:TRIGGERS]->(a)
    SET r.relation_time = $relation_time
)
RETURN count(*) AS total
""",
            {
                "alert_id": alert_id,
                "event_ids": related_event_ids,
                "relation_time": relation_time,
            },
        )

    def _upsert_block_action(
        self,
        *,
        action_id: str,
        alert_id: str,
        behavior: Dict[str, Any],
        ip_node: Dict[str, Any],
        current_time: str,
        block_reason: str,
        severity: str,
        risk_score: int,
        confidence: float,
        event_count: int,
        source_type: str,
    ) -> None:
        """
        将可封禁行为映射为兼容当前封禁页和 ban_service 的 BlockAction 记录。
        """
        existing = self.execute_read(
            """
MATCH (b:BlockAction {action_id: $action_id})
RETURN properties(b) AS ban
LIMIT 1
""",
            {"action_id": action_id},
        )
        existing_ban = existing[0]["ban"] if existing else {}
        history_actions = self._build_next_history_actions(existing_ban, current_time, block_reason)
        history_summary = self._build_history_summary(history_actions)
        block_count = sum(1 for item in history_actions if normalize_upper_text(item.get("to_status")) == "BLOCKED")
        release_count = sum(1 for item in history_actions if normalize_upper_text(item.get("to_status")) == "RELEASED")
        rule_name = self._build_firewall_rule_name(action_id, ip_node.get("ip_address"))

        enforcement_status = "SIMULATED" if self.enforcement_mode == "MOCK" else "PENDING"
        enforcement_message = (
            "当前为行为驱动最小接入版，已生成封禁记录并等待后续复核或宿主机规则执行。"
            if self.enforcement_mode == "REAL"
            else "当前为模拟执行模式，行为驱动结果仅生成业务封禁记录。"
        )
        verification_message = (
            "当前为模拟执行模式，未真正下发宿主机规则"
            if self.enforcement_mode == "MOCK"
            else "当前为行为驱动最小接入版，尚未执行宿主机规则校验"
        )

        self.execute_write(
            """
MATCH (a:Alert {alert_id: $alert_id})
MATCH (ip:IP {ip_id: $ip_id})
MERGE (b:BlockAction {action_id: $action_id})
SET b.action_type = 'BLOCK_IP',
    b.latest_action_type = 'BLOCK_IP',
    b.target_type = 'IP',
    b.status = 'BLOCKED',
    b.current_ban_status = 'BLOCKED',
    b.current_block_status = 'BLOCKED',
    b.executed_at = coalesce(b.executed_at, $action_at),
    b.executor = coalesce(b.executor, 'behavior_engine'),
    b.ticket_no = coalesce(b.ticket_no, $behavior_id),
    b.rollback_supported = true,
    b.remark = $block_reason,
    b.blocked_at = coalesce(b.blocked_at, $action_at),
    b.blocked_by = coalesce(b.blocked_by, 'behavior_engine'),
    b.block_reason = $block_reason,
    b.latest_action_at = $action_at,
    b.latest_action_by = 'behavior_engine',
    b.latest_action_reason = $block_reason,
    b.latest_operator = 'behavior_engine',
    b.latest_reason = $block_reason,
    b.history_actions_json = $history_actions_json,
    b.history_summary = $history_summary,
    b.history_action_count = $history_action_count,
    b.block_count = $block_count,
    b.release_count = $release_count,
    b.behavior_id = $behavior_id,
    b.behavior_type = $behavior_type,
    b.source_type = $source_type,
    b.risk_score = $risk_score,
    b.confidence = $confidence,
    b.event_count = $event_count,
    b.target_ip = $target_ip,
    b.enforcement_mode = $enforcement_mode,
    b.enforcement_backend = $enforcement_backend,
    b.enforcement_status = $enforcement_status,
    b.enforcement_rule_name = $enforcement_rule_name,
    b.enforcement_message = $enforcement_message,
    b.verification_status = 'NOT_VERIFIED',
    b.verified_at = coalesce(b.verified_at, ''),
    b.verification_message = $verification_message,
    b.enforcement_scope_ports = $enforcement_scope_ports,
    b.updated_at = $action_at
MERGE (b)-[da:DISPOSES]->(a)
SET da.relation_time = $action_at
MERGE (b)-[ti:TARGETS_IP]->(ip)
SET ti.relation_time = $action_at
SET ip.is_blocked = true,
    ip.ip_block_status = 'BLOCKED',
    ip.current_block_status = 'BLOCKED',
    ip.latest_action_type = 'BLOCK_IP',
    ip.latest_action_at = $action_at,
    ip.latest_action_by = 'behavior_engine',
    ip.latest_action_reason = $block_reason,
    ip.blocked_at = coalesce(ip.blocked_at, $action_at),
    ip.risk_score = CASE
        WHEN coalesce(ip.risk_score, 0) < $risk_score THEN $risk_score
        ELSE ip.risk_score
    END
SET a.disposition_status = 'BLOCKED',
    a.latest_action_type = 'BLOCK_IP',
    a.latest_action_at = $action_at,
    a.latest_action_by = 'behavior_engine',
    a.latest_action_reason = $block_reason
RETURN b.action_id AS action_id
""",
            {
                "alert_id": alert_id,
                "ip_id": ip_node.get("ip_id"),
                "action_id": action_id,
                "action_at": current_time,
                "behavior_id": normalize_text(behavior.get("behavior_id")),
                "behavior_type": normalize_upper_text(behavior.get("behavior_type")),
                "source_type": source_type,
                "risk_score": risk_score,
                "confidence": confidence,
                "event_count": event_count,
                "target_ip": ip_node.get("ip_address"),
                "block_reason": block_reason,
                "history_actions_json": json.dumps(history_actions, ensure_ascii=False),
                "history_summary": history_summary,
                "history_action_count": len(history_actions),
                "block_count": block_count,
                "release_count": release_count,
                "enforcement_mode": self.enforcement_mode,
                "enforcement_backend": self.enforcement_backend,
                "enforcement_status": enforcement_status,
                "enforcement_rule_name": rule_name,
                "enforcement_message": enforcement_message,
                "verification_message": verification_message,
                "enforcement_scope_ports": ",".join(self.local_ports),
            },
        )

    def _build_next_history_actions(
        self,
        existing_ban: Dict[str, Any],
        current_time: str,
        block_reason: str,
    ) -> List[Dict[str, Any]]:
        """
        构造下一版历史动作列表。

        规则：
        1. 若当前已经是 BLOCKED 且最近动作也是 BLOCK_IP，则不重复追加。
        2. 若当前是 RELEASED 或尚无历史，则补一条新的自动封禁动作。
        """
        normalized_history: List[Dict[str, Any]] = []

        try:
            existing_history = json.loads(normalize_text(existing_ban.get("history_actions_json")) or "[]")
        except json.JSONDecodeError:
            existing_history = []

        if isinstance(existing_history, list):
            for item in existing_history:
                if isinstance(item, dict):
                    normalized_history.append(item)

        current_status = normalize_upper_text(existing_ban.get("current_ban_status")) or normalize_upper_text(existing_ban.get("status"))
        latest_action_type = normalize_upper_text(existing_ban.get("latest_action_type")) or normalize_upper_text(existing_ban.get("action_type"))

        if current_status == "BLOCKED" and latest_action_type == "BLOCK_IP" and normalized_history:
            return normalized_history

        normalized_history.append(
            {
                "sequence": len(normalized_history) + 1,
                "action_type": "BLOCK_IP",
                "from_status": current_status or "NEW",
                "to_status": "BLOCKED",
                "operated_at": current_time,
                "operated_by": "behavior_engine",
                "reason": block_reason,
                "origin": "AUTO",
            }
        )
        return normalized_history

    def _build_history_summary(self, history_actions: List[Dict[str, Any]]) -> str:
        """
        生成轻量历史摘要字符串，供封禁页列表直接展示。
        """
        if not history_actions:
            return ""

        tail_items = history_actions[-4:]
        fragments = []
        for item in tail_items:
            action_type = normalize_upper_text(item.get("action_type"))
            operated_at = normalize_text(item.get("operated_at"))
            fragments.append(f"{action_type}@{operated_at}")
        return " | ".join(fragments)

    def _evaluate_block_candidate(self, behavior: Dict[str, Any]) -> tuple[bool, str]:
        """
        判断当前行为是否应进入封禁候选。
        """
        behavior_type = normalize_upper_text(behavior.get("behavior_type"))
        attacker_ip = normalize_text(behavior.get("attacker_ip"))
        risk_score = safe_int(behavior.get("risk_score"), 0)
        can_block = to_bool(behavior.get("can_block"))
        reason = normalize_text(behavior.get("block_reason"))

        if not attacker_ip:
            return False, "当前行为缺少攻击源 IP，无法进入封禁候选。"

        if behavior_type in {"SQL_INJECTION", "COMMAND_INJECTION"}:
            return can_block or risk_score >= 75, reason or "高危注入类行为满足自动封禁候选条件。"

        if behavior_type in {"BRUTE_FORCE", "FIREWALL_DROP_ABUSE"}:
            return can_block or risk_score >= 80, reason or "高风险持续异常行为满足自动封禁候选条件。"

        if behavior_type == "SCAN_PROBE":
            return can_block and risk_score >= 90, reason or "扫描探测风险极高，进入封禁候选。"

        return can_block and risk_score >= 90, reason or "行为风险达到自动封禁阈值。"

    def _resolve_enforcement_mode(self, mode_value: str) -> str:
        """
        解析当前封禁执行模式。
        """
        normalized_mode = normalize_upper_text(mode_value)
        return normalized_mode if normalized_mode in {"REAL", "MOCK"} else "MOCK"

    def _build_firewall_rule_name(self, ban_id: str, target_ip: str) -> str:
        """
        构造与现有 firewall_service 一致的规则名，便于后续 verify / unban / reblock 继续复用。
        """
        sanitized_ip = re.sub(r"[^0-9A-Za-z]+", "_", normalize_text(target_ip or "UNKNOWN"))
        sanitized_id = re.sub(r"[^0-9A-Za-z_-]+", "_", normalize_text(ban_id or "UNKNOWN"))
        return f"{self.rule_prefix}-BAN-{sanitized_id}-{sanitized_ip}"


def map_behavior_file(attack_behavior_file: Path) -> Dict[str, Any]:
    """
    对单个批次 attack_behaviors.json 执行行为驱动映射。
    """
    behaviors = load_attack_behaviors(attack_behavior_file)
    mapper = BehaviorAlertMapper()
    try:
        return mapper.apply_behaviors(behaviors)
    finally:
        mapper.close()


def build_argument_parser() -> argparse.ArgumentParser:
    """
    构造命令行参数。
    """
    parser = argparse.ArgumentParser(description="将 attack_behaviors 映射为兼容的行为级告警与封禁记录。")
    parser.add_argument("--input", required=True, help="attack_behaviors.json 文件路径")
    return parser


def main() -> int:
    """
    命令行入口。
    """
    args = build_argument_parser().parse_args()
    result = map_behavior_file(Path(args.input))

    print("[behavior_alert_mapper] 行为驱动映射完成")
    print(f"  - 已启用：{result['behavior_driven_enabled']}")
    print(f"  - 实际使用：{result['behavior_driven_used']}")
    print(f"  - 告警数量：{result['alert_count_from_behaviors']}")
    print(f"  - 封禁候选数：{result['block_candidate_count_from_behaviors']}")
    print(f"  - 已生成封禁记录数：{result['blocked_behavior_count']}")
    print(f"  - Top 可封禁行为：{result['top_blockable_behavior_type'] or '-'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
