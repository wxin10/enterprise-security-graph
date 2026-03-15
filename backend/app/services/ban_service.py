#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
文件路径：backend/app/services/ban_service.py

文件作用：
1. 统一处理封禁记录查询、放行/解封和状态同步逻辑。
2. 封装 Neo4j 中 BlockAction、IP、Alert 的状态更新，避免将业务逻辑直接写在路由层。
3. 兼容旧数据中缺失 release 字段的情况，并保证重复放行具有幂等性。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from app.core.errors import NotFoundError, ValidationError
from app.db import neo4j_client


class BanService:
    """
    封禁与放行服务。

    设计说明：
    1. 当前阶段优先实现“最小可运行版本”，因此保留原有 BlockAction 节点，不引入新的复杂审计子图。
    2. 放行时通过补充 released_at / released_by / release_reason 等字段形成可审计记录。
    3. 同时同步更新目标 IP 的 is_blocked 状态，并在 Alert 上补充最新处置状态，便于前端图谱和列表查询展示。
    """

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

        兼容性处理：
        1. 旧数据只有 BlockAction.status，没有 released_at/current_ban_status，也可以正常展示。
        2. status 查询既支持原始执行状态，也支持前端更关心的 BLOCKED / RELEASED 当前封禁状态。
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
        OR ($status = 'RELEASED' AND (coalesce(b.released_at, '') <> '' OR toUpper(coalesce(b.current_ban_status, '')) = 'RELEASED'))
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
        OR ($status = 'RELEASED' AND (coalesce(b.released_at, '') <> '' OR toUpper(coalesce(b.current_ban_status, '')) = 'RELEASED'))
      )
  AND ($target_ip IS NULL OR coalesce(ip.ip_address, '') CONTAINS $target_ip)
RETURN properties(b) AS ban,
       properties(a) AS alert,
       properties(ip) AS ip
ORDER BY coalesce(b.executed_at, '') DESC, b.action_id ASC
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
        执行放行 / 解封操作。

        幂等策略：
        1. 如果记录已经处于 RELEASED 状态，则直接返回最新记录，不报 500。
        2. 如果旧数据状态缺失，但目标 IP 已经不在封禁状态，则补齐 release 字段并返回最新记录。
        """
        record = self._fetch_ban_context(ban_id)
        if not record:
            raise NotFoundError(f"未找到封禁记录 {ban_id}")

        current_item = self._build_ban_item(record)
        if self._normalize_text(current_item.get("target_type")).upper() != "IP":
            raise ValidationError("当前最小可运行版本仅支持 IP 类型封禁记录的放行")

        if current_item["is_released"]:
            return {
                "already_released": True,
                "item": current_item,
                "message": "该封禁记录已经放行，无需重复执行",
            }

        released_at = self._build_local_timestamp()
        normalized_reason = self._normalize_text(release_reason) or "人工复核后确认放行"
        normalized_operator = self._normalize_text(released_by) or "security_console"

        update_query = """
MATCH (b:BlockAction {action_id: $action_id})
OPTIONAL MATCH (b)-[:TARGETS_IP]->(ip:IP)
OPTIONAL MATCH (b)-[:DISPOSES]->(a:Alert)
SET b.status = 'RELEASED',
    b.current_ban_status = 'RELEASED',
    b.latest_action_type = 'UNBLOCK_IP',
    b.is_released = true,
    b.released_at = $released_at,
    b.released_by = $released_by,
    b.release_reason = $release_reason,
    b.updated_at = $released_at
FOREACH (_ IN CASE WHEN ip IS NULL THEN [] ELSE [1] END |
    SET ip.is_blocked = false,
        ip.ip_block_status = 'RELEASED',
        ip.released_at = $released_at,
        ip.released_by = $released_by,
        ip.release_reason = $release_reason,
        ip.last_released_at = $released_at
)
FOREACH (_ IN CASE WHEN a IS NULL THEN [] ELSE [1] END |
    SET a.disposition_status = 'RELEASED',
        a.latest_action_type = 'UNBLOCK_IP',
        a.released_at = $released_at,
        a.released_by = $released_by
)
RETURN b.action_id AS action_id
"""

        self.client.execute_write(
            update_query,
            {
                "action_id": ban_id,
                "released_at": released_at,
                "released_by": normalized_operator,
                "release_reason": normalized_reason,
            },
        )

        latest_item = self.get_ban_detail(ban_id)
        return {
            "already_released": False,
            "item": latest_item,
            "message": "放行 / 解封操作执行成功",
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

    def _build_ban_item(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """
        将 Neo4j 查询结果标准化为前端可直接消费的封禁记录。
        """
        ban = record.get("ban") or {}
        alert = record.get("alert") or {}
        ip = record.get("ip") or {}

        action_type = self._normalize_text(ban.get("action_type")).upper() or "BLOCK_IP"
        status = self._normalize_text(ban.get("status")).upper() or "UNKNOWN"
        released_at = self._normalize_text(ban.get("released_at"))
        ip_is_blocked = bool(ip.get("is_blocked")) if ip else False

        current_ban_status = self._normalize_text(ban.get("current_ban_status")).upper()
        if not current_ban_status:
            if ip_is_blocked:
                current_ban_status = "BLOCKED"
            elif released_at or status in self.RELEASED_STATUS_SET:
                current_ban_status = "RELEASED"
            elif status in self.FAILED_STATUS_SET:
                current_ban_status = "FAILED"
            elif status in self.PENDING_STATUS_SET:
                current_ban_status = "PENDING"
            elif action_type.startswith("BLOCK") and status in self.ACTIVE_BLOCK_STATUS_SET:
                current_ban_status = "BLOCKED"
            else:
                current_ban_status = "UNKNOWN"

        is_released = current_ban_status == "RELEASED"
        latest_action_type = self._normalize_text(ban.get("latest_action_type")).upper()
        if not latest_action_type:
            latest_action_type = "UNBLOCK_IP" if is_released else action_type

        can_unban = bool(ban.get("rollback_supported")) and current_ban_status == "BLOCKED"

        return {
            "action_id": self._normalize_text(ban.get("action_id")) or "-",
            "action_type": action_type,
            "latest_action_type": latest_action_type,
            "target_type": self._normalize_text(ban.get("target_type")).upper() or "IP",
            "status": status,
            "current_ban_status": current_ban_status,
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
            "is_blocked": bool(ip.get("is_blocked")) if ip else current_ban_status == "BLOCKED",
            "released_at": released_at or "-",
            "released_by": self._normalize_text(ban.get("released_by")) or "-",
            "release_reason": self._normalize_text(ban.get("release_reason")) or "-",
            "is_released": is_released,
            "can_unban": can_unban,
        }

    def _normalize_text(self, value: Any) -> str:
        """
        将任意值安全转为字符串。
        """
        if value is None:
            return ""
        return str(value).strip()

    def _build_local_timestamp(self) -> str:
        """
        生成本地时区的 ISO 时间字符串。
        """
        return datetime.now().astimezone().isoformat(timespec="seconds")


ban_service = BanService(neo4j_client)
