#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
文件路径：backend/app/services/detection_service.py

文件作用：
1. 基于当前 Neo4j 图数据实现恶意行为检测与风险评分。
2. 按“身份认证异常 -> 访问行为异常 -> 风险聚合异常”三层规则执行检测。
3. 将检测结果回写为 Rule / Alert 节点及其关系，形成“日志 -> 检测 -> 告警”的闭环。
4. 同步更新 User、IP、Session、Host 等核心实体的检测风险字段，支撑后续展示与联动处置。

本轮实际实现的核心规则：
1. 身份认证异常
   - 连续登录失败
   - 短时间连续失败后成功登录
   - 异常 / 可疑 IP 登录
   - 同账号短时间多源 IP 登录
   - 非工作时间登录
2. 访问行为异常
   - 高频访问多个主机
   - 横向移动行为
   - 高危主机异常访问
   - 短时间访问多个敏感端口
   - 单会话触发多类异常事件
3. 风险聚合异常
   - 同一用户 / IP / 会话命中多条规则
   - 同一链路关联多个高危告警
   - 已处置或已封禁对象再次出现异常行为

后续可扩展规则（本轮只做设计预留，不在代码中实现）：
1. 异地登录 / 不可能旅行登录检测。
2. 账号权限突增与敏感命令执行检测。
3. 敏感文件批量外传与横向数据窃取检测。
4. DNS 隧道、异常流量放大、长连接隐蔽通信检测。

设计说明：
1. 当前项目数据规模较小，更适合先以“Neo4j 查询 + Python 可解释规则”的方式实现最小可运行版本。
2. 评分逻辑采用“规则基础分 + 证据强度加分 + 关键资产加分 + 叠加风险加分”的可解释模型，便于论文描述。
3. 新生成的告警会兼容当前 /api/alerts 接口所需字段，因此前端无需改动即可看到检测结果。
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Sequence

from app.db import neo4j_client


DETECTION_ENGINE_NAME = "DETECTION_ENGINE"
WORK_HOUR_START = 8
WORK_HOUR_END = 19
SENSITIVE_PORTS = {22, 3389, 445, 1433, 3306, 5432, 5900, 6379}
HIGH_RISK_SEVERITIES = {"HIGH", "CRITICAL"}


@dataclass(frozen=True)
class RuleDefinition:
    """
    检测规则定义。

    这里将“规则元数据”和“规则实现逻辑”分离：
    1. 元数据用于回写 Rule 节点。
    2. 规则实现逻辑由 DetectionService 中的检测函数负责。
    3. 这样后续扩展规则时，只需新增一条定义和对应方法即可。
    """

    rule_id: str
    rule_name: str
    alert_name: str
    rule_category: str
    rule_level: str
    threshold_desc: str
    description: str
    suggestion: str
    base_score: int


@dataclass
class SessionContext:
    """
    会话检测上下文。

    该对象将 User、Session、IP、Host、Event、Alert、BlockAction 统一打包，
    便于在 Python 侧进行多维度规则分析。
    """

    user: Dict[str, Any]
    session: Dict[str, Any]
    ip: Optional[Dict[str, Any]]
    hosts: List[Dict[str, Any]]
    events: List[Dict[str, Any]]
    alerts: List[Dict[str, Any]]
    block_actions: List[Dict[str, Any]]
    start_dt: Optional[datetime] = field(init=False)
    end_dt: Optional[datetime] = field(init=False)

    def __post_init__(self) -> None:
        self.hosts = dedupe_records(self.hosts, "host_id")
        self.events = dedupe_records(self.events, "event_id")
        self.alerts = dedupe_records(self.alerts, "alert_id")
        self.block_actions = dedupe_records(self.block_actions, "action_id")
        self.start_dt = parse_iso_datetime(self.session.get("start_time"))
        self.end_dt = parse_iso_datetime(self.session.get("end_time"))

    @property
    def user_id(self) -> Optional[str]:
        return as_text(self.user.get("user_id"))

    @property
    def username(self) -> str:
        return as_text(self.user.get("username")) or (self.user_id or "未知用户")

    @property
    def session_id(self) -> Optional[str]:
        return as_text(self.session.get("session_id"))

    @property
    def ip_id(self) -> Optional[str]:
        if not self.ip:
            return None
        return as_text(self.ip.get("ip_id"))

    @property
    def ip_address(self) -> str:
        if not self.ip:
            return "未知 IP"
        return as_text(self.ip.get("ip_address")) or (self.ip_id or "未知 IP")

    @property
    def event_types(self) -> List[str]:
        return sorted({as_text(item.get("event_type")) for item in self.events if as_text(item.get("event_type"))})

    @property
    def event_ids(self) -> List[str]:
        return sorted({as_text(item.get("event_id")) for item in self.events if as_text(item.get("event_id"))})

    @property
    def host_ids(self) -> List[str]:
        return sorted({as_text(item.get("host_id")) for item in self.hosts if as_text(item.get("host_id"))})

    @property
    def host_names(self) -> List[str]:
        return sorted({as_text(item.get("hostname")) for item in self.hosts if as_text(item.get("hostname"))})

    @property
    def alert_ids(self) -> List[str]:
        return sorted({as_text(item.get("alert_id")) for item in self.alerts if as_text(item.get("alert_id"))})

    @property
    def max_event_risk_score(self) -> int:
        return max((safe_int(item.get("risk_score")) for item in self.events), default=0)

    @property
    def max_host_critical_level(self) -> int:
        return max((safe_int(item.get("critical_level")) for item in self.hosts), default=0)

    @property
    def sensitive_ports(self) -> List[int]:
        dst_port = safe_int(self.session.get("dst_port"))
        return [dst_port] if dst_port in SENSITIVE_PORTS else []

    @property
    def latest_block_time(self) -> Optional[datetime]:
        executed_times = [
            parse_iso_datetime(item.get("executed_at"))
            for item in self.block_actions
            if parse_iso_datetime(item.get("executed_at")) is not None
        ]
        if not executed_times:
            return None
        return max(executed_times)

    @property
    def high_severity_alert_ids(self) -> List[str]:
        return sorted(
            {
                as_text(item.get("alert_id"))
                for item in self.alerts
                if as_text(item.get("alert_id")) and as_text(item.get("severity")) in HIGH_RISK_SEVERITIES
            }
        )

    @property
    def evidence_first_seen(self) -> Optional[str]:
        time_values = []
        if self.session.get("start_time"):
            time_values.append(as_text(self.session.get("start_time")))
        for event_item in self.events:
            if event_item.get("event_time"):
                time_values.append(as_text(event_item.get("event_time")))
        if not time_values:
            return None
        return min(time_values)

    @property
    def evidence_last_seen(self) -> Optional[str]:
        time_values = []
        if self.session.get("end_time"):
            time_values.append(as_text(self.session.get("end_time")))
        if self.session.get("start_time"):
            time_values.append(as_text(self.session.get("start_time")))
        for event_item in self.events:
            if event_item.get("event_time"):
                time_values.append(as_text(event_item.get("event_time")))
        if not time_values:
            return None
        return max(time_values)

    def has_login_failure(self) -> bool:
        login_result = as_text(self.session.get("login_result"))
        if login_result in {"FAILURE", "FAILED"}:
            return True

        for event_item in self.events:
            if as_text(event_item.get("event_type")) == "LOGIN_FAIL":
                return True
            if as_text(event_item.get("result")) in {"FAILURE", "FAILED"}:
                return True

        return False

    def has_successful_login(self) -> bool:
        login_result = as_text(self.session.get("login_result"))
        if login_result == "SUCCESS":
            return True

        for event_item in self.events:
            if as_text(event_item.get("result")) == "SUCCESS" and as_text(event_item.get("action")) in {
                "LOGIN",
                "REMOTE_ACCESS",
            }:
                return True

        return False

    def has_event_type(self, event_type: str) -> bool:
        return event_type in self.event_types

    def suspicious_ip_reasons(self) -> List[str]:
        if not self.ip:
            return []

        reasons: List[str] = []
        ip_type = as_text(self.ip.get("ip_type"))
        reputation_level = as_text(self.ip.get("reputation_level"))
        geo_location = as_text(self.ip.get("geo_location"))
        is_blocked = bool(self.ip.get("is_blocked"))

        if ip_type == "EXTERNAL":
            reasons.append("外部来源地址")
        if reputation_level in {"HIGH", "CRITICAL"}:
            reasons.append("高风险信誉等级")
        if is_blocked:
            reasons.append("已处于封禁标记")
        if geo_location and ("境外" in geo_location or "海外" in geo_location):
            reasons.append("非常用地理位置")

        return reasons

    def is_suspicious_ip(self) -> bool:
        return len(self.suspicious_ip_reasons()) > 0


@dataclass
class DetectionMatch:
    """
    单条检测结果。

    一条检测结果最终会对应：
    1. 一个 Alert 节点。
    2. 一个 Alert -> Rule 的 HIT_RULE 关系。
    3. 若存在证据事件，则建立 Event -> Alert 的 TRIGGERS 关系。
    """

    rule_id: str
    rule_name: str
    rule_category: str
    alert_id: str
    alert_name: str
    anchor_type: str
    anchor_id: str
    anchor_name: str
    score: int
    severity: str
    first_seen: str
    last_seen: str
    description: str
    suggestion: str
    evidence_summary: str
    score_breakdown: Dict[str, Any]
    evidence_user_ids: List[str] = field(default_factory=list)
    evidence_session_ids: List[str] = field(default_factory=list)
    evidence_event_ids: List[str] = field(default_factory=list)
    evidence_ip_ids: List[str] = field(default_factory=list)
    evidence_host_ids: List[str] = field(default_factory=list)
    evidence_alert_ids: List[str] = field(default_factory=list)
    related_rule_ids: List[str] = field(default_factory=list)
    related_rule_names: List[str] = field(default_factory=list)

    def to_persist_row(self, detected_at: str) -> Dict[str, Any]:
        """
        将检测结果转换成适合 Neo4j UNWIND 写入的字典。
        """
        return {
            "rule_id": self.rule_id,
            "rule_name": self.rule_name,
            "rule_category": self.rule_category,
            "alert_id": self.alert_id,
            "alert_name": self.alert_name,
            "anchor_type": self.anchor_type,
            "anchor_id": self.anchor_id,
            "anchor_name": self.anchor_name,
            "severity": self.severity,
            "score": self.score,
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
            "description": self.description,
            "suggestion": self.suggestion,
            "evidence_summary": self.evidence_summary,
            "score_breakdown_json": json.dumps(self.score_breakdown, ensure_ascii=False, sort_keys=True),
            "evidence_user_ids": sorted(set(filter(None, self.evidence_user_ids))),
            "evidence_session_ids": sorted(set(filter(None, self.evidence_session_ids))),
            "evidence_event_ids": sorted(set(filter(None, self.evidence_event_ids))),
            "evidence_ip_ids": sorted(set(filter(None, self.evidence_ip_ids))),
            "evidence_host_ids": sorted(set(filter(None, self.evidence_host_ids))),
            "evidence_alert_ids": sorted(set(filter(None, self.evidence_alert_ids))),
            "related_rule_ids": sorted(set(filter(None, self.related_rule_ids))),
            "related_rule_names": sorted(set(filter(None, self.related_rule_names))),
            "detected_at": detected_at,
        }


RULE_DEFINITIONS: List[RuleDefinition] = [
    RuleDefinition(
        rule_id="DR_AUTH_001",
        rule_name="连续登录失败检测规则",
        alert_name="连续登录失败告警",
        rule_category="AUTH_ANOMALY",
        rule_level="HIGH",
        threshold_desc="会话存在登录失败结果或 LOGIN_FAIL 事件",
        description="用于识别暴力破解、口令探测或异常认证失败行为。",
        suggestion="建议复核账号状态、认证策略与源地址信誉，必要时执行人工封禁。",
        base_score=60,
    ),
    RuleDefinition(
        rule_id="DR_AUTH_002",
        rule_name="失败后成功登录检测规则",
        alert_name="失败后成功登录告警",
        rule_category="AUTH_ANOMALY",
        rule_level="HIGH",
        threshold_desc="30分钟内同一账号先出现失败登录后又成功登录",
        description="用于识别撞库成功、口令猜解后成功登录或异常认证绕过。",
        suggestion="建议人工核查该账号近期认证记录并确认是否存在口令泄露。",
        base_score=72,
    ),
    RuleDefinition(
        rule_id="DR_AUTH_003",
        rule_name="可疑IP登录检测规则",
        alert_name="可疑IP登录告警",
        rule_category="AUTH_ANOMALY",
        rule_level="HIGH",
        threshold_desc="源 IP 为外部来源、高风险信誉或已封禁对象",
        description="用于识别来自异常网络边界、恶意信誉地址或已封禁地址的认证行为。",
        suggestion="建议结合地理位置、信誉等级与账号画像进一步核查来源合法性。",
        base_score=58,
    ),
    RuleDefinition(
        rule_id="DR_AUTH_004",
        rule_name="多源IP登录检测规则",
        alert_name="同账号多源IP登录告警",
        rule_category="AUTH_ANOMALY",
        rule_level="HIGH",
        threshold_desc="15分钟内同一账号使用2个及以上源IP登录",
        description="用于识别账号共享、会话劫持或同一账号多点并发登录行为。",
        suggestion="建议核查账号是否被共享、代理或异常接管。",
        base_score=68,
    ),
    RuleDefinition(
        rule_id="DR_AUTH_005",
        rule_name="非工作时间登录检测规则",
        alert_name="非工作时间登录告警",
        rule_category="AUTH_ANOMALY",
        rule_level="MEDIUM",
        threshold_desc="工作日 08:00-19:00 之外或周末登录",
        description="用于识别非常规时段认证访问，适合作为异常时序检测信号。",
        suggestion="建议结合用户岗位和运维窗口判断是否属于正常值班或计划任务。",
        base_score=48,
    ),
    RuleDefinition(
        rule_id="DR_ACCESS_001",
        rule_name="高频访问多个主机检测规则",
        alert_name="高频访问多个主机告警",
        rule_category="ACCESS_ANOMALY",
        rule_level="HIGH",
        threshold_desc="10分钟内访问2台及以上主机，或出现 HIGH_FREQ_ACCESS 事件",
        description="用于识别批量探测、自动化脚本访问和高频横向探查行为。",
        suggestion="建议检查该账号或来源地址是否运行扫描脚本或异常任务。",
        base_score=62,
    ),
    RuleDefinition(
        rule_id="DR_ACCESS_002",
        rule_name="横向移动检测规则",
        alert_name="横向移动行为告警",
        rule_category="ACCESS_ANOMALY",
        rule_level="CRITICAL",
        threshold_desc="10分钟内访问2台及以上高危主机，或出现 LATERAL_MOVE 事件",
        description="用于识别在企业内部资产之间横向渗透与权限扩散行为。",
        suggestion="建议重点核查该账号权限范围，并评估是否需要隔离关联终端。",
        base_score=78,
    ),
    RuleDefinition(
        rule_id="DR_ACCESS_003",
        rule_name="高危主机异常访问检测规则",
        alert_name="高危主机异常访问告警",
        rule_category="ACCESS_ANOMALY",
        rule_level="HIGH",
        threshold_desc="访问 critical_level >= 4 主机且伴随可疑来源或高风险事件",
        description="用于识别针对高价值资产的异常访问活动。",
        suggestion="建议重点复核高价值主机访问链路与账号授权边界。",
        base_score=70,
    ),
    RuleDefinition(
        rule_id="DR_ACCESS_004",
        rule_name="多敏感端口访问检测规则",
        alert_name="多敏感端口访问告警",
        rule_category="ACCESS_ANOMALY",
        rule_level="HIGH",
        threshold_desc="15分钟内访问2个及以上敏感端口",
        description="用于识别服务探测、批量登录尝试及敏感端口横向测试。",
        suggestion="建议核查目标端口的业务用途，并检查是否存在未授权访问。",
        base_score=66,
    ),
    RuleDefinition(
        rule_id="DR_ACCESS_005",
        rule_name="单会话多异常检测规则",
        alert_name="单会话多异常告警",
        rule_category="ACCESS_ANOMALY",
        rule_level="CRITICAL",
        threshold_desc="同一会话命中3类及以上异常指征",
        description="用于识别单次访问会话内同时出现多种异常信号的复合风险场景。",
        suggestion="建议将该会话视为重点调查对象，追踪其上下游链路。",
        base_score=76,
    ),
    RuleDefinition(
        rule_id="DR_AGG_001",
        rule_name="多规则命中聚合规则",
        alert_name="多规则命中聚合告警",
        rule_category="RISK_AGGREGATION",
        rule_level="CRITICAL",
        threshold_desc="同一用户、IP 或会话命中2条及以上核心规则",
        description="用于识别多个检测信号叠加后的高可信风险对象。",
        suggestion="建议优先将该对象纳入人工复核或联动处置队列。",
        base_score=80,
    ),
    RuleDefinition(
        rule_id="DR_AGG_002",
        rule_name="高危告警链路聚合规则",
        alert_name="高危告警链路聚合告警",
        rule_category="RISK_AGGREGATION",
        rule_level="CRITICAL",
        threshold_desc="同一链路关联2条及以上 HIGH / CRITICAL 告警",
        description="用于识别攻击链已呈现连续告警扩散的高危场景。",
        suggestion="建议围绕该链路开展攻击路径排查与影响面评估。",
        base_score=82,
    ),
    RuleDefinition(
        rule_id="DR_AGG_003",
        rule_name="已处置对象再次异常规则",
        alert_name="已处置对象再次异常告警",
        rule_category="RISK_AGGREGATION",
        rule_level="CRITICAL",
        threshold_desc="已处置或已封禁对象再次出现异常行为",
        description="用于识别封禁绕过、策略失效或残留风险未清除场景。",
        suggestion="建议核查处置策略是否真正生效，并检查是否存在代理替身或策略绕过。",
        base_score=88,
    ),
]

RULE_MAP = {item.rule_id: item for item in RULE_DEFINITIONS}


def current_timestamp() -> str:
    """
    生成当前时间的 ISO 8601 字符串。
    """
    return datetime.now().astimezone().isoformat(timespec="seconds")


def parse_iso_datetime(value: Any) -> Optional[datetime]:
    """
    将字符串时间安全解析为 datetime。

    如果格式异常，则返回 None，避免因为单条脏数据中断整个检测流程。
    """
    text = as_text(value)
    if not text:
        return None

    try:
        normalized_text = text.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized_text)
    except ValueError:
        return None


def as_text(value: Any) -> str:
    """
    安全转换为字符串。
    """
    if value is None:
        return ""
    return str(value).strip()


def safe_int(value: Any, default_value: int = 0) -> int:
    """
    安全转换为整数。
    """
    if value in (None, ""):
        return default_value

    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default_value


def dedupe_records(records: Optional[Sequence[Dict[str, Any]]], key_field: str) -> List[Dict[str, Any]]:
    """
    对字典列表按主键字段去重。
    """
    if not records:
        return []

    result: List[Dict[str, Any]] = []
    seen_keys = set()
    for item in records:
        if not isinstance(item, dict):
            continue
        key_value = as_text(item.get(key_field))
        if not key_value or key_value in seen_keys:
            continue
        seen_keys.add(key_value)
        result.append(item)
    return result


def to_score_level(score: int) -> str:
    """
    将总风险分映射为风险等级。

    分级标准：
    1. 90-100：CRITICAL
    2. 75-89：HIGH
    3. 55-74：MEDIUM
    4. 0-54：LOW
    """
    if score >= 90:
        return "CRITICAL"
    if score >= 75:
        return "HIGH"
    if score >= 55:
        return "MEDIUM"
    return "LOW"


def sanitize_identifier(value: str) -> str:
    """
    将业务主键转换为适合拼接告警编号的安全文本。
    """
    cleaned_text = re.sub(r"[^0-9A-Za-z_]+", "_", as_text(value))
    return cleaned_text.strip("_") or "UNKNOWN"


def unique_sorted(items: Iterable[Any]) -> List[str]:
    """
    去重并排序字符串列表。
    """
    return sorted({as_text(item) for item in items if as_text(item)})


def first_non_empty_min(values: Iterable[Any], default_value: str) -> str:
    """
    返回非空字符串集合中的最小值。
    """
    filtered_values = [as_text(item) for item in values if as_text(item)]
    return min(filtered_values) if filtered_values else default_value


def first_non_empty_max(values: Iterable[Any], default_value: str) -> str:
    """
    返回非空字符串集合中的最大值。
    """
    filtered_values = [as_text(item) for item in values if as_text(item)]
    return max(filtered_values) if filtered_values else default_value


class DetectionService:
    """
    图谱检测与评分服务。

    处理流程：
    1. 从 Neo4j 读取会话上下文。
    2. 执行身份认证类和访问行为类核心规则。
    3. 在核心规则结果基础上再执行风险聚合规则。
    4. 将检测结果写回 Neo4j，并更新实体风险字段。
    """

    def __init__(self, client):
        self.client = client

    def run_detection(self, dry_run: bool = False) -> Dict[str, Any]:
        """
        执行完整检测流程。

        参数说明：
        1. dry_run=True 时只做检测计算，不落库。
        2. dry_run=False 时会把 Alert、Rule 和风险评分结果回写 Neo4j。
        """
        run_started_at = current_timestamp()

        session_contexts = self._load_session_contexts()
        entity_maps = self._build_entity_maps(session_contexts)

        core_matches = self._merge_matches(
            self._detect_continuous_login_failure(session_contexts)
            + self._detect_fail_then_success(session_contexts)
            + self._detect_suspicious_ip_login(session_contexts)
            + self._detect_multi_source_ip_login(session_contexts)
            + self._detect_off_hours_login(session_contexts)
            + self._detect_high_frequency_multi_host(session_contexts)
            + self._detect_lateral_movement(session_contexts)
            + self._detect_high_risk_host_access(session_contexts)
            + self._detect_multi_sensitive_ports(session_contexts)
            + self._detect_multi_anomaly_session(session_contexts)
        )

        aggregate_matches = self._merge_matches(
            self._detect_multi_rule_hits(core_matches, entity_maps, session_contexts)
            + self._detect_multi_high_risk_alert_chain(session_contexts, core_matches)
            + self._detect_reappeared_after_disposal(session_contexts)
        )

        all_matches = self._merge_matches(core_matches + aggregate_matches)
        detection_finished_at = current_timestamp()

        persist_stats = {
            "rules_upserted": 0,
            "alerts_upserted": 0,
            "entity_updates": {
                "User": 0,
                "IP": 0,
                "Session": 0,
                "Host": 0,
            },
        }

        if not dry_run:
            persist_stats["rules_upserted"] = self._upsert_rule_nodes()
            persist_stats["alerts_upserted"] = self._persist_alerts(all_matches, detection_finished_at)
            persist_stats["entity_updates"] = self._update_entity_scores(all_matches, detection_finished_at)

        return {
            "run_started_at": run_started_at,
            "run_finished_at": detection_finished_at,
            "dry_run": dry_run,
            "implemented_rule_count": len(RULE_DEFINITIONS),
            "implemented_rules": [
                {
                    "rule_id": item.rule_id,
                    "rule_name": item.rule_name,
                    "rule_category": item.rule_category,
                    "rule_level": item.rule_level,
                    "threshold_desc": item.threshold_desc,
                }
                for item in RULE_DEFINITIONS
            ],
            "future_extension_rules": [
                "异地登录 / 不可能旅行登录检测",
                "异常提权与敏感命令执行检测",
                "敏感文件外传与批量下载检测",
                "异常 DNS / 隧道通信检测",
            ],
            "summary": {
                "session_context_count": len(session_contexts),
                "core_match_count": len(core_matches),
                "aggregate_match_count": len(aggregate_matches),
                "total_match_count": len(all_matches),
            },
            "rule_match_stats": self._build_rule_stats(all_matches),
            "persist_stats": persist_stats,
            "results_preview": [
                {
                    "alert_id": item.alert_id,
                    "alert_name": item.alert_name,
                    "rule_id": item.rule_id,
                    "anchor_type": item.anchor_type,
                    "anchor_id": item.anchor_id,
                    "score": item.score,
                    "severity": item.severity,
                    "first_seen": item.first_seen,
                    "last_seen": item.last_seen,
                }
                for item in all_matches
            ],
        }

    def _load_session_contexts(self) -> List[SessionContext]:
        """
        从 Neo4j 读取会话上下文。

        查询目标：
        1. 一次性取回 Session 为中心的用户、IP、主机、事件、告警、处置动作。
        2. 降低规则计算阶段反复访问 Neo4j 的次数。
        """
        query = """
MATCH (u:User)-[:INITIATES]->(s:Session)
OPTIONAL MATCH (s)-[:USES_SOURCE_IP]->(ip:IP)
OPTIONAL MATCH (s)-[:ACCESSES]->(h:Host)
OPTIONAL MATCH (s)-[:GENERATES]->(e:Event)
OPTIONAL MATCH (e)-[:TRIGGERS]->(a:Alert)
OPTIONAL MATCH (b:BlockAction)-[:TARGETS_IP]->(ip)
WITH u, s, ip,
     collect(DISTINCT h{.*}) AS hosts,
     collect(DISTINCT e{.*}) AS events,
     collect(DISTINCT a{.*}) AS alerts,
     collect(DISTINCT b{.*}) AS block_actions
RETURN u{.*} AS user,
       s{.*} AS session,
       CASE WHEN ip IS NULL THEN NULL ELSE ip{.*} END AS ip,
       [item IN hosts WHERE item.host_id IS NOT NULL] AS hosts,
       [item IN events WHERE item.event_id IS NOT NULL] AS events,
       [item IN alerts WHERE item.alert_id IS NOT NULL] AS alerts,
       [item IN block_actions WHERE item.action_id IS NOT NULL] AS block_actions
ORDER BY s.start_time ASC
"""
        records = self.client.execute_read(query)
        return [
            SessionContext(
                user=record.get("user") or {},
                session=record.get("session") or {},
                ip=record.get("ip"),
                hosts=record.get("hosts") or [],
                events=record.get("events") or [],
                alerts=record.get("alerts") or [],
                block_actions=record.get("block_actions") or [],
            )
            for record in records
        ]

    def _build_entity_maps(self, session_contexts: List[SessionContext]) -> Dict[str, Dict[str, Dict[str, Any]]]:
        """
        根据检测上下文构造实体索引，便于聚合规则和风险回写时快速定位实体名称。
        """
        entity_maps = {
            "USER": {},
            "SESSION": {},
            "IP": {},
            "HOST": {},
        }

        for ctx in session_contexts:
            if ctx.user_id:
                entity_maps["USER"][ctx.user_id] = ctx.user
            if ctx.session_id:
                entity_maps["SESSION"][ctx.session_id] = ctx.session
            if ctx.ip_id and ctx.ip:
                entity_maps["IP"][ctx.ip_id] = ctx.ip
            for host_item in ctx.hosts:
                host_id = as_text(host_item.get("host_id"))
                if host_id:
                    entity_maps["HOST"][host_id] = host_item

        return entity_maps

    def _build_match(
        self,
        rule: RuleDefinition,
        anchor_type: str,
        anchor_id: str,
        anchor_name: str,
        first_seen: str,
        last_seen: str,
        description: str,
        evidence_summary: str,
        metrics: Dict[str, Any],
        evidence_user_ids: Optional[List[str]] = None,
        evidence_session_ids: Optional[List[str]] = None,
        evidence_event_ids: Optional[List[str]] = None,
        evidence_ip_ids: Optional[List[str]] = None,
        evidence_host_ids: Optional[List[str]] = None,
        evidence_alert_ids: Optional[List[str]] = None,
        related_rule_ids: Optional[List[str]] = None,
        related_rule_names: Optional[List[str]] = None,
    ) -> DetectionMatch:
        """
        构造 DetectionMatch 对象，并统一完成风险评分。
        """
        score, score_breakdown = self._calculate_total_score(rule, metrics)
        severity = to_score_level(score)
        alert_id = f"DALT_{rule.rule_id}_{anchor_type}_{sanitize_identifier(anchor_id)}"

        score_breakdown["risk_level"] = severity
        score_breakdown["score_formula"] = "总分 = 基础分 + 证据加分 + 事件加分 + 主机关键度加分 + 来源/IP加分 + 时间紧迫度加分 + 规则叠加加分 + 处置回流加分"

        return DetectionMatch(
            rule_id=rule.rule_id,
            rule_name=rule.rule_name,
            rule_category=rule.rule_category,
            alert_id=alert_id,
            alert_name=rule.alert_name,
            anchor_type=anchor_type,
            anchor_id=anchor_id,
            anchor_name=anchor_name,
            score=score,
            severity=severity,
            first_seen=first_seen,
            last_seen=last_seen,
            description=description,
            suggestion=rule.suggestion,
            evidence_summary=evidence_summary,
            score_breakdown=score_breakdown,
            evidence_user_ids=unique_sorted(evidence_user_ids or []),
            evidence_session_ids=unique_sorted(evidence_session_ids or []),
            evidence_event_ids=unique_sorted(evidence_event_ids or []),
            evidence_ip_ids=unique_sorted(evidence_ip_ids or []),
            evidence_host_ids=unique_sorted(evidence_host_ids or []),
            evidence_alert_ids=unique_sorted(evidence_alert_ids or []),
            related_rule_ids=unique_sorted(related_rule_ids or []),
            related_rule_names=unique_sorted(related_rule_names or []),
        )

    def _calculate_total_score(self, rule: RuleDefinition, metrics: Dict[str, Any]) -> tuple[int, Dict[str, Any]]:
        """
        计算总风险分。

        评分模型说明：
        1. 基础分：由规则自身危险程度决定。
        2. 证据加分：命中证据越多，分值越高。
        3. 事件加分：关联事件风险越高，分值越高。
        4. 主机关键度加分：涉及高价值资产时额外提高风险。
        5. 来源/IP加分：可疑来源、已封禁对象会提高风险。
        6. 时间紧迫度加分：越短时间内发生越密集，风险越高。
        7. 规则叠加加分：多个规则同时命中时说明置信度更高。
        """
        evidence_count = safe_int(metrics.get("evidence_count"), 1)
        max_event_risk_score = safe_int(metrics.get("max_event_risk_score"), 0)
        max_host_critical_level = safe_int(metrics.get("max_host_critical_level"), 0)
        suspicious_ip = bool(metrics.get("suspicious_ip"))
        blocked_target = bool(metrics.get("blocked_target"))
        reappeared_after_block = bool(metrics.get("reappeared_after_block"))
        time_span_minutes = safe_int(metrics.get("time_span_minutes"), 0)
        overlap_rule_count = safe_int(metrics.get("overlap_rule_count"), 1)

        evidence_bonus = min(12, max(0, evidence_count - 1) * 4)
        event_bonus = min(12, round(max_event_risk_score / 10))
        host_bonus = min(10, max_host_critical_level * 2)
        suspicious_ip_bonus = 10 if suspicious_ip else 0
        blocked_bonus = 15 if reappeared_after_block else (6 if blocked_target else 0)
        overlap_bonus = min(18, max(0, overlap_rule_count - 1) * 6)

        if 0 <= time_span_minutes <= 10:
            time_bonus = 8
        elif 10 < time_span_minutes <= 30:
            time_bonus = 4
        else:
            time_bonus = 0

        final_score = min(
            100,
            round(
                rule.base_score
                + evidence_bonus
                + event_bonus
                + host_bonus
                + suspicious_ip_bonus
                + blocked_bonus
                + overlap_bonus
                + time_bonus
            ),
        )

        return final_score, {
            "base_score": rule.base_score,
            "evidence_bonus": evidence_bonus,
            "event_bonus": event_bonus,
            "host_bonus": host_bonus,
            "suspicious_ip_bonus": suspicious_ip_bonus,
            "blocked_bonus": blocked_bonus,
            "overlap_bonus": overlap_bonus,
            "time_bonus": time_bonus,
            "evidence_count": evidence_count,
            "max_event_risk_score": max_event_risk_score,
            "max_host_critical_level": max_host_critical_level,
            "time_span_minutes": time_span_minutes,
            "overlap_rule_count": overlap_rule_count,
            "final_score": final_score,
        }

    def _merge_matches(self, matches: List[DetectionMatch]) -> List[DetectionMatch]:
        """
        对检测结果按 alert_id 去重并合并证据。
        """
        match_map: Dict[str, DetectionMatch] = {}

        for match_item in matches:
            if match_item.alert_id not in match_map:
                match_map[match_item.alert_id] = match_item
                continue

            existing_item = match_map[match_item.alert_id]
            existing_item.score = max(existing_item.score, match_item.score)
            existing_item.severity = to_score_level(existing_item.score)
            existing_item.first_seen = min(existing_item.first_seen, match_item.first_seen)
            existing_item.last_seen = max(existing_item.last_seen, match_item.last_seen)
            existing_item.description = existing_item.description or match_item.description
            existing_item.evidence_summary = "；".join(
                unique_sorted([existing_item.evidence_summary, match_item.evidence_summary])
            )
            existing_item.evidence_user_ids = unique_sorted(existing_item.evidence_user_ids + match_item.evidence_user_ids)
            existing_item.evidence_session_ids = unique_sorted(existing_item.evidence_session_ids + match_item.evidence_session_ids)
            existing_item.evidence_event_ids = unique_sorted(existing_item.evidence_event_ids + match_item.evidence_event_ids)
            existing_item.evidence_ip_ids = unique_sorted(existing_item.evidence_ip_ids + match_item.evidence_ip_ids)
            existing_item.evidence_host_ids = unique_sorted(existing_item.evidence_host_ids + match_item.evidence_host_ids)
            existing_item.evidence_alert_ids = unique_sorted(existing_item.evidence_alert_ids + match_item.evidence_alert_ids)
            existing_item.related_rule_ids = unique_sorted(existing_item.related_rule_ids + match_item.related_rule_ids)
            existing_item.related_rule_names = unique_sorted(existing_item.related_rule_names + match_item.related_rule_names)

        return sorted(match_map.values(), key=lambda item: (item.last_seen, item.alert_id), reverse=True)

    def _group_contexts_by_user(self, session_contexts: List[SessionContext]) -> Dict[str, List[SessionContext]]:
        """
        按 user_id 分组。
        """
        result: Dict[str, List[SessionContext]] = defaultdict(list)
        for ctx in session_contexts:
            if ctx.user_id:
                result[ctx.user_id].append(ctx)
        return result

    def _sort_contexts_by_start_time(self, contexts: List[SessionContext]) -> List[SessionContext]:
        """
        按 start_time 排序。
        """
        return sorted(
            contexts,
            key=lambda item: item.start_dt or parse_iso_datetime("2999-12-31T00:00:00+00:00"),
        )

    def _slice_time_window(self, contexts: List[SessionContext], start_index: int, window_minutes: int) -> List[SessionContext]:
        """
        获取从某条会话开始的时间窗口切片。
        """
        if start_index >= len(contexts):
            return []

        start_ctx = contexts[start_index]
        if start_ctx.start_dt is None:
            return [start_ctx]

        window_contexts: List[SessionContext] = []
        for ctx in contexts[start_index:]:
            if ctx.start_dt is None:
                continue
            delta_seconds = (ctx.start_dt - start_ctx.start_dt).total_seconds()
            if 0 <= delta_seconds <= window_minutes * 60:
                window_contexts.append(ctx)
            elif delta_seconds > window_minutes * 60:
                break

        return window_contexts

    def _new_entity_bucket(self) -> Dict[str, Any]:
        """
        初始化实体聚合桶。
        """
        return {
            "rule_ids": [],
            "rule_names": [],
            "alert_ids": [],
            "user_ids": [],
            "session_ids": [],
            "event_ids": [],
            "ip_ids": [],
            "host_ids": [],
            "first_seen": "9999-12-31T23:59:59+00:00",
            "last_seen": "",
        }

    def _append_match_to_entity_bucket(self, bucket: Dict[str, Any], match_item: DetectionMatch) -> None:
        """
        将一条检测结果累积到实体聚合桶中。
        """
        bucket["rule_ids"].append(match_item.rule_id)
        bucket["rule_names"].append(match_item.rule_name)
        bucket["alert_ids"].append(match_item.alert_id)
        bucket["user_ids"].extend(match_item.evidence_user_ids)
        bucket["session_ids"].extend(match_item.evidence_session_ids)
        bucket["event_ids"].extend(match_item.evidence_event_ids)
        bucket["ip_ids"].extend(match_item.evidence_ip_ids)
        bucket["host_ids"].extend(match_item.evidence_host_ids)
        if match_item.first_seen and match_item.first_seen < bucket["first_seen"]:
            bucket["first_seen"] = match_item.first_seen
        if match_item.last_seen and match_item.last_seen > bucket["last_seen"]:
            bucket["last_seen"] = match_item.last_seen

    def _resolve_anchor_name(
        self,
        anchor_type: str,
        anchor_id: str,
        entity_maps: Dict[str, Dict[str, Dict[str, Any]]],
    ) -> str:
        """
        根据实体类型和主键解析展示名称。
        """
        if anchor_type == "USER":
            return as_text(entity_maps["USER"].get(anchor_id, {}).get("username")) or anchor_id
        if anchor_type == "IP":
            return as_text(entity_maps["IP"].get(anchor_id, {}).get("ip_address")) or anchor_id
        if anchor_type == "SESSION":
            return as_text(entity_maps["SESSION"].get(anchor_id, {}).get("session_id")) or anchor_id
        return anchor_id

    def _detect_continuous_login_failure(self, session_contexts: List[SessionContext]) -> List[DetectionMatch]:
        """
        规则 1：连续登录失败。

        当前实现采用“失败会话 / LOGIN_FAIL 事件”作为连续失败的归并信号：
        1. 原始样例数据已在清洗阶段将“多次失败”聚合为 LOGIN_FAIL 事件。
        2. 因此对最小可运行版本而言，可以直接把该事件视为连续登录失败结果。
        """
        results: List[DetectionMatch] = []
        rule = RULE_MAP["DR_AUTH_001"]

        for ctx in session_contexts:
            if not ctx.has_login_failure():
                continue

            failure_event_ids = [
                as_text(event_item.get("event_id"))
                for event_item in ctx.events
                if as_text(event_item.get("event_type")) == "LOGIN_FAIL"
                or as_text(event_item.get("result")) in {"FAILURE", "FAILED"}
            ]
            suspicious_reasons = ctx.suspicious_ip_reasons()
            evidence_count = max(1, len(failure_event_ids))

            description = (
                f"【检测引擎】检测到账号 {ctx.username} 在会话 {ctx.session_id} 中出现连续登录失败特征，"
                f"源 IP 为 {ctx.ip_address}。"
                f"{'；可疑来源特征：' + '、'.join(suspicious_reasons) if suspicious_reasons else ''}"
            )

            metrics = {
                "evidence_count": evidence_count,
                "max_event_risk_score": ctx.max_event_risk_score,
                "max_host_critical_level": ctx.max_host_critical_level,
                "suspicious_ip": ctx.is_suspicious_ip(),
                "blocked_target": bool(ctx.ip and ctx.ip.get("is_blocked")),
                "time_span_minutes": 0,
            }

            results.append(
                self._build_match(
                    rule=rule,
                    anchor_type="SESSION",
                    anchor_id=ctx.session_id or "UNKNOWN_SESSION",
                    anchor_name=ctx.session_id or "未知会话",
                    first_seen=ctx.evidence_first_seen or current_timestamp(),
                    last_seen=ctx.evidence_last_seen or current_timestamp(),
                    description=description,
                    evidence_summary=f"失败事件数：{evidence_count}；事件类型：{' / '.join(ctx.event_types) or '无'}",
                    metrics=metrics,
                    evidence_user_ids=[ctx.user_id or ""],
                    evidence_session_ids=[ctx.session_id or ""],
                    evidence_event_ids=failure_event_ids or ctx.event_ids,
                    evidence_ip_ids=[ctx.ip_id or ""],
                    evidence_host_ids=ctx.host_ids,
                )
            )

        return results

    def _detect_fail_then_success(self, session_contexts: List[SessionContext]) -> List[DetectionMatch]:
        """
        规则 2：短时间连续失败后成功登录。
        """
        rule = RULE_MAP["DR_AUTH_002"]
        user_groups = self._group_contexts_by_user(session_contexts)
        results: List[DetectionMatch] = []

        for user_id, contexts in user_groups.items():
            sorted_contexts = self._sort_contexts_by_start_time(contexts)
            failed_contexts: List[SessionContext] = []

            for ctx in sorted_contexts:
                if ctx.has_login_failure():
                    failed_contexts.append(ctx)
                    continue

                if not ctx.has_successful_login():
                    continue

                matched_failures = [
                    failure_ctx
                    for failure_ctx in failed_contexts
                    if failure_ctx.start_dt
                    and ctx.start_dt
                    and 0 <= (ctx.start_dt - failure_ctx.start_dt).total_seconds() <= 30 * 60
                ]
                if not matched_failures:
                    continue

                related_contexts = matched_failures + [ctx]
                distinct_ip_ids = unique_sorted(ip_id for ip_id in [item.ip_id for item in related_contexts] if ip_id)
                failure_count = len(matched_failures)

                metrics = {
                    "evidence_count": len(related_contexts),
                    "max_event_risk_score": max(item.max_event_risk_score for item in related_contexts),
                    "max_host_critical_level": max(item.max_host_critical_level for item in related_contexts),
                    "suspicious_ip": any(item.is_suspicious_ip() for item in related_contexts),
                    "blocked_target": any(item.ip and item.ip.get("is_blocked") for item in related_contexts),
                    "time_span_minutes": minutes_between(matched_failures[0].start_dt, ctx.start_dt),
                }

                description = (
                    f"【检测引擎】账号 {ctx.username} 在 30 分钟内先出现 {failure_count} 次失败认证后又成功登录，"
                    f"存在口令撞库成功或认证绕过风险。"
                )
                if len(distinct_ip_ids) >= 2:
                    description += " 且前后使用了多个源 IP，风险进一步升高。"

                results.append(
                    self._build_match(
                        rule=rule,
                        anchor_type="USER",
                        anchor_id=user_id,
                        anchor_name=ctx.username,
                        first_seen=first_non_empty_min(
                            [item.evidence_first_seen for item in related_contexts],
                            current_timestamp(),
                        ),
                        last_seen=first_non_empty_max(
                            [item.evidence_last_seen for item in related_contexts],
                            current_timestamp(),
                        ),
                        description=description,
                        evidence_summary=f"失败会话数：{failure_count}；关联 IP 数：{len(distinct_ip_ids)}",
                        metrics=metrics,
                        evidence_user_ids=[user_id],
                        evidence_session_ids=[item.session_id or "" for item in related_contexts],
                        evidence_event_ids=[event_id for item in related_contexts for event_id in item.event_ids],
                        evidence_ip_ids=[item.ip_id or "" for item in related_contexts],
                        evidence_host_ids=[host_id for item in related_contexts for host_id in item.host_ids],
                    )
                )
                break

        return results

    def _detect_suspicious_ip_login(self, session_contexts: List[SessionContext]) -> List[DetectionMatch]:
        """
        规则 3：异常 / 可疑 IP 登录。
        """
        rule = RULE_MAP["DR_AUTH_003"]
        results: List[DetectionMatch] = []

        for ctx in session_contexts:
            if not ctx.ip or not ctx.is_suspicious_ip():
                continue

            if not (ctx.has_login_failure() or ctx.has_successful_login() or ctx.events):
                continue

            reasons = ctx.suspicious_ip_reasons()
            description = (
                f"【检测引擎】会话 {ctx.session_id} 使用可疑源 IP {ctx.ip_address} 发起认证或访问行为，"
                f"原因包括：{'、'.join(reasons)}。"
            )

            metrics = {
                "evidence_count": max(1, len(ctx.events)),
                "max_event_risk_score": ctx.max_event_risk_score,
                "max_host_critical_level": ctx.max_host_critical_level,
                "suspicious_ip": True,
                "blocked_target": bool(ctx.ip.get("is_blocked")),
                "time_span_minutes": 0,
            }

            results.append(
                self._build_match(
                    rule=rule,
                    anchor_type="SESSION",
                    anchor_id=ctx.session_id or "UNKNOWN_SESSION",
                    anchor_name=ctx.session_id or "未知会话",
                    first_seen=ctx.evidence_first_seen or current_timestamp(),
                    last_seen=ctx.evidence_last_seen or current_timestamp(),
                    description=description,
                    evidence_summary=f"可疑特征：{'、'.join(reasons)}",
                    metrics=metrics,
                    evidence_user_ids=[ctx.user_id or ""],
                    evidence_session_ids=[ctx.session_id or ""],
                    evidence_event_ids=ctx.event_ids,
                    evidence_ip_ids=[ctx.ip_id or ""],
                    evidence_host_ids=ctx.host_ids,
                )
            )

        return results

    def _detect_multi_source_ip_login(self, session_contexts: List[SessionContext]) -> List[DetectionMatch]:
        """
        规则 4：同账号短时间多源 IP 登录。
        """
        rule = RULE_MAP["DR_AUTH_004"]
        user_groups = self._group_contexts_by_user(session_contexts)
        results: List[DetectionMatch] = []

        for user_id, contexts in user_groups.items():
            sorted_contexts = self._sort_contexts_by_start_time(contexts)
            best_window: List[SessionContext] = []
            best_ip_ids: List[str] = []

            for index, _ in enumerate(sorted_contexts):
                window = self._slice_time_window(sorted_contexts, index, 15)
                if not window:
                    continue

                ip_ids = unique_sorted(item.ip_id for item in window if item.ip_id)
                if len(ip_ids) < 2:
                    continue

                if len(ip_ids) > len(best_ip_ids):
                    best_window = window
                    best_ip_ids = ip_ids

            if not best_window:
                continue

            user_name = best_window[0].username
            description = (
                f"【检测引擎】账号 {user_name} 在 15 分钟内使用多个源 IP 发起认证或访问，"
                f"共涉及 {len(best_ip_ids)} 个源地址，存在账号共享或会话接管风险。"
            )

            metrics = {
                "evidence_count": len(best_window),
                "max_event_risk_score": max(item.max_event_risk_score for item in best_window),
                "max_host_critical_level": max(item.max_host_critical_level for item in best_window),
                "suspicious_ip": any(item.is_suspicious_ip() for item in best_window),
                "blocked_target": any(item.ip and item.ip.get("is_blocked") for item in best_window),
                "time_span_minutes": minutes_between(best_window[0].start_dt, best_window[-1].start_dt),
            }

            results.append(
                self._build_match(
                    rule=rule,
                    anchor_type="USER",
                    anchor_id=user_id,
                    anchor_name=user_name,
                    first_seen=first_non_empty_min(
                        [item.evidence_first_seen for item in best_window],
                        current_timestamp(),
                    ),
                    last_seen=first_non_empty_max(
                        [item.evidence_last_seen for item in best_window],
                        current_timestamp(),
                    ),
                    description=description,
                    evidence_summary=f"源 IP 数：{len(best_ip_ids)}；源地址：{' / '.join(best_ip_ids)}",
                    metrics=metrics,
                    evidence_user_ids=[user_id],
                    evidence_session_ids=[item.session_id or "" for item in best_window],
                    evidence_event_ids=[event_id for item in best_window for event_id in item.event_ids],
                    evidence_ip_ids=best_ip_ids,
                    evidence_host_ids=[host_id for item in best_window for host_id in item.host_ids],
                )
            )

        return results

    def _detect_off_hours_login(self, session_contexts: List[SessionContext]) -> List[DetectionMatch]:
        """
        规则 5：非工作时间登录。
        """
        rule = RULE_MAP["DR_AUTH_005"]
        results: List[DetectionMatch] = []

        for ctx in session_contexts:
            if not ctx.has_successful_login():
                continue
            if not is_non_work_hour(ctx.start_dt):
                continue

            description = (
                f"【检测引擎】账号 {ctx.username} 在非工作时间发起成功登录，"
                f"时间为 {ctx.session.get('start_time') or '未知'}。"
            )

            metrics = {
                "evidence_count": 1,
                "max_event_risk_score": ctx.max_event_risk_score,
                "max_host_critical_level": ctx.max_host_critical_level,
                "suspicious_ip": ctx.is_suspicious_ip(),
                "blocked_target": bool(ctx.ip and ctx.ip.get("is_blocked")),
                "time_span_minutes": 0,
            }

            results.append(
                self._build_match(
                    rule=rule,
                    anchor_type="SESSION",
                    anchor_id=ctx.session_id or "UNKNOWN_SESSION",
                    anchor_name=ctx.session_id or "未知会话",
                    first_seen=ctx.evidence_first_seen or current_timestamp(),
                    last_seen=ctx.evidence_last_seen or current_timestamp(),
                    description=description,
                    evidence_summary="时序异常：登录发生在非工作时间",
                    metrics=metrics,
                    evidence_user_ids=[ctx.user_id or ""],
                    evidence_session_ids=[ctx.session_id or ""],
                    evidence_event_ids=ctx.event_ids,
                    evidence_ip_ids=[ctx.ip_id or ""],
                    evidence_host_ids=ctx.host_ids,
                )
            )

        return results

    def _detect_high_frequency_multi_host(self, session_contexts: List[SessionContext]) -> List[DetectionMatch]:
        """
        规则 6：高频访问多个主机。
        """
        rule = RULE_MAP["DR_ACCESS_001"]
        user_groups = self._group_contexts_by_user(session_contexts)
        results: List[DetectionMatch] = []

        for user_id, contexts in user_groups.items():
            sorted_contexts = self._sort_contexts_by_start_time(contexts)
            best_window: List[SessionContext] = []
            best_host_ids: List[str] = []
            best_has_high_freq_event = False

            for index, _ in enumerate(sorted_contexts):
                window = self._slice_time_window(sorted_contexts, index, 10)
                if not window:
                    continue

                host_ids = unique_sorted(host_id for item in window for host_id in item.host_ids)
                has_high_freq_event = any(item.has_event_type("HIGH_FREQ_ACCESS") for item in window)
                if len(host_ids) < 2 and not has_high_freq_event:
                    continue

                if len(host_ids) > len(best_host_ids) or (has_high_freq_event and not best_has_high_freq_event):
                    best_window = window
                    best_host_ids = host_ids
                    best_has_high_freq_event = has_high_freq_event

            if not best_window:
                continue

            description = (
                f"【检测引擎】账号 {best_window[0].username} 在短时间内访问多个主机，"
                f"涉及 {len(best_host_ids)} 台主机。"
                f"{' 同时出现 HIGH_FREQ_ACCESS 事件。' if best_has_high_freq_event else ''}"
            )

            metrics = {
                "evidence_count": max(len(best_window), len(best_host_ids)),
                "max_event_risk_score": max(item.max_event_risk_score for item in best_window),
                "max_host_critical_level": max(item.max_host_critical_level for item in best_window),
                "suspicious_ip": any(item.is_suspicious_ip() for item in best_window),
                "blocked_target": any(item.ip and item.ip.get("is_blocked") for item in best_window),
                "time_span_minutes": minutes_between(best_window[0].start_dt, best_window[-1].start_dt),
            }

            results.append(
                self._build_match(
                    rule=rule,
                    anchor_type="USER",
                    anchor_id=user_id,
                    anchor_name=best_window[0].username,
                    first_seen=first_non_empty_min(
                        [item.evidence_first_seen for item in best_window],
                        current_timestamp(),
                    ),
                    last_seen=first_non_empty_max(
                        [item.evidence_last_seen for item in best_window],
                        current_timestamp(),
                    ),
                    description=description,
                    evidence_summary=f"访问主机数：{len(best_host_ids)}；主机：{' / '.join(best_host_ids)}",
                    metrics=metrics,
                    evidence_user_ids=[user_id],
                    evidence_session_ids=[item.session_id or "" for item in best_window],
                    evidence_event_ids=[event_id for item in best_window for event_id in item.event_ids],
                    evidence_ip_ids=[item.ip_id or "" for item in best_window],
                    evidence_host_ids=best_host_ids,
                )
            )

        return results

    def _detect_lateral_movement(self, session_contexts: List[SessionContext]) -> List[DetectionMatch]:
        """
        规则 7：横向移动行为。
        """
        rule = RULE_MAP["DR_ACCESS_002"]
        user_groups = self._group_contexts_by_user(session_contexts)
        results: List[DetectionMatch] = []

        for user_id, contexts in user_groups.items():
            sorted_contexts = self._sort_contexts_by_start_time(contexts)
            best_window: List[SessionContext] = []
            best_critical_hosts: List[str] = []
            best_has_lateral_event = False

            for index, _ in enumerate(sorted_contexts):
                window = self._slice_time_window(sorted_contexts, index, 10)
                if not window:
                    continue

                critical_hosts = unique_sorted(
                    as_text(host_item.get("host_id"))
                    for item in window
                    for host_item in item.hosts
                    if safe_int(host_item.get("critical_level")) >= 4
                )
                has_lateral_event = any(item.has_event_type("LATERAL_MOVE") for item in window)
                if len(critical_hosts) < 2 and not has_lateral_event:
                    continue

                if len(critical_hosts) > len(best_critical_hosts) or (has_lateral_event and not best_has_lateral_event):
                    best_window = window
                    best_critical_hosts = critical_hosts
                    best_has_lateral_event = has_lateral_event

            if not best_window:
                continue

            description = (
                f"【检测引擎】账号 {best_window[0].username} 在短时间内访问多台高价值主机，"
                f"涉及 {len(best_critical_hosts)} 台关键资产。"
                f"{' 同时出现 LATERAL_MOVE 事件。' if best_has_lateral_event else ''}"
            )

            metrics = {
                "evidence_count": max(len(best_window), len(best_critical_hosts)),
                "max_event_risk_score": max(item.max_event_risk_score for item in best_window),
                "max_host_critical_level": max(item.max_host_critical_level for item in best_window),
                "suspicious_ip": any(item.is_suspicious_ip() for item in best_window),
                "blocked_target": any(item.ip and item.ip.get("is_blocked") for item in best_window),
                "time_span_minutes": minutes_between(best_window[0].start_dt, best_window[-1].start_dt),
            }

            results.append(
                self._build_match(
                    rule=rule,
                    anchor_type="USER",
                    anchor_id=user_id,
                    anchor_name=best_window[0].username,
                    first_seen=first_non_empty_min(
                        [item.evidence_first_seen for item in best_window],
                        current_timestamp(),
                    ),
                    last_seen=first_non_empty_max(
                        [item.evidence_last_seen for item in best_window],
                        current_timestamp(),
                    ),
                    description=description,
                    evidence_summary=f"高危主机数：{len(best_critical_hosts)}；主机：{' / '.join(best_critical_hosts)}",
                    metrics=metrics,
                    evidence_user_ids=[user_id],
                    evidence_session_ids=[item.session_id or "" for item in best_window],
                    evidence_event_ids=[event_id for item in best_window for event_id in item.event_ids],
                    evidence_ip_ids=[item.ip_id or "" for item in best_window],
                    evidence_host_ids=best_critical_hosts,
                )
            )

        return results

    def _detect_high_risk_host_access(self, session_contexts: List[SessionContext]) -> List[DetectionMatch]:
        """
        规则 8：高危主机异常访问。
        """
        rule = RULE_MAP["DR_ACCESS_003"]
        results: List[DetectionMatch] = []

        for ctx in session_contexts:
            if ctx.max_host_critical_level < 4:
                continue

            abnormal_reasons: List[str] = []
            if ctx.is_suspicious_ip():
                abnormal_reasons.append("源 IP 可疑")
            if ctx.max_event_risk_score >= 80 or ctx.has_event_type("LATERAL_MOVE"):
                abnormal_reasons.append("伴随高风险事件")
            if safe_int(ctx.user.get("privilege_level")) >= 4 and not bool(ctx.user.get("is_whitelisted")):
                abnormal_reasons.append("高权限账号访问")

            if not abnormal_reasons:
                continue

            description = (
                f"【检测引擎】会话 {ctx.session_id} 访问了高危主机 {', '.join(ctx.host_names) or '未知主机'}，"
                f"同时存在异常因素：{'、'.join(abnormal_reasons)}。"
            )

            metrics = {
                "evidence_count": max(1, len(ctx.hosts)),
                "max_event_risk_score": ctx.max_event_risk_score,
                "max_host_critical_level": ctx.max_host_critical_level,
                "suspicious_ip": ctx.is_suspicious_ip(),
                "blocked_target": bool(ctx.ip and ctx.ip.get("is_blocked")),
                "time_span_minutes": 0,
            }

            results.append(
                self._build_match(
                    rule=rule,
                    anchor_type="SESSION",
                    anchor_id=ctx.session_id or "UNKNOWN_SESSION",
                    anchor_name=ctx.session_id or "未知会话",
                    first_seen=ctx.evidence_first_seen or current_timestamp(),
                    last_seen=ctx.evidence_last_seen or current_timestamp(),
                    description=description,
                    evidence_summary=f"异常因素：{'、'.join(abnormal_reasons)}",
                    metrics=metrics,
                    evidence_user_ids=[ctx.user_id or ""],
                    evidence_session_ids=[ctx.session_id or ""],
                    evidence_event_ids=ctx.event_ids,
                    evidence_ip_ids=[ctx.ip_id or ""],
                    evidence_host_ids=ctx.host_ids,
                )
            )

        return results

    def _detect_multi_sensitive_ports(self, session_contexts: List[SessionContext]) -> List[DetectionMatch]:
        """
        规则 9：短时间访问多个敏感端口。
        """
        rule = RULE_MAP["DR_ACCESS_004"]
        user_groups = self._group_contexts_by_user(session_contexts)
        results: List[DetectionMatch] = []

        for user_id, contexts in user_groups.items():
            sorted_contexts = self._sort_contexts_by_start_time(contexts)
            best_window: List[SessionContext] = []
            best_ports: List[str] = []

            for index, _ in enumerate(sorted_contexts):
                window = self._slice_time_window(sorted_contexts, index, 15)
                if not window:
                    continue

                ports = sorted({str(port) for item in window for port in item.sensitive_ports})
                if len(ports) < 2:
                    continue

                if len(ports) > len(best_ports):
                    best_window = window
                    best_ports = ports

            if not best_window:
                continue

            description = (
                f"【检测引擎】账号 {best_window[0].username} 在 15 分钟内访问了多个敏感端口，"
                f"端口集合为 {' / '.join(best_ports)}。"
            )

            metrics = {
                "evidence_count": len(best_ports),
                "max_event_risk_score": max(item.max_event_risk_score for item in best_window),
                "max_host_critical_level": max(item.max_host_critical_level for item in best_window),
                "suspicious_ip": any(item.is_suspicious_ip() for item in best_window),
                "blocked_target": any(item.ip and item.ip.get("is_blocked") for item in best_window),
                "time_span_minutes": minutes_between(best_window[0].start_dt, best_window[-1].start_dt),
            }

            results.append(
                self._build_match(
                    rule=rule,
                    anchor_type="USER",
                    anchor_id=user_id,
                    anchor_name=best_window[0].username,
                    first_seen=first_non_empty_min(
                        [item.evidence_first_seen for item in best_window],
                        current_timestamp(),
                    ),
                    last_seen=first_non_empty_max(
                        [item.evidence_last_seen for item in best_window],
                        current_timestamp(),
                    ),
                    description=description,
                    evidence_summary=f"敏感端口数：{len(best_ports)}；端口：{' / '.join(best_ports)}",
                    metrics=metrics,
                    evidence_user_ids=[user_id],
                    evidence_session_ids=[item.session_id or "" for item in best_window],
                    evidence_event_ids=[event_id for item in best_window for event_id in item.event_ids],
                    evidence_ip_ids=[item.ip_id or "" for item in best_window],
                    evidence_host_ids=[host_id for item in best_window for host_id in item.host_ids],
                )
            )

        return results

    def _detect_multi_anomaly_session(self, session_contexts: List[SessionContext]) -> List[DetectionMatch]:
        """
        规则 10：单会话触发多类异常事件。
        """
        rule = RULE_MAP["DR_ACCESS_005"]
        results: List[DetectionMatch] = []

        for ctx in session_contexts:
            indicators: List[str] = []

            if ctx.is_suspicious_ip():
                indicators.append("可疑源 IP")
            if ctx.max_host_critical_level >= 4:
                indicators.append("高危主机访问")
            if ctx.max_event_risk_score >= 70:
                indicators.append("高风险事件")
            if ctx.has_login_failure():
                indicators.append("登录失败")
            if len(ctx.event_types) >= 2:
                indicators.append("多种事件类型")

            if len(indicators) < 3:
                continue

            description = (
                f"【检测引擎】会话 {ctx.session_id} 同时出现多类异常信号：{'、'.join(indicators)}，"
                f"属于复合型高风险会话。"
            )

            metrics = {
                "evidence_count": len(indicators),
                "max_event_risk_score": ctx.max_event_risk_score,
                "max_host_critical_level": ctx.max_host_critical_level,
                "suspicious_ip": ctx.is_suspicious_ip(),
                "blocked_target": bool(ctx.ip and ctx.ip.get("is_blocked")),
                "time_span_minutes": 0,
            }

            results.append(
                self._build_match(
                    rule=rule,
                    anchor_type="SESSION",
                    anchor_id=ctx.session_id or "UNKNOWN_SESSION",
                    anchor_name=ctx.session_id or "未知会话",
                    first_seen=ctx.evidence_first_seen or current_timestamp(),
                    last_seen=ctx.evidence_last_seen or current_timestamp(),
                    description=description,
                    evidence_summary=f"异常指征数：{len(indicators)}；指征：{'、'.join(indicators)}",
                    metrics=metrics,
                    evidence_user_ids=[ctx.user_id or ""],
                    evidence_session_ids=[ctx.session_id or ""],
                    evidence_event_ids=ctx.event_ids,
                    evidence_ip_ids=[ctx.ip_id or ""],
                    evidence_host_ids=ctx.host_ids,
                )
            )

        return results

    def _detect_multi_rule_hits(
        self,
        core_matches: List[DetectionMatch],
        entity_maps: Dict[str, Dict[str, Dict[str, Any]]],
        session_contexts: List[SessionContext],
    ) -> List[DetectionMatch]:
        """
        规则 11：同一用户 / IP / 会话命中多条规则。
        """
        rule = RULE_MAP["DR_AGG_001"]
        results: List[DetectionMatch] = []
        entity_buckets = {
            "USER": defaultdict(lambda: self._new_entity_bucket()),
            "IP": defaultdict(lambda: self._new_entity_bucket()),
            "SESSION": defaultdict(lambda: self._new_entity_bucket()),
        }

        for match_item in core_matches:
            for user_id in match_item.evidence_user_ids:
                self._append_match_to_entity_bucket(entity_buckets["USER"][user_id], match_item)
            for ip_id in match_item.evidence_ip_ids:
                self._append_match_to_entity_bucket(entity_buckets["IP"][ip_id], match_item)
            for session_id in match_item.evidence_session_ids:
                self._append_match_to_entity_bucket(entity_buckets["SESSION"][session_id], match_item)

        session_map = {ctx.session_id: ctx for ctx in session_contexts if ctx.session_id}

        for anchor_type, bucket_map in entity_buckets.items():
            for anchor_id, bucket in bucket_map.items():
                rule_ids = unique_sorted(bucket["rule_ids"])
                if len(rule_ids) < 2:
                    continue

                rule_names = unique_sorted(bucket["rule_names"])
                anchor_name = self._resolve_anchor_name(anchor_type, anchor_id, entity_maps)
                related_session_contexts = [
                    session_map.get(session_id)
                    for session_id in unique_sorted(bucket["session_ids"])
                    if session_map.get(session_id)
                ]

                metrics = {
                    "evidence_count": len(rule_ids),
                    "max_event_risk_score": max((ctx.max_event_risk_score for ctx in related_session_contexts), default=0),
                    "max_host_critical_level": max((ctx.max_host_critical_level for ctx in related_session_contexts), default=0),
                    "suspicious_ip": any(ctx.is_suspicious_ip() for ctx in related_session_contexts),
                    "blocked_target": anchor_type == "IP" and bool(entity_maps["IP"].get(anchor_id, {}).get("is_blocked")),
                    "time_span_minutes": minutes_between(
                        parse_iso_datetime(bucket["first_seen"]),
                        parse_iso_datetime(bucket["last_seen"]),
                    ),
                    "overlap_rule_count": len(rule_ids),
                }

                description = (
                    f"【检测引擎】{anchor_type} 对象 {anchor_name} 在当前检测周期内同时命中多条规则，"
                    f"命中规则包括：{'、'.join(rule_names)}。"
                )

                results.append(
                    self._build_match(
                        rule=rule,
                        anchor_type=anchor_type,
                        anchor_id=anchor_id,
                        anchor_name=anchor_name,
                        first_seen=bucket["first_seen"],
                        last_seen=bucket["last_seen"],
                        description=description,
                        evidence_summary=f"命中规则数：{len(rule_ids)}；规则：{' / '.join(rule_names)}",
                        metrics=metrics,
                        evidence_user_ids=bucket["user_ids"],
                        evidence_session_ids=bucket["session_ids"],
                        evidence_event_ids=bucket["event_ids"],
                        evidence_ip_ids=bucket["ip_ids"],
                        evidence_host_ids=bucket["host_ids"],
                        evidence_alert_ids=bucket["alert_ids"],
                        related_rule_ids=rule_ids,
                        related_rule_names=rule_names,
                    )
                )

        return results

    def _detect_multi_high_risk_alert_chain(
        self,
        session_contexts: List[SessionContext],
        core_matches: List[DetectionMatch],
    ) -> List[DetectionMatch]:
        """
        规则 12：同一链路关联多个高危告警。
        """
        rule = RULE_MAP["DR_AGG_002"]
        results: List[DetectionMatch] = []
        generated_alerts_by_session = defaultdict(list)

        for match_item in core_matches:
            if match_item.score < 75:
                continue
            for session_id in match_item.evidence_session_ids:
                generated_alerts_by_session[session_id].append(match_item)

        for ctx in session_contexts:
            if not ctx.session_id:
                continue

            high_risk_alert_ids = set(ctx.high_severity_alert_ids)
            related_rule_names: List[str] = []
            for match_item in generated_alerts_by_session.get(ctx.session_id, []):
                high_risk_alert_ids.add(match_item.alert_id)
                related_rule_names.append(match_item.rule_name)

            if len(high_risk_alert_ids) < 2:
                continue

            metrics = {
                "evidence_count": len(high_risk_alert_ids),
                "max_event_risk_score": ctx.max_event_risk_score,
                "max_host_critical_level": ctx.max_host_critical_level,
                "suspicious_ip": ctx.is_suspicious_ip(),
                "blocked_target": bool(ctx.ip and ctx.ip.get("is_blocked")),
                "time_span_minutes": minutes_between(ctx.start_dt, ctx.end_dt or ctx.start_dt),
                "overlap_rule_count": len(high_risk_alert_ids),
            }

            description = (
                f"【检测引擎】会话 {ctx.session_id} 所在链路同时关联多条高危告警，"
                f"说明攻击路径已出现连续风险扩散。"
            )

            results.append(
                self._build_match(
                    rule=rule,
                    anchor_type="SESSION",
                    anchor_id=ctx.session_id,
                    anchor_name=ctx.session_id,
                    first_seen=ctx.evidence_first_seen or current_timestamp(),
                    last_seen=ctx.evidence_last_seen or current_timestamp(),
                    description=description,
                    evidence_summary=f"高危告警数：{len(high_risk_alert_ids)}",
                    metrics=metrics,
                    evidence_user_ids=[ctx.user_id or ""],
                    evidence_session_ids=[ctx.session_id],
                    evidence_event_ids=ctx.event_ids,
                    evidence_ip_ids=[ctx.ip_id or ""],
                    evidence_host_ids=ctx.host_ids,
                    evidence_alert_ids=list(high_risk_alert_ids),
                    related_rule_names=related_rule_names,
                )
            )

        return results

    def _detect_reappeared_after_disposal(self, session_contexts: List[SessionContext]) -> List[DetectionMatch]:
        """
        规则 13：已处置或已封禁对象再次出现异常行为。
        """
        rule = RULE_MAP["DR_AGG_003"]
        results: List[DetectionMatch] = []

        for ctx in session_contexts:
            if not ctx.ip or not ctx.ip_id:
                continue

            latest_block_time = ctx.latest_block_time
            if latest_block_time is None or ctx.start_dt is None:
                continue
            if ctx.start_dt <= latest_block_time:
                continue

            if not (ctx.max_event_risk_score >= 70 or ctx.has_login_failure() or ctx.max_host_critical_level >= 4):
                continue

            metrics = {
                "evidence_count": max(1, len(ctx.event_ids)),
                "max_event_risk_score": ctx.max_event_risk_score,
                "max_host_critical_level": ctx.max_host_critical_level,
                "suspicious_ip": True,
                "blocked_target": True,
                "time_span_minutes": minutes_between(latest_block_time, ctx.start_dt),
                "reappeared_after_block": True,
            }

            description = (
                f"【检测引擎】已处置 IP {ctx.ip_address} 在封禁时间 {latest_block_time.isoformat(timespec='seconds')} 之后，"
                f"仍再次出现异常会话 {ctx.session_id}，说明处置策略可能被绕过或未完全生效。"
            )

            results.append(
                self._build_match(
                    rule=rule,
                    anchor_type="IP",
                    anchor_id=ctx.ip_id,
                    anchor_name=ctx.ip_address,
                    first_seen=ctx.evidence_first_seen or current_timestamp(),
                    last_seen=ctx.evidence_last_seen or current_timestamp(),
                    description=description,
                    evidence_summary="已处置对象再次出现异常行为",
                    metrics=metrics,
                    evidence_user_ids=[ctx.user_id or ""],
                    evidence_session_ids=[ctx.session_id or ""],
                    evidence_event_ids=ctx.event_ids,
                    evidence_ip_ids=[ctx.ip_id],
                    evidence_host_ids=ctx.host_ids,
                )
            )

        return results

    def _upsert_rule_nodes(self) -> int:
        """
        将本轮实现的规则定义回写为 Rule 节点。
        """
        query = """
UNWIND $rows AS row
MERGE (r:Rule {rule_id: row.rule_id})
SET r.rule_name = row.rule_name,
    r.rule_category = row.rule_category,
    r.rule_level = row.rule_level,
    r.threshold_desc = row.threshold_desc,
    r.description = row.description,
    r.enabled = true,
    r.rule_source = $rule_source,
    r.updated_at = row.updated_at
RETURN count(r) AS total
"""
        rows = [
            {
                "rule_id": item.rule_id,
                "rule_name": item.rule_name,
                "rule_category": item.rule_category,
                "rule_level": item.rule_level,
                "threshold_desc": item.threshold_desc,
                "description": item.description,
                "updated_at": current_timestamp(),
            }
            for item in RULE_DEFINITIONS
        ]
        query_result = self.client.execute_write(query, {"rows": rows, "rule_source": DETECTION_ENGINE_NAME})
        if not query_result:
            return len(rows)
        return safe_int(query_result[0].get("total"), len(rows))

    def _persist_alerts(self, matches: List[DetectionMatch], detected_at: str) -> int:
        """
        将检测结果写回 Neo4j。
        """
        if not matches:
            return 0

        rows = [item.to_persist_row(detected_at) for item in matches]
        alert_ids = [item["alert_id"] for item in rows]

        upsert_alert_query = """
UNWIND $rows AS row
MERGE (a:Alert {alert_id: row.alert_id})
ON CREATE SET a.created_at = row.detected_at,
              a.status = 'NEW'
SET a.alert_name = row.alert_name,
    a.severity = row.severity,
    a.score = row.score,
    a.status = CASE WHEN a.status IS NULL OR a.status = '' THEN 'NEW' ELSE a.status END,
    a.first_seen = CASE
        WHEN a.first_seen IS NULL OR a.first_seen = '' THEN row.first_seen
        WHEN row.first_seen IS NULL OR row.first_seen = '' THEN a.first_seen
        WHEN row.first_seen < a.first_seen THEN row.first_seen
        ELSE a.first_seen
    END,
    a.last_seen = row.last_seen,
    a.description = row.description,
    a.suggestion = row.suggestion,
    a.generated_by = $generated_by,
    a.rule_id = row.rule_id,
    a.rule_name = row.rule_name,
    a.rule_category = row.rule_category,
    a.anchor_type = row.anchor_type,
    a.anchor_id = row.anchor_id,
    a.anchor_name = row.anchor_name,
    a.evidence_user_ids = row.evidence_user_ids,
    a.evidence_session_ids = row.evidence_session_ids,
    a.evidence_event_ids = row.evidence_event_ids,
    a.evidence_ip_ids = row.evidence_ip_ids,
    a.evidence_host_ids = row.evidence_host_ids,
    a.evidence_alert_ids = row.evidence_alert_ids,
    a.related_rule_ids = row.related_rule_ids,
    a.related_rule_names = row.related_rule_names,
    a.evidence_summary = row.evidence_summary,
    a.score_breakdown_json = row.score_breakdown_json,
    a.detected_at = row.detected_at
RETURN count(a) AS total
"""
        upsert_result = self.client.execute_write(
            upsert_alert_query,
            {"rows": rows, "generated_by": DETECTION_ENGINE_NAME},
        )

        self.client.execute_write(
            """
UNWIND $alert_ids AS alert_id
MATCH (a:Alert {alert_id: alert_id})-[rel:HIT_RULE]->(:Rule)
DELETE rel
""",
            {"alert_ids": alert_ids},
        )

        self.client.execute_write(
            """
UNWIND $alert_ids AS alert_id
MATCH (:Event)-[rel:TRIGGERS]->(a:Alert {alert_id: alert_id})
DELETE rel
""",
            {"alert_ids": alert_ids},
        )

        self.client.execute_write(
            """
UNWIND $rows AS row
MATCH (a:Alert {alert_id: row.alert_id})
MATCH (r:Rule {rule_id: row.rule_id})
MERGE (a)-[rel:HIT_RULE]->(r)
SET rel.relation_time = row.last_seen,
    rel.generated_by = $generated_by
""",
            {"rows": rows, "generated_by": DETECTION_ENGINE_NAME},
        )

        self.client.execute_write(
            """
UNWIND $rows AS row
MATCH (a:Alert {alert_id: row.alert_id})
UNWIND row.evidence_event_ids AS event_id
MATCH (e:Event {event_id: event_id})
MERGE (e)-[rel:TRIGGERS]->(a)
SET rel.relation_time = row.last_seen,
    rel.generated_by = $generated_by
""",
            {"rows": rows, "generated_by": DETECTION_ENGINE_NAME},
        )

        if not upsert_result:
            return len(rows)
        return safe_int(upsert_result[0].get("total"), len(rows))

    def _update_entity_scores(self, matches: List[DetectionMatch], detected_at: str) -> Dict[str, int]:
        """
        根据检测结果回写 User / IP / Session / Host 的检测风险字段。
        """
        aggregate_map = {
            "USER": defaultdict(lambda: self._new_entity_score_bucket()),
            "IP": defaultdict(lambda: self._new_entity_score_bucket()),
            "SESSION": defaultdict(lambda: self._new_entity_score_bucket()),
            "HOST": defaultdict(lambda: self._new_entity_score_bucket()),
        }

        for match_item in matches:
            self._append_entity_score(aggregate_map["USER"], match_item.evidence_user_ids, match_item)
            self._append_entity_score(aggregate_map["IP"], match_item.evidence_ip_ids, match_item)
            self._append_entity_score(aggregate_map["SESSION"], match_item.evidence_session_ids, match_item)
            self._append_entity_score(aggregate_map["HOST"], match_item.evidence_host_ids, match_item)

        return {
            "User": self._write_entity_scores("User", "user_id", self._build_entity_score_rows(aggregate_map["USER"], detected_at)),
            "IP": self._write_entity_scores("IP", "ip_id", self._build_entity_score_rows(aggregate_map["IP"], detected_at)),
            "Session": self._write_entity_scores("Session", "session_id", self._build_entity_score_rows(aggregate_map["SESSION"], detected_at)),
            "Host": self._write_entity_scores("Host", "host_id", self._build_entity_score_rows(aggregate_map["HOST"], detected_at)),
        }

    def _new_entity_score_bucket(self) -> Dict[str, Any]:
        """
        初始化实体评分桶。
        """
        return {"max_score": 0, "rule_ids": [], "alert_ids": [], "hit_count": 0}

    def _append_entity_score(
        self,
        bucket_map: Dict[str, Dict[str, Any]],
        entity_ids: List[str],
        match_item: DetectionMatch,
    ) -> None:
        """
        将检测结果累积到实体评分桶中。
        """
        for entity_id in unique_sorted(entity_ids):
            bucket = bucket_map[entity_id]
            bucket["max_score"] = max(bucket["max_score"], match_item.score)
            bucket["rule_ids"].append(match_item.rule_id)
            bucket["alert_ids"].append(match_item.alert_id)
            bucket["hit_count"] += 1

    def _build_entity_score_rows(self, bucket_map: Dict[str, Dict[str, Any]], detected_at: str) -> List[Dict[str, Any]]:
        """
        将实体评分桶转换为批量写入行。
        """
        rows = []
        for entity_id, bucket in bucket_map.items():
            hit_count = safe_int(bucket.get("hit_count"))
            if hit_count <= 0:
                continue

            detection_score = min(100, bucket["max_score"] + min(20, max(0, hit_count - 1) * 5))
            rows.append(
                {
                    "entity_id": entity_id,
                    "detection_score": detection_score,
                    "detection_level": to_score_level(detection_score),
                    "detection_hit_count": hit_count,
                    "detected_rule_ids": unique_sorted(bucket["rule_ids"]),
                    "detected_alert_ids": unique_sorted(bucket["alert_ids"]),
                    "last_detected_at": detected_at,
                }
            )
        return rows

    def _write_entity_scores(self, label_name: str, key_field: str, rows: List[Dict[str, Any]]) -> int:
        """
        批量写入实体评分。
        """
        if not rows:
            return 0

        query = f"""
UNWIND $rows AS row
MATCH (n:{label_name} {{{key_field}: row.entity_id}})
SET n.detection_score = row.detection_score,
    n.detection_level = row.detection_level,
    n.detection_hit_count = row.detection_hit_count,
    n.detected_rule_ids = row.detected_rule_ids,
    n.detected_alert_ids = row.detected_alert_ids,
    n.last_detected_at = row.last_detected_at,
    n.risk_score = CASE
        WHEN coalesce(n.risk_score, 0) < row.detection_score THEN row.detection_score
        ELSE n.risk_score
    END
RETURN count(n) AS total
"""
        query_result = self.client.execute_write(query, {"rows": rows})
        if not query_result:
            return len(rows)
        return safe_int(query_result[0].get("total"), len(rows))

    def _build_rule_stats(self, matches: List[DetectionMatch]) -> List[Dict[str, Any]]:
        """
        统计各规则命中数量。
        """
        stats_map = {item.rule_id: 0 for item in RULE_DEFINITIONS}
        for match_item in matches:
            stats_map[match_item.rule_id] = stats_map.get(match_item.rule_id, 0) + 1

        return [
            {
                "rule_id": item.rule_id,
                "rule_name": item.rule_name,
                "rule_category": item.rule_category,
                "match_count": stats_map.get(item.rule_id, 0),
            }
            for item in RULE_DEFINITIONS
        ]


def minutes_between(start_time: Optional[datetime], end_time: Optional[datetime]) -> int:
    """
    计算两个时间之间的分钟差。
    """
    if start_time is None or end_time is None:
        return 0
    return int(abs((end_time - start_time).total_seconds()) // 60)


def is_non_work_hour(value: Optional[datetime]) -> bool:
    """
    判断是否为非工作时间。
    """
    if value is None:
        return False
    if value.weekday() >= 5:
        return True
    if value.hour < WORK_HOUR_START or value.hour >= WORK_HOUR_END:
        return True
    return False


detection_service = DetectionService(neo4j_client)
