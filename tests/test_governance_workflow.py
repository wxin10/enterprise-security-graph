from __future__ import annotations

import json

from app.services.auth_service import auth_service
from app.services.ban_service import ban_service


def login(client, username: str, password: str = "123456") -> dict:
    response = client.post(
        "/api/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["code"] == 0
    return payload["data"]


def build_headers(session_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {session_token}"}


def test_login_and_session_restore(app_client):
    analyst_session = login(app_client, "analyst")
    session_token = analyst_session["session_token"]

    auth_service._session_store = {}
    auth_service._session_store = auth_service._load_session_store()

    me_response = app_client.get("/api/auth/me", headers=build_headers(session_token))
    assert me_response.status_code == 200
    me_payload = me_response.get_json()

    assert me_payload["code"] == 0
    assert me_payload["data"]["user"]["username"] == "analyst"

    governance_text = app_client.governance_file.read_text(encoding="utf-8")
    assert '"password":' not in governance_text
    assert '"password_hash":' in governance_text


def test_password_reset_invalidates_legacy_session_and_keeps_hash_only(app_client):
    analyst_session = login(app_client, "analyst")
    admin_session = login(app_client, "admin")

    reset_response = app_client.post(
        "/api/users/OPS-001/reset-password",
        headers=build_headers(admin_session["session_token"]),
    )
    assert reset_response.status_code == 200
    reset_payload = reset_response.get_json()
    assert reset_payload["code"] == 0
    assert reset_payload["data"]["temporary_password"] == "123456"

    expired_response = app_client.get(
        "/api/auth/me",
        headers=build_headers(analyst_session["session_token"]),
    )
    assert expired_response.status_code == 401

    refreshed_session = login(app_client, "analyst", "123456")
    assert refreshed_session["user"]["username"] == "analyst"

    governance_payload = json.loads(app_client.governance_file.read_text(encoding="utf-8"))
    analyst_user = next(item for item in governance_payload["users"] if item["username"] == "analyst")
    assert "password" not in analyst_user
    assert isinstance(analyst_user.get("password_hash"), str)
    assert analyst_user["password_hash"]


def test_disposal_workflow_and_audit_linkage(app_client, monkeypatch):
    analyst_session = login(app_client, "analyst")
    admin_session = login(app_client, "admin")

    analyst_headers = build_headers(analyst_session["session_token"])
    admin_headers = build_headers(admin_session["session_token"])

    approve_response = app_client.post(
        "/api/disposals",
        headers=analyst_headers,
        json={
            "alert_id": "ALT-APPROVE-001",
            "alert_name": "异常登录封禁申请",
            "source_ip": "10.10.10.25",
            "severity": "HIGH",
            "disposal_type": "封禁申请",
            "urgency_level": "高",
            "disposition_opinion": "建议立即封禁来源 IP 并持续观察"
        },
    )
    assert approve_response.status_code == 200
    approve_request = approve_response.get_json()["data"]

    reject_response = app_client.post(
        "/api/disposals",
        headers=analyst_headers,
        json={
            "alert_id": "ALT-REJECT-001",
            "alert_name": "人工复核申请",
            "source_ip": "10.10.10.26",
            "severity": "MEDIUM",
            "disposal_type": "人工复核申请",
            "urgency_level": "中",
            "disposition_opinion": "建议补充证据后再执行高风险动作"
        },
    )
    assert reject_response.status_code == 200
    reject_request = reject_response.get_json()["data"]

    list_response = app_client.get("/api/disposals", headers=admin_headers)
    assert list_response.status_code == 200
    list_payload = list_response.get_json()["data"]

    assert list_payload["summary"]["pending"] >= 2
    assert any(item["request_id"] == approve_request["request_id"] for item in list_payload["items"])
    assert any(item["request_id"] == reject_request["request_id"] for item in list_payload["items"])

    approve_patch = app_client.patch(
        f"/api/disposals/{approve_request['request_id']}",
        headers=admin_headers,
        json={"status": "已通过", "review_comment": "同意封禁来源 IP，按审批结果执行"},
    )
    assert approve_patch.status_code == 200
    approved_payload = approve_patch.get_json()["data"]

    assert approved_payload["status"] == "已通过"
    assert approved_payload["execution_status"] == "已封禁"
    assert approved_payload["linked_ban_action_id"] == "LINKED-BAN-10_10_10_25"

    reject_patch = app_client.patch(
        f"/api/disposals/{reject_request['request_id']}",
        headers=admin_headers,
        json={"status": "已驳回", "review_comment": "证据不足，暂不执行高风险处置"},
    )
    assert reject_patch.status_code == 200
    rejected_payload = reject_patch.get_json()["data"]

    assert rejected_payload["status"] == "已驳回"
    assert rejected_payload["review_comment"] == "证据不足，暂不执行高风险处置"
    assert rejected_payload["execution_status"] == ""

    my_records_response = app_client.get("/api/disposals/my", headers=analyst_headers)
    assert my_records_response.status_code == 200
    my_records = my_records_response.get_json()["data"]["items"]

    approved_record = next(item for item in my_records if item["request_id"] == approve_request["request_id"])
    rejected_record = next(item for item in my_records if item["request_id"] == reject_request["request_id"])

    assert approved_record["status"] == "已通过"
    assert approved_record["execution_status"] == "已封禁"
    assert approved_record["review_comment"] == "同意封禁来源 IP，按审批结果执行"
    assert rejected_record["status"] == "已驳回"
    assert rejected_record["review_comment"] == "证据不足，暂不执行高风险处置"

    audit_response = app_client.get("/api/audit/logs", headers=admin_headers)
    assert audit_response.status_code == 200
    audit_items = audit_response.get_json()["data"]["items"]

    assert any(
        item["action"] == "提交处置申请" and item["target_id"] == ""
        for item in audit_items
    )
    assert any(
        item["action"] == "审批处置申请"
        and item["result"] == "已通过"
        and approve_request["request_id"] in item["target"]
        for item in audit_items
    )
    assert any(
        item["action"] == "审批处置申请"
        and item["result"] == "已驳回"
        and reject_request["request_id"] in item["target"]
        for item in audit_items
    )
    assert any(
        item["action"] == "联动封禁处置"
        and item["result"] == "已封禁"
        and approve_request["request_id"] in item["detail"]
        for item in audit_items
    )

    linked_ban_record = {
        "ban": {
            "action_id": approved_payload["linked_ban_action_id"],
            "action_type": "BLOCK_IP",
            "block_source": "manual",
            "latest_action_type": "MANUAL_BLOCK_IP",
            "target_type": "IP",
            "status": "BLOCKED",
            "current_ban_status": "BLOCKED",
            "blocked_at": approved_payload["reviewed_at"],
            "blocked_by": approved_payload["reviewer_name"],
            "block_reason": approved_payload["review_comment"],
            "latest_action_at": approved_payload["reviewed_at"],
            "latest_action_by": approved_payload["reviewer_name"],
            "latest_action_reason": approved_payload["review_comment"],
            "source_type": "disposal_approval",
            "enforcement_mode": "MOCK",
            "enforcement_backend": "MOCK",
            "enforcement_status": "SIMULATED",
            "verification_status": "NOT_VERIFIED",
        },
        "alert": {
            "alert_id": approve_request["alert_id"],
            "alert_name": approve_request["alert_name"],
            "severity": approve_request["severity"],
        },
        "ip": {
            "ip_id": "AUTO-IP-10_10_10_25",
            "ip_address": approve_request["source_ip"],
            "ip_block_status": "BLOCKED",
            "is_blocked": True,
        },
    }

    def fake_execute_read(query: str, params: dict[str, str]) -> list[dict]:
        if "RETURN count(DISTINCT b) AS total" in query:
            return [{"total": 1}]
        if "MATCH (b:BlockAction {action_id: $action_id})" in query:
            return [linked_ban_record]
        if "RETURN properties(b) AS ban," in query:
            return [linked_ban_record]
        return []

    monkeypatch.setattr(ban_service.client, "execute_read", fake_execute_read)

    bans_response = app_client.get("/api/bans", headers=admin_headers)
    assert bans_response.status_code == 200
    ban_item = bans_response.get_json()["data"]["items"][0]

    assert ban_item["approval_source_label"] == "处置申请审批"
    assert ban_item["approval_request_id"] == approve_request["request_id"]
    assert ban_item["approval_reviewer_name"] == "平台管理员"
    assert ban_item["approval_review_comment"] == "同意封禁来源 IP，按审批结果执行"
    assert ban_item["approval_execution_status"] == "已封禁"

    ban_detail_response = app_client.get(
        f"/api/bans/{approved_payload['linked_ban_action_id']}",
        headers=admin_headers,
    )
    assert ban_detail_response.status_code == 200
    ban_detail = ban_detail_response.get_json()["data"]

    assert ban_detail["approval_request_id"] == approve_request["request_id"]
    assert ban_detail["approval_execution_status"] == "已封禁"
