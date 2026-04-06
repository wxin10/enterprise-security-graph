#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
文件路径：backend/app/services/ban_service.py

文件作用：
1. 统一封装封禁目标的当前状态管理、历史动作审计、真实执行与规则校验逻辑。
2. 在不重构现有图模型的前提下，为 BlockAction / IP / Alert 同步写入最新封禁状态与执行状态。
3. 对旧数据做兼容处理，保证缺少 history / release / enforcement 字段的样例记录也能稳定展示。

设计原则：
1. “当前状态”和“动作历史”严格分离：current_ban_status 表示当前状态，history_actions_json 表示审计历史。
2. “业务状态”和“执行状态”严格分离：即使业务状态已切到 BLOCKED，真实规则也可能下发失败，此时由 enforcement_status 表达。
3. 所有真实执行细节都下沉到 firewall_service，ban_service 只负责编排业务流程与图数据库同步。
"""

from __future__ import annotations

import ipaddress
import json
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

from flask import current_app

from app.core.errors import NotFoundError, ValidationError
from app.db import neo4j_client
from app.middleware import add_ip_to_blocklist, query_blocked_ip, remove_ip_from_blocklist
from app.services.firewall_service import firewall_service


class BanService:
    """
    封禁与放行服务。

    当前支持的核心能力：
    1. 获取封禁列表与详情。
    2. 已封禁 -> 放行。
    3. 已放行 -> 重新封禁。
    4. 对当前规则执行状态做真实校验。
    5. 把“当前状态 + 最近动作 + 历史动作 + 真实执行结果”统一返回给前端。
    """

    BLOCKED_STATUS = "BLOCKED"
    RELEASED_STATUS = "RELEASED"
    MODE_WEB_BLOCKLIST = "WEB_BLOCKLIST"
    BACKEND_WEB_BLOCKLIST = "WEB_BLOCKLIST"

    ACTIVE_BLOCK_STATUS_SET = {"SUCCESS", "DONE", "EXECUTED", "BLOCKED", "ACTIVE"}
    RELEASED_STATUS_SET = {"RELEASED", "UNBLOCKED", "ROLLED_BACK", "RESOLVED"}
    FAILED_STATUS_SET = {"FAILED"}
    PENDING_STATUS_SET = {"PENDING", "WAITING", "QUEUED"}

    def __init__(self, client):
        self.client = client

    def list_bans(
        self,
        page: int,
        size: int,
        status: Optional[str] = None,
        target_ip: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        获取封禁列表。

        返回结构中额外补充 enforcement_profile，供前端页面展示当前是模拟执行模式还是真实执行模式。
        """
        normalized_status = self._normalize_text(status).upper() or None
        normalized_target_ip = self._normalize_text(target_ip) or None

        params = {
            "status": normalized_status,
            "target_ip": normalized_target_ip,
            "skip": (page - 1) * size,
            "limit": size,
        }

        count_query = """
MATCH (b:BlockAction)
OPTIONAL MATCH (b)-[:TARGETS_IP]->(ip:IP)
WHERE (
        $status IS NULL
        OR toUpper(coalesce(b.status, '')) = $status
        OR toUpper(coalesce(b.current_ban_status, '')) = $status
        OR ($status = 'BLOCKED' AND coalesce(ip.is_blocked, false) = true)
        OR (
            $status = 'RELEASED'
            AND (
                coalesce(b.released_at, '') <> ''
                OR toUpper(coalesce(b.current_ban_status, '')) = 'RELEASED'
                OR coalesce(ip.is_blocked, true) = false
            )
        )
      )
  AND ($target_ip IS NULL OR coalesce(ip.ip_address, '') CONTAINS $target_ip)
RETURN count(DISTINCT b) AS total
"""

        list_query = """
MATCH (b:BlockAction)
OPTIONAL MATCH (b)-[:DISPOSES]->(a:Alert)
OPTIONAL MATCH (b)-[:TARGETS_IP]->(ip:IP)
WHERE (
        $status IS NULL
        OR toUpper(coalesce(b.status, '')) = $status
        OR toUpper(coalesce(b.current_ban_status, '')) = $status
        OR ($status = 'BLOCKED' AND coalesce(ip.is_blocked, false) = true)
        OR (
            $status = 'RELEASED'
            AND (
                coalesce(b.released_at, '') <> ''
                OR toUpper(coalesce(b.current_ban_status, '')) = 'RELEASED'
                OR coalesce(ip.is_blocked, true) = false
            )
        )
      )
  AND ($target_ip IS NULL OR coalesce(ip.ip_address, '') CONTAINS $target_ip)
RETURN properties(b) AS ban,
       properties(a) AS alert,
       properties(ip) AS ip
ORDER BY coalesce(b.updated_at, b.executed_at, '') DESC, b.action_id ASC
SKIP $skip
LIMIT $limit
"""

        total_records = self.client.execute_read(count_query, params)
        raw_items = self.client.execute_read(list_query, params)
        total = total_records[0]["total"] if total_records else 0

        approval_linkage_lookup = self._build_approval_linkage_lookup()
        items = [self._build_ban_item(item, approval_linkage_lookup=approval_linkage_lookup) for item in raw_items]

        return {
            "items": items,
            "pagination": {
                "page": page,
                "size": size,
                "total": total,
            },
            "filters": {
                "status": normalized_status,
                "target_ip": normalized_target_ip,
            },
            "enforcement_profile": self._get_enforcement_profile(),
        }

    def get_ban_detail(self, ban_id: str) -> Dict[str, Any]:
        """
        获取单条封禁记录详情。
        """
        record = self._fetch_ban_context(ban_id)
        if not record:
            raise NotFoundError(f"未找到封禁记录 {ban_id}")

        approval_linkage_lookup = self._build_approval_linkage_lookup()
        return self._build_ban_item(record, approval_linkage_lookup=approval_linkage_lookup)

    def unban(self, ban_id: str, release_reason: str, released_by: str) -> Dict[str, Any]:
        """
        从 BLOCKED 切换为 RELEASED。
        """
        return self._switch_ban_status(
            ban_id=ban_id,
            target_status=self.RELEASED_STATUS,
            latest_action_type="MANUAL_UNBLOCK_IP",
            action_reason=release_reason,
            action_operator=released_by,
            default_reason="人工复核后确认放行",
        )

    def reblock(self, ban_id: str, block_reason: str, blocked_by: str) -> Dict[str, Any]:
        """
        从 RELEASED 切回 BLOCKED。
        """
        return self._switch_ban_status(
            ban_id=ban_id,
            target_status=self.BLOCKED_STATUS,
            latest_action_type="MANUAL_BLOCK_IP",
            action_reason=block_reason,
            action_operator=blocked_by,
            default_reason="人工复核后重新封禁",
        )

    def verify(self, ban_id: str) -> Dict[str, Any]:
        """
        校验当前封禁记录的真实执行状态。
        """
        current_item = self.get_ban_detail(ban_id)
        self._ensure_supported_ip_target(current_item)

        enforcement_result = self._verify_current_state(current_item)
        self._persist_enforcement_state(
            ban_id=ban_id,
            current_status=current_item["current_ban_status"],
            enforcement_result=enforcement_result,
        )

        latest_item = self.get_ban_detail(ban_id)
        return {
            "item": latest_item,
            "enforcement": enforcement_result,
            "message": enforcement_result.get("message") or "规则校验完成",
        }

    def block_ip(
        self,
        target_ip: str,
        reason: str,
        *,
        source: str = "automatic",
        attack_type: str = "",
        risk_score: int = 0,
        operator: str = "security_console",
        source_type: str = "",
        event_count: int = 1,
        confidence: float = 0.95,
        can_block: bool = True,
    ) -> Dict[str, Any]:
        """
        直接按目标 IP 创建或更新主机级封禁记录，并立即执行真实封禁。

        设计说明：
        1. 这是“日志原地读取 -> 最小分析 -> 直接主机级封禁”的核心入口。
        2. 与原有 ban_id 驱动的放行 / 重新封禁能力兼容：这里会为同一个 IP 生成稳定 action_id。
        3. 当目标当前已处于 BLOCKED 时，直接返回幂等结果，不重复创建记录。
        """
        normalized_ip = self._validate_target_ip(target_ip)
        action_id = self._build_direct_action_id(normalized_ip)

        existing_record = self._fetch_ban_context(action_id)
        if existing_record:
            current_item = self._build_ban_item(existing_record)
            current_status = self._normalize_text(current_item.get("current_ban_status")).upper()
            if current_status == self.BLOCKED_STATUS:
                return {
                    "already_in_target_status": True,
                    "item": current_item,
                    "message": "目标 IP 当前已处于主机级封禁状态，无需重复执行",
                }
            history_actions = list(current_item.get("history_actions") or [])
        else:
            history_actions = []

        action_at = self._build_local_timestamp()
        normalized_reason = self._normalize_text(reason) or "检测到高危攻击行为，自动执行主机级封禁"
        normalized_source = self._normalize_text(source).lower() or "automatic"
        normalized_operator = self._normalize_text(operator) or (
            "behavior_engine" if normalized_source == "automatic" else "security_console"
        )
        normalized_attack_type = self._normalize_text(attack_type).upper()
        normalized_source_type = self._normalize_text(source_type).lower()
        normalized_event_count = max(1, self._safe_int(event_count, 1))
        normalized_risk_score = max(0, self._safe_int(risk_score, 0))
        normalized_confidence = max(0.0, min(1.0, self._safe_float(confidence)))
        latest_action_type = "AUTO_BLOCK_IP" if normalized_source == "automatic" else "MANUAL_BLOCK_IP"

        history_actions.append(
            {
                "sequence": len(history_actions) + 1,
                "action_type": latest_action_type,
                "from_status": self.RELEASED_STATUS if existing_record else "NONE",
                "to_status": self.BLOCKED_STATUS,
                "operated_at": action_at,
                "operated_by": normalized_operator,
                "reason": normalized_reason,
                "origin": normalized_source.upper(),
            }
        )

        history_actions = self._normalize_history_actions(history_actions)
        history_actions_json = json.dumps(history_actions, ensure_ascii=False)
        history_summary = self._build_history_summary(history_actions)
        block_count = self._count_status_transitions(history_actions, self.BLOCKED_STATUS)
        release_count = self._count_status_transitions(history_actions, self.RELEASED_STATUS)
        enforcement_profile = self._get_enforcement_profile()
        try:
            self.client.execute_write(
                self._build_direct_block_upsert_query(),
                {
                    "action_id": action_id,
                    "target_ip": normalized_ip,
                    "ip_id": self._build_generated_ip_id(normalized_ip),
                    "target_status": self.BLOCKED_STATUS,
                    "action_type": "BLOCK_IP",
                    "latest_action_type": latest_action_type,
                    "action_at": action_at,
                    "action_by": normalized_operator,
                    "action_reason": normalized_reason,
                    "block_source": normalized_source,
                    "behavior_type": normalized_attack_type,
                    "source_type": normalized_source_type,
                    "risk_score": normalized_risk_score,
                    "confidence": normalized_confidence,
                    "event_count": normalized_event_count,
                    "can_block": bool(can_block),
                    "history_actions_json": history_actions_json,
                    "history_summary": history_summary,
                    "history_action_count": len(history_actions),
                    "block_count": block_count,
                    "release_count": release_count,
                    "enforcement_mode": enforcement_profile["mode"],
                    "enforcement_backend": enforcement_profile["backend"],
                },
            )

            latest_item = self.get_ban_detail(action_id)
            enforcement_result = self._enforce_current_state(latest_item)
            self._persist_enforcement_state(
                ban_id=action_id,
                current_status=self.BLOCKED_STATUS,
                enforcement_result=enforcement_result,
            )

            latest_item = self.get_ban_detail(action_id)
            return {
                "already_in_target_status": False,
                "item": latest_item,
                "enforcement": enforcement_result,
                "message": enforcement_result.get("message") or "主机级封禁执行完成",
            }
        except Exception as exc:
            enforcement_result = self._enforce_direct_without_persistence(
                action_id=action_id,
                target_ip=normalized_ip,
                current_status=self.BLOCKED_STATUS,
                action_operator=normalized_operator,
                action_reason=normalized_reason,
            )
            fallback_item = self._build_direct_fallback_item(
                action_id=action_id,
                target_ip=normalized_ip,
                current_status=self.BLOCKED_STATUS,
                block_source=normalized_source,
                behavior_type=normalized_attack_type,
                risk_score=normalized_risk_score,
                action_operator=normalized_operator,
                action_reason=normalized_reason,
                action_at=action_at,
                enforcement_result=enforcement_result,
                persistence_warning=f"Neo4j 不可用，已退化为仅执行主机级封禁动作：{exc}",
            )
            return {
                "already_in_target_status": False,
                "item": fallback_item,
                "enforcement": enforcement_result,
                "message": enforcement_result.get("message") or "主机级封禁执行完成（未写入图数据库）",
            }

    def unblock_ip(
        self,
        target_ip: str,
        reason: str,
        *,
        source: str = "manual",
        operator: str = "security_console",
    ) -> Dict[str, Any]:
        """
        直接按目标 IP 放行。

        说明：
        1. 该方法是现有 ban_id 放行接口的补充封装，便于后续做“按 IP 直接放行”。
        2. 当前仍复用统一的状态切换与真实执行逻辑，不另起一套流程。
        """
        normalized_ip = self._validate_target_ip(target_ip)
        action_id = self._build_direct_action_id(normalized_ip)
        latest_action_type = "AUTO_UNBLOCK_IP" if self._normalize_text(source).lower() == "automatic" else "MANUAL_UNBLOCK_IP"
        try:
            return self._switch_ban_status(
                ban_id=action_id,
                target_status=self.RELEASED_STATUS,
                latest_action_type=latest_action_type,
                action_reason=reason,
                action_operator=operator,
                default_reason="人工确认后执行主机级放行",
            )
        except Exception as exc:
            action_at = self._build_local_timestamp()
            normalized_reason = self._normalize_text(reason) or "人工确认后执行主机级放行"
            normalized_operator = self._normalize_text(operator) or "security_console"
            enforcement_result = self._enforce_direct_without_persistence(
                action_id=action_id,
                target_ip=normalized_ip,
                current_status=self.RELEASED_STATUS,
                action_operator=normalized_operator,
                action_reason=normalized_reason,
            )
            fallback_item = self._build_direct_fallback_item(
                action_id=action_id,
                target_ip=normalized_ip,
                current_status=self.RELEASED_STATUS,
                block_source=self._normalize_text(source).lower() or "manual",
                behavior_type="",
                risk_score=0,
                action_operator=normalized_operator,
                action_reason=normalized_reason,
                action_at=action_at,
                enforcement_result=enforcement_result,
                persistence_warning=f"Neo4j 不可用，已退化为仅执行主机级放行动作：{exc}",
            )
            return {
                "already_in_target_status": False,
                "item": fallback_item,
                "enforcement": enforcement_result,
                "message": enforcement_result.get("message") or "主机级放行执行完成（未写入图数据库）",
            }

    def verify_block(self, target_ip: str) -> Dict[str, Any]:
        """
        直接按目标 IP 校验当前封禁规则是否生效。
        """
        normalized_ip = self._validate_target_ip(target_ip)
        action_id = self._build_direct_action_id(normalized_ip)
        try:
            return self.verify(action_id)
        except Exception:
            return {
                "item": self._build_direct_fallback_item(
                    action_id=action_id,
                    target_ip=normalized_ip,
                    current_status=self.BLOCKED_STATUS,
                    block_source="automatic",
                    behavior_type="",
                    risk_score=0,
                    action_operator="security_console",
                    action_reason="直接校验主机级阻断状态",
                    action_at=self._build_local_timestamp(),
                    enforcement_result=self._verify_direct_without_persistence(
                        action_id=action_id,
                        target_ip=normalized_ip,
                        current_status=self.BLOCKED_STATUS,
                    ),
                    persistence_warning="Neo4j 不可用，当前校验结果来自直接执行器",
                ),
                "enforcement": self._verify_direct_without_persistence(
                    action_id=action_id,
                    target_ip=normalized_ip,
                    current_status=self.BLOCKED_STATUS,
                ),
                "message": "直接校验完成（未依赖图数据库）",
            }

    def _switch_ban_status(
        self,
        ban_id: str,
        target_status: str,
        latest_action_type: str,
        action_reason: str,
        action_operator: str,
        default_reason: str,
    ) -> Dict[str, Any]:
        """
        执行统一的状态切换逻辑。

        先更新业务状态，再执行宿主机规则下发或移除，最后把执行结果同步写回图数据库。
        """
        record = self._fetch_ban_context(ban_id)
        if not record:
            raise NotFoundError(f"未找到封禁记录 {ban_id}")

        current_item = self._build_ban_item(record)
        self._ensure_supported_ip_target(current_item)

        current_status = self._normalize_text(current_item.get("current_ban_status")).upper()
        if current_status not in {self.BLOCKED_STATUS, self.RELEASED_STATUS}:
            raise ValidationError(f"当前记录状态为 {current_status or 'UNKNOWN'}，暂不支持切换")

        if current_status == target_status:
            return {
                "already_in_target_status": True,
                "item": current_item,
                "message": self._build_idempotent_message(target_status),
            }

        action_at = self._build_local_timestamp()
        normalized_reason = self._normalize_text(action_reason) or default_reason
        normalized_operator = self._normalize_text(action_operator) or "security_console"

        history_actions = list(current_item.get("history_actions") or [])
        history_actions.append(
            {
                "sequence": len(history_actions) + 1,
                "action_type": latest_action_type,
                "from_status": current_status,
                "to_status": target_status,
                "operated_at": action_at,
                "operated_by": normalized_operator,
                "reason": normalized_reason,
                "origin": "MANUAL",
            }
        )

        history_actions = self._normalize_history_actions(history_actions)
        history_actions_json = json.dumps(history_actions, ensure_ascii=False)
        history_summary = self._build_history_summary(history_actions)
        block_count = self._count_status_transitions(history_actions, self.BLOCKED_STATUS)
        release_count = self._count_status_transitions(history_actions, self.RELEASED_STATUS)

        self.client.execute_write(
            self._build_switch_query(),
            {
                "action_id": ban_id,
                "target_status": target_status,
                "latest_action_type": latest_action_type,
                "action_at": action_at,
                "action_by": normalized_operator,
                "action_reason": normalized_reason,
                "history_actions_json": history_actions_json,
                "history_summary": history_summary,
                "history_action_count": len(history_actions),
                "block_count": block_count,
                "release_count": release_count,
            },
        )

        latest_item = self.get_ban_detail(ban_id)
        enforcement_result = self._enforce_current_state(latest_item)
        self._persist_enforcement_state(
            ban_id=ban_id,
            current_status=target_status,
            enforcement_result=enforcement_result,
        )

        latest_item = self.get_ban_detail(ban_id)
        return {
            "already_in_target_status": False,
            "item": latest_item,
            "enforcement": enforcement_result,
            "message": self._build_success_message(target_status, enforcement_result),
        }

    def _ensure_supported_ip_target(self, current_item: Dict[str, Any]) -> None:
        """
        当前最小可运行版本仅对 IP 目标做真实执行。
        """
        if self._normalize_text(current_item.get("target_type")).upper() != "IP":
            raise ValidationError("当前最小可运行版本仅支持 IP 类型封禁记录的状态切换与真实执行")

        target_ip = self._normalize_text(current_item.get("ip_address"))
        if not target_ip:
            raise ValidationError("当前封禁记录缺少目标 IP，无法执行真实封禁或校验")

        self._validate_target_ip(target_ip)

    def _enforce_current_state(self, current_item: Dict[str, Any]) -> Dict[str, Any]:
        """
        按当前业务状态触发真实执行。
        """
        current_status = self._normalize_text(current_item.get("current_ban_status")).upper()
        action_id = self._normalize_text(current_item.get("action_id"))
        target_ip = self._normalize_text(current_item.get("ip_address"))

        if self._is_web_blocklist_mode():
            return self._enforce_web_blocklist(
                action_id=action_id,
                target_ip=target_ip,
                current_status=current_status,
                current_item=current_item,
            )

        if current_status == self.BLOCKED_STATUS:
            return firewall_service.apply_block(action_id, target_ip)
        if current_status == self.RELEASED_STATUS:
            return firewall_service.remove_block(action_id, target_ip)

        raise ValidationError(f"当前状态 {current_status or 'UNKNOWN'} 暂不支持执行宿主机规则")

    def _verify_current_state(self, current_item: Dict[str, Any]) -> Dict[str, Any]:
        """
        根据当前状态执行规则校验。
        """
        current_status = self._normalize_text(current_item.get("current_ban_status")).upper()
        action_id = self._normalize_text(current_item.get("action_id"))
        target_ip = self._normalize_text(current_item.get("ip_address"))

        if self._is_web_blocklist_mode():
            return self._verify_web_blocklist(
                action_id=action_id,
                target_ip=target_ip,
                current_status=current_status,
            )

        return firewall_service.verify_rule(action_id, target_ip, current_status)

    def _persist_enforcement_state(
        self,
        ban_id: str,
        current_status: str,
        enforcement_result: Dict[str, Any],
    ) -> None:
        """
        把真实执行结果与校验结果写回 Neo4j。

        同步范围：
        1. BlockAction：作为主要审计对象。
        2. IP：作为当前处置目标状态展示对象。
        3. Alert：作为前端攻击链摘要的联动字段。
        """
        profile = self._get_enforcement_profile()
        local_ports = ",".join(profile.get("local_ports", []))
        verified_at = self._normalize_text(enforcement_result.get("verified_at")) or self._build_local_timestamp()

        self.client.execute_write(
            self._build_enforcement_query(),
            {
                "action_id": ban_id,
                "current_status": current_status,
                "enforcement_mode": self._normalize_text(enforcement_result.get("mode")) or profile["mode"],
                "enforcement_backend": self._normalize_text(enforcement_result.get("backend")) or profile["backend"],
                "enforcement_status": self._normalize_text(enforcement_result.get("enforcement_status")) or "PENDING",
                "enforcement_rule_name": self._normalize_text(enforcement_result.get("enforcement_rule_name")),
                "enforcement_message": self._normalize_text(enforcement_result.get("message")),
                "enforcement_executed": bool(enforcement_result.get("executed", False)),
                "enforcement_success": bool(enforcement_result.get("success", False)),
                "verification_status": self._normalize_text(enforcement_result.get("verification_status")) or "NOT_VERIFIED",
                "verified_at": verified_at,
                "verification_message": self._normalize_text(enforcement_result.get("verification_message")),
                "verification_supported": bool(enforcement_result.get("verification_supported", False)),
                "verification_attempted": bool(enforcement_result.get("verification_attempted", False)),
                "block_effective": bool(enforcement_result.get("block_effective", False)),
                "enforcement_scope_ports": local_ports,
                "updated_at": self._build_local_timestamp(),
            },
        )

    def _fetch_ban_context(self, ban_id: str) -> Optional[Dict[str, Any]]:
        """
        查询单条封禁记录的完整上下文。
        """
        query = """
MATCH (b:BlockAction {action_id: $action_id})
OPTIONAL MATCH (b)-[:DISPOSES]->(a:Alert)
OPTIONAL MATCH (b)-[:TARGETS_IP]->(ip:IP)
RETURN properties(b) AS ban,
       properties(a) AS alert,
       properties(ip) AS ip
"""
        records = self.client.execute_read(query, {"action_id": ban_id})
        return records[0] if records else None

    def _build_switch_query(self) -> str:
        """
        构造当前状态切换的统一 Cypher。
        """
        return """
MATCH (b:BlockAction {action_id: $action_id})
OPTIONAL MATCH (b)-[:TARGETS_IP]->(ip:IP)
OPTIONAL MATCH (b)-[:DISPOSES]->(a:Alert)
SET b.current_ban_status = $target_status,
    b.current_block_status = $target_status,
    b.status = $target_status,
    b.latest_action_type = $latest_action_type,
    b.latest_action_at = $action_at,
    b.latest_action_by = $action_by,
    b.latest_action_reason = $action_reason,
    b.latest_operator = $action_by,
    b.latest_reason = $action_reason,
    b.updated_at = $action_at,
    b.history_actions_json = $history_actions_json,
    b.history_summary = $history_summary,
    b.history_action_count = $history_action_count,
    b.block_count = $block_count,
    b.release_count = $release_count,
    b.blocked_at = CASE WHEN $target_status = 'BLOCKED' THEN $action_at ELSE coalesce(b.blocked_at, b.executed_at, '') END,
    b.blocked_by = CASE WHEN $target_status = 'BLOCKED' THEN $action_by ELSE coalesce(b.blocked_by, b.executor, '') END,
    b.block_reason = CASE WHEN $target_status = 'BLOCKED' THEN $action_reason ELSE coalesce(b.block_reason, '') END,
    b.released_at = CASE WHEN $target_status = 'RELEASED' THEN $action_at ELSE coalesce(b.released_at, '') END,
    b.released_by = CASE WHEN $target_status = 'RELEASED' THEN $action_by ELSE coalesce(b.released_by, '') END,
    b.release_reason = CASE WHEN $target_status = 'RELEASED' THEN $action_reason ELSE coalesce(b.release_reason, '') END
SET ip.is_blocked = CASE WHEN $target_status = 'BLOCKED' THEN true ELSE false END,
    ip.ip_block_status = $target_status,
    ip.current_block_status = $target_status,
    ip.latest_action_type = $latest_action_type,
    ip.latest_action_at = $action_at,
    ip.latest_action_by = $action_by,
    ip.latest_action_reason = $action_reason,
    ip.blocked_at = CASE WHEN $target_status = 'BLOCKED' THEN $action_at ELSE coalesce(ip.blocked_at, b.executed_at, '') END,
    ip.released_at = CASE WHEN $target_status = 'RELEASED' THEN $action_at ELSE coalesce(ip.released_at, '') END
SET a.disposition_status = $target_status,
    a.latest_action_type = $latest_action_type,
    a.latest_action_at = $action_at,
    a.latest_action_by = $action_by,
    a.latest_action_reason = $action_reason
RETURN b.action_id AS action_id
"""

    def _build_enforcement_query(self) -> str:
        """
        构造执行结果与校验结果回写 Cypher。
        """
        return """
MATCH (b:BlockAction {action_id: $action_id})
OPTIONAL MATCH (b)-[:TARGETS_IP]->(ip:IP)
OPTIONAL MATCH (b)-[:DISPOSES]->(a:Alert)
SET b.enforcement_mode = $enforcement_mode,
    b.enforcement_backend = $enforcement_backend,
    b.enforcement_status = $enforcement_status,
    b.enforcement_rule_name = $enforcement_rule_name,
    b.enforcement_message = $enforcement_message,
    b.enforcement_executed = $enforcement_executed,
    b.enforcement_success = $enforcement_success,
    b.verification_status = $verification_status,
    b.verified_at = $verified_at,
    b.verification_message = $verification_message,
    b.verification_supported = $verification_supported,
    b.verification_attempted = $verification_attempted,
    b.block_effective = $block_effective,
    b.enforcement_scope_ports = $enforcement_scope_ports,
    b.updated_at = $updated_at
SET ip.enforcement_mode = $enforcement_mode,
    ip.enforcement_backend = $enforcement_backend,
    ip.enforcement_status = $enforcement_status,
    ip.enforcement_rule_name = $enforcement_rule_name,
    ip.enforcement_message = $enforcement_message,
    ip.enforcement_executed = $enforcement_executed,
    ip.enforcement_success = $enforcement_success,
    ip.verification_status = $verification_status,
    ip.verified_at = $verified_at,
    ip.verification_message = $verification_message,
    ip.verification_supported = $verification_supported,
    ip.verification_attempted = $verification_attempted,
    ip.block_effective = $block_effective,
    ip.current_block_status = $current_status,
    ip.ip_block_status = $current_status
SET a.enforcement_mode = $enforcement_mode,
    a.enforcement_backend = $enforcement_backend,
    a.enforcement_status = $enforcement_status,
    a.enforcement_rule_name = $enforcement_rule_name,
    a.enforcement_executed = $enforcement_executed,
    a.enforcement_success = $enforcement_success,
    a.verification_status = $verification_status,
    a.verified_at = $verified_at,
    a.verification_message = $verification_message,
    a.verification_supported = $verification_supported,
    a.verification_attempted = $verification_attempted,
    a.block_effective = $block_effective
RETURN b.action_id AS action_id
"""

    def _build_ban_item(
        self,
        record: Dict[str, Any],
        *,
        approval_linkage_lookup: Optional[Dict[str, Dict[str, Dict[str, str]]]] = None,
    ) -> Dict[str, Any]:
        """
        将 Neo4j 查询结果转换为前端可直接消费的封禁记录对象。
        """
        ban = record.get("ban") or {}
        alert = record.get("alert") or {}
        ip = record.get("ip") or {}

        profile = self._get_enforcement_profile()
        action_id = self._normalize_text(ban.get("action_id"))
        ip_address = self._normalize_text(ip.get("ip_address"))
        current_status = self._resolve_current_status(ban=ban, ip=ip)
        history_actions = self._normalize_history_actions(self._build_history_actions(ban=ban))
        source_type = self._normalize_text(ban.get("source_type")) or self._normalize_text(alert.get("source_type"))

        stored_mode = self._normalize_text(ban.get("enforcement_mode")).upper()
        enforcement_mode = stored_mode if stored_mode in {"REAL", "MOCK", self.MODE_WEB_BLOCKLIST} else profile["mode"]
        enforcement_backend = self._normalize_text(ban.get("enforcement_backend")).upper() or profile["backend"]
        enforcement_rule_name = (
            self._normalize_text(ban.get("enforcement_rule_name"))
            or (self._build_enforcement_rule_name(action_id, ip_address, enforcement_mode) if action_id and ip_address else "")
        )
        enforcement_status = self._normalize_text(ban.get("enforcement_status")).upper()
        verification_status = self._normalize_text(ban.get("verification_status")).upper()

        if not enforcement_status:
            if enforcement_mode == "MOCK":
                enforcement_status = "SIMULATED" if current_status == self.BLOCKED_STATUS else "REMOVED"
            else:
                enforcement_status = "PENDING"

        if not verification_status:
            verification_status = "NOT_VERIFIED"

        verification_message = self._normalize_text(ban.get("verification_message"))
        if not verification_message:
            if enforcement_mode == "MOCK":
                verification_message = "当前为模拟执行模式，未真正校验宿主机规则"
            elif enforcement_mode == self.MODE_WEB_BLOCKLIST:
                verification_message = "尚未执行 WEB_BLOCKLIST 阻断校验"
            else:
                verification_message = "尚未执行规则校验"

        enforcement_executed = bool(ban.get("enforcement_executed", False))
        enforcement_success = bool(ban.get("enforcement_success", False))
        verification_supported = bool(ban.get("verification_supported", enforcement_mode == self.MODE_WEB_BLOCKLIST))
        verification_attempted = bool(ban.get("verification_attempted", False))
        block_effective = bool(ban.get("block_effective", False))
        if current_status == self.BLOCKED_STATUS and verification_status == "VERIFIED":
            block_effective = True
        if current_status == self.RELEASED_STATUS:
            block_effective = False

        history_summary = self._build_history_summary(history_actions)
        block_count = self._safe_int(ban.get("block_count"))
        release_count = self._safe_int(ban.get("release_count"))
        if block_count == 0:
            block_count = self._count_status_transitions(history_actions, self.BLOCKED_STATUS)
        if release_count == 0:
            release_count = self._count_status_transitions(history_actions, self.RELEASED_STATUS)

        approval_linkage = self._resolve_approval_linkage(
            action_id=action_id,
            target_ip=ip_address,
            source_type=source_type,
            approval_linkage_lookup=approval_linkage_lookup,
        )

        item = {
            "action_id": action_id,
            "action_type": self._normalize_text(ban.get("action_type")) or "BLOCK_IP",
            "block_source": self._normalize_text(ban.get("block_source")) or "manual",
            "latest_action_type": self._normalize_text(ban.get("latest_action_type")) or self._normalize_text(ban.get("action_type")) or "BLOCK_IP",
            "target_type": self._normalize_text(ban.get("target_type")) or "IP",
            "status": self._normalize_text(ban.get("status")),
            "current_ban_status": current_status,
            "current_block_status": current_status,
            "executed_at": self._normalize_text(ban.get("executed_at")),
            "executor": self._normalize_text(ban.get("executor")),
            "ticket_no": self._normalize_text(ban.get("ticket_no")),
            "rollback_supported": bool(ban.get("rollback_supported", False)),
            "remark": self._normalize_text(ban.get("remark")),
            "alert_id": self._normalize_text(alert.get("alert_id")),
            "alert_name": self._normalize_text(alert.get("alert_name")),
            "severity": self._normalize_text(alert.get("severity")),
            "ip_id": self._normalize_text(ip.get("ip_id")),
            "ip_address": ip_address,
            "ip_block_status": self._normalize_text(ip.get("ip_block_status")) or current_status,
            "is_blocked": bool(ip.get("is_blocked", current_status == self.BLOCKED_STATUS)),
            "blocked_at": self._normalize_text(ban.get("blocked_at")) or self._normalize_text(ban.get("executed_at")),
            "blocked_by": self._normalize_text(ban.get("blocked_by")) or self._normalize_text(ban.get("executor")),
            "block_reason": self._normalize_text(ban.get("block_reason")) or self._normalize_text(ban.get("remark")),
            "behavior_id": self._normalize_text(ban.get("behavior_id")) or self._normalize_text(alert.get("behavior_id")),
            "behavior_type": self._normalize_text(ban.get("behavior_type")) or self._normalize_text(alert.get("behavior_type")),
            "risk_score": self._safe_int(ban.get("risk_score"), self._safe_int(alert.get("score"))),
            "confidence": self._safe_float(ban.get("confidence")),
            "event_count": self._safe_int(ban.get("event_count"), self._safe_int(alert.get("event_count"))),
            "source_type": source_type,
            "released_at": self._normalize_text(ban.get("released_at")),
            "released_by": self._normalize_text(ban.get("released_by")),
            "release_reason": self._normalize_text(ban.get("release_reason")),
            "latest_action_at": self._normalize_text(ban.get("latest_action_at")) or self._normalize_text(ban.get("executed_at")),
            "latest_action_by": self._normalize_text(ban.get("latest_action_by")) or self._normalize_text(ban.get("executor")),
            "latest_action_reason": self._normalize_text(ban.get("latest_action_reason")) or self._normalize_text(ban.get("remark")),
            "latest_operator": self._normalize_text(ban.get("latest_operator")) or self._normalize_text(ban.get("latest_action_by")) or self._normalize_text(ban.get("executor")),
            "latest_reason": self._normalize_text(ban.get("latest_reason")) or self._normalize_text(ban.get("latest_action_reason")) or self._normalize_text(ban.get("remark")),
            "history_action_count": len(history_actions),
            "history_actions": history_actions,
            "history_actions_brief": history_actions[-3:],
            "history_summary": history_summary,
            "block_count": block_count,
            "release_count": release_count,
            "is_released": current_status == self.RELEASED_STATUS,
            "can_unban": current_status == self.BLOCKED_STATUS,
            "can_reblock": current_status == self.RELEASED_STATUS,
            "can_verify": self._normalize_text(ban.get("target_type") or "IP").upper() == "IP",
            "enforcement_mode": enforcement_mode,
            "enforcement_backend": enforcement_backend,
            "enforcement_status": enforcement_status,
            "enforcement_rule_name": enforcement_rule_name,
            "enforcement_message": self._normalize_text(ban.get("enforcement_message")),
            "enforcement_executed": enforcement_executed,
            "enforcement_success": enforcement_success,
            "verification_status": verification_status,
            "verified_at": self._normalize_text(ban.get("verified_at")),
            "verification_message": verification_message,
            "verification_supported": verification_supported,
            "verification_attempted": verification_attempted,
            "block_effective": block_effective,
            "truly_blocked": block_effective,
            "enforcement_scope_ports": self._normalize_text(ban.get("enforcement_scope_ports")) or ",".join(profile.get("local_ports", [])),
            "enforcement_scope_description": profile.get("scope_description"),
            "approval_source_label": approval_linkage["approval_source_label"],
            "approval_request_id": approval_linkage["approval_request_id"],
            "approval_reviewer_name": approval_linkage["approval_reviewer_name"],
            "approval_reviewed_at": approval_linkage["approval_reviewed_at"],
            "approval_review_comment": approval_linkage["approval_review_comment"],
            "approval_execution_status": approval_linkage["approval_execution_status"],
        }
        return item

    def _build_approval_linkage_lookup(self) -> Dict[str, Dict[str, Dict[str, str]]]:
        from app.services.governance_service import governance_service

        return governance_service.get_ban_approval_linkage_lookup()

    def _resolve_approval_linkage(
        self,
        *,
        action_id: str,
        target_ip: str,
        source_type: str,
        approval_linkage_lookup: Optional[Dict[str, Dict[str, Dict[str, str]]]] = None,
    ) -> Dict[str, str]:
        empty_linkage = {
            "approval_source_label": "",
            "approval_request_id": "",
            "approval_reviewer_name": "",
            "approval_reviewed_at": "",
            "approval_review_comment": "",
            "approval_execution_status": "",
        }
        lookup = approval_linkage_lookup or self._build_approval_linkage_lookup()
        by_action_id = lookup.get("by_action_id") or {}
        by_target_ip = lookup.get("by_target_ip") or {}

        if action_id and action_id in by_action_id:
            return dict(by_action_id[action_id])

        if self._normalize_text(source_type).lower() == "disposal_approval" and target_ip and target_ip in by_target_ip:
            return dict(by_target_ip[target_ip])

        return empty_linkage

    def _resolve_current_status(self, ban: Dict[str, Any], ip: Dict[str, Any]) -> str:
        """
        解析当前封禁状态。

        解析优先级：
        1. current_ban_status
        2. current_block_status
        3. released_at / ip.is_blocked
        4. 旧字段 status
        """
        current_ban_status = self._normalize_text(ban.get("current_ban_status")).upper()
        if current_ban_status in {self.BLOCKED_STATUS, self.RELEASED_STATUS}:
            return current_ban_status

        current_block_status = self._normalize_text(ban.get("current_block_status")).upper()
        if current_block_status in {self.BLOCKED_STATUS, self.RELEASED_STATUS}:
            return current_block_status

        if self._normalize_text(ban.get("released_at")):
            return self.RELEASED_STATUS

        if "is_blocked" in ip:
            return self.BLOCKED_STATUS if bool(ip.get("is_blocked")) else self.RELEASED_STATUS

        raw_status = self._normalize_text(ban.get("status")).upper()
        if raw_status in self.ACTIVE_BLOCK_STATUS_SET:
            return self.BLOCKED_STATUS
        if raw_status in self.RELEASED_STATUS_SET:
            return self.RELEASED_STATUS
        if raw_status in self.FAILED_STATUS_SET:
            return "FAILED"
        if raw_status in self.PENDING_STATUS_SET:
            return "PENDING"
        return self.BLOCKED_STATUS

    def _build_history_actions(self, ban: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        构造历史动作列表。

        优先使用 history_actions_json；若旧数据缺失，则由原始动作和放行字段自动补齐。
        """
        history_json = self._normalize_text(ban.get("history_actions_json"))
        if history_json:
            try:
                parsed_history = json.loads(history_json)
                if isinstance(parsed_history, list):
                    return parsed_history
            except json.JSONDecodeError:
                pass

        fallback_history: List[Dict[str, Any]] = []
        executed_at = self._normalize_text(ban.get("executed_at")) or self._build_local_timestamp()
        executor = self._normalize_text(ban.get("executor")) or "auto_engine"
        remark = self._normalize_text(ban.get("remark")) or "系统初始封禁记录"

        fallback_history.append(
            {
                "sequence": 1,
                "action_type": self._normalize_text(ban.get("action_type")) or "BLOCK_IP",
                "from_status": "NEW",
                "to_status": self.BLOCKED_STATUS,
                "operated_at": executed_at,
                "operated_by": executor,
                "reason": remark,
                "origin": "AUTO",
            }
        )

        released_at = self._normalize_text(ban.get("released_at"))
        if released_at:
            fallback_history.append(
                {
                    "sequence": 2,
                    "action_type": self._normalize_text(ban.get("latest_action_type")) or "UNBLOCK_IP",
                    "from_status": self.BLOCKED_STATUS,
                    "to_status": self.RELEASED_STATUS,
                    "operated_at": released_at,
                    "operated_by": self._normalize_text(ban.get("released_by")) or "security_console",
                    "reason": self._normalize_text(ban.get("release_reason")) or "历史放行记录",
                    "origin": "MANUAL",
                }
            )

        return fallback_history

    def _normalize_history_actions(self, history_actions: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        清洗历史动作列表，统一字段并按序号排序。
        """
        normalized_items: List[Dict[str, Any]] = []
        for index, raw_item in enumerate(history_actions, start=1):
            if not isinstance(raw_item, dict):
                continue

            normalized_items.append(
                {
                    "sequence": self._safe_int(raw_item.get("sequence")) or index,
                    "action_type": self._normalize_text(raw_item.get("action_type")) or "BLOCK_IP",
                    "from_status": self._normalize_text(raw_item.get("from_status")) or "UNKNOWN",
                    "to_status": self._normalize_text(raw_item.get("to_status")) or "UNKNOWN",
                    "operated_at": self._normalize_text(raw_item.get("operated_at")) or self._build_local_timestamp(),
                    "operated_by": self._normalize_text(raw_item.get("operated_by")) or "security_console",
                    "reason": self._normalize_text(raw_item.get("reason")),
                    "origin": self._normalize_text(raw_item.get("origin")) or "MANUAL",
                }
            )

        normalized_items.sort(key=lambda item: item["sequence"])
        return normalized_items

    def _count_status_transitions(self, history_actions: Iterable[Dict[str, Any]], target_status: str) -> int:
        """
        统计切换到某个目标状态的次数。
        """
        target = self._normalize_text(target_status).upper()
        return sum(
            1
            for item in history_actions
            if self._normalize_text(item.get("to_status")).upper() == target
        )

    def _build_history_summary(self, history_actions: Iterable[Dict[str, Any]]) -> str:
        """
        生成历史动作摘要，供表格快速展示。
        """
        readable_parts: List[str] = []
        for item in history_actions:
            action_type = self._normalize_text(item.get("action_type")).upper()
            label = {
                "BLOCK_IP": "自动封禁",
                "MANUAL_BLOCK_IP": "人工重新封禁",
                "UNBLOCK_IP": "自动放行",
                "MANUAL_UNBLOCK_IP": "人工放行",
            }.get(action_type, action_type or "动作")
            readable_parts.append(label)

        return " -> ".join(readable_parts) if readable_parts else "-"

    def _build_success_message(self, target_status: str, enforcement_result: Dict[str, Any]) -> str:
        """
        生成状态切换后的友好提示。
        """
        status_label = "已放行" if target_status == self.RELEASED_STATUS else "已重新封禁"
        verification_status = self._normalize_text(enforcement_result.get("verification_status")).upper()
        if verification_status == "VERIFIED":
            return f"{status_label}，且规则执行校验通过"
        if verification_status in {"MISSING", "FAILED"}:
            return f"{status_label}，但规则校验未通过，请关注执行状态"
        return status_label

    def _build_idempotent_message(self, target_status: str) -> str:
        """
        生成重复操作时的幂等提示。
        """
        if target_status == self.RELEASED_STATUS:
            return "当前记录已经处于已放行状态，无需重复执行放行"
        return "当前记录已经处于已封禁状态，无需重复执行重新封禁"

    def _get_enforcement_mode(self) -> str:
        """
        获取当前后端实际使用的封禁执行模式。

        说明：
        1. 这次最小版重点补齐 WEB_BLOCKLIST。
        2. 其余模式仍继续交给原有 firewall_service 处理。
        """
        return self._normalize_text(current_app.config.get("BAN_ENFORCEMENT_MODE")).upper() or "MOCK"

    def _is_web_blocklist_mode(self) -> bool:
        """
        判断当前是否处于 WEB_BLOCKLIST 真实阻断模式。
        """
        return self._get_enforcement_mode() == self.MODE_WEB_BLOCKLIST

    def _get_enforcement_profile(self) -> Dict[str, Any]:
        """
        返回当前封禁执行配置。

        设计思路：
        1. WEB_BLOCKLIST 模式由 ban_service 直接处理。
        2. MOCK / REAL 等原有模式继续沿用 firewall_service 的配置输出。
        """
        if not self._is_web_blocklist_mode():
            return firewall_service.get_enforcement_profile()

        return {
            "mode": self.MODE_WEB_BLOCKLIST,
            "backend": self.BACKEND_WEB_BLOCKLIST,
            "host_platform": "APPLICATION",
            "supports_real_execution": True,
            "rule_prefix": current_app.config.get("BAN_WEB_BLOCKLIST_RULE_PREFIX", "ESGWEB"),
            "local_ports": [],
            "scope_description": "在 Flask 请求入口按源 IP 执行应用层真实阻断",
        }

    def _build_enforcement_rule_name(self, ban_id: str, target_ip: str, enforcement_mode: str) -> str:
        """
        为不同执行模式生成可追踪的规则名。
        """
        if enforcement_mode == self.MODE_WEB_BLOCKLIST:
            prefix = current_app.config.get("BAN_WEB_BLOCKLIST_RULE_PREFIX", "ESGWEB")
            sanitized_ban_id = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in str(ban_id or "UNKNOWN"))
            sanitized_ip = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in str(target_ip or "UNKNOWN"))
            return f"{prefix}-BAN-{sanitized_ban_id}-{sanitized_ip}"

        return firewall_service.build_rule_name(ban_id, target_ip)

    def _get_blocklist_file_path(self) -> str:
        """
        获取 WEB_BLOCKLIST 存储文件路径。
        """
        return str(current_app.config.get("BAN_WEB_BLOCKLIST_FILE") or "")

    def _validate_target_ip(self, target_ip: str) -> str:
        """
        校验目标 IP 合法性，避免把非法文本写入 blocklist。
        """
        normalized_ip = self._normalize_text(target_ip)
        try:
            return str(ipaddress.ip_address(normalized_ip))
        except ValueError as exc:
            raise ValidationError(f"目标 IP 非法，无法执行封禁：{normalized_ip or 'EMPTY'}") from exc

    def _enforce_web_blocklist(
        self,
        action_id: str,
        target_ip: str,
        current_status: str,
        current_item: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        在 WEB_BLOCKLIST 模式下执行最小真实阻断。

        BLOCKED：
        1. 将目标 IP 写入 blocklist.json。
        2. 之后该 IP 再访问 Flask 服务时会在 before_request 中被 403 拒绝。

        RELEASED：
        1. 将目标 IP 从 blocklist.json 中删除。
        2. 之后该 IP 访问 Flask 服务时恢复正常。
        """
        normalized_ip = self._validate_target_ip(target_ip)
        blocklist_file = self._get_blocklist_file_path()
        rule_name = self._build_enforcement_rule_name(action_id, normalized_ip, self.MODE_WEB_BLOCKLIST)
        operator = self._normalize_text(current_item.get("latest_action_by")) or "security_console"
        reason = self._normalize_text(current_item.get("latest_action_reason")) or "封禁处置"
        executed_at = self._build_local_timestamp()

        try:
            if current_status == self.BLOCKED_STATUS:
                write_result = add_ip_to_blocklist(
                    blocklist_file,
                    normalized_ip,
                    metadata={
                        "ban_id": action_id,
                        "blocked_at": executed_at,
                        "reason": reason,
                        "operator": operator,
                    },
                )
                blocked, _ = query_blocked_ip(blocklist_file, normalized_ip)
                return {
                    "executed": True,
                    "success": blocked,
                    "mode": self.MODE_WEB_BLOCKLIST,
                    "backend": self.BACKEND_WEB_BLOCKLIST,
                    "target_ip": normalized_ip,
                    "enforcement_rule_name": rule_name,
                    "enforcement_status": "APPLIED" if blocked else "FAILED",
                    "message": "目标 IP 已写入 WEB_BLOCKLIST 并开始阻断" if blocked else "目标 IP 写入 WEB_BLOCKLIST 失败",
                    "executed_at": executed_at,
                    "verification_supported": True,
                    "verification_attempted": True,
                    "verification_status": "VERIFIED" if blocked else "FAILED",
                    "verified_at": executed_at,
                    "verification_message": "blocklist 中已存在该 IP，后续请求会被 Flask 直接拒绝" if blocked else "blocklist 校验未通过，未检测到目标 IP",
                    "rollback_supported": True,
                    "rollback_result": "",
                    "block_effective": blocked,
                    "already_existed": bool(write_result.get("existed", False)),
                    "verification_result": "VERIFIED" if blocked else "FAILED",
                }

            remove_result = remove_ip_from_blocklist(blocklist_file, normalized_ip)
            blocked, _ = query_blocked_ip(blocklist_file, normalized_ip)
            released_success = not blocked
            return {
                "executed": True,
                "success": released_success,
                "mode": self.MODE_WEB_BLOCKLIST,
                "backend": self.BACKEND_WEB_BLOCKLIST,
                "target_ip": normalized_ip,
                "enforcement_rule_name": rule_name,
                "enforcement_status": "REMOVED" if released_success else "FAILED",
                "message": "目标 IP 已从 WEB_BLOCKLIST 移除，访问将恢复正常" if released_success else "目标 IP 移除失败，仍在 WEB_BLOCKLIST 中",
                "executed_at": executed_at,
                "verification_supported": True,
                "verification_attempted": True,
                "verification_status": "VERIFIED" if released_success else "FAILED",
                "verified_at": executed_at,
                "verification_message": "未在 blocklist 中检测到该 IP，说明放行已生效" if released_success else "blocklist 中仍存在该 IP，放行未生效",
                "rollback_supported": True,
                "rollback_result": "",
                "block_effective": False,
                "already_missing": not bool(remove_result.get("existed", False)),
                "verification_result": "VERIFIED" if released_success else "FAILED",
            }
        except Exception as exc:
            return {
                "executed": False,
                "success": False,
                "mode": self.MODE_WEB_BLOCKLIST,
                "backend": self.BACKEND_WEB_BLOCKLIST,
                "target_ip": normalized_ip,
                "enforcement_rule_name": rule_name,
                "enforcement_status": "FAILED",
                "message": f"WEB_BLOCKLIST 执行失败：{exc}",
                "executed_at": executed_at,
                "verification_supported": True,
                "verification_attempted": False,
                "verification_status": "FAILED",
                "verified_at": executed_at,
                "verification_message": f"执行失败，未完成 blocklist 校验：{exc}",
                "rollback_supported": True,
                "rollback_result": "",
                "block_effective": False,
                "verification_result": "FAILED",
            }

    def _verify_web_blocklist(self, action_id: str, target_ip: str, current_status: str) -> Dict[str, Any]:
        """
        对 WEB_BLOCKLIST 当前状态做最小校验。
        """
        normalized_ip = self._validate_target_ip(target_ip)
        blocklist_file = self._get_blocklist_file_path()
        rule_name = self._build_enforcement_rule_name(action_id, normalized_ip, self.MODE_WEB_BLOCKLIST)
        verified_at = self._build_local_timestamp()
        blocked, entry = query_blocked_ip(blocklist_file, normalized_ip)

        if current_status == self.BLOCKED_STATUS:
            return {
                "executed": False,
                "success": blocked,
                "mode": self.MODE_WEB_BLOCKLIST,
                "backend": self.BACKEND_WEB_BLOCKLIST,
                "target_ip": normalized_ip,
                "enforcement_rule_name": rule_name,
                "enforcement_status": "APPLIED" if blocked else "FAILED",
                "message": "WEB_BLOCKLIST 校验通过，目标 IP 当前处于阻断状态" if blocked else "WEB_BLOCKLIST 校验失败，目标 IP 当前未处于阻断状态",
                "executed_at": "",
                "verification_supported": True,
                "verification_attempted": True,
                "verification_status": "VERIFIED" if blocked else "MISSING",
                "verified_at": verified_at,
                "verification_message": "blocklist 中已命中该 IP，后续请求会被 403 拒绝" if blocked else "blocklist 中未找到该 IP，说明当前并未真实阻断",
                "rollback_supported": True,
                "rollback_result": "",
                "block_effective": blocked,
                "verification_result": "VERIFIED" if blocked else "MISSING",
                "rule_detail": entry,
            }

        released_success = not blocked
        return {
            "executed": False,
            "success": released_success,
            "mode": self.MODE_WEB_BLOCKLIST,
            "backend": self.BACKEND_WEB_BLOCKLIST,
            "target_ip": normalized_ip,
            "enforcement_rule_name": rule_name,
            "enforcement_status": "REMOVED" if released_success else "FAILED",
            "message": "WEB_BLOCKLIST 校验通过，目标 IP 当前已放行" if released_success else "WEB_BLOCKLIST 校验失败，目标 IP 仍在阻断列表中",
            "executed_at": "",
            "verification_supported": True,
            "verification_attempted": True,
            "verification_status": "VERIFIED" if released_success else "FAILED",
            "verified_at": verified_at,
            "verification_message": "blocklist 中未命中该 IP，说明放行已生效" if released_success else "blocklist 中仍存在该 IP，说明放行未真正生效",
            "rollback_supported": True,
            "rollback_result": "",
            "block_effective": False,
            "verification_result": "VERIFIED" if released_success else "FAILED",
            "rule_detail": entry,
        }

    def _build_direct_action_id(self, target_ip: str) -> str:
        """
        为“按 IP 直接主机级封禁”生成稳定的 action_id。

        设计说明：
        1. 同一个 IP 反复被自动封禁时，沿用同一条 BlockAction 主记录。
        2. 这样列表页看到的是“当前状态 + 历史动作”，而不是无限新增重复行。
        """
        sanitized_ip = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in str(target_ip or "UNKNOWN"))
        return f"AUTO_HOST_BLOCK_{sanitized_ip}"

    def _build_generated_ip_id(self, target_ip: str) -> str:
        """
        为自动创建的 IP 节点生成稳定 ip_id。
        """
        sanitized_ip = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in str(target_ip or "UNKNOWN"))
        return f"AUTO_IP_{sanitized_ip}"

    def _build_direct_block_upsert_query(self) -> str:
        """
        构造“按 IP 直接主机级封禁”的最小写入 Cypher。

        说明：
        1. 这里不大改图模型，只最小维护 BlockAction 和 IP 的当前状态。
        2. 若该 IP 已在图中存在，则复用现有节点；若不存在，则自动创建最小节点。
        """
        return """
MERGE (ip:IP {ip_address: $target_ip})
ON CREATE SET ip.ip_id = $ip_id,
              ip.created_at = $action_at,
              ip.first_seen = $action_at
MERGE (b:BlockAction {action_id: $action_id})
ON CREATE SET b.created_at = $action_at,
              b.action_type = $action_type,
              b.target_type = 'IP'
MERGE (b)-[:TARGETS_IP]->(ip)
SET b.target_type = 'IP',
    b.target_ip = $target_ip,
    b.current_ban_status = $target_status,
    b.current_block_status = $target_status,
    b.status = $target_status,
    b.block_source = $block_source,
    b.behavior_type = $behavior_type,
    b.source_type = $source_type,
    b.risk_score = $risk_score,
    b.confidence = $confidence,
    b.event_count = $event_count,
    b.can_block = $can_block,
    b.block_reason = $action_reason,
    b.latest_action_type = $latest_action_type,
    b.latest_action_at = $action_at,
    b.latest_action_by = $action_by,
    b.latest_action_reason = $action_reason,
    b.latest_operator = $action_by,
    b.latest_reason = $action_reason,
    b.updated_at = $action_at,
    b.executed_at = $action_at,
    b.executor = $action_by,
    b.blocked_at = $action_at,
    b.blocked_by = $action_by,
    b.history_actions_json = $history_actions_json,
    b.history_summary = $history_summary,
    b.history_action_count = $history_action_count,
    b.block_count = $block_count,
    b.release_count = $release_count,
    b.enforcement_mode = $enforcement_mode,
    b.enforcement_backend = $enforcement_backend
SET ip.is_blocked = true,
    ip.ip_block_status = $target_status,
    ip.current_block_status = $target_status,
    ip.latest_action_type = $latest_action_type,
    ip.latest_action_at = $action_at,
    ip.latest_action_by = $action_by,
    ip.latest_action_reason = $action_reason,
    ip.blocked_at = $action_at
RETURN b.action_id AS action_id
"""

    def _normalize_text(self, value: Any) -> str:
        """
        统一规范化字符串。
        """
        return str(value or "").strip()

    def _safe_int(self, value: Any, default_value: int = 0) -> int:
        """
        安全转换整数。
        """
        try:
            return int(value)
        except (TypeError, ValueError):
            return default_value

    def _safe_float(self, value: Any) -> float:
        """
        安全转换浮点数。
        """
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    def _build_local_timestamp(self) -> str:
        """
        构造本地时区时间字符串。
        """
        return datetime.now().astimezone().isoformat(timespec="seconds")


ban_service = BanService(neo4j_client)
