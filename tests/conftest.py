from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app import create_app
from app.services.auth_service import auth_service
from app.services.ban_service import ban_service
from app.services.governance_service import governance_service


@pytest.fixture()
def app_client(tmp_path, monkeypatch):
    governance_file = tmp_path / "governance_state.json"
    session_file = tmp_path / "session_state.json"

    governance_file.write_text(
        (REPO_ROOT / "backend" / "app" / "data" / "governance_state.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    session_file.write_text(json.dumps({"sessions": []}, ensure_ascii=False, indent=2), encoding="utf-8")

    monkeypatch.setattr(governance_service, "DATA_FILE_PATH", governance_file)
    governance_service._ensure_state_file()

    monkeypatch.setattr(auth_service, "SESSION_FILE_PATH", session_file)
    auth_service._ensure_session_file()
    auth_service._session_store = auth_service._load_session_store()

    def fake_block_ip(
        target_ip: str,
        reason: str,
        *,
        source: str = "manual",
        attack_type: str = "",
        risk_score: int = 0,
        operator: str = "security_console",
        source_type: str = "",
        event_count: int = 1,
        confidence: float = 0.95,
        can_block: bool = True,
    ) -> dict:
        action_id = f"LINKED-BAN-{target_ip.replace('.', '_')}"
        return {
            "item": {
                "action_id": action_id,
                "ip_address": target_ip,
                "current_ban_status": "BLOCKED",
                "block_source": source,
                "behavior_type": attack_type,
                "risk_score": risk_score,
            },
            "message": f"已根据审批结果封禁 {target_ip}",
        }

    monkeypatch.setattr(ban_service, "block_ip", fake_block_ip)

    app = create_app()
    app.config.update(TESTING=True)

    with app.test_client() as client:
        client.governance_file = governance_file
        client.session_file = session_file
        yield client
