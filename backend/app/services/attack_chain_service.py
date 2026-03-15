#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
文件路径：backend/app/services/attack_chain_service.py

文件作用：
1. 面向告警页面提供“攻击链图谱”服务。
2. 不直接返回 Neo4j Browser 风格的原始点图，而是围绕单条告警构造安全语义清晰的攻击链。
3. 优先复用 Neo4j 中已经入库的业务实体关系；如果某些语义节点并未独立建模，则在服务层按业务规则组装临时节点。

设计原则：
1. 攻击链图谱围绕具体告警展开，重点展示“攻击源 IP -> 攻击事件 -> 目标资源 -> 命中规则 -> 攻击类型 -> 受害资产 -> 告警 -> 封禁动作”。
2. 对于日志详情中的 URL、攻击类型等信息，优先从 Event/Rule/Alert 中提取；若图数据库中尚未独立建模，则以派生节点方式呈现。
3. 该服务不改动当前已有的 Neo4j 入库模型，只在查询层做业务语义增强，便于后续论文撰写说明“逻辑图谱”与“存储图谱”的分层设计。
"""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional

from app.core.errors import NotFoundError
from app.db import neo4j_client


EVENT_TYPE_NAME_MAPPING = {
    "SQL_INJECTION": "SQL 注入",
    "COMMAND_INJECTION": "命令注入",
    "XSS": "跨站脚本攻击",
    "LOGIN_FAIL": "暴力破解 / 认证失败",
    "LATERAL_MOVE": "横向移动",
    "HIGH_FREQ_ACCESS": "高频访问",
    "FIREWALL_DROP": "防火墙拦截 / 敏感端口探测",
    "PORT_SCAN": "端口扫描",
}

MAX_EVENT_CONTEXTS = 4
MAX_RULE_NODES = 4
MAX_BAN_NODES = 3


class AttackChainService:
    """
    攻击链图谱服务。

    核心职责：
    1. 根据 alert_id 查询告警周边的 Event、Session、IP、Host、Rule、BlockAction。
    2. 将原始实体关系转化为更适合前端展示的攻击链节点和边。
    3. 生成摘要信息，供告警页抽屉顶部快速展示攻击源、攻击类型和封禁状态。
    """

    def __init__(self, client):
        self.client = client

    def get_alert_attack_chain(self, alert_id: str) -> Dict[str, Any]:
        """
        根据告警编号构建攻击链图谱。

        返回结构：
        1. nodes：攻击链节点列表。
        2. links：攻击链关系列表。
        3. summary：摘要字段，便于告警页直接展示。
        """
        alert_context = self._fetch_alert_context(alert_id)
        if not alert_context or not alert_context.get("alert"):
            raise NotFoundError(f"未找到告警 {alert_id} 对应的攻击链数据")

        alert = alert_context["alert"]
        evidence = self._extract_alert_evidence(alert)
        event_contexts = self._fetch_event_contexts(alert_id=alert_id, evidence_event_ids=evidence["event_ids"])

        extra_ips = self._fetch_nodes_by_ids("IP", "ip_id", evidence["ip_ids"])
        extra_hosts = self._fetch_nodes_by_ids("Host", "host_id", evidence["host_ids"])
        extra_rules = self._fetch_nodes_by_ids("Rule", "rule_id", evidence["rule_ids"])

        rules = self._dedupe_dicts(alert_context["rules"] + extra_rules, "rule_id")[:MAX_RULE_NODES]
        bans = self._dedupe_dicts(alert_context["bans"], "action_id")[:MAX_BAN_NODES]
        ban_target_ips = self._dedupe_dicts(alert_context["target_ips"], "ip_id")

        return self._build_attack_chain_payload(
            alert=alert,
            event_contexts=event_contexts,
            rules=rules,
            bans=bans,
            fallback_ips=extra_ips + ban_target_ips,
            fallback_hosts=extra_hosts,
        )

    def _fetch_alert_context(self, alert_id: str) -> Dict[str, Any]:
        """
        查询告警本体、命中规则、封禁动作和封禁目标 IP。
        """
        query = """
MATCH (a:Alert {alert_id: $alert_id})
OPTIONAL MATCH (a)-[:HIT_RULE]->(r:Rule)
WITH a, [x IN collect(DISTINCT properties(r)) WHERE x IS NOT NULL] AS rules
OPTIONAL MATCH (b:BlockAction)-[:DISPOSES]->(a)
OPTIONAL MATCH (b)-[:TARGETS_IP]->(tip:IP)
RETURN properties(a) AS alert,
       rules AS rules,
       [x IN collect(DISTINCT properties(b)) WHERE x IS NOT NULL] AS bans,
       [x IN collect(DISTINCT properties(tip)) WHERE x IS NOT NULL] AS target_ips
"""
        records = self.client.execute_read(query, {"alert_id": alert_id})
        return records[0] if records else {}

    def _fetch_event_contexts(self, alert_id: str, evidence_event_ids: List[str]) -> List[Dict[str, Any]]:
        """
        查询与告警关联的攻击事件上下文。

        说明：
        1. 优先取 Event -> Alert 的直接关系。
        2. 对于检测引擎生成的聚合告警，会补充 alert.evidence_event_ids 中记录的证据事件。
        3. 每条事件上下文同时带出关联 Session、源 IP 和目标 Host，便于构造完整攻击链。
        """
        query = """
MATCH (a:Alert {alert_id: $alert_id})
WITH a, $event_ids AS event_ids
OPTIONAL MATCH (e:Event)
WHERE e.event_id IN event_ids OR EXISTS { MATCH (e)-[:TRIGGERS]->(a) }
WITH collect(DISTINCT e) AS event_nodes
UNWIND event_nodes AS e
OPTIONAL MATCH (s:Session)-[:GENERATES]->(e)
OPTIONAL MATCH (s)-[:USES_SOURCE_IP]->(ip:IP)
OPTIONAL MATCH (s)-[:ACCESSES]->(h:Host)
WITH e,
     [x IN collect(DISTINCT properties(s)) WHERE x IS NOT NULL] AS sessions,
     [x IN collect(DISTINCT properties(ip)) WHERE x IS NOT NULL] AS ips,
     [x IN collect(DISTINCT properties(h)) WHERE x IS NOT NULL] AS hosts
RETURN properties(e) AS event,
       sessions,
       ips,
       hosts
ORDER BY coalesce(event.event_time, '') DESC
"""
        records = self.client.execute_read(query, {"alert_id": alert_id, "event_ids": evidence_event_ids})

        normalized_records: List[Dict[str, Any]] = []
        for item in records:
            event = item.get("event")
            if not event:
                continue

            normalized_records.append(
                {
                    "event": event,
                    "sessions": self._dedupe_dicts(item.get("sessions", []), "session_id"),
                    "ips": self._dedupe_dicts(item.get("ips", []), "ip_id"),
                    "hosts": self._dedupe_dicts(item.get("hosts", []), "host_id"),
                }
            )

        normalized_records.sort(
            key=lambda item: (
                self._safe_int(item["event"].get("risk_score")),
                self._safe_text(item["event"].get("event_time")),
            ),
            reverse=True,
        )
        return normalized_records[:MAX_EVENT_CONTEXTS]

    def _fetch_nodes_by_ids(self, label_name: str, key_field: str, entity_ids: Iterable[str]) -> List[Dict[str, Any]]:
        """
        按主键批量查询节点属性。

        说明：
        1. 这里只允许查询既有业务标签，避免动态拼接带来的风险。
        2. 返回值统一为 properties(n) 的字典列表，便于后续与直接关系查询结果合并。
        """
        valid_labels = {"IP", "Host", "Rule"}
        if label_name not in valid_labels:
            return []

        normalized_ids = [item for item in self._unique_list(entity_ids) if item]
        if not normalized_ids:
            return []

        query = f"""
MATCH (n:{label_name})
WHERE n.{key_field} IN $entity_ids
RETURN properties(n) AS item
"""
        records = self.client.execute_read(query, {"entity_ids": normalized_ids})
        return [record["item"] for record in records if record.get("item")]

    def _build_attack_chain_payload(
        self,
        alert: Dict[str, Any],
        event_contexts: List[Dict[str, Any]],
        rules: List[Dict[str, Any]],
        bans: List[Dict[str, Any]],
        fallback_ips: List[Dict[str, Any]],
        fallback_hosts: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        将查询结果转换为前端攻击链图谱结构。
        """
        nodes_by_id: Dict[str, Dict[str, Any]] = {}
        links_by_id: Dict[str, Dict[str, Any]] = {}

        def add_node(
            node_id: str,
            name: str,
            node_type: str,
            stage: int,
            lane: int,
            symbol_size: int,
            detail_lines: Optional[List[str]] = None,
            status: str = "ACTIVE",
        ) -> None:
            """
            添加攻击链节点。
            """
            if node_id in nodes_by_id:
                return

            nodes_by_id[node_id] = {
                "id": node_id,
                "name": name,
                "type": node_type,
                "stage": stage,
                "lane": lane,
                "symbolSize": symbol_size,
                "status": status,
                "detail_lines": detail_lines or [],
            }

        def add_link(
            source: str,
            target: str,
            relation: str,
            detail_lines: Optional[List[str]] = None,
            status: str = "ACTIVE",
        ) -> None:
            """
            添加攻击链关系边。
            """
            link_id = f"{source}->{relation}->{target}"
            if link_id in links_by_id:
                return

            links_by_id[link_id] = {
                "id": link_id,
                "source": source,
                "target": target,
                "relation": relation,
                "status": status,
                "detail_lines": detail_lines or [],
            }

        primary_rule = rules[0] if rules else {}
        primary_context = event_contexts[0] if event_contexts else {}
        primary_event = primary_context.get("event") or {}
        primary_ip = (primary_context.get("ips") or fallback_ips or [{}])[0]
        primary_host = (primary_context.get("hosts") or fallback_hosts or [{}])[0]

        alert_node_id = f"alert::{self._safe_text(alert.get('alert_id'))}"
        add_node(
            node_id=alert_node_id,
            name=self._safe_text(alert.get("alert_name")) or "告警",
            node_type="alert",
            stage=6,
            lane=0,
            symbol_size=72,
            status=self._safe_text(alert.get("severity")) or "ACTIVE",
            detail_lines=[
                f"告警编号：{self._safe_text(alert.get('alert_id')) or '-'}",
                f"严重等级：{self._safe_text(alert.get('severity')) or '-'}",
                f"风险得分：{self._safe_text(alert.get('score')) or '-'}",
                f"告警状态：{self._safe_text(alert.get('status')) or '-'}",
                f"说明：{self._safe_text(alert.get('description')) or '-'}",
            ],
        )

        for rule_index, rule in enumerate(rules):
            rule_id = self._safe_text(rule.get("rule_id")) or f"derived-rule-{rule_index}"
            rule_node_id = f"rule::{rule_id}"
            add_node(
                node_id=rule_node_id,
                name=self._safe_text(rule.get("rule_name")) or f"规则 {rule_index + 1}",
                node_type="rule",
                stage=4,
                lane=rule_index,
                symbol_size=58,
                status=self._safe_text(rule.get("rule_level")) or "ACTIVE",
                detail_lines=[
                    f"规则编号：{rule_id}",
                    f"规则分类：{self._safe_text(rule.get('rule_category')) or '-'}",
                    f"规则等级：{self._safe_text(rule.get('rule_level')) or '-'}",
                    f"阈值描述：{self._safe_text(rule.get('threshold_desc')) or '-'}",
                ],
            )
            add_link(
                source=rule_node_id,
                target=alert_node_id,
                relation="命中规则对应告警",
                detail_lines=[f"规则 {self._safe_text(rule.get('rule_name')) or rule_id} 命中后生成当前告警"],
            )

        for ban_index, ban in enumerate(bans):
            action_id = self._safe_text(ban.get("action_id")) or f"derived-ban-{ban_index}"
            ban_node_id = f"ban::{action_id}"
            ban_status = self._safe_text(ban.get("current_ban_status")) or self._safe_text(ban.get("status")) or "READY"
            latest_action_type = self._safe_text(ban.get("latest_action_type")) or self._safe_text(ban.get("action_type"))
            ban_name = self._safe_text(ban.get("action_type")) or "封禁动作"
            if ban_status == "RELEASED":
                ban_name = f"{ban_name}（已放行）"
            elif latest_action_type == "MANUAL_BLOCK_IP" and self._safe_text(ban.get("block_count")) not in {"", "0", "1"}:
                ban_name = f"{ban_name}（重新封禁）"
            add_node(
                node_id=ban_node_id,
                name=ban_name,
                node_type="ban_action",
                stage=7,
                lane=ban_index,
                symbol_size=66,
                status=ban_status,
                detail_lines=[
                    f"动作编号：{action_id}",
                    f"动作类型：{self._safe_text(ban.get('action_type')) or '-'}",
                    f"最近动作：{latest_action_type or '-'}",
                    f"当前状态：{ban_status}",
                    f"执行状态：{self._safe_text(ban.get('status')) or '-'}",
                    f"最近操作时间：{self._safe_text(ban.get('latest_action_at')) or '-'}",
                    f"最近操作人：{self._safe_text(ban.get('latest_action_by')) or '-'}",
                    f"最近操作原因：{self._safe_text(ban.get('latest_action_reason')) or '-'}",
                    f"执行时间：{self._safe_text(ban.get('executed_at')) or '-'}",
                    f"执行人：{self._safe_text(ban.get('executor')) or '-'}",
                    f"执行模式：{self._safe_text(ban.get('enforcement_mode')) or '-'}",
                    f"执行后端：{self._safe_text(ban.get('enforcement_backend')) or '-'}",
                    f"规则下发结果：{self._safe_text(ban.get('enforcement_status')) or '-'}",
                    f"规则名：{self._safe_text(ban.get('enforcement_rule_name')) or '-'}",
                    f"校验状态：{self._safe_text(ban.get('verification_status')) or '-'}",
                    f"校验时间：{self._safe_text(ban.get('verified_at')) or '-'}",
                    f"校验说明：{self._safe_text(ban.get('verification_message')) or '-'}",
                    f"放行时间：{self._safe_text(ban.get('released_at')) or '-'}",
                    f"放行人：{self._safe_text(ban.get('released_by')) or '-'}",
                    f"放行原因：{self._safe_text(ban.get('release_reason')) or '-'}",
                    f"封禁次数：{self._safe_text(ban.get('block_count')) or '-'}",
                    f"放行次数：{self._safe_text(ban.get('release_count')) or '-'}",
                    f"历史摘要：{self._safe_text(ban.get('history_summary')) or '-'}",
                ],
            )
            add_link(
                source=alert_node_id,
                target=ban_node_id,
                relation="告警联动封禁动作",
                detail_lines=[f"告警处置动作：{self._safe_text(ban.get('action_type')) or action_id}"],
                status=self._safe_text(ban.get("status")) or "ACTIVE",
            )

        if not event_contexts:
            fallback_ip = primary_ip if primary_ip else {}
            fallback_host = primary_host if primary_host else {}
            fallback_message = "当前告警缺少完整事件证据，已回退展示告警摘要与现有处置信息。"

            if fallback_ip:
                ip_node_id = f"ip::{self._safe_text(fallback_ip.get('ip_id')) or self._safe_text(fallback_ip.get('ip_address'))}"
                add_node(
                    node_id=ip_node_id,
                    name=self._safe_text(fallback_ip.get("ip_address")) or "攻击源 IP",
                    node_type="source_ip",
                    stage=0,
                    lane=0,
                    symbol_size=60,
                    status="DANGER" if fallback_ip.get("is_blocked") else "ACTIVE",
                    detail_lines=[
                        f"IP 编号：{self._safe_text(fallback_ip.get('ip_id')) or '-'}",
                        f"地理位置：{self._safe_text(fallback_ip.get('geo_location')) or '-'}",
                        f"信誉等级：{self._safe_text(fallback_ip.get('reputation_level')) or '-'}",
                    ],
                )
                add_link(
                    source=ip_node_id,
                    target=alert_node_id,
                    relation="攻击线索关联告警",
                    detail_lines=["当前告警缺少完整 Event 证据，已使用 IP 线索回退关联"],
                )

            if fallback_host:
                host_node_id = f"host::{self._safe_text(fallback_host.get('host_id')) or self._safe_text(fallback_host.get('hostname'))}"
                add_node(
                    node_id=host_node_id,
                    name=self._safe_text(fallback_host.get("hostname")) or "目标资产",
                    node_type="target_asset",
                    stage=5,
                    lane=0,
                    symbol_size=60,
                    status="ACTIVE",
                    detail_lines=[
                        f"资产编号：{self._safe_text(fallback_host.get('host_id')) or '-'}",
                        f"资产类型：{self._safe_text(fallback_host.get('asset_type')) or '-'}",
                        f"重要等级：{self._safe_text(fallback_host.get('critical_level')) or '-'}",
                    ],
                )
                add_link(
                    source=host_node_id,
                    target=alert_node_id,
                    relation="受害资产关联告警",
                    detail_lines=["当前告警缺少完整 Event 证据，已使用资产线索回退关联"],
                )

            return {
                "nodes": list(nodes_by_id.values()),
                "links": list(links_by_id.values()),
                "summary": self._build_summary(
                    alert=alert,
                    source_ip=self._safe_text(fallback_ip.get("ip_address")),
                    attack_type=self._derive_attack_type(primary_event, primary_rule, alert),
                    target_asset=self._safe_text(fallback_host.get("hostname")),
                    matched_rule=self._safe_text(primary_rule.get("rule_name")),
                    bans=bans,
                    message=fallback_message,
                ),
            }

        for event_index, context in enumerate(event_contexts):
            event = context["event"]
            sessions = context["sessions"]
            ips = context["ips"] or fallback_ips
            hosts = context["hosts"] or fallback_hosts

            event_id = self._safe_text(event.get("event_id")) or f"derived-event-{event_index}"
            event_node_id = f"event::{event_id}"
            attack_type_name = self._derive_attack_type(event, primary_rule, alert)
            attack_type_node_id = f"attack_type::{self._slugify(attack_type_name)}"
            resource_name = self._derive_resource_name(event, sessions, hosts)
            resource_node_id = f"resource::{event_id}"

            add_node(
                node_id=event_node_id,
                name=self._safe_text(event.get("event_type")) or f"事件 {event_index + 1}",
                node_type="security_event",
                stage=1,
                lane=event_index,
                symbol_size=62,
                status=self._safe_text(event.get("event_level")) or "ACTIVE",
                detail_lines=[
                    f"事件编号：{event_id}",
                    f"事件类型：{self._safe_text(event.get('event_type')) or '-'}",
                    f"事件时间：{self._safe_text(event.get('event_time')) or '-'}",
                    f"日志来源：{self._safe_text(event.get('log_source')) or '-'}",
                    f"事件详情：{self._safe_text(event.get('detail')) or '-'}",
                ],
            )
            add_node(
                node_id=attack_type_node_id,
                name=attack_type_name,
                node_type="attack_type",
                stage=3,
                lane=event_index,
                symbol_size=54,
                status="ACTIVE",
                detail_lines=[
                    f"归类依据：{self._safe_text(event.get('event_type')) or self._safe_text(primary_rule.get('rule_name')) or '事件语义推断'}",
                ],
            )
            add_node(
                node_id=resource_node_id,
                name=resource_name,
                node_type="request_resource",
                stage=2,
                lane=event_index,
                symbol_size=54,
                status="ACTIVE",
                detail_lines=[
                    f"资源标识：{resource_name}",
                    f"推断方式：{self._resource_origin_description(event, sessions, hosts)}",
                ],
            )

            add_link(
                source=event_node_id,
                target=resource_node_id,
                relation="攻击事件访问目标资源",
                detail_lines=[f"事件 {event_id} 访问或针对 {resource_name}"],
            )
            add_link(
                source=event_node_id,
                target=attack_type_node_id,
                relation="攻击事件属于攻击类型",
                detail_lines=[f"根据事件类型归类为 {attack_type_name}"],
            )
            add_link(
                source=event_node_id,
                target=alert_node_id,
                relation="攻击事件触发告警",
                detail_lines=[f"事件 {event_id} 与告警 {self._safe_text(alert.get('alert_id')) or '-'} 关联"],
                status=self._safe_text(alert.get("severity")) or "ACTIVE",
            )

            for ip_index, ip in enumerate(ips[:1]):
                ip_key = self._safe_text(ip.get("ip_id")) or self._safe_text(ip.get("ip_address")) or f"event-ip-{event_index}-{ip_index}"
                ip_node_id = f"ip::{ip_key}"
                add_node(
                    node_id=ip_node_id,
                    name=self._safe_text(ip.get("ip_address")) or self._extract_first_ip(event) or "攻击源 IP",
                    node_type="source_ip",
                    stage=0,
                    lane=event_index,
                    symbol_size=60,
                    status="DANGER" if ip.get("is_blocked") else "ACTIVE",
                    detail_lines=[
                        f"IP 编号：{self._safe_text(ip.get('ip_id')) or '-'}",
                        f"地理位置：{self._safe_text(ip.get('geo_location')) or '-'}",
                        f"信誉等级：{self._safe_text(ip.get('reputation_level')) or '-'}",
                        f"封禁状态：{'已封禁' if ip.get('is_blocked') else '未封禁'}",
                    ],
                )
                add_link(
                    source=ip_node_id,
                    target=event_node_id,
                    relation="IP 发起攻击事件",
                    detail_lines=[f"攻击源 {self._safe_text(ip.get('ip_address')) or '-'} 发起事件 {event_id}"],
                )

            for host_index, host in enumerate(hosts[:2]):
                host_key = self._safe_text(host.get("host_id")) or self._safe_text(host.get("hostname")) or f"event-host-{event_index}-{host_index}"
                host_node_id = f"host::{host_key}"
                add_node(
                    node_id=host_node_id,
                    name=self._safe_text(host.get("hostname")) or "受害资产",
                    node_type="target_asset",
                    stage=5,
                    lane=event_index + host_index,
                    symbol_size=60,
                    status="ACTIVE",
                    detail_lines=[
                        f"资产编号：{self._safe_text(host.get('host_id')) or '-'}",
                        f"资产类型：{self._safe_text(host.get('asset_type')) or '-'}",
                        f"操作系统：{self._safe_text(host.get('os_name')) or '-'}",
                        f"重要等级：{self._safe_text(host.get('critical_level')) or '-'}",
                    ],
                )
                add_link(
                    source=event_node_id,
                    target=host_node_id,
                    relation="攻击事件针对主机资产",
                    detail_lines=[f"事件 {event_id} 针对目标资产 {self._safe_text(host.get('hostname')) or '-'}"],
                )

            for rule_index, rule in enumerate(rules):
                rule_id = self._safe_text(rule.get("rule_id")) or f"derived-rule-{rule_index}"
                rule_node_id = f"rule::{rule_id}"
                add_link(
                    source=event_node_id,
                    target=rule_node_id,
                    relation="攻击事件命中规则",
                    detail_lines=[f"事件 {event_id} 关联规则 {self._safe_text(rule.get('rule_name')) or rule_id}"],
                )

        summary = self._build_summary(
            alert=alert,
            source_ip=self._select_summary_source_ip(primary_ip, primary_event),
            attack_type=self._derive_attack_type(primary_event, primary_rule, alert),
            target_asset=self._select_summary_target_asset(primary_host, primary_event),
            matched_rule=self._safe_text(primary_rule.get("rule_name")),
            bans=bans,
            message="已基于告警周边的事件、规则、资产和处置动作构建攻击链。",
        )

        return {
            "nodes": list(nodes_by_id.values()),
            "links": list(links_by_id.values()),
            "summary": summary,
        }

    def _extract_alert_evidence(self, alert: Dict[str, Any]) -> Dict[str, List[str]]:
        """
        从 Alert 属性中提取证据 ID 列表。
        """
        rule_ids = self._unique_list(
            [self._safe_text(alert.get("rule_id"))]
            + self._ensure_string_list(alert.get("related_rule_ids"))
        )
        return {
            "event_ids": self._ensure_string_list(alert.get("evidence_event_ids")),
            "session_ids": self._ensure_string_list(alert.get("evidence_session_ids")),
            "ip_ids": self._ensure_string_list(alert.get("evidence_ip_ids")),
            "host_ids": self._ensure_string_list(alert.get("evidence_host_ids")),
            "rule_ids": rule_ids,
        }

    def _build_summary(
        self,
        alert: Dict[str, Any],
        source_ip: str,
        attack_type: str,
        target_asset: str,
        matched_rule: str,
        bans: List[Dict[str, Any]],
        message: str,
    ) -> Dict[str, Any]:
        """
        构造攻击链摘要。
        """
        first_ban = bans[0] if bans else {}
        ban_status = self._safe_text(first_ban.get("current_ban_status")) or self._safe_text(first_ban.get("status"))
        if not ban_status:
            ban_status = "已阻断" if self._safe_text(alert.get("status")) == "BLOCKED" else "未联动封禁"

        return {
            "source_ip": source_ip or "-",
            "attack_type": attack_type or "-",
            "target_asset": target_asset or "-",
            "matched_rule": matched_rule or "-",
            "alert_level": self._safe_text(alert.get("severity")) or "-",
            "ban_status": ban_status,
            "ban_execution_mode": self._safe_text(first_ban.get("enforcement_mode")) or "-",
            "ban_verification_status": self._safe_text(first_ban.get("verification_status")) or "-",
            "alert_name": self._safe_text(alert.get("alert_name")) or "-",
            "message": message,
        }

    def _select_summary_source_ip(self, primary_ip: Dict[str, Any], primary_event: Dict[str, Any]) -> str:
        """
        选择摘要中展示的攻击源 IP。
        """
        return self._safe_text(primary_ip.get("ip_address")) or self._extract_first_ip(primary_event) or "-"

    def _select_summary_target_asset(self, primary_host: Dict[str, Any], primary_event: Dict[str, Any]) -> str:
        """
        选择摘要中展示的目标资产。
        """
        return (
            self._safe_text(primary_host.get("hostname"))
            or self._extract_target_host(primary_event)
            or self._derive_resource_name(primary_event, [], [primary_host] if primary_host else [])
        )

    def _derive_attack_type(self, event: Dict[str, Any], rule: Dict[str, Any], alert: Dict[str, Any]) -> str:
        """
        从事件、规则和告警信息中推断攻击类型名称。
        """
        event_type = self._safe_text(event.get("event_type")).upper()
        if event_type in EVENT_TYPE_NAME_MAPPING:
            return EVENT_TYPE_NAME_MAPPING[event_type]

        rule_name = self._safe_text(rule.get("rule_name"))
        alert_name = self._safe_text(alert.get("alert_name"))
        description = self._safe_text(alert.get("description"))
        combined_text = f"{rule_name} {alert_name} {description}"

        keyword_mapping = [
            ("注入", "SQL 注入 / 命令注入"),
            ("横向", "横向移动"),
            ("爆破", "暴力破解"),
            ("登录失败", "暴力破解 / 认证失败"),
            ("高频访问", "高频访问"),
            ("处置对象再次异常", "处置绕过 / 再次入侵"),
        ]
        for keyword, label in keyword_mapping:
            if keyword in combined_text:
                return label

        return self._safe_text(event.get("event_type")) or rule_name or alert_name or "未知攻击类型"

    def _derive_resource_name(
        self,
        event: Dict[str, Any],
        sessions: List[Dict[str, Any]],
        hosts: List[Dict[str, Any]],
    ) -> str:
        """
        推断目标资源名称。

        优先级：
        1. 事件详情中的 URL。
        2. 主机名 + 目标端口。
        3. 单独的主机名。
        4. 单独的目标端口。
        5. 事件动作或日志来源。
        """
        url_value = self._extract_url(event)
        if url_value:
            return url_value

        primary_host = hosts[0] if hosts else {}
        primary_session = sessions[0] if sessions else {}
        host_name = self._safe_text(primary_host.get("hostname")) or self._extract_target_host(event)
        dst_port = self._safe_text(primary_session.get("dst_port"))

        if host_name and dst_port:
            return f"{host_name}:{dst_port}"
        if host_name:
            return host_name
        if dst_port:
            return f"目标端口 {dst_port}"

        action = self._safe_text(event.get("action"))
        if action:
            return f"{action} 目标资源"

        return self._safe_text(event.get("log_source")) or "未知目标资源"

    def _resource_origin_description(
        self,
        event: Dict[str, Any],
        sessions: List[Dict[str, Any]],
        hosts: List[Dict[str, Any]],
    ) -> str:
        """
        描述目标资源节点的推断来源。
        """
        if self._extract_url(event):
            return "从事件详情中解析到 URL / 请求路径"
        if hosts and sessions and self._safe_text(sessions[0].get("dst_port")):
            return "由主机资产与会话目标端口组合推断"
        if hosts:
            return "由受害主机资产信息推断"
        if sessions and self._safe_text(sessions[0].get("dst_port")):
            return "由会话目标端口推断"
        return "由事件动作与日志来源推断"

    def _extract_url(self, event: Dict[str, Any]) -> str:
        """
        从事件详情中提取 URL 或请求路径。
        """
        detail_text = self._safe_text(event.get("detail"))
        if not detail_text:
            return ""

        path_candidates = re.findall(r"(/[A-Za-z0-9_\-./?=&%]+)", detail_text)
        filtered_candidates = [item for item in path_candidates if len(item) > 1 and not item.startswith("//")]
        if not filtered_candidates:
            return ""

        filtered_candidates.sort(key=len, reverse=True)
        return filtered_candidates[0]

    def _extract_first_ip(self, event: Dict[str, Any]) -> str:
        """
        从事件详情中提取首个 IPv4 地址。
        """
        detail_text = self._safe_text(event.get("detail"))
        if not detail_text:
            return ""

        ip_match = re.search(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", detail_text)
        return ip_match.group(0) if ip_match else ""

    def _extract_target_host(self, event: Dict[str, Any]) -> str:
        """
        从事件详情中提取目标主机名称。
        """
        detail_text = self._safe_text(event.get("detail"))
        if not detail_text:
            return ""

        english_match = re.search(r"\bto\s+([A-Za-z0-9._-]+)\b", detail_text)
        if english_match:
            return english_match.group(1)

        return ""

    def _dedupe_dicts(self, items: Iterable[Dict[str, Any]], key_field: str) -> List[Dict[str, Any]]:
        """
        按主键字段去重字典列表。
        """
        result_map: Dict[str, Dict[str, Any]] = {}
        for item in items or []:
            if not item:
                continue
            key_value = self._safe_text(item.get(key_field))
            if not key_value:
                continue
            if key_value not in result_map:
                result_map[key_value] = item
        return list(result_map.values())

    def _ensure_string_list(self, value: Any) -> List[str]:
        """
        将任意输入标准化为字符串列表。
        """
        if value is None:
            return []
        if isinstance(value, list):
            return self._unique_list([self._safe_text(item) for item in value if self._safe_text(item)])
        normalized_text = self._safe_text(value)
        return [normalized_text] if normalized_text else []

    def _unique_list(self, values: Iterable[str]) -> List[str]:
        """
        去重并保留顺序。
        """
        result: List[str] = []
        for item in values or []:
            if item and item not in result:
                result.append(item)
        return result

    def _safe_text(self, value: Any) -> str:
        """
        将任意值转为安全字符串。
        """
        if value is None:
            return ""
        return str(value).strip()

    def _safe_int(self, value: Any) -> int:
        """
        安全地将任意值转为整数。
        """
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return 0

    def _slugify(self, text: str) -> str:
        """
        将文本转换为适合节点 ID 的简化标识。
        """
        normalized = re.sub(r"[^A-Za-z0-9\u4e00-\u9fff]+", "-", self._safe_text(text))
        normalized = normalized.strip("-")
        return normalized or "unknown"


attack_chain_service = AttackChainService(neo4j_client)
