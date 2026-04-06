from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"


def prepare_temp_data_root() -> dict[str, Path]:
    temp_root = Path(os.getenv("DESIGN_REAL_E2E_DATA_ROOT") or Path(tempfile.gettempdir()) / "design-real-e2e")
    if temp_root.exists():
        shutil.rmtree(temp_root, ignore_errors=True)
    temp_root.mkdir(parents=True, exist_ok=True)

    governance_file = temp_root / "governance_state.json"
    session_file = temp_root / "session_state.json"
    blocklist_file = temp_root / "blocklist.json"
    ban_file = temp_root / "ban_state.json"

    shutil.copy2(REPO_ROOT / "backend" / "app" / "data" / "governance_state.json", governance_file)
    session_file.write_text(json.dumps({"sessions": []}, ensure_ascii=False, indent=2), encoding="utf-8")
    blocklist_file.write_text(
        json.dumps({"blocked_ips": {}, "updated_at": ""}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    ban_file.write_text(json.dumps({"items": []}, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "root": temp_root,
        "governance_file": governance_file,
        "session_file": session_file,
        "blocklist_file": blocklist_file,
        "ban_file": ban_file,
    }


prepared_paths = prepare_temp_data_root()
os.environ["GOVERNANCE_STATE_FILE"] = str(prepared_paths["governance_file"])
os.environ["SESSION_STATE_FILE"] = str(prepared_paths["session_file"])
os.environ["BAN_WEB_BLOCKLIST_FILE"] = str(prepared_paths["blocklist_file"])
os.environ.setdefault("BAN_ENFORCEMENT_MODE", "MOCK")
os.environ.setdefault("FLASK_HOST", "127.0.0.1")
os.environ.setdefault("FLASK_PORT", "5000")
os.environ.setdefault("CORS_ORIGINS", "http://127.0.0.1:4173")

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app import create_app
from app.services.ban_service import ban_service
from app.services.governance_service import governance_service
from app.services.graph_service import graph_service


class FileBackedBanAdapter:
    def __init__(self, storage_path: Path) -> None:
        self.storage_path = storage_path

    def execute_read(self, query: str, parameters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        params = parameters or {}
        query_text = str(query or "")
        records = self._load_records()

        if "RETURN count(DISTINCT b) AS total" in query_text:
            return [{"total": len(self._filter_records(records, params))}]

        if "MATCH (b:BlockAction {action_id: $action_id})" in query_text:
            action_id = str(params.get("action_id") or "").strip()
            record = next(
                (item for item in records if str((item.get("ban") or {}).get("action_id") or "").strip() == action_id),
                None,
            )
            return [self._hydrate_record(record)] if record else []

        if "RETURN properties(b) AS ban," in query_text:
            filtered_records = self._filter_records(records, params)
            skip = int(params.get("skip") or 0)
            limit = int(params.get("limit") or len(filtered_records) or 20)
            return [self._hydrate_record(item) for item in filtered_records[skip : skip + limit]]

        return []

    def execute_write(self, query: str, parameters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        params = parameters or {}
        query_text = str(query or "")

        if "MERGE (b:BlockAction {action_id: $action_id})" in query_text:
            return [self._upsert_block_action(params)]

        if "SET b.current_ban_status = $target_status" in query_text:
            return [self._switch_block_status(params)]

        if "SET b.enforcement_mode = $enforcement_mode" in query_text:
            return [self._update_enforcement_state(params)]

        return []

    def _load_records(self) -> list[dict[str, Any]]:
        payload = json.loads(self.storage_path.read_text(encoding="utf-8") or '{"items": []}')
        items = payload.get("items") or []
        return [item for item in items if isinstance(item, dict)]

    def _save_records(self, records: list[dict[str, Any]]) -> None:
        temp_path = self.storage_path.with_suffix(".tmp")
        temp_path.write_text(json.dumps({"items": records}, ensure_ascii=False, indent=2), encoding="utf-8")
        temp_path.replace(self.storage_path)

    def _filter_records(self, records: list[dict[str, Any]], params: dict[str, Any]) -> list[dict[str, Any]]:
        normalized_status = str(params.get("status") or "").strip().upper()
        normalized_target_ip = str(params.get("target_ip") or "").strip()
        filtered_records: list[dict[str, Any]] = []

        for item in records:
            ban = item.get("ban") or {}
            ip = item.get("ip") or {}
            current_status = str(
                ban.get("current_ban_status")
                or ban.get("current_block_status")
                or ban.get("status")
                or ("BLOCKED" if ip.get("is_blocked") else "RELEASED")
            ).strip().upper()
            ip_address = str(ip.get("ip_address") or "").strip()

            if normalized_status and current_status != normalized_status:
                continue
            if normalized_target_ip and normalized_target_ip not in ip_address:
                continue

            filtered_records.append(item)

        filtered_records.sort(
            key=lambda item: str((item.get("ban") or {}).get("updated_at") or (item.get("ban") or {}).get("executed_at") or ""),
            reverse=True,
        )
        return filtered_records

    def _hydrate_record(self, record: dict[str, Any]) -> dict[str, Any]:
        hydrated_record = deepcopy(record)
        ban = hydrated_record.setdefault("ban", {})
        alert = hydrated_record.setdefault("alert", {})
        linked_request = self._find_linked_disposal(
            str(ban.get("action_id") or "").strip(),
            str((hydrated_record.get("ip") or {}).get("ip_address") or "").strip(),
        )
        if linked_request:
            alert.setdefault("alert_id", linked_request.get("alert_id") or "")
            alert.setdefault("alert_name", linked_request.get("alert_name") or "")
            alert.setdefault("severity", linked_request.get("severity") or "")
            ban.setdefault("behavior_type", linked_request.get("alert_name") or linked_request.get("disposal_type") or "")
            ban.setdefault("block_reason", linked_request.get("review_comment") or linked_request.get("disposition_opinion") or "")
            ban.setdefault("remark", linked_request.get("review_comment") or "")
        return hydrated_record

    def _find_linked_disposal(self, action_id: str, ip_address: str) -> dict[str, Any] | None:
        state = governance_service._read_state()
        for item in state.get("disposals", []):
            linked_action_id = str(item.get("linked_ban_action_id") or "").strip()
            execution_target = str(item.get("execution_target") or item.get("source_ip") or "").strip()
            if linked_action_id and linked_action_id == action_id:
                return deepcopy(item)
            if action_id and execution_target and execution_target == ip_address and str(item.get("status") or "").strip() == "已通过":
                return deepcopy(item)
        return None

    def _upsert_block_action(self, params: dict[str, Any]) -> dict[str, Any]:
        action_id = str(params.get("action_id") or "").strip()
        target_ip = str(params.get("target_ip") or "").strip()
        target_status = str(params.get("target_status") or "BLOCKED").strip().upper()
        records = self._load_records()
        record = next(
            (item for item in records if str((item.get("ban") or {}).get("action_id") or "").strip() == action_id),
            None,
        )
        if record is None:
            record = {"ban": {}, "alert": {}, "ip": {}}
            records.insert(0, record)

        action_at = str(params.get("action_at") or "")
        action_by = str(params.get("action_by") or "")
        action_reason = str(params.get("action_reason") or "")
        enforcement_mode = str(params.get("enforcement_mode") or "MOCK").strip().upper()
        current_is_blocked = target_status == "BLOCKED"

        record["ban"] = {
            **(record.get("ban") or {}),
            "action_id": action_id,
            "action_type": str(params.get("action_type") or "BLOCK_IP"),
            "target_type": "IP",
            "status": target_status,
            "current_ban_status": target_status,
            "current_block_status": target_status,
            "block_source": str(params.get("block_source") or "manual"),
            "behavior_type": str(params.get("behavior_type") or ""),
            "source_type": str(params.get("source_type") or ""),
            "risk_score": int(params.get("risk_score") or 0),
            "confidence": float(params.get("confidence") or 0),
            "event_count": int(params.get("event_count") or 1),
            "can_block": bool(params.get("can_block", True)),
            "block_reason": action_reason,
            "latest_action_type": str(params.get("latest_action_type") or "MANUAL_BLOCK_IP"),
            "latest_action_at": action_at,
            "latest_action_by": action_by,
            "latest_action_reason": action_reason,
            "latest_operator": action_by,
            "latest_reason": action_reason,
            "updated_at": action_at,
            "executed_at": action_at,
            "executor": action_by,
            "blocked_at": action_at if current_is_blocked else str((record.get("ban") or {}).get("blocked_at") or ""),
            "blocked_by": action_by if current_is_blocked else str((record.get("ban") or {}).get("blocked_by") or ""),
            "released_at": "" if current_is_blocked else action_at,
            "released_by": "" if current_is_blocked else action_by,
            "release_reason": "" if current_is_blocked else action_reason,
            "history_actions_json": str(params.get("history_actions_json") or "[]"),
            "history_summary": str(params.get("history_summary") or ""),
            "history_action_count": int(params.get("history_action_count") or 1),
            "block_count": int(params.get("block_count") or 1),
            "release_count": int(params.get("release_count") or 0),
            "rollback_supported": True,
            "remark": action_reason,
            "ticket_no": "",
            "enforcement_mode": enforcement_mode,
            "enforcement_backend": str(params.get("enforcement_backend") or enforcement_mode),
        }
        record["ip"] = {
            **(record.get("ip") or {}),
            "ip_id": str(params.get("ip_id") or f"AUTO-IP-{target_ip.replace('.', '_')}"),
            "ip_address": target_ip,
            "ip_block_status": target_status,
            "current_block_status": target_status,
            "is_blocked": current_is_blocked,
            "latest_action_type": str(params.get("latest_action_type") or "MANUAL_BLOCK_IP"),
            "latest_action_at": action_at,
            "latest_action_by": action_by,
            "latest_action_reason": action_reason,
            "blocked_at": action_at if current_is_blocked else str((record.get("ip") or {}).get("blocked_at") or ""),
        }

        linked_request = self._find_linked_disposal(action_id, target_ip)
        if linked_request:
            record["alert"] = {
                "alert_id": linked_request.get("alert_id") or "",
                "alert_name": linked_request.get("alert_name") or "",
                "severity": linked_request.get("severity") or "",
            }

        self._save_records(records)
        return {"action_id": action_id}

    def _switch_block_status(self, params: dict[str, Any]) -> dict[str, Any]:
        action_id = str(params.get("action_id") or "").strip()
        target_status = str(params.get("target_status") or "").strip().upper()
        records = self._load_records()
        record = next(
            (item for item in records if str((item.get("ban") or {}).get("action_id") or "").strip() == action_id),
            None,
        )
        if not record:
            return {"action_id": action_id}

        action_at = str(params.get("action_at") or "")
        action_by = str(params.get("action_by") or "")
        action_reason = str(params.get("action_reason") or "")
        current_is_blocked = target_status == "BLOCKED"
        ban = record.setdefault("ban", {})
        ip = record.setdefault("ip", {})

        ban.update(
            {
                "status": target_status,
                "current_ban_status": target_status,
                "current_block_status": target_status,
                "latest_action_type": str(params.get("latest_action_type") or ban.get("latest_action_type") or ""),
                "latest_action_at": action_at,
                "latest_action_by": action_by,
                "latest_action_reason": action_reason,
                "latest_operator": action_by,
                "latest_reason": action_reason,
                "updated_at": action_at,
                "released_at": action_at if not current_is_blocked else "",
                "released_by": action_by if not current_is_blocked else "",
                "release_reason": action_reason if not current_is_blocked else "",
                "blocked_at": action_at if current_is_blocked else str(ban.get("blocked_at") or ""),
                "blocked_by": action_by if current_is_blocked else str(ban.get("blocked_by") or ""),
                "block_reason": action_reason if current_is_blocked else str(ban.get("block_reason") or ""),
                "history_actions_json": str(params.get("history_actions_json") or ban.get("history_actions_json") or "[]"),
                "history_summary": str(params.get("history_summary") or ban.get("history_summary") or ""),
                "history_action_count": int(params.get("history_action_count") or ban.get("history_action_count") or 0),
                "block_count": int(params.get("block_count") or ban.get("block_count") or 0),
                "release_count": int(params.get("release_count") or ban.get("release_count") or 0),
            }
        )
        ip.update(
            {
                "ip_block_status": target_status,
                "current_block_status": target_status,
                "is_blocked": current_is_blocked,
                "latest_action_type": str(params.get("latest_action_type") or ip.get("latest_action_type") or ""),
                "latest_action_at": action_at,
                "latest_action_by": action_by,
                "latest_action_reason": action_reason,
            }
        )
        self._save_records(records)
        return {"action_id": action_id}

    def _update_enforcement_state(self, params: dict[str, Any]) -> dict[str, Any]:
        action_id = str(params.get("action_id") or "").strip()
        records = self._load_records()
        record = next(
            (item for item in records if str((item.get("ban") or {}).get("action_id") or "").strip() == action_id),
            None,
        )
        if not record:
            return {"action_id": action_id}

        ban = record.setdefault("ban", {})
        ban.update(
            {
                "enforcement_mode": str(params.get("enforcement_mode") or ban.get("enforcement_mode") or "MOCK"),
                "enforcement_backend": str(params.get("enforcement_backend") or ban.get("enforcement_backend") or "MOCK"),
                "enforcement_status": str(params.get("enforcement_status") or ""),
                "enforcement_rule_name": str(params.get("enforcement_rule_name") or ""),
                "enforcement_message": str(params.get("enforcement_message") or ""),
                "enforcement_executed": bool(params.get("enforcement_executed", False)),
                "enforcement_success": bool(params.get("enforcement_success", False)),
                "verification_status": str(params.get("verification_status") or ""),
                "verified_at": str(params.get("verified_at") or ""),
                "verification_message": str(params.get("verification_message") or ""),
                "verification_supported": bool(params.get("verification_supported", False)),
                "verification_attempted": bool(params.get("verification_attempted", False)),
                "block_effective": bool(params.get("block_effective", False)),
                "enforcement_scope_ports": str(params.get("enforcement_scope_ports") or ""),
                "updated_at": str(params.get("updated_at") or ban.get("updated_at") or ""),
            }
        )
        self._save_records(records)
        return {"action_id": action_id}


class StaticGraphAdapter:
    def __init__(self, ban_adapter: FileBackedBanAdapter) -> None:
        self.ban_adapter = ban_adapter

    def execute_read(self, query: str, parameters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        query_text = str(query or "")
        blocked_count = len(self.ban_adapter._filter_records(self.ban_adapter._load_records(), {"status": "BLOCKED"}))

        if "MATCH (n)" in query_text and "node_total" in query_text:
            return [
                {
                    "node_total": 128,
                    "relation_total": 246,
                    "alert_total": 18,
                    "blocked_ip_total": blocked_count,
                    "high_risk_event_total": 6,
                }
            ]

        if "MATCH (a:Alert)" in query_text and "a.alert_id AS alert_id" in query_text:
            return [
                {
                    "alert_id": "ALT-BASE-001",
                    "alert_name": "异常登录集中告警",
                    "severity": "HIGH",
                    "status": "待研判",
                    "score": 92,
                    "first_seen": "2026-04-05 08:00:00",
                    "last_seen": "2026-04-06 09:20:00",
                    "event_type": "LOGIN",
                    "rule_name": "异常登录行为识别",
                    "has_block_action": blocked_count > 0,
                }
            ]

        if "MATCH (u:User)" in query_text and "risk_score" in query_text:
            return [
                {
                    "user_id": "OPS-001",
                    "username": "analyst",
                    "department": "安全运营中心",
                    "risk_score": 88,
                    "is_whitelisted": False,
                }
            ]

        if "MATCH (ip:IP)" in query_text and "ip_address AS ip_address" in query_text:
            return [
                {
                    "ip_id": "IP-001",
                    "ip_address": "10.10.10.10",
                    "ip_type": "办公终端",
                    "risk_score": 86,
                    "is_blocked": blocked_count > 0,
                }
            ]

        if "MATCH (h:Host)" in query_text:
            return [
                {
                    "host_id": "HOST-001",
                    "hostname": "SRV-APP-01",
                    "asset_type": "业务主机",
                    "critical_level": 5,
                    "risk_score": 82,
                }
            ]

        return []


def create_real_e2e_app():
    ban_adapter = FileBackedBanAdapter(prepared_paths["ban_file"])
    graph_adapter = StaticGraphAdapter(ban_adapter)

    ban_service.client = ban_adapter
    graph_service.client = graph_adapter

    app = create_app("default")
    app.config.update(
        TESTING=True,
        DEBUG=False,
    )
    return app


if __name__ == "__main__":
    app = create_real_e2e_app()
    print(f"REAL_E2E_DATA_ROOT={prepared_paths['root']}", flush=True)
    app.run(
        host=os.environ.get("FLASK_HOST", "127.0.0.1"),
        port=int(os.environ.get("FLASK_PORT", "5000")),
        debug=False,
        use_reloader=False,
    )
