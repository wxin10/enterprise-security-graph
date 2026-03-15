#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
文件路径：backend/app/services/ban_service.py

文件作用：
1. 将封禁管理从“单次动作展示”升级为“当前状态管理 + 历史动作审计”模式。
2. 统一处理封禁记录查询、人工放行、人工重新封禁以及 Neo4j 状态同步。
3. 兼容旧数据缺少 release/history 字段的情况，避免历史样例因为字段缺失而报错。

设计说明：
1. 当前最小可运行版本仍然复用既有 BlockAction 节点，不额外引入新的复杂审计子图。
2. “当前状态”通过 current_ban_status / current_block_status 表达，“历史动作”通过 history_actions_json 记录。
3. 每次状态切换都会追加一条历史动作，并同步更新 IP、Alert 的当前状态与最近操作字段。
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

from app.core.errors import NotFoundError, ValidationError
from app.db import neo4j_client


class BanService:
    """
    封禁与放行服务。

    当前支持的状态切换：
    1. BLOCKED -> RELEASED：人工放行 / 解封。
    2. RELEASED -> BLOCKED：人工重新封禁。
    3. 相同状态重复操作采用幂等处理，返回友好提示而不是 500。
    """

    BLOCKED_STATUS = "BLOCKED"
    RELEASED_STATUS = "RELEASED"

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
        获取封禁记录列表。

        兼容性说明：
        1. 旧数据没有 current_ban_status/history_actions_json 时，会在服务层自动推断并补齐展示字段。
        2. status 查询既兼容旧字段 status，也兼容 current_ban_status/current_block_status。
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

        items = [self._build_ban_item(item) for item in raw_items]

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
        }

    def get_ban_detail(self, ban_id: str) -> Dict[str, Any]:
        """
        获取单条封禁记录详情。
        """
        record = self._fetch_ban_context(ban_id)
        if not record:
            raise NotFoundError(f"未找到封禁记录 {ban_id}")

        return self._build_ban_item(record)

    def unban(self, ban_id: str, release_reason: str, released_by: str) -> Dict[str, Any]:
        """
        从 BLOCKED 切换到 RELEASED。
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
        从 RELEASED 切换回 BLOCKED。
        """
        return self._switch_ban_status(
            ban_id=ban_id,
            target_status=self.BLOCKED_STATUS,
            latest_action_type="MANUAL_BLOCK_IP",
            action_reason=block_reason,
            action_operator=blocked_by,
            default_reason="人工复核后重新封禁",
        )

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

        说明：
        1. 当前状态与最近动作分离，当前状态写 current_ban_status，最近动作写 latest_action_*。
        2. 每次切换都会向 history_actions_json 追加一条审计记录。
        """
        record = self._fetch_ban_context(ban_id)
        if not record:
            raise NotFoundError(f"未找到封禁记录 {ban_id}")

        current_item = self._build_ban_item(record)
        if self._normalize_text(current_item.get("target_type")).upper() != "IP":
            raise ValidationError("当前最小可运行版本仅支持 IP 类型封禁记录的状态切换")

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
        return {
            "already_in_target_status": False,
            "item": latest_item,
            "message": self._build_success_message(target_status),
        }

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
    b.history_actions_json = $history_actions_json,
    b.history_summary = $history_summary,
    b.history_action_count = $history_action_count,
    b.block_count = $block_count,
    b.release_count = $release_count,
    b.updated_at = $action_at,
    b.is_released = CASE WHEN $target_status = 'RELEASED' THEN true ELSE false END,
    b.first_blocked_at = coalesce(b.first_blocked_at, b.executed_at, b.blocked_at, $action_at),
    b.blocked_at = CASE WHEN $target_status = 'BLOCKED' THEN $action_at ELSE coalesce(b.blocked_at, b.executed_at) END,
    b.blocked_by = CASE WHEN $target_status = 'BLOCKED' THEN $action_by ELSE b.blocked_by END,
    b.block_reason = CASE WHEN $target_status = 'BLOCKED' THEN $action_reason ELSE b.block_reason END,
    b.released_at = CASE WHEN $target_status = 'RELEASED' THEN $action_at ELSE b.released_at END,
    b.released_by = CASE WHEN $target_status = 'RELEASED' THEN $action_by ELSE b.released_by END,
    b.release_reason = CASE WHEN $target_status = 'RELEASED' THEN $action_reason ELSE b.release_reason END
FOREACH (_ IN CASE WHEN ip IS NULL THEN [] ELSE [1] END |
    SET ip.is_blocked = CASE WHEN $target_status = 'BLOCKED' THEN true ELSE false END,
        ip.ip_block_status = $target_status,
        ip.current_block_status = $target_status,
        ip.latest_action_type = $latest_action_type,
        ip.latest_action_at = $action_at,
        ip.latest_action_by = $action_by,
        ip.latest_action_reason = $action_reason,
        ip.last_status_change_at = $action_at,
        ip.last_blocked_at = CASE WHEN $target_status = 'BLOCKED' THEN $action_at ELSE ip.last_blocked_at END,
        ip.last_released_at = CASE WHEN $target_status = 'RELEASED' THEN $action_at ELSE ip.last_released_at END,
        ip.blocked_at = CASE WHEN $target_status = 'BLOCKED' THEN $action_at ELSE coalesce(ip.blocked_at, b.executed_at) END,
        ip.blocked_by = CASE WHEN $target_status = 'BLOCKED' THEN $action_by ELSE ip.blocked_by END,
        ip.block_reason = CASE WHEN $target_status = 'BLOCKED' THEN $action_reason ELSE ip.block_reason END,
        ip.released_at = CASE WHEN $target_status = 'RELEASED' THEN $action_at ELSE ip.released_at END,
        ip.released_by = CASE WHEN $target_status = 'RELEASED' THEN $action_by ELSE ip.released_by END,
        ip.release_reason = CASE WHEN $target_status = 'RELEASED' THEN $action_reason ELSE ip.release_reason END
)
FOREACH (_ IN CASE WHEN a IS NULL THEN [] ELSE [1] END |
    SET a.disposition_status = $target_status,
        a.latest_action_type = $latest_action_type,
        a.latest_action_at = $action_at,
        a.latest_action_by = $action_by,
        a.latest_action_reason = $action_reason,
        a.block_count = $block_count,
        a.release_count = $release_count
)
RETURN b.action_id AS action_id
"""

    def _build_ban_item(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """
        将 Neo4j 查询结果标准化为前端可直接消费的封禁记录。
        """
        ban = record.get("ban") or {}
        alert = record.get("alert") or {}
        ip = record.get("ip") or {}

        action_type = self._normalize_text(ban.get("action_type")).upper() or "BLOCK_IP"
        status = self._normalize_text(ban.get("status")).upper() or "UNKNOWN"
        ip_is_blocked = bool(ip.get("is_blocked")) if ip else False

        current_ban_status = self._resolve_current_status(ban, ip_is_blocked)
        history_actions = self._build_history_actions(record, current_ban_status, action_type)
        history_action_count = len(history_actions)

        latest_action_type = self._normalize_text(ban.get("latest_action_type")).upper()
        if not latest_action_type and history_actions:
            latest_action_type = self._normalize_text(history_actions[-1].get("action_type")).upper()
        if not latest_action_type:
            latest_action_type = "MANUAL_UNBLOCK_IP" if current_ban_status == self.RELEASED_STATUS else action_type

        latest_history_action = history_actions[-1] if history_actions else {}
        latest_action_at = self._normalize_text(ban.get("latest_action_at")) or self._normalize_text(
            latest_history_action.get("operated_at")
        )
        latest_action_by = self._normalize_text(ban.get("latest_action_by")) or self._normalize_text(
            latest_history_action.get("operated_by")
        )
        latest_action_reason = self._normalize_text(ban.get("latest_action_reason")) or self._normalize_text(
            latest_history_action.get("reason")
        )

        blocked_at = self._normalize_text(ban.get("blocked_at")) or self._normalize_text(ban.get("executed_at"))
        blocked_by = self._normalize_text(ban.get("blocked_by")) or self._normalize_text(ban.get("executor"))
        block_reason = self._normalize_text(ban.get("block_reason")) or self._normalize_text(ban.get("remark"))
        released_at = self._normalize_text(ban.get("released_at"))
        released_by = self._normalize_text(ban.get("released_by"))
        release_reason = self._normalize_text(ban.get("release_reason"))

        block_count = self._safe_int(ban.get("block_count")) or self._count_status_transitions(history_actions, self.BLOCKED_STATUS)
        release_count = self._safe_int(ban.get("release_count")) or self._count_status_transitions(history_actions, self.RELEASED_STATUS)

        can_unban = bool(ban.get("rollback_supported")) and current_ban_status == self.BLOCKED_STATUS
        can_reblock = current_ban_status == self.RELEASED_STATUS

        return {
            "action_id": self._normalize_text(ban.get("action_id")) or "-",
            "action_type": action_type,
            "latest_action_type": latest_action_type,
            "target_type": self._normalize_text(ban.get("target_type")).upper() or "IP",
            "status": status,
            "current_ban_status": current_ban_status,
            "current_block_status": current_ban_status,
            "executed_at": self._normalize_text(ban.get("executed_at")) or "-",
            "executor": self._normalize_text(ban.get("executor")) or "-",
            "ticket_no": self._normalize_text(ban.get("ticket_no")) or "-",
            "rollback_supported": bool(ban.get("rollback_supported")),
            "remark": self._normalize_text(ban.get("remark")) or "-",
            "alert_id": self._normalize_text(alert.get("alert_id")) or "-",
            "alert_name": self._normalize_text(alert.get("alert_name")) or "-",
            "severity": self._normalize_text(alert.get("severity")) or "-",
            "ip_id": self._normalize_text(ip.get("ip_id")) or "-",
            "ip_address": self._normalize_text(ip.get("ip_address")) or "-",
            "ip_block_status": self._normalize_text(ip.get("ip_block_status")).upper() or current_ban_status,
            "is_blocked": bool(ip.get("is_blocked")) if ip else current_ban_status == self.BLOCKED_STATUS,
            "blocked_at": blocked_at or "-",
            "blocked_by": blocked_by or "-",
            "block_reason": block_reason or "-",
            "released_at": released_at or "-",
            "released_by": released_by or "-",
            "release_reason": release_reason or "-",
            "latest_action_at": latest_action_at or blocked_at or released_at or "-",
            "latest_action_by": latest_action_by or blocked_by or released_by or "-",
            "latest_action_reason": latest_action_reason or block_reason or release_reason or "-",
            "latest_operator": latest_action_by or blocked_by or released_by or "-",
            "latest_reason": latest_action_reason or block_reason or release_reason or "-",
            "history_action_count": history_action_count,
            "history_actions": history_actions,
            "history_actions_brief": list(reversed(history_actions[-3:])),
            "history_summary": self._build_history_summary(history_actions),
            "block_count": block_count,
            "release_count": release_count,
            "is_released": current_ban_status == self.RELEASED_STATUS,
            "can_unban": can_unban,
            "can_reblock": can_reblock,
        }

    def _resolve_current_status(self, ban: Dict[str, Any], ip_is_blocked: bool) -> str:
        """
        兼容旧字段，推断当前封禁状态。
        """
        explicit_status = self._normalize_text(
            ban.get("current_ban_status") or ban.get("current_block_status")
        ).upper()
        if explicit_status:
            return explicit_status

        status = self._normalize_text(ban.get("status")).upper()
        released_at = self._normalize_text(ban.get("released_at"))
        action_type = self._normalize_text(ban.get("action_type")).upper()

        if ip_is_blocked:
            return self.BLOCKED_STATUS
        if released_at or status in self.RELEASED_STATUS_SET:
            return self.RELEASED_STATUS
        if status in self.FAILED_STATUS_SET:
            return "FAILED"
        if status in self.PENDING_STATUS_SET:
            return "PENDING"
        if action_type.startswith("BLOCK") and status in self.ACTIVE_BLOCK_STATUS_SET:
            return self.BLOCKED_STATUS
        return "UNKNOWN"

    def _build_history_actions(
        self,
        record: Dict[str, Any],
        current_ban_status: str,
        default_action_type: str,
    ) -> List[Dict[str, Any]]:
        """
        构造历史动作列表。

        兼容逻辑：
        1. 优先读取 history_actions_json。
        2. 若旧记录没有该字段，则根据 executed_at / released_at / latest_action_type 回填最小历史。
        """
        ban = record.get("ban") or {}
        raw_history_json = self._normalize_text(ban.get("history_actions_json"))
        if raw_history_json:
            try:
                loaded_history = json.loads(raw_history_json)
                if isinstance(loaded_history, list):
                    return self._normalize_history_actions(loaded_history)
            except json.JSONDecodeError:
                pass

        history_actions: List[Dict[str, Any]] = []
        initial_operated_at = self._normalize_text(ban.get("executed_at")) or self._normalize_text(ban.get("blocked_at"))
        initial_operator = self._normalize_text(ban.get("executor")) or self._normalize_text(ban.get("blocked_by"))
        initial_reason = self._normalize_text(ban.get("remark")) or self._normalize_text(ban.get("block_reason"))
        history_actions.append(
            {
                "sequence": 1,
                "action_type": default_action_type or "BLOCK_IP",
                "from_status": "UNKNOWN",
                "to_status": self.BLOCKED_STATUS,
                "operated_at": initial_operated_at or "-",
                "operated_by": initial_operator or "-",
                "reason": initial_reason or "初始封禁记录",
                "origin": "INITIAL",
            }
        )

        released_at = self._normalize_text(ban.get("released_at"))
        latest_action_type = self._normalize_text(ban.get("latest_action_type")).upper()
        if released_at or latest_action_type in {"UNBLOCK_IP", "MANUAL_UNBLOCK_IP"} or current_ban_status == self.RELEASED_STATUS:
            history_actions.append(
                {
                    "sequence": len(history_actions) + 1,
                    "action_type": latest_action_type or "MANUAL_UNBLOCK_IP",
                    "from_status": self.BLOCKED_STATUS,
                    "to_status": self.RELEASED_STATUS,
                    "operated_at": released_at or self._normalize_text(ban.get("latest_action_at")) or "-",
                    "operated_by": self._normalize_text(ban.get("released_by")) or self._normalize_text(ban.get("latest_action_by")) or "-",
                    "reason": self._normalize_text(ban.get("release_reason")) or self._normalize_text(ban.get("latest_action_reason")) or "历史放行记录",
                    "origin": "MIGRATED",
                }
            )

        return self._normalize_history_actions(history_actions)

    def _normalize_history_actions(self, history_actions: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        将历史动作统一标准化，便于前端直接展示。
        """
        normalized_actions: List[Dict[str, Any]] = []
        for index, item in enumerate(history_actions or [], start=1):
            if not isinstance(item, dict):
                continue
            normalized_actions.append(
                {
                    "sequence": self._safe_int(item.get("sequence")) or index,
                    "action_type": self._normalize_text(item.get("action_type")) or "-",
                    "from_status": self._normalize_text(item.get("from_status")) or "-",
                    "to_status": self._normalize_text(item.get("to_status")) or "-",
                    "operated_at": self._normalize_text(item.get("operated_at")) or "-",
                    "operated_by": self._normalize_text(item.get("operated_by")) or "-",
                    "reason": self._normalize_text(item.get("reason")) or "-",
                    "origin": self._normalize_text(item.get("origin")) or "MANUAL",
                }
            )

        normalized_actions.sort(
            key=lambda item: (
                self._normalize_text(item.get("operated_at")),
                self._safe_int(item.get("sequence")),
            )
        )
        return normalized_actions

    def _count_status_transitions(self, history_actions: Iterable[Dict[str, Any]], target_status: str) -> int:
        """
        统计历史中切换到目标状态的次数。
        """
        return len(
            [
                item
                for item in history_actions or []
                if self._normalize_text(item.get("to_status")).upper() == target_status
            ]
        )

    def _build_history_summary(self, history_actions: Iterable[Dict[str, Any]]) -> str:
        """
        生成历史动作摘要，供列表页快速展示。
        """
        latest_items = list(history_actions or [])[-3:]
        if not latest_items:
            return "-"

        summary_items = []
        for item in latest_items:
            action_type = self._normalize_text(item.get("action_type")) or "-"
            to_status = self._normalize_text(item.get("to_status")) or "-"
            operated_at = self._normalize_text(item.get("operated_at")) or "-"
            summary_items.append(f"{action_type} -> {to_status}（{operated_at}）")

        return " / ".join(summary_items)

    def _build_success_message(self, target_status: str) -> str:
        """
        构造切换成功提示。
        """
        if target_status == self.RELEASED_STATUS:
            return "放行 / 解封操作执行成功"
        return "重新封禁操作执行成功"

    def _build_idempotent_message(self, target_status: str) -> str:
        """
        构造幂等提示。
        """
        if target_status == self.RELEASED_STATUS:
            return "该封禁记录已经处于已放行状态，无需重复执行"
        return "该封禁记录已经处于已封禁状态，无需重复执行"

    def _normalize_text(self, value: Any) -> str:
        """
        将任意值安全转为字符串。
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

    def _build_local_timestamp(self) -> str:
        """
        生成本地时区的 ISO 时间字符串。
        """
        return datetime.now().astimezone().isoformat(timespec="seconds")


ban_service = BanService(neo4j_client)
