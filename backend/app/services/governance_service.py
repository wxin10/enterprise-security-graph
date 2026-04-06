#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import annotations

import ipaddress
import json
import os
import re
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any, Callable

from werkzeug.security import check_password_hash, generate_password_hash

from app.core.errors import NotFoundError, ValidationError


class GovernanceService:
    DEFAULT_DATA_FILE_PATH = Path(__file__).resolve().parents[1] / "data" / "governance_state.json"
    DATA_FILE_PATH = DEFAULT_DATA_FILE_PATH
    DATA_FILE_ENV = "GOVERNANCE_STATE_FILE"
    DEFAULT_PASSWORD = "123456"
    DISPOSAL_STATUS_PENDING = "待审批"
    DISPOSAL_STATUS_APPROVED = "已通过"
    DISPOSAL_STATUS_REJECTED = "已驳回"
    DISPOSAL_AUDIT_ACTION_SUBMIT = "提交处置申请"
    DISPOSAL_AUDIT_ACTION_REVIEW = "审批处置申请"
    DISPOSAL_AUDIT_ACTION_BAN_LINK = "联动封禁处置"
    BAN_EXECUTION_STATUS_BLOCKED = "已封禁"
    BAN_RELATED_DISPOSAL_TYPES = {"封禁申请"}

    PASSWORD_MIN_LENGTH = 8

    def __init__(self) -> None:
        self._lock = RLock()
        self._ensure_state_file()

    def list_users(self) -> dict[str, Any]:
        state = self._read_state()
        items = [self._build_public_user(item) for item in state["users"]]

        pending_approvals = []
        for item in state["users"]:
            if item.get("status") != "待审批":
                continue

            pending_approvals.append(
                {
                    "id": f"APP-{item['user_id']}",
                    "title": "账号开通审批",
                    "applicant": item.get("department") or "平台治理中心",
                    "target": f"{item['display_name']} / {item['user_id']}",
                    "status": item.get("status") or "待审批",
                    "created_at": item.get("created_at") or "-",
                }
            )

        return {
            "items": items,
            "pending_approvals": pending_approvals,
        }

    def create_user(self, payload: dict[str, Any], operator: dict[str, Any]) -> dict[str, Any]:
        username = self._normalize_username(payload.get("username"))
        if not username:
            raise ValidationError("用户名不能为空", data={"field": "username"})

        display_name = str(payload.get("display_name") or "").strip()
        department = str(payload.get("department") or "").strip()
        title = str(payload.get("title") or "").strip()
        role = self._normalize_role(payload.get("role"))
        status = self._normalize_user_status(payload.get("status") or "启用")
        email = str(payload.get("email") or "").strip()
        phone = str(payload.get("phone") or "").strip()
        bio = str(payload.get("bio") or "").strip()
        password = str(payload.get("password") or self.DEFAULT_PASSWORD).strip()

        if not display_name:
            raise ValidationError("姓名不能为空", data={"field": "display_name"})
        if not department:
            raise ValidationError("部门不能为空", data={"field": "department"})
        if not title:
            raise ValidationError("岗位职责不能为空", data={"field": "title"})
        if not password:
            raise ValidationError("初始密码不能为空", data={"field": "password"})

        now = self._now_text()

        def mutation(state: dict[str, Any]) -> dict[str, Any]:
            if self._find_user_by_username(state, username):
                raise ValidationError("用户名已存在", data={"field": "username"})

            next_user = {
                "user_id": self._next_id(state["users"], "user_id", "ADMIN-" if role == "admin" else "OPS-"),
                "username": username,
                "password_hash": self.build_password_hash(password),
                "password_updated_at": now,
                "display_name": display_name,
                "department": department,
                "title": title,
                "role": role,
                "status": status,
                "email": email,
                "phone": phone,
                "bio": bio,
                "last_login_at": "",
                "created_at": now,
                "updated_at": now,
            }
            state["users"].append(next_user)
            self._append_audit_log(
                state,
                module="用户管理",
                action="创建账号",
                operator=operator,
                target=f"{next_user['display_name']} / {next_user['user_id']}",
                result="已归档",
                risk_level="中",
                detail=f"新增账号 {next_user['username']}，角色为{self._role_label(next_user['role'])}。",
            )
            return {
                "user": self._build_public_user(next_user),
                "temporary_password": password,
            }

        return self._update_state(mutation)

    def update_user(self, user_id: str, payload: dict[str, Any], operator: dict[str, Any]) -> dict[str, Any]:
        now = self._now_text()

        def mutation(state: dict[str, Any]) -> dict[str, Any]:
            user = self._find_user(state, user_id)

            if "username" in payload:
                next_username = self._normalize_username(payload.get("username"))
                if not next_username:
                    raise ValidationError("用户名不能为空", data={"field": "username"})
                existed = self._find_user_by_username(state, next_username)
                if existed and existed["user_id"] != user_id:
                    raise ValidationError("用户名已存在", data={"field": "username"})
                user["username"] = next_username

            if "display_name" in payload:
                user["display_name"] = str(payload.get("display_name") or "").strip()
            if "department" in payload:
                user["department"] = str(payload.get("department") or "").strip()
            if "title" in payload:
                user["title"] = str(payload.get("title") or "").strip()
            if "role" in payload:
                user["role"] = self._normalize_role(payload.get("role"))
            if "status" in payload:
                user["status"] = self._normalize_user_status(payload.get("status"))
            if "email" in payload:
                user["email"] = str(payload.get("email") or "").strip()
            if "phone" in payload:
                user["phone"] = str(payload.get("phone") or "").strip()
            if "bio" in payload:
                user["bio"] = str(payload.get("bio") or "").strip()

            if not user.get("display_name"):
                raise ValidationError("姓名不能为空", data={"field": "display_name"})
            if not user.get("department"):
                raise ValidationError("部门不能为空", data={"field": "department"})
            if not user.get("title"):
                raise ValidationError("岗位职责不能为空", data={"field": "title"})

            user["updated_at"] = now

            self._append_audit_log(
                state,
                module="用户管理",
                action="更新账号资料",
                operator=operator,
                target=f"{user['display_name']} / {user['user_id']}",
                result="已归档",
                risk_level="中",
                detail=f"更新账号 {user['username']} 的资料和治理属性。",
            )
            return self._build_public_user(user)

        return self._update_state(mutation)

    def reset_user_password(self, user_id: str, operator: dict[str, Any]) -> dict[str, Any]:
        now = self._now_text()

        def mutation(state: dict[str, Any]) -> dict[str, Any]:
            user = self._find_user(state, user_id)
            user["password_hash"] = self.build_password_hash(self.DEFAULT_PASSWORD)
            user.pop("password", None)
            user["password_updated_at"] = now
            user["updated_at"] = now
            self._append_audit_log(
                state,
                module="用户管理",
                action="重置登录密码",
                operator=operator,
                target=f"{user['display_name']} / {user['user_id']}",
                result="已归档",
                risk_level="高",
                detail=f"账号 {user['username']} 的登录密码已重置。",
            )
            return {
                "user": self._build_public_user(user),
                "temporary_password": self.DEFAULT_PASSWORD,
            }

        return self._update_state(mutation)

    def toggle_user_status(self, user_id: str, operator: dict[str, Any]) -> dict[str, Any]:
        now = self._now_text()

        def mutation(state: dict[str, Any]) -> dict[str, Any]:
            user = self._find_user(state, user_id)
            current_status = user.get("status") or "启用"

            if operator.get("user_id") == user_id and current_status != "停用":
                raise ValidationError("当前账号不能停用自己")

            next_status = "启用" if current_status in {"停用", "待审批"} else "停用"

            if user.get("role") == "admin" and next_status == "停用":
                enabled_admins = [
                    item
                    for item in state["users"]
                    if item.get("role") == "admin" and item.get("status") == "启用" and item["user_id"] != user_id
                ]
                if not enabled_admins:
                    raise ValidationError("至少保留一个启用中的管理员账号")

            user["status"] = next_status
            user["updated_at"] = now

            action = "审批启用账号" if current_status == "待审批" else "切换账号状态"
            detail = (
                f"账号 {user['username']} 已审批启用。"
                if current_status == "待审批"
                else f"账号 {user['username']} 状态已切换为{next_status}。"
            )
            self._append_audit_log(
                state,
                module="用户管理",
                action=action,
                operator=operator,
                target=f"{user['display_name']} / {user['user_id']}",
                result="已归档",
                risk_level="高" if next_status == "停用" else "中",
                detail=detail,
            )
            return self._build_public_user(user)

        return self._update_state(mutation)

    def list_rules(self) -> dict[str, Any]:
        state = self._read_state()
        items = sorted(
            [deepcopy(item) for item in state["rules"]],
            key=lambda item: str(item.get("updated_at") or ""),
            reverse=True,
        )
        change_queue = sorted(
            [deepcopy(item) for item in state["rule_change_queue"]],
            key=lambda item: str(item.get("created_at") or ""),
            reverse=True,
        )
        return {
            "items": items,
            "change_queue": change_queue,
        }

    def create_rule(self, payload: dict[str, Any], operator: dict[str, Any]) -> dict[str, Any]:
        rule_code = str(payload.get("rule_code") or "").strip().upper()
        rule_name = str(payload.get("rule_name") or "").strip()
        category = self._normalize_rule_category(payload.get("category"))
        threshold = str(payload.get("threshold") or "").strip()
        description = str(payload.get("description") or "").strip()
        status = self._normalize_rule_status(payload.get("status") or "停用")
        hit_count = self._parse_int(payload.get("hit_count"), 0, "hit_count")
        owner = str(payload.get("owner") or operator.get("display_name") or "").strip()

        if not rule_code:
            raise ValidationError("规则编号不能为空", data={"field": "rule_code"})
        if not rule_name:
            raise ValidationError("规则名称不能为空", data={"field": "rule_name"})
        if not threshold:
            raise ValidationError("触发阈值不能为空", data={"field": "threshold"})
        if not description:
            raise ValidationError("规则说明不能为空", data={"field": "description"})

        now = self._now_text()

        def mutation(state: dict[str, Any]) -> dict[str, Any]:
            existed = next((item for item in state["rules"] if item.get("rule_code") == rule_code), None)
            if existed:
                raise ValidationError("规则编号已存在", data={"field": "rule_code"})

            next_rule = {
                "id": self._next_id(state["rules"], "id", "RULE-"),
                "rule_code": rule_code,
                "rule_name": rule_name,
                "category": category,
                "status": status,
                "threshold": threshold,
                "hit_count": hit_count,
                "updated_at": now,
                "description": description,
                "owner": owner,
            }
            state["rules"].append(next_rule)
            self._append_audit_log(
                state,
                module="规则管理",
                action="新增规则",
                operator=operator,
                target=f"{next_rule['rule_name']} / {next_rule['rule_code']}",
                result="已归档",
                risk_level="中",
                detail=f"新增{next_rule['category']}，当前状态为{next_rule['status']}。",
            )
            return deepcopy(next_rule)

        return self._update_state(mutation)

    def update_rule(self, rule_id: str, payload: dict[str, Any], operator: dict[str, Any]) -> dict[str, Any]:
        now = self._now_text()

        def mutation(state: dict[str, Any]) -> dict[str, Any]:
            rule = self._find_rule(state, rule_id)

            if "rule_name" in payload:
                rule["rule_name"] = str(payload.get("rule_name") or "").strip()
            if "category" in payload:
                rule["category"] = self._normalize_rule_category(payload.get("category"))
            if "threshold" in payload:
                rule["threshold"] = str(payload.get("threshold") or "").strip()
            if "description" in payload:
                rule["description"] = str(payload.get("description") or "").strip()
            if "status" in payload:
                rule["status"] = self._normalize_rule_status(payload.get("status"))
            if "hit_count" in payload:
                rule["hit_count"] = self._parse_int(payload.get("hit_count"), rule.get("hit_count") or 0, "hit_count")
            if "owner" in payload:
                rule["owner"] = str(payload.get("owner") or "").strip()

            if not rule.get("rule_name"):
                raise ValidationError("规则名称不能为空", data={"field": "rule_name"})
            if not rule.get("threshold"):
                raise ValidationError("触发阈值不能为空", data={"field": "threshold"})
            if not rule.get("description"):
                raise ValidationError("规则说明不能为空", data={"field": "description"})

            rule["updated_at"] = now
            self._append_audit_log(
                state,
                module="规则管理",
                action="更新规则",
                operator=operator,
                target=f"{rule['rule_name']} / {rule['rule_code']}",
                result="已归档",
                risk_level="中",
                detail="已更新规则阈值、说明或治理属性。",
            )
            return deepcopy(rule)

        return self._update_state(mutation)

    def gray_release_rule(self, rule_id: str, payload: dict[str, Any], operator: dict[str, Any]) -> dict[str, Any]:
        now = self._now_text()
        note = str(payload.get("note") or "按评估计划执行灰度发布").strip()

        def mutation(state: dict[str, Any]) -> dict[str, Any]:
            rule = self._find_rule(state, rule_id)
            rule["status"] = "灰度"
            rule["updated_at"] = now
            state["rule_change_queue"] = [
                item for item in state["rule_change_queue"] if item.get("rule_id") != rule_id
            ]
            self._append_audit_log(
                state,
                module="规则管理",
                action="灰度发布规则",
                operator=operator,
                target=f"{rule['rule_name']} / {rule['rule_code']}",
                result="待复核",
                risk_level="高",
                detail=note,
            )
            return deepcopy(rule)

        return self._update_state(mutation)

    def toggle_rule_status(self, rule_id: str, operator: dict[str, Any]) -> dict[str, Any]:
        now = self._now_text()

        def mutation(state: dict[str, Any]) -> dict[str, Any]:
            rule = self._find_rule(state, rule_id)
            rule["status"] = "启用" if rule.get("status") == "停用" else "停用"
            rule["updated_at"] = now
            self._append_audit_log(
                state,
                module="规则管理",
                action="切换规则状态",
                operator=operator,
                target=f"{rule['rule_name']} / {rule['rule_code']}",
                result="已归档",
                risk_level="高" if rule["status"] == "启用" else "中",
                detail=f"规则状态已切换为{rule['status']}。",
            )
            return deepcopy(rule)

        return self._update_state(mutation)

    def list_audit_logs(self) -> dict[str, Any]:
        state = self._read_state()
        items = sorted(
            [deepcopy(item) for item in state["audit_logs"]],
            key=lambda item: str(item.get("operated_at") or ""),
            reverse=True,
        )
        return {"items": items}

    def get_audit_log(self, audit_id: str) -> dict[str, Any]:
        state = self._read_state()
        audit_log = next((item for item in state["audit_logs"] if item.get("audit_id") == audit_id), None)
        if not audit_log:
            raise NotFoundError("审计记录不存在", data={"audit_id": audit_id})
        return deepcopy(audit_log)

    def list_disposals(self, current_user: dict[str, Any], own_only: bool = False) -> dict[str, Any]:
        state = self._read_state()
        items = [deepcopy(item) for item in state["disposals"]]

        if own_only:
            items = [item for item in items if item.get("applicant_id") == current_user.get("user_id")]

        items.sort(key=lambda item: str(item.get("updated_at") or item.get("created_at") or ""), reverse=True)
        return {
            "items": items,
            "summary": {
                "total": len(items),
                "pending": len([item for item in items if item.get("status") == self.DISPOSAL_STATUS_PENDING]),
                "approved": len([item for item in items if item.get("status") == self.DISPOSAL_STATUS_APPROVED]),
                "rejected": len([item for item in items if item.get("status") == self.DISPOSAL_STATUS_REJECTED]),
            },
        }

    def get_ban_approval_linkage_lookup(self) -> dict[str, dict[str, dict[str, str]]]:
        state = self._read_state()
        by_action_id: dict[str, dict[str, str]] = {}
        by_target_ip: dict[str, dict[str, str]] = {}
        items = sorted(
            [deepcopy(item) for item in state.get("disposals", [])],
            key=lambda item: str(item.get("reviewed_at") or item.get("updated_at") or ""),
            reverse=True,
        )

        for item in items:
            if item.get("status") != self.DISPOSAL_STATUS_APPROVED:
                continue

            if not self._is_ban_related_disposal(item.get("disposal_type")):
                continue

            linkage_item = {
                "approval_source_label": "处置申请审批",
                "approval_request_id": str(item.get("request_id") or "").strip(),
                "approval_reviewer_name": str(item.get("reviewer_name") or "").strip(),
                "approval_reviewed_at": str(item.get("reviewed_at") or item.get("updated_at") or "").strip(),
                "approval_review_comment": str(item.get("review_comment") or "").strip(),
                "approval_execution_status": str(item.get("execution_status") or "").strip(),
            }

            linked_ban_action_id = str(item.get("linked_ban_action_id") or "").strip()
            if linked_ban_action_id and linked_ban_action_id not in by_action_id:
                by_action_id[linked_ban_action_id] = linkage_item

            target_ip = self._normalize_optional_ip(item.get("execution_target") or item.get("source_ip"))
            if target_ip and target_ip not in by_target_ip:
                by_target_ip[target_ip] = linkage_item

        return {
            "by_action_id": by_action_id,
            "by_target_ip": by_target_ip,
        }

    def get_dashboard_approval_overview(self, current_user: dict[str, Any]) -> dict[str, Any]:
        if self._normalize_role(current_user.get("role")) != "admin":
            return {
                "enabled": False,
                "pending_disposal_count": 0,
                "approved_today_count": 0,
                "rejected_today_count": 0,
                "recent_action_time": "",
                "recent_disposals": [],
                "recent_reviews": [],
            }

        state = self._read_state()
        items = [deepcopy(item) for item in state.get("disposals", [])]
        today_text = self._now_text()[:10]

        pending_items = sorted(
            [item for item in items if item.get("status") == self.DISPOSAL_STATUS_PENDING],
            key=lambda item: str(item.get("created_at") or ""),
            reverse=True,
        )
        reviewed_items = sorted(
            [item for item in items if item.get("status") in {self.DISPOSAL_STATUS_APPROVED, self.DISPOSAL_STATUS_REJECTED}],
            key=lambda item: str(item.get("reviewed_at") or item.get("updated_at") or ""),
            reverse=True,
        )

        return {
            "enabled": True,
            "pending_disposal_count": len(pending_items),
            "approved_today_count": len(
                [
                    item
                    for item in reviewed_items
                    if item.get("status") == self.DISPOSAL_STATUS_APPROVED
                    and str(item.get("reviewed_at") or item.get("updated_at") or "").startswith(today_text)
                ]
            ),
            "rejected_today_count": len(
                [
                    item
                    for item in reviewed_items
                    if item.get("status") == self.DISPOSAL_STATUS_REJECTED
                    and str(item.get("reviewed_at") or item.get("updated_at") or "").startswith(today_text)
                ]
            ),
            "recent_action_time": (
                (reviewed_items[0].get("reviewed_at") or reviewed_items[0].get("updated_at") or "")
                if reviewed_items
                else ""
            ),
            "recent_disposals": pending_items[:5],
            "recent_reviews": reviewed_items[:5],
        }

    def create_disposal(self, payload: dict[str, Any], current_user: dict[str, Any]) -> dict[str, Any]:
        alert_id = str(payload.get("alert_id") or "").strip()
        alert_name = str(payload.get("alert_name") or "").strip()
        severity = self._normalize_alert_severity(payload.get("severity"))
        disposal_type = str(payload.get("disposal_type") or "").strip()
        urgency_level = self._normalize_urgency(payload.get("urgency_level"))
        disposition_opinion = str(payload.get("disposition_opinion") or "").strip()
        source_ip = self._normalize_optional_ip(payload.get("source_ip"))

        if not alert_id:
            raise ValidationError("告警编号不能为空", data={"field": "alert_id"})
        if not alert_name:
            raise ValidationError("告警名称不能为空", data={"field": "alert_name"})
        if not disposal_type:
            raise ValidationError("处置类型不能为空", data={"field": "disposal_type"})
        if not disposition_opinion:
            raise ValidationError("处置意见不能为空", data={"field": "disposition_opinion"})

        resolved_source_ip = source_ip or self._resolve_alert_source_ip(alert_id)

        now = self._now_text()

        def mutation(state: dict[str, Any]) -> dict[str, Any]:
            request_id = self._next_request_id(state["disposals"])
            record = {
                "request_id": request_id,
                "alert_id": alert_id,
                "alert_name": alert_name,
                "severity": severity,
                "status": self.DISPOSAL_STATUS_PENDING,
                "applicant_id": current_user["user_id"],
                "applicant_name": current_user["display_name"],
                "applicant_role": current_user["role"],
                "disposal_type": disposal_type,
                "urgency_level": urgency_level,
                "disposition_opinion": disposition_opinion,
                "source_ip": resolved_source_ip,
                "review_comment": "",
                "reviewer_id": "",
                "reviewer_name": "",
                "reviewed_at": "",
                "execution_status": "",
                "execution_target": resolved_source_ip,
                "execution_message": "",
                "linked_ban_action_id": "",
                "created_at": now,
                "updated_at": now,
            }
            state["disposals"].insert(0, record)
            self._append_audit_log(
                state,
                module="处置申请",
                action=self.DISPOSAL_AUDIT_ACTION_SUBMIT,
                operator=current_user,
                target=f"{alert_name} / {alert_id}",
                result=self.DISPOSAL_STATUS_PENDING,
                risk_level=self._severity_to_risk_level(severity, urgency_level),
                detail=f"提交{disposal_type}，处置意见：{disposition_opinion}",
            )
            return deepcopy(record)

        return self._update_state(mutation)

    def update_disposal(self, request_id: str, payload: dict[str, Any], operator: dict[str, Any]) -> dict[str, Any]:
        status = self._normalize_disposal_status(payload.get("status"))
        review_comment = str(payload.get("review_comment") or "").strip()
        now = self._now_text()

        def mutation(state: dict[str, Any]) -> dict[str, Any]:
            record = self._find_disposal(state, request_id)
            if record.get("status") != self.DISPOSAL_STATUS_PENDING:
                raise ValidationError("当前申请已完成审批，不能重复处理", data={"request_id": request_id})

            resolved_comment = review_comment or (
                "已同意按申请内容执行处置动作"
                if status == self.DISPOSAL_STATUS_APPROVED
                else "已驳回当前申请，请补充研判依据后再提交"
            )
            record["status"] = status
            record["review_comment"] = resolved_comment
            record["reviewer_id"] = operator["user_id"]
            record["reviewer_name"] = operator["display_name"]
            record["reviewed_at"] = now
            record["updated_at"] = now
            record["execution_status"] = ""
            record["execution_message"] = ""
            record["linked_ban_action_id"] = ""
            self._append_audit_log(
                state,
                module="处置申请",
                action=self.DISPOSAL_AUDIT_ACTION_REVIEW,
                operator=operator,
                target=f"{record['alert_name']} / {record['request_id']}",
                result=status,
                risk_level=self._severity_to_risk_level(record.get("severity"), record.get("urgency_level")),
                detail=f"审批备注：{resolved_comment}",
            )

            if status == self.DISPOSAL_STATUS_APPROVED and self._is_ban_related_disposal(record.get("disposal_type")):
                ban_link_result = self._execute_ban_linkage(record, operator, resolved_comment)
                record["execution_status"] = ban_link_result.get("execution_status") or ""
                record["execution_message"] = ban_link_result.get("execution_message") or ""
                record["execution_target"] = ban_link_result.get("execution_target") or record.get("execution_target") or ""
                record["linked_ban_action_id"] = ban_link_result.get("linked_ban_action_id") or ""

                if ban_link_result.get("audit_detail"):
                    self._append_audit_log(
                        state,
                        module="处置申请",
                        action=self.DISPOSAL_AUDIT_ACTION_BAN_LINK,
                        operator=operator,
                        target=f"{record['alert_name']} / {record['request_id']}",
                        result=ban_link_result.get("execution_status") or self.DISPOSAL_STATUS_APPROVED,
                        risk_level=self._severity_to_risk_level(record.get("severity"), record.get("urgency_level")),
                        detail=ban_link_result["audit_detail"],
                    )
            return deepcopy(record)

        return self._update_state(mutation)

    def get_profile(self, user_id: str) -> dict[str, Any]:
        state = self._read_state()
        user = self._find_user(state, user_id)
        return self._build_profile(user)

    def update_profile(self, user_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        now = self._now_text()

        def mutation(state: dict[str, Any]) -> dict[str, Any]:
            user = self._find_user(state, user_id)
            for field in ("display_name", "department", "title", "email", "phone", "bio"):
                if field in payload:
                    user[field] = str(payload.get(field) or "").strip()

            if not user.get("display_name"):
                raise ValidationError("姓名不能为空", data={"field": "display_name"})
            if not user.get("department"):
                raise ValidationError("部门不能为空", data={"field": "department"})
            if not user.get("title"):
                raise ValidationError("岗位职责不能为空", data={"field": "title"})

            user["updated_at"] = now
            self._append_audit_log(
                state,
                module="个人中心",
                action="更新个人资料",
                operator=self._build_public_user(user),
                target=f"{user['display_name']} / {user['user_id']}",
                result="已归档",
                risk_level="低",
                detail="已更新个人资料字段。",
            )
            return self._build_profile(user)

        return self._update_state(mutation)

    def change_profile_password(self, user_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        current_password = str(payload.get("current_password") or "").strip()
        new_password = str(payload.get("new_password") or "").strip()
        confirm_password = str(payload.get("confirm_password") or "").strip()

        if not current_password:
            raise ValidationError("当前密码不能为空", data={"field": "current_password"})
        if not new_password:
            raise ValidationError("新密码不能为空", data={"field": "new_password"})
        if not confirm_password:
            raise ValidationError("请再次确认新密码", data={"field": "confirm_password"})
        if new_password != confirm_password:
            raise ValidationError("两次输入的新密码不一致", data={"field": "confirm_password"})

        now = self._now_text()

        def mutation(state: dict[str, Any]) -> dict[str, Any]:
            user = self._find_user(state, user_id)

            if not self.verify_password(current_password, user):
                raise ValidationError("当前密码不正确", data={"field": "current_password"})
            if self.verify_password(new_password, user):
                raise ValidationError("新密码不能与当前密码相同", data={"field": "new_password"})
            self.validate_password_complexity(new_password, field_name="new_password")

            user["password_hash"] = self.build_password_hash(new_password)
            user.pop("password", None)
            user["password_updated_at"] = now
            user["updated_at"] = now

            operator = self._build_public_user(user) or {}
            self._append_audit_log(
                state,
                module="个人中心",
                action="修改登录密码",
                operator=operator,
                target=f"{user['display_name']} / {user['user_id']}",
                result="已完成",
                risk_level="中",
                detail="用户已完成登录密码轮换，系统已撤销该账号原有登录会话。",
            )
            return {
                "user_id": user["user_id"],
                "reauth_required": True,
                "session_scope": "all",
                "password_updated_at": user["password_updated_at"],
            }

        return self._update_state(mutation)

    def build_password_hash(self, password: Any) -> str:
        normalized_password = str(password or "").strip()
        if not normalized_password:
            raise ValidationError("密码不能为空", data={"field": "password"})
        return generate_password_hash(normalized_password)

    def validate_password_complexity(self, password: Any, *, field_name: str = "password") -> str:
        normalized_password = str(password or "").strip()
        if not normalized_password:
            raise ValidationError("密码不能为空", data={"field": field_name})
        if len(normalized_password) < self.PASSWORD_MIN_LENGTH:
            raise ValidationError(
                f"密码长度不能少于 {self.PASSWORD_MIN_LENGTH} 位",
                data={"field": field_name},
            )
        if not normalized_password.strip():
            raise ValidationError("密码不能全为空格", data={"field": field_name})
        if not re.search(r"[A-Za-z]", normalized_password) or not re.search(r"\d", normalized_password):
            raise ValidationError("密码需同时包含字母和数字", data={"field": field_name})
        return normalized_password

    def verify_password(self, password: Any, user: dict[str, Any] | None) -> bool:
        if not user:
            return False

        normalized_password = str(password or "").strip()
        if not normalized_password:
            return False

        password_hash = str(user.get("password_hash") or "").strip()
        if password_hash:
            return check_password_hash(password_hash, normalized_password)

        legacy_password = str(user.get("password") or "").strip()
        return bool(legacy_password) and legacy_password == normalized_password

    def get_login_user(self, username: str) -> dict[str, Any] | None:
        state = self._read_state()
        user = self._find_user_by_username(state, self._normalize_username(username))
        return deepcopy(user) if user else None

    def get_public_user_by_id(self, user_id: str) -> dict[str, Any] | None:
        state = self._read_state()
        user = next((item for item in state["users"] if item.get("user_id") == user_id), None)
        return self._build_public_user(user) if user else None

    def get_auth_user_by_id(self, user_id: str) -> dict[str, Any] | None:
        state = self._read_state()
        user = next((item for item in state["users"] if item.get("user_id") == user_id), None)
        if not user:
            return None

        return deepcopy(user)

    def mark_user_login(self, user_id: str, login_at: str) -> dict[str, Any]:
        def mutation(state: dict[str, Any]) -> dict[str, Any]:
            user = self._find_user(state, user_id)
            user["last_login_at"] = login_at
            user["updated_at"] = login_at
            return self._build_public_user(user)

        return self._update_state(mutation)

    def _get_data_file_path(self) -> Path:
        env_value = str(os.getenv(self.DATA_FILE_ENV, "") or "").strip()
        if env_value:
            return Path(env_value)
        return Path(self.DATA_FILE_PATH or self.DEFAULT_DATA_FILE_PATH)

    def _ensure_state_file(self) -> None:
        data_file_path = self._get_data_file_path()
        with self._lock:
            data_file_path.parent.mkdir(parents=True, exist_ok=True)
            if not data_file_path.exists():
                self._write_state(self._build_default_state())

    def _read_state(self) -> dict[str, Any]:
        data_file_path = self._get_data_file_path()
        with self._lock:
            self._ensure_state_file()
            with data_file_path.open("r", encoding="utf-8") as file:
                state = json.load(file)

            if self._migrate_state(state):
                self._write_state(state)

            return state

    def _write_state(self, state: dict[str, Any]) -> None:
        data_file_path = self._get_data_file_path()
        temp_path = data_file_path.with_suffix(".tmp")
        with temp_path.open("w", encoding="utf-8") as file:
            json.dump(state, file, ensure_ascii=False, indent=2)
        temp_path.replace(data_file_path)

    def _update_state(self, mutation: Callable[[dict[str, Any]], Any]) -> Any:
        with self._lock:
            state = self._read_state()
            result = mutation(state)
            self._write_state(state)
            return result

    def _migrate_state(self, state: dict[str, Any]) -> bool:
        changed = False

        for user in state.get("users", []):
            if not user.get("password_hash"):
                legacy_password = str(user.get("password") or self.DEFAULT_PASSWORD).strip() or self.DEFAULT_PASSWORD
                user["password_hash"] = self.build_password_hash(legacy_password)
                changed = True

            if "password" in user:
                user.pop("password", None)
                changed = True

            if not user.get("password_updated_at"):
                user["password_updated_at"] = user.get("updated_at") or user.get("created_at") or self._now_text()
                changed = True

        for item in state.get("disposals", []):
            if item.get("status") == "待复核":
                item["status"] = self.DISPOSAL_STATUS_PENDING
                changed = True

            if "reviewed_at" not in item:
                item["reviewed_at"] = item.get("updated_at") if item.get("reviewer_id") else ""
                changed = True

            if "source_ip" not in item:
                item["source_ip"] = self._resolve_alert_source_ip(item.get("alert_id"))
                changed = True

            if "execution_status" not in item:
                item["execution_status"] = ""
                changed = True

            if "execution_target" not in item:
                item["execution_target"] = item.get("source_ip") or ""
                changed = True

            if "execution_message" not in item:
                item["execution_message"] = ""
                changed = True

            if "linked_ban_action_id" not in item:
                item["linked_ban_action_id"] = ""
                changed = True

        for log in state.get("audit_logs", []):
            if log.get("module") != "处置申请":
                continue

            if log.get("action") == "提交申请":
                log["action"] = self.DISPOSAL_AUDIT_ACTION_SUBMIT
                changed = True

            if log.get("action") == "审核处置申请":
                log["action"] = self.DISPOSAL_AUDIT_ACTION_REVIEW
                changed = True

            if log.get("result") == "待复核":
                log["result"] = self.DISPOSAL_STATUS_PENDING
                changed = True

        return changed

    def _is_ban_related_disposal(self, disposal_type: Any) -> bool:
        return str(disposal_type or "").strip() in self.BAN_RELATED_DISPOSAL_TYPES

    def _normalize_optional_ip(self, raw_ip: Any) -> str:
        ip_text = str(raw_ip or "").strip()
        if not ip_text:
            return ""
        try:
            return str(ipaddress.ip_address(ip_text))
        except ValueError as exc:
            raise ValidationError("处置目标 IP 格式不合法", data={"field": "source_ip"}) from exc

    def _resolve_alert_source_ip(self, alert_id: Any) -> str:
        alert_id_text = str(alert_id or "").strip()
        if not alert_id_text:
            return ""

        try:
            from app.db import neo4j_client

            records = neo4j_client.execute_read(
                """
MATCH (a:Alert {alert_id: $alert_id})
OPTIONAL MATCH (s:Session)-[:GENERATES]->(:Event)-[:TRIGGERS]->(a)
OPTIONAL MATCH (s)-[:USES_SOURCE_IP]->(ip:IP)
RETURN coalesce(a.attacker_ip, '') AS attacker_ip,
       head([value IN collect(DISTINCT ip.ip_address) WHERE value IS NOT NULL AND value <> '']) AS source_ip
LIMIT 1
""",
                {"alert_id": alert_id_text},
            )
        except Exception:
            return ""

        if not records:
            return ""

        for candidate in (records[0].get("attacker_ip"), records[0].get("source_ip")):
            try:
                return self._normalize_optional_ip(candidate)
            except ValidationError:
                continue

        return ""

    def _execute_ban_linkage(
        self,
        record: dict[str, Any],
        operator: dict[str, Any],
        review_comment: str,
    ) -> dict[str, str]:
        source_ip = self._normalize_optional_ip(record.get("source_ip"))
        if not source_ip:
            return {
                "execution_status": "",
                "execution_target": "",
                "execution_message": "审批已通过，未解析到可执行的封禁目标 IP。",
                "linked_ban_action_id": "",
                "audit_detail": "审批已通过，但当前申请未解析到可执行的封禁目标 IP，未触发联动封禁。",
            }

        from app.services.ban_service import ban_service

        linkage_reason = (
            f"处置申请 {record['request_id']} 审批通过，按申请意见执行封禁。"
            f"审批备注：{review_comment or '按审批意见执行'}"
        )
        ban_result = ban_service.block_ip(
            source_ip,
            linkage_reason,
            source="manual",
            attack_type=str(record.get("alert_name") or record.get("disposal_type") or "").strip(),
            risk_score=90 if str(record.get("severity") or "").upper() == "CRITICAL" else 80,
            operator=str(operator.get("display_name") or operator.get("user_id") or "security_console"),
            source_type="disposal_approval",
        )

        ban_item = ban_result.get("item") or {}
        current_ban_status = str(ban_item.get("current_ban_status") or "").upper()
        execution_status = self.BAN_EXECUTION_STATUS_BLOCKED if current_ban_status == "BLOCKED" else ""
        execution_message = str(ban_result.get("message") or ban_item.get("enforcement_message") or "").strip()

        return {
            "execution_status": execution_status,
            "execution_target": source_ip,
            "execution_message": execution_message,
            "linked_ban_action_id": str(ban_item.get("action_id") or "").strip(),
            "audit_detail": (
                f"处置申请 {record['request_id']} 审批通过后已联动封禁来源 IP {source_ip}，"
                f"审批人：{operator.get('display_name') or operator.get('user_id') or '-'}，"
                f"审批备注：{review_comment or '按审批意见执行'}，"
                f"联动结果：{execution_status or '未完成封禁'}。"
            ),
        }

    def _append_audit_log(
        self,
        state: dict[str, Any],
        *,
        module: str,
        action: str,
        operator: dict[str, Any],
        target: str,
        result: str,
        risk_level: str,
        detail: str,
    ) -> None:
        state["audit_logs"].insert(
            0,
            {
                "audit_id": self._next_audit_id(state["audit_logs"]),
                "module": module,
                "action": action,
                "operator_id": operator.get("user_id") or "",
                "operator": operator.get("display_name") or operator.get("operator") or "",
                "operator_role": self._role_label(operator.get("role")),
                "target": target,
                "target_id": "",
                "result": result,
                "risk_level": risk_level,
                "operated_at": self._now_text(),
                "detail": detail,
            },
        )

    def _build_public_user(self, user: dict[str, Any] | None) -> dict[str, Any] | None:
        if not user:
            return None

        return {
            "user_id": user.get("user_id") or "",
            "username": user.get("username") or "",
            "display_name": user.get("display_name") or "",
            "department": user.get("department") or "",
            "title": user.get("title") or "",
            "role": self._normalize_role(user.get("role")),
            "status": self._normalize_user_status(user.get("status")),
            "email": user.get("email") or "",
            "phone": user.get("phone") or "",
            "bio": user.get("bio") or "",
            "last_login_at": user.get("last_login_at") or "",
            "created_at": user.get("created_at") or "",
            "updated_at": user.get("updated_at") or "",
            "login_at": user.get("last_login_at") or "",
        }

    def _build_profile(self, user: dict[str, Any]) -> dict[str, Any]:
        profile = self._build_public_user(user) or {}
        profile["role_label"] = self._role_label(profile.get("role"))
        return profile

    def _find_user(self, state: dict[str, Any], user_id: str) -> dict[str, Any]:
        user = next((item for item in state["users"] if item.get("user_id") == user_id), None)
        if not user:
            raise NotFoundError("用户不存在", data={"user_id": user_id})
        return user

    def _find_user_by_username(self, state: dict[str, Any], username: str) -> dict[str, Any] | None:
        return next((item for item in state["users"] if item.get("username") == username), None)

    def _find_rule(self, state: dict[str, Any], rule_id: str) -> dict[str, Any]:
        rule = next((item for item in state["rules"] if item.get("id") == rule_id), None)
        if not rule:
            raise NotFoundError("规则不存在", data={"rule_id": rule_id})
        return rule

    def _find_disposal(self, state: dict[str, Any], request_id: str) -> dict[str, Any]:
        record = next((item for item in state["disposals"] if item.get("request_id") == request_id), None)
        if not record:
            raise NotFoundError("处置申请不存在", data={"request_id": request_id})
        return record

    def _normalize_username(self, username: Any) -> str:
        return str(username or "").strip().lower()

    def _normalize_role(self, role: Any) -> str:
        return "admin" if str(role or "").strip().lower() == "admin" else "user"

    def _role_label(self, role: Any) -> str:
        return "管理员" if self._normalize_role(role) == "admin" else "普通用户"

    def _normalize_user_status(self, status: Any) -> str:
        status_text = str(status or "").strip()
        if status_text in {"启用", "停用", "待审批"}:
            return status_text
        raise ValidationError("账号状态不合法", data={"field": "status"})

    def _normalize_rule_category(self, category: Any) -> str:
        category_text = str(category or "").strip()
        if category_text in {"识别规则", "封禁规则"}:
            return category_text
        raise ValidationError("规则类型不合法", data={"field": "category"})

    def _normalize_rule_status(self, status: Any) -> str:
        status_text = str(status or "").strip()
        if status_text in {"启用", "灰度", "停用"}:
            return status_text
        raise ValidationError("规则状态不合法", data={"field": "status"})

    def _normalize_alert_severity(self, severity: Any) -> str:
        severity_text = str(severity or "").strip().upper()
        if severity_text in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}:
            return severity_text
        raise ValidationError("风险等级不合法", data={"field": "severity"})

    def _normalize_urgency(self, urgency: Any) -> str:
        urgency_text = str(urgency or "").strip()
        if urgency_text in {"高", "中", "低"}:
            return urgency_text
        raise ValidationError("紧急程度不合法", data={"field": "urgency_level"})

    def _normalize_disposal_status(self, status: Any) -> str:
        status_text = str(status or "").strip()
        if status_text in {
            self.DISPOSAL_STATUS_PENDING,
            self.DISPOSAL_STATUS_APPROVED,
            self.DISPOSAL_STATUS_REJECTED,
        }:
            return status_text
        raise ValidationError("处置申请状态不合法", data={"field": "status"})

    def _severity_to_risk_level(self, severity: Any, urgency: Any) -> str:
        severity_text = str(severity or "").strip().upper()
        urgency_text = str(urgency or "").strip()
        if severity_text == "CRITICAL" or urgency_text == "高":
            return "高"
        if severity_text == "HIGH" or urgency_text == "中":
            return "中"
        return "低"

    def _parse_int(self, value: Any, default_value: int, field_name: str) -> int:
        if value in (None, ""):
            return default_value
        try:
            return int(value)
        except (TypeError, ValueError) as exc:
            raise ValidationError(f"{field_name} 必须为整数", data={"field": field_name}) from exc

    def _next_id(self, items: list[dict[str, Any]], field_name: str, prefix: str) -> str:
        max_value = 0
        for item in items:
            raw_value = str(item.get(field_name) or "")
            if not raw_value.startswith(prefix):
                continue
            try:
                max_value = max(max_value, int(raw_value[len(prefix) :]))
            except ValueError:
                continue
        return f"{prefix}{max_value + 1:03d}"

    def _next_request_id(self, items: list[dict[str, Any]]) -> str:
        date_prefix = datetime.now(timezone.utc).astimezone().strftime("%Y%m%d")
        current_items = [item for item in items if str(item.get("request_id") or "").startswith(f"REQ-{date_prefix}-")]
        suffix = len(current_items) + 1
        return f"REQ-{date_prefix}-{suffix:03d}"

    def _next_audit_id(self, items: list[dict[str, Any]]) -> str:
        date_prefix = datetime.now(timezone.utc).astimezone().strftime("%Y%m%d")
        suffix = len([item for item in items if date_prefix in str(item.get("audit_id") or "")]) + 1
        return f"AUD-{date_prefix}-{suffix:03d}"

    def _now_text(self) -> str:
        return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S")

    def _build_default_state(self) -> dict[str, Any]:
        return {
            "users": [
                {
                    "user_id": "ADMIN-001",
                    "username": "admin",
                    "password_hash": self.build_password_hash(self.DEFAULT_PASSWORD),
                    "password_updated_at": "2026-04-03 09:00:00",
                    "display_name": "平台管理员",
                    "department": "安全运营中心",
                    "title": "高权限运维负责人",
                    "role": "admin",
                    "status": "启用",
                    "email": "admin@enterprise.local",
                    "phone": "13800000001",
                    "bio": "负责平台账号治理、规则管理与审计监督。",
                    "last_login_at": "2026-04-05 01:42:12",
                    "created_at": "2026-04-03 09:00:00",
                    "updated_at": "2026-04-05 01:42:12",
                },
                {
                    "user_id": "OPS-001",
                    "username": "analyst",
                    "password_hash": self.build_password_hash(self.DEFAULT_PASSWORD),
                    "password_updated_at": "2026-04-03 09:12:00",
                    "display_name": "值班分析员",
                    "department": "安全运营中心",
                    "title": "一线运维 / 安全分析员",
                    "role": "user",
                    "status": "启用",
                    "email": "analyst@enterprise.local",
                    "phone": "13800000002",
                    "bio": "负责告警研判、处置申请和风险跟踪。",
                    "last_login_at": "2026-04-05 01:35:40",
                    "created_at": "2026-04-03 09:12:00",
                    "updated_at": "2026-04-05 01:35:40",
                },
                {
                    "user_id": "OPS-002",
                    "username": "user",
                    "password_hash": self.build_password_hash(self.DEFAULT_PASSWORD),
                    "password_updated_at": "2026-04-04 21:30:00",
                    "display_name": "研判专员",
                    "department": "安全运营中心",
                    "title": "告警复核与处置联络",
                    "role": "user",
                    "status": "待审批",
                    "email": "reviewer@enterprise.local",
                    "phone": "13800000003",
                    "bio": "负责告警复核与处置协调。",
                    "last_login_at": "2026-04-04 23:18:25",
                    "created_at": "2026-04-04 21:30:00",
                    "updated_at": "2026-04-04 23:18:25",
                },
                {
                    "user_id": "OPS-003",
                    "username": "nightwatch",
                    "password_hash": self.build_password_hash(self.DEFAULT_PASSWORD),
                    "password_updated_at": "2026-04-03 18:00:00",
                    "display_name": "夜班值守",
                    "department": "态势感知组",
                    "title": "夜班告警处置",
                    "role": "user",
                    "status": "停用",
                    "email": "nightwatch@enterprise.local",
                    "phone": "13800000004",
                    "bio": "负责夜班告警处置与升级通知。",
                    "last_login_at": "2026-04-03 22:07:58",
                    "created_at": "2026-04-03 18:00:00",
                    "updated_at": "2026-04-05 00:48:00",
                },
            ],
            "rules": [
                {
                    "id": "RULE-001",
                    "rule_code": "DET-LOGIN-01",
                    "rule_name": "异常登录失败激增识别",
                    "category": "识别规则",
                    "status": "启用",
                    "threshold": "10 分钟内失败次数 >= 15",
                    "hit_count": 38,
                    "updated_at": "2026-04-05 00:16:00",
                    "description": "识别短时间内登录失败次数快速上升的账号与源 IP 组合。",
                    "owner": "平台管理员",
                },
                {
                    "id": "RULE-002",
                    "rule_code": "DET-LATERAL-02",
                    "rule_name": "横向移动链路异常扩散识别",
                    "category": "识别规则",
                    "status": "灰度",
                    "threshold": "图谱扩散层级 >= 3 且高危节点数 >= 5",
                    "hit_count": 12,
                    "updated_at": "2026-04-04 21:48:00",
                    "description": "结合 Neo4j 图谱分析结果识别横向移动路径扩散风险。",
                    "owner": "平台管理员",
                },
                {
                    "id": "RULE-003",
                    "rule_code": "BAN-IP-03",
                    "rule_name": "高危源 IP 自动封禁策略",
                    "category": "封禁规则",
                    "status": "启用",
                    "threshold": "命中 CRITICAL 告警并经管理员审批",
                    "hit_count": 6,
                    "updated_at": "2026-04-04 23:36:00",
                    "description": "管理员审批通过后执行源 IP 封禁，并同步写入封禁台账。",
                    "owner": "平台管理员",
                },
                {
                    "id": "RULE-004",
                    "rule_code": "BAN-ACCOUNT-04",
                    "rule_name": "异常账号冻结策略",
                    "category": "封禁规则",
                    "status": "停用",
                    "threshold": "连续命中 3 次高风险行为",
                    "hit_count": 0,
                    "updated_at": "2026-04-03 17:22:00",
                    "description": "用于冻结高风险账号，当前处于停用状态。",
                    "owner": "平台管理员",
                },
            ],
            "rule_change_queue": [
                {
                    "id": "CHG-001",
                    "rule_id": "RULE-002",
                    "rule_name": "横向移动链路异常扩散识别",
                    "source": "值班分析员处置建议",
                    "change_summary": "建议提高节点扩散阈值，降低误报率。",
                    "status": "待评估",
                    "created_at": "2026-04-05 00:05:00",
                },
                {
                    "id": "CHG-002",
                    "rule_id": "RULE-004",
                    "rule_name": "异常账号冻结策略",
                    "source": "封禁审批复盘",
                    "change_summary": "建议恢复灰度发布并增加人工确认步骤。",
                    "status": "待评估",
                    "created_at": "2026-04-04 22:40:00",
                },
            ],
            "disposals": [
                {
                    "request_id": "REQ-20260404-001",
                    "alert_id": "ALT-20031",
                    "alert_name": "异常登录失败激增",
                    "severity": "HIGH",
                    "status": "待审批",
                    "applicant_id": "OPS-001",
                    "applicant_name": "值班分析员",
                    "applicant_role": "user",
                    "disposal_type": "封禁申请",
                    "urgency_level": "高",
                    "disposition_opinion": "建议先封禁源 IP 2 小时，并继续观察同源账号行为。",
                    "review_comment": "",
                    "reviewer_id": "",
                    "reviewer_name": "",
                    "reviewed_at": "",
                    "created_at": "2026-04-04 08:30:00",
                    "updated_at": "2026-04-04 08:30:00",
                },
                {
                    "request_id": "REQ-20260404-002",
                    "alert_id": "ALT-20056",
                    "alert_name": "异常会话横向访问",
                    "severity": "CRITICAL",
                    "status": "已通过",
                    "applicant_id": "OPS-001",
                    "applicant_name": "值班分析员",
                    "applicant_role": "user",
                    "disposal_type": "人工复核申请",
                    "urgency_level": "中",
                    "disposition_opinion": "建议进入人工复核并联动封禁策略校验。",
                    "review_comment": "已安排管理员复核并进入联动处置。",
                    "reviewer_id": "ADMIN-001",
                    "reviewer_name": "平台管理员",
                    "reviewed_at": "2026-04-04 11:10:00",
                    "created_at": "2026-04-04 09:50:00",
                    "updated_at": "2026-04-04 11:10:00",
                },
            ],
            "audit_logs": [
                {
                    "audit_id": "AUD-RULE-20260405-001",
                    "module": "规则管理",
                    "action": "灰度发布规则",
                    "operator_id": "ADMIN-001",
                    "operator": "平台管理员",
                    "operator_role": "管理员",
                    "target": "横向移动链路异常扩散识别 / DET-LATERAL-02",
                    "target_id": "RULE-002",
                    "result": "待复核",
                    "risk_level": "高",
                    "operated_at": "2026-04-05 00:32:00",
                    "detail": "已对图谱扩散识别规则执行灰度发布，等待观察误报率与命中效果。",
                },
                {
                    "audit_id": "AUD-USER-20260405-002",
                    "module": "用户管理",
                    "action": "切换账号状态",
                    "operator_id": "ADMIN-001",
                    "operator": "平台管理员",
                    "operator_role": "管理员",
                    "target": "夜班值守 / OPS-003",
                    "target_id": "OPS-003",
                    "result": "已归档",
                    "risk_level": "中",
                    "operated_at": "2026-04-05 00:48:00",
                    "detail": "针对夜班值守账号完成停用处置，并留存审批来源。",
                },
                {
                    "audit_id": "AUD-DISPOSAL-20260404-003",
                    "module": "处置申请",
                    "action": "审批处置申请",
                    "operator_id": "ADMIN-001",
                    "operator": "平台管理员",
                    "operator_role": "管理员",
                    "target": "异常会话横向访问 / REQ-20260404-002",
                    "target_id": "REQ-20260404-002",
                    "result": "已通过",
                    "risk_level": "高",
                    "operated_at": "2026-04-04 11:10:00",
                    "detail": "已完成管理员复核并进入联动处置流程。",
                },
                {
                    "audit_id": "AUD-DISPOSAL-20260404-004",
                    "module": "处置申请",
                    "action": "提交处置申请",
                    "operator_id": "OPS-001",
                    "operator": "值班分析员",
                    "operator_role": "普通用户",
                    "target": "异常登录失败激增 / ALT-20031",
                    "target_id": "REQ-20260404-001",
                    "result": "待审批",
                    "risk_level": "高",
                    "operated_at": "2026-04-04 08:30:00",
                    "detail": "提交封禁申请，建议先封禁源 IP 2 小时。",
                },
            ],
        }


governance_service = GovernanceService()
