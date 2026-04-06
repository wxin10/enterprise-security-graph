#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
文件路径：backend/app/services/graph_service.py

文件作用：
1. 集中封装图谱相关查询逻辑。
2. 对 Neo4j 查询结果进行二次加工，转成接口更适合直接返回的结构。
3. 为当前阶段的图总览、统计、告警列表、封禁列表和用户图谱提供服务支撑。
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from app.core.errors import NotFoundError
from app.db import neo4j_client


NODE_KEY_FIELD_MAPPING = {
    "User": "user_id",
    "Host": "host_id",
    "IP": "ip_id",
    "Session": "session_id",
    "Event": "event_id",
    "Rule": "rule_id",
    "Alert": "alert_id",
    "BlockAction": "action_id",
}


NODE_NAME_FIELD_MAPPING = {
    "User": "username",
    "Host": "hostname",
    "IP": "ip_address",
    "Session": "session_id",
    "Event": "event_type",
    "Rule": "rule_name",
    "Alert": "alert_name",
    "BlockAction": "action_type",
}


class GraphService:
    """
    图谱查询服务类。

    当前阶段只实现查询类接口，因此主要使用 execute_read。
    后续如果增加封禁写入、审计写入，可继续扩展写事务方法。
    """

    def __init__(self, client):
        self.client = client

    def get_graph_overview(self, current_user: Dict[str, Any] | None = None) -> Dict[str, Any]:
        """
        获取图谱总览数据。
        """
        summary_query = """
MATCH (n)
WITH count(n) AS node_total
MATCH ()-[r]->()
WITH node_total, count(r) AS relation_total
MATCH (a:Alert)
WITH node_total, relation_total, count(a) AS alert_total
MATCH (ip:IP)
WITH node_total, relation_total, alert_total, count(CASE WHEN ip.is_blocked = true THEN 1 END) AS blocked_ip_total
MATCH (e:Event)
WITH node_total, relation_total, alert_total, blocked_ip_total, count(CASE WHEN coalesce(e.risk_score, 0) >= 80 THEN 1 END) AS high_risk_event_total
OPTIONAL MATCH (a2:Alert)-[:HIT_RULE]->(rule:Rule)
WITH node_total, relation_total, alert_total, blocked_ip_total, high_risk_event_total, count(a2) AS rule_hit_total
OPTIONAL MATCH (b:BlockAction)
WITH node_total, relation_total, alert_total, blocked_ip_total, high_risk_event_total, rule_hit_total, count(CASE WHEN b.action_status = 'SUCCESS' OR b.status = 'SUCCESS' THEN 1 END) AS block_exec_total
RETURN node_total,
       relation_total,
       alert_total,
       blocked_ip_total,
       high_risk_event_total,
       rule_hit_total,
       block_exec_total,
       CASE WHEN alert_total > 0 THEN round(node_total * 1.5 / alert_total, 1) ELSE 0.0 END AS avg_chain_nodes
"""

        latest_alerts_query = """
MATCH (a:Alert)
OPTIONAL MATCH (e:Event)-[:TRIGGERS]->(a)
OPTIONAL MATCH (a)-[:HIT_RULE]->(r:Rule)
OPTIONAL MATCH (b:BlockAction)-[:DISPOSES]->(a)
RETURN a.alert_id AS alert_id,
       a.alert_name AS alert_name,
       a.severity AS severity,
       a.status AS status,
       a.score AS score,
       a.first_seen AS first_seen,
       a.last_seen AS last_seen,
       e.event_type AS event_type,
       r.rule_name AS rule_name,
       CASE WHEN b IS NULL THEN false ELSE true END AS has_block_action
ORDER BY coalesce(a.last_seen, a.first_seen) DESC
LIMIT 5
"""

        top_risk_users_query = """
MATCH (u:User)
RETURN u.user_id AS user_id,
       u.username AS username,
       u.department AS department,
       u.risk_score AS risk_score,
       u.is_whitelisted AS is_whitelisted
ORDER BY coalesce(u.risk_score, 0) DESC, u.user_id ASC
LIMIT 5
"""

        top_risk_ips_query = """
MATCH (ip:IP)
RETURN ip.ip_id AS ip_id,
       ip.ip_address AS ip_address,
       ip.ip_type AS ip_type,
       ip.risk_score AS risk_score,
       ip.is_blocked AS is_blocked
ORDER BY coalesce(ip.risk_score, 0) DESC, ip.ip_id ASC
LIMIT 5
"""

        top_risk_hosts_query = """
MATCH (h:Host)
RETURN h.host_id AS host_id,
       h.hostname AS hostname,
       h.asset_type AS asset_type,
       h.critical_level AS critical_level,
       h.risk_score AS risk_score
ORDER BY coalesce(h.risk_score, 0) DESC, coalesce(h.critical_level, 0) DESC, h.host_id ASC
LIMIT 5
"""

        summary_records = self.client.execute_read(summary_query)
        latest_alerts = self.client.execute_read(latest_alerts_query)
        top_risk_users = self.client.execute_read(top_risk_users_query)
        top_risk_ips = self.client.execute_read(top_risk_ips_query)
        top_risk_hosts = self.client.execute_read(top_risk_hosts_query)

        summary = summary_records[0] if summary_records else {}

        overview = {
            "summary": summary,
            "latest_alerts": latest_alerts,
            "top_risk_users": top_risk_users,
            "top_risk_ips": top_risk_ips,
            "top_risk_hosts": top_risk_hosts,
        }

        if current_user:
            from app.services.governance_service import governance_service

            overview["approval_overview"] = governance_service.get_dashboard_approval_overview(current_user)
        else:
            overview["approval_overview"] = {
                "enabled": False,
                "pending_disposal_count": 0,
                "approved_today_count": 0,
                "rejected_today_count": 0,
                "recent_action_time": "",
                "recent_disposals": [],
                "recent_reviews": [],
            }

        return overview

    def get_graph_stats(self) -> Dict[str, Any]:
        """
        获取图谱统计数据。
        """
        node_stats_query = """
MATCH (n)
UNWIND labels(n) AS label
RETURN label AS category, count(*) AS total
ORDER BY label ASC
"""

        relation_stats_query = """
MATCH ()-[r]->()
RETURN type(r) AS category, count(*) AS total
ORDER BY category ASC
"""

        alert_status_query = """
MATCH (a:Alert)
RETURN a.status AS category, count(*) AS total
ORDER BY category ASC
"""

        alert_severity_query = """
MATCH (a:Alert)
RETURN a.severity AS category, count(*) AS total
ORDER BY category ASC
"""

        return {
            "node_stats": self.client.execute_read(node_stats_query),
            "relation_stats": self.client.execute_read(relation_stats_query),
            "alert_status_stats": self.client.execute_read(alert_status_query),
            "alert_severity_stats": self.client.execute_read(alert_severity_query),
        }

    def list_alerts(
        self,
        page: int,
        size: int,
        status: str | None = None,
        severity: str | None = None,
        keyword: str | None = None,
    ) -> Dict[str, Any]:
        """
        获取告警列表。
        """
        params = {
            "status": status or None,
            "severity": severity or None,
            "keyword": keyword or None,
            "skip": (page - 1) * size,
            "limit": size,
        }

        count_query = """
MATCH (a:Alert)
WHERE ($status IS NULL OR a.status = $status)
  AND ($severity IS NULL OR a.severity = $severity)
  AND ($keyword IS NULL OR a.alert_name CONTAINS $keyword OR a.description CONTAINS $keyword)
RETURN count(a) AS total
"""

        list_query = """
MATCH (a:Alert)
OPTIONAL MATCH (e:Event)-[:TRIGGERS]->(a)
OPTIONAL MATCH (a)-[:HIT_RULE]->(r:Rule)
OPTIONAL MATCH (b:BlockAction)-[:DISPOSES]->(a)
WITH a,
     collect(DISTINCT e.event_type) AS event_types,
     collect(DISTINCT r.rule_name) AS rule_names,
     collect(DISTINCT b.action_type) AS action_types
WHERE ($status IS NULL OR a.status = $status)
  AND ($severity IS NULL OR a.severity = $severity)
  AND ($keyword IS NULL OR a.alert_name CONTAINS $keyword OR a.description CONTAINS $keyword)
RETURN a.alert_id AS alert_id,
       a.alert_name AS alert_name,
       a.severity AS severity,
       a.score AS score,
       a.status AS status,
       coalesce(a.behavior_type, '') AS behavior_type,
       coalesce(a.event_count, size([item IN event_types WHERE item IS NOT NULL])) AS event_count,
       coalesce(a.can_block, false) AS can_block,
       coalesce(a.attacker_ip, '') AS attacker_ip,
       coalesce(a.target_asset, '') AS target_asset,
       coalesce(a.confidence, 0.0) AS confidence,
       a.first_seen AS first_seen,
       a.last_seen AS last_seen,
       a.description AS description,
       a.suggestion AS suggestion,
       event_types,
       rule_names,
       action_types
ORDER BY coalesce(a.last_seen, a.first_seen) DESC, a.alert_id ASC
SKIP $skip
LIMIT $limit
"""

        total_records = self.client.execute_read(count_query, params)
        items = self.client.execute_read(list_query, params)
        total = total_records[0]["total"] if total_records else 0

        return {
            "items": items,
            "pagination": {
                "page": page,
                "size": size,
                "total": total,
            },
            "filters": {
                "status": status,
                "severity": severity,
                "keyword": keyword,
            },
        }

    def list_bans(self, page: int, size: int, status: str | None = None, target_ip: str | None = None) -> Dict[str, Any]:
        """
        获取封禁动作列表。
        """
        params = {
            "status": status or None,
            "target_ip": target_ip or None,
            "skip": (page - 1) * size,
            "limit": size,
        }

        count_query = """
MATCH (b:BlockAction)
OPTIONAL MATCH (b)-[:TARGETS_IP]->(ip:IP)
WHERE ($status IS NULL OR b.status = $status)
  AND ($target_ip IS NULL OR ip.ip_address CONTAINS $target_ip)
RETURN count(DISTINCT b) AS total
"""

        list_query = """
MATCH (b:BlockAction)
OPTIONAL MATCH (b)-[:DISPOSES]->(a:Alert)
OPTIONAL MATCH (b)-[:TARGETS_IP]->(ip:IP)
WHERE ($status IS NULL OR b.status = $status)
  AND ($target_ip IS NULL OR ip.ip_address CONTAINS $target_ip)
RETURN b.action_id AS action_id,
       b.action_type AS action_type,
       b.target_type AS target_type,
       b.status AS status,
       b.executed_at AS executed_at,
       b.executor AS executor,
       b.ticket_no AS ticket_no,
       b.rollback_supported AS rollback_supported,
       b.remark AS remark,
       a.alert_id AS alert_id,
       a.alert_name AS alert_name,
       a.severity AS severity,
       ip.ip_id AS ip_id,
       ip.ip_address AS ip_address,
       ip.is_blocked AS is_blocked
ORDER BY coalesce(b.executed_at, '') DESC, b.action_id ASC
SKIP $skip
LIMIT $limit
"""

        total_records = self.client.execute_read(count_query, params)
        items = self.client.execute_read(list_query, params)
        total = total_records[0]["total"] if total_records else 0

        return {
            "items": items,
            "pagination": {
                "page": page,
                "size": size,
                "total": total,
            },
            "filters": {
                "status": status,
                "target_ip": target_ip,
            },
        }

    def get_user_graph(self, user_id: str) -> Dict[str, Any]:
        """
        获取指定用户的图谱详情。
        """
        summary_query = """
MATCH (u:User {user_id: $user_id})
OPTIONAL MATCH (u)-[:INITIATES]->(s:Session)
OPTIONAL MATCH (s)-[:GENERATES]->(e:Event)
OPTIONAL MATCH (e)-[:TRIGGERS]->(a:Alert)
RETURN u.user_id AS user_id,
       u.username AS username,
       u.display_name AS display_name,
       u.department AS department,
       u.role AS role,
       u.privilege_level AS privilege_level,
       u.status AS status,
       u.is_whitelisted AS is_whitelisted,
       u.risk_score AS risk_score,
       count(DISTINCT s) AS session_count,
       count(DISTINCT e) AS event_count,
       count(DISTINCT a) AS alert_count,
       max(a.score) AS max_alert_score
"""

        graph_query = """
MATCH (u:User {user_id: $user_id})
OPTIONAL MATCH (u)-[r1:INITIATES]->(s:Session)
OPTIONAL MATCH (s)-[r2:USES_SOURCE_IP]->(ip:IP)
OPTIONAL MATCH (s)-[r3:ACCESSES]->(h:Host)
OPTIONAL MATCH (s)-[r4:GENERATES]->(e:Event)
OPTIONAL MATCH (e)-[r5:TRIGGERS]->(a:Alert)
OPTIONAL MATCH (a)-[r6:HIT_RULE]->(rule:Rule)
OPTIONAL MATCH (b:BlockAction)-[r7:DISPOSES]->(a)
OPTIONAL MATCH (b)-[r8:TARGETS_IP]->(target_ip:IP)
RETURN u, r1, s, r2, ip, r3, h, r4, e, r5, a, r6, rule, r7, b, r8, target_ip
"""

        summary_records = self.client.execute_read(summary_query, {"user_id": user_id})
        if not summary_records or summary_records[0]["user_id"] is None:
            raise NotFoundError(f"未找到用户 {user_id} 对应的图谱数据")

        graph_records = self.client.execute_read(graph_query, {"user_id": user_id})
        nodes, edges = self._build_graph_payload(graph_records)

        return {
            "summary": summary_records[0],
            "graph": {
                "nodes": nodes,
                "edges": edges,
            },
        }

    def _build_graph_payload(self, records: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        将 Neo4j 查询结果转换为图谱接口通用结构。
        """
        node_map: Dict[str, Dict[str, Any]] = {}
        edge_map: Dict[str, Dict[str, Any]] = {}

        for record in records:
            for node_key in ["u", "s", "ip", "h", "e", "a", "rule", "b", "target_ip"]:
                self._add_node(node_map, record.get(node_key))

            self._add_edge(edge_map, record.get("r1"), record.get("u"), record.get("s"))
            self._add_edge(edge_map, record.get("r2"), record.get("s"), record.get("ip"))
            self._add_edge(edge_map, record.get("r3"), record.get("s"), record.get("h"))
            self._add_edge(edge_map, record.get("r4"), record.get("s"), record.get("e"))
            self._add_edge(edge_map, record.get("r5"), record.get("e"), record.get("a"))
            self._add_edge(edge_map, record.get("r6"), record.get("a"), record.get("rule"))
            self._add_edge(edge_map, record.get("r7"), record.get("b"), record.get("a"))
            self._add_edge(edge_map, record.get("r8"), record.get("b"), record.get("target_ip"))

        return list(node_map.values()), list(edge_map.values())

    def _add_node(self, node_map: Dict[str, Dict[str, Any]], node: Any) -> None:
        """
        向图谱节点集合中加入节点。
        """
        if node is None:
            return

        label, node_id = self._resolve_node_identity(node)
        if not label or not node_id:
            return

        graph_node_id = f"{label}:{node_id}"
        if graph_node_id in node_map:
            return

        properties = dict(node)
        name_field = NODE_NAME_FIELD_MAPPING.get(label)
        node_map[graph_node_id] = {
            "id": graph_node_id,
            "label": label,
            "name": properties.get(name_field) if name_field else node_id,
            "properties": properties,
        }

    def _add_edge(self, edge_map: Dict[str, Dict[str, Any]], relation: Any, start_node: Any, end_node: Any) -> None:
        """
        向图谱边集合中加入边。
        """
        if relation is None or start_node is None or end_node is None:
            return

        start_label, start_id = self._resolve_node_identity(start_node)
        end_label, end_id = self._resolve_node_identity(end_node)

        if not start_label or not start_id or not end_label or not end_id:
            return

        source = f"{start_label}:{start_id}"
        target = f"{end_label}:{end_id}"
        relation_type = relation.type
        edge_id = f"{source}->{relation_type}->{target}"

        if edge_id in edge_map:
            return

        edge_map[edge_id] = {
            "id": edge_id,
            "source": source,
            "target": target,
            "type": relation_type,
            "properties": dict(relation),
        }

    def _resolve_node_identity(self, node: Any) -> Tuple[str | None, str | None]:
        """
        解析 Neo4j 节点的业务主键。
        """
        if node is None:
            return None, None

        labels = list(node.labels)
        if not labels:
            return None, None

        label = labels[0]
        key_field = NODE_KEY_FIELD_MAPPING.get(label)
        if not key_field:
            return label, str(getattr(node, "element_id", "unknown"))

        return label, str(node.get(key_field))


graph_service = GraphService(neo4j_client)
