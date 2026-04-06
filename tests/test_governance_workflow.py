from __future__ import annotations

from app.services.auth_service import auth_service


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


def test_disposal_workflow_and_audit_linkage(app_client):
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
