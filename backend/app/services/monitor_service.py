#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
文件路径：backend/app/services/monitor_service.py

文件作用：
1. 提供“日志监控中心”的核心服务逻辑。
2. 负责启动、停止并查询 scripts/log_watcher.py 的运行状态。
3. 将监控状态持久化到 data/runtime/monitor_state.json，降低 Flask Debug 重载带来的状态丢失影响。
4. 复用 data/runtime/batches/*/status.json 汇总最近处理记录，并生成“监控关系图谱”所需的拓扑数据。

设计说明：
1. 当前版本优先保持最小可运行，因此继续使用 subprocess 启动现有 log_watcher.py，不重写监听主流程。
2. 监控关系图谱不是 Neo4j Browser 的数据库点图，而是面向业务语义的“处理链路拓扑图”。
3. 拓扑图重点展示日志从 incoming 目录进入系统，到适配解析、Neo4j 入库、检测、告警、封禁预留节点的闭环链路。
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from flask import current_app

from app.core.errors import APIError


STATUS_PRIORITY = {
    "FAILED": 5,
    "ERROR": 5,
    "PARTIAL": 4,
    "WARNING": 3,
    "SUCCESS": 2,
    "ACTIVE": 2,
    "READY": 2,
    "STANDBY": 1,
    "IDLE": 0,
    "UNKNOWN": 0,
}


def build_now_text() -> str:
    """
    生成带时区的当前时间字符串。

    说明：
    1. 统一使用 ISO 8601 格式，便于前端展示和论文截图。
    2. 使用本地时区时间，更贴合本地 Windows 演示环境。
    """
    return datetime.now().astimezone().isoformat(timespec="seconds")


class MonitorService:
    """
    日志监控服务。

    核心职责：
    1. 管理 log_watcher.py 的生命周期。
    2. 提供监控配置、运行状态与最近处理记录。
    3. 生成用于前端 ECharts graph 的监控链路拓扑数据。
    """

    def get_monitor_config(self) -> Dict[str, Any]:
        """
        返回监控配置。
        """
        self._ensure_runtime_environment()

        return {
            "incoming_root": str(self._incoming_root()),
            "watch_directories": self._build_watch_directories(),
            "default_interval_seconds": self._default_interval_seconds(),
            "runtime_state_file": str(self._state_file_path()),
            "watcher_log_file": str(self._watcher_log_file_path()),
        }

    def get_monitor_status(self) -> Dict[str, Any]:
        """
        返回当前监控状态。
        """
        self._ensure_runtime_environment()

        state_data = self._sync_process_state(self._read_state_file())
        recent_payload = self._collect_recent_records()

        return {
            "running": bool(state_data.get("running")),
            "pid": state_data.get("pid"),
            "started_at": state_data.get("started_at", ""),
            "interval_seconds": state_data.get("interval_seconds", self._default_interval_seconds()),
            "watch_directories": state_data.get("watch_directories") or self._build_watch_directories(),
            "processed_file_count": recent_payload["processed_file_count"],
            "latest_processed_at": recent_payload["latest_processed_at"],
            "latest_detection_status": recent_payload["latest_detection_status"],
            "recent_records": recent_payload["recent_records"],
        }

    def get_monitor_topology(self) -> Dict[str, Any]:
        """
        返回“监控关系图谱”的拓扑数据。
        """
        self._ensure_runtime_environment()

        state_data = self._sync_process_state(self._read_state_file())
        recent_batches = self._collect_recent_batch_payloads(limit=min(max(self._recent_record_limit(), 4), 6))
        return self._build_monitor_topology(recent_batches=recent_batches, state_data=state_data)

    def start_monitor(self, interval_seconds: Optional[int] = None) -> Dict[str, Any]:
        """
        启动日志监听任务。
        """
        self._ensure_runtime_environment()

        resolved_interval = max(1, int(interval_seconds or self._default_interval_seconds()))
        current_state = self._sync_process_state(self._read_state_file())
        if current_state.get("running") and current_state.get("pid"):
            return self.get_monitor_status()

        watcher_command = [
            sys.executable,
            str(self._watcher_script_path()),
            "--interval",
            str(resolved_interval),
        ]

        env_mapping = os.environ.copy()
        env_mapping["PYTHONIOENCODING"] = "utf-8"

        log_file_path = self._watcher_log_file_path()
        log_file_path.parent.mkdir(parents=True, exist_ok=True)

        popen_kwargs: Dict[str, Any] = {
            "cwd": str(self._repo_root()),
            "stdout": None,
            "stderr": None,
            "env": env_mapping,
        }

        if os.name == "nt":
            creation_flags = 0
            if hasattr(subprocess, "CREATE_NEW_PROCESS_GROUP"):
                creation_flags |= subprocess.CREATE_NEW_PROCESS_GROUP
            if hasattr(subprocess, "DETACHED_PROCESS"):
                creation_flags |= subprocess.DETACHED_PROCESS
            popen_kwargs["creationflags"] = creation_flags
        else:
            popen_kwargs["start_new_session"] = True

        with log_file_path.open("a", encoding="utf-8") as log_file:
            log_file.write(
                f"\n[{build_now_text()}] [monitor_service] 尝试启动 log_watcher，命令：{' '.join(watcher_command)}\n"
            )
            log_file.flush()
            popen_kwargs["stdout"] = log_file
            popen_kwargs["stderr"] = log_file
            watcher_process = subprocess.Popen(watcher_command, **popen_kwargs)

        time.sleep(1)
        if watcher_process.poll() is not None:
            error_detail = self._tail_log_file(log_file_path)
            failed_state = self._build_default_state()
            failed_state.update(
                {
                    "running": False,
                    "pid": None,
                    "started_at": "",
                    "interval_seconds": resolved_interval,
                    "last_action": "START_FAILED",
                    "last_error": error_detail,
                    "updated_at": build_now_text(),
                }
            )
            self._write_state_file(failed_state)
            raise APIError(
                message="日志监控任务启动失败，请检查 log_watcher.py 或运行环境配置",
                code=5002,
                http_status=500,
                data={"detail": error_detail},
            )

        started_state = self._build_default_state()
        started_state.update(
            {
                "running": True,
                "pid": watcher_process.pid,
                "started_at": build_now_text(),
                "interval_seconds": resolved_interval,
                "watch_directories": self._build_watch_directories(),
                "last_action": "STARTED",
                "last_error": "",
                "updated_at": build_now_text(),
            }
        )
        self._write_state_file(started_state)

        return self.get_monitor_status()

    def stop_monitor(self) -> Dict[str, Any]:
        """
        停止日志监听任务。
        """
        self._ensure_runtime_environment()

        state_data = self._sync_process_state(self._read_state_file())
        target_pid = state_data.get("pid")

        if not target_pid:
            stopped_state = self._build_default_state()
            stopped_state.update(
                {
                    "running": False,
                    "pid": None,
                    "started_at": state_data.get("started_at", ""),
                    "interval_seconds": state_data.get("interval_seconds", self._default_interval_seconds()),
                    "watch_directories": state_data.get("watch_directories") or self._build_watch_directories(),
                    "last_action": "STOPPED",
                    "last_error": "",
                    "updated_at": build_now_text(),
                }
            )
            self._write_state_file(stopped_state)
            return self.get_monitor_status()

        stop_success, stop_message = self._terminate_process(int(target_pid))
        if not stop_success:
            raise APIError(
                message="日志监控任务停止失败",
                code=5003,
                http_status=500,
                data={"detail": stop_message, "pid": target_pid},
            )

        stopped_state = self._build_default_state()
        stopped_state.update(
            {
                "running": False,
                "pid": None,
                "started_at": "",
                "interval_seconds": state_data.get("interval_seconds", self._default_interval_seconds()),
                "watch_directories": state_data.get("watch_directories") or self._build_watch_directories(),
                "last_action": "STOPPED",
                "last_error": "",
                "updated_at": build_now_text(),
            }
        )
        self._write_state_file(stopped_state)

        return self.get_monitor_status()

    def _repo_root(self) -> Path:
        """
        返回项目根目录。
        """
        return Path(__file__).resolve().parents[3]

    def _incoming_root(self) -> Path:
        """
        返回 incoming 根目录。
        """
        return Path(current_app.config["MONITOR_INCOMING_ROOT"])

    def _batch_root(self) -> Path:
        """
        返回批次状态目录。
        """
        return Path(current_app.config["MONITOR_BATCH_ROOT"])

    def _state_file_path(self) -> Path:
        """
        返回 monitor_state.json 路径。
        """
        return Path(current_app.config["MONITOR_STATE_FILE"])

    def _watcher_log_file_path(self) -> Path:
        """
        返回 watcher 日志文件路径。
        """
        return Path(current_app.config["MONITOR_WATCHER_LOG_FILE"])

    def _watcher_script_path(self) -> Path:
        """
        返回 log_watcher.py 脚本路径。
        """
        return self._repo_root() / "scripts" / "log_watcher.py"

    def _default_interval_seconds(self) -> int:
        """
        返回默认监听间隔。
        """
        return int(current_app.config["MONITOR_DEFAULT_INTERVAL_SECONDS"])

    def _recent_record_limit(self) -> int:
        """
        返回最近记录数量上限。
        """
        return int(current_app.config["MONITOR_RECENT_RECORD_LIMIT"])

    def _build_watch_directories(self) -> List[str]:
        """
        根据配置展开监听目录绝对路径列表。
        """
        incoming_root = self._incoming_root()
        directory_names = list(current_app.config.get("MONITOR_WATCH_DIRECTORIES", []))
        return [str(incoming_root / item_name) for item_name in directory_names]

    def _ensure_runtime_environment(self) -> None:
        """
        确保运行时目录存在。
        """
        self._incoming_root().mkdir(parents=True, exist_ok=True)
        self._batch_root().mkdir(parents=True, exist_ok=True)
        self._state_file_path().parent.mkdir(parents=True, exist_ok=True)
        self._watcher_log_file_path().parent.mkdir(parents=True, exist_ok=True)

    def _build_default_state(self) -> Dict[str, Any]:
        """
        构造默认监控状态。
        """
        return {
            "running": False,
            "pid": None,
            "started_at": "",
            "interval_seconds": self._default_interval_seconds(),
            "watch_directories": self._build_watch_directories(),
            "last_action": "",
            "last_error": "",
            "updated_at": build_now_text(),
        }

    def _read_state_file(self) -> Dict[str, Any]:
        """
        读取 monitor_state.json。

        容错策略：
        1. 文件不存在时返回默认状态。
        2. 文件损坏时记录日志并回退到默认状态，避免状态接口直接崩溃。
        """
        state_file_path = self._state_file_path()
        if not state_file_path.exists():
            return self._build_default_state()

        try:
            loaded_data = json.loads(state_file_path.read_text(encoding="utf-8"))
        except Exception as exc:  # pragma: no cover - 仅在文件损坏时触发
            current_app.logger.warning("读取监控状态文件失败，已回退默认状态：%s", exc)
            return self._build_default_state()

        if not isinstance(loaded_data, dict):
            return self._build_default_state()

        default_state = self._build_default_state()
        default_state.update(loaded_data)
        return default_state

    def _write_state_file(self, state_data: Dict[str, Any]) -> None:
        """
        将监控状态写回 monitor_state.json。
        """
        state_file_path = self._state_file_path()
        state_file_path.parent.mkdir(parents=True, exist_ok=True)
        state_file_path.write_text(
            json.dumps(state_data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _sync_process_state(self, state_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        校正 monitor_state.json 中记录的运行状态。

        作用：
        1. 如果状态文件记录为 running，但 PID 实际已退出，则自动纠正。
        2. 这样即使 Flask Debug 重载或 watcher 异常退出，前端也能尽量看到真实状态。
        """
        normalized_state = self._build_default_state()
        normalized_state.update(state_data or {})

        current_pid = normalized_state.get("pid")
        if normalized_state.get("running") and current_pid:
            if not self._is_process_running(int(current_pid)):
                normalized_state["running"] = False
                normalized_state["pid"] = None
                normalized_state["last_action"] = "STALE_RESET"
                normalized_state["last_error"] = "检测到 watcher 进程已退出，状态已自动纠正"
                normalized_state["updated_at"] = build_now_text()
                self._write_state_file(normalized_state)

        return normalized_state

    def _is_process_running(self, pid: int) -> bool:
        """
        判断目标 PID 是否仍在运行。

        Windows：
        1. 使用 tasklist 通过 PID 查询。

        Linux / macOS：
        1. 使用 os.kill(pid, 0) 探测进程是否存在。
        """
        if pid <= 0:
            return False

        if os.name == "nt":
            completed = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="ignore",
            )
            output_text = (completed.stdout or "").strip()
            if not output_text:
                return False
            if output_text.startswith("INFO:") or "No tasks are running" in output_text:
                return False
            return str(pid) in output_text

        try:
            os.kill(pid, 0)
        except OSError:
            return False

        return True

    def _terminate_process(self, pid: int) -> tuple[bool, str]:
        """
        停止指定 PID 的 watcher 进程。

        返回值：
        1. 布尔值表示是否停止成功。
        2. 文本说明用于接口报错排查。
        """
        if pid <= 0:
            return True, ""

        if not self._is_process_running(pid):
            return True, "目标进程已不存在"

        try:
            if os.name == "nt":
                completed = subprocess.run(
                    ["taskkill", "/PID", str(pid), "/T", "/F"],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="ignore",
                )
                message_text = ((completed.stdout or "") + "\n" + (completed.stderr or "")).strip()
            else:
                try:
                    os.killpg(os.getpgid(pid), signal.SIGTERM)
                except Exception:
                    os.kill(pid, signal.SIGTERM)
                message_text = "已发送 SIGTERM 停止信号"
        except Exception as exc:  # pragma: no cover - 仅在系统终止命令异常时触发
            return False, str(exc)

        for _ in range(8):
            if not self._is_process_running(pid):
                return True, message_text
            time.sleep(0.25)

        return False, message_text or "进程停止超时"

    def _tail_log_file(self, log_file_path: Path, max_lines: int = 20) -> str:
        """
        读取 watcher 日志文件的最后若干行。

        用途：
        1. 当 watcher 启动失败时，把最后日志片段返回给前端。
        2. 便于快速排查启动异常。
        """
        if not log_file_path.exists():
            return ""

        try:
            log_lines = log_file_path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except Exception:  # pragma: no cover - 仅读日志失败场景
            return ""

        return "\n".join(log_lines[-max_lines:])

    def _collect_recent_batch_payloads(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        收集最近批次的原始状态信息，并补充拓扑图所需的派生字段。

        返回字段示例：
        1. batch_id、source_file、source_directory_name
        2. adapter_id、adapter_name
        3. batch_status、detection_status、pipeline_status
        4. parse_error_count、failed_step、processed_at
        """
        batch_root = self._batch_root()
        if not batch_root.exists():
            return []

        status_files = sorted(
            batch_root.rglob("status.json"),
            key=lambda item: item.stat().st_mtime,
            reverse=True,
        )
        if limit is not None:
            status_files = status_files[:limit]

        batch_payloads: List[Dict[str, Any]] = []
        for status_file_path in status_files:
            try:
                payload = json.loads(status_file_path.read_text(encoding="utf-8"))
            except Exception as exc:  # pragma: no cover - 仅在状态文件损坏时触发
                current_app.logger.warning("读取批次状态文件失败：%s", exc)
                continue

            if not isinstance(payload, dict):
                continue

            batch_payloads.append(self._normalize_batch_payload(status_file_path, payload))

        return batch_payloads

    def _normalize_batch_payload(self, status_file_path: Path, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        将 status.json 统一整理为前端和拓扑构建更容易消费的结构。
        """
        source_file = str(payload.get("source_file", "") or "")
        source_path = Path(source_file) if source_file else None
        source_directory_name = source_path.parent.name if source_path else self._infer_directory_name_from_batch(
            status_file_path.parent.name
        )
        source_file_name = source_path.name if source_path else ""

        batch_status = str(payload.get("status", "UNKNOWN") or "UNKNOWN").upper()
        detection_status = self._resolve_detection_status(payload)
        pipeline_status = self._resolve_pipeline_status(
            batch_status=batch_status,
            detection_status=detection_status,
            parse_error_count=int(payload.get("parse_error_count", 0) or 0),
            failed_step=str(payload.get("failed_step", "") or "").strip(),
        )
        adapter_metadata = self._resolve_adapter_metadata(source_directory_name)

        return {
            "batch_id": status_file_path.parent.name,
            "status_file": str(status_file_path),
            "processed_at": datetime.fromtimestamp(status_file_path.stat().st_mtime)
            .astimezone()
            .isoformat(timespec="seconds"),
            "batch_status": batch_status,
            "detection_status": detection_status,
            "pipeline_status": pipeline_status,
            "source_file": source_file,
            "source_file_name": source_file_name,
            "source_directory_name": source_directory_name,
            "archived_file": str(payload.get("archived_file", "") or ""),
            "normalized_file": str(payload.get("normalized_file", "") or ""),
            "raw_files": payload.get("raw_files", []) or [],
            "processed_dir": str(payload.get("processed_dir", "") or ""),
            "parse_error_count": int(payload.get("parse_error_count", 0) or 0),
            "parse_warning_file": str(payload.get("parse_warning_file", "") or ""),
            "failed_step": str(payload.get("failed_step", "") or "").strip(),
            "outputs": payload.get("outputs", {}) or {},
            "adapter_id": adapter_metadata["adapter_id"],
            "adapter_name": adapter_metadata["adapter_name"],
            "adapter_script": adapter_metadata["adapter_script"],
        }

    def _collect_recent_records(self) -> Dict[str, Any]:
        """
        扫描批次状态文件并汇总最近处理记录。
        """
        batch_payloads = self._collect_recent_batch_payloads(limit=self._recent_record_limit())
        if not batch_payloads:
            return {
                "processed_file_count": 0,
                "latest_processed_at": "",
                "latest_detection_status": "IDLE",
                "recent_records": [],
            }

        recent_records = [
            {
                "batch_id": payload["batch_id"],
                "source_file": payload["source_file"],
                "status": payload["batch_status"],
                "processed_at": payload["processed_at"],
                "failed_step": payload["failed_step"],
                "parse_error_count": payload["parse_error_count"],
                "detection_status": payload["detection_status"],
            }
            for payload in batch_payloads
        ]

        return {
            "processed_file_count": len(batch_payloads),
            "latest_processed_at": batch_payloads[0]["processed_at"],
            "latest_detection_status": batch_payloads[0]["detection_status"],
            "recent_records": recent_records,
        }

    def _resolve_detection_status(self, payload: Dict[str, Any]) -> str:
        """
        根据批次状态推断检测执行状态。

        规则：
        1. 整个批次 SUCCESS 时，视为检测成功。
        2. failed_step 为 run_detection 时，视为检测失败。
        3. 其他失败一般表示检测步骤尚未执行，返回 NOT_RUN。
        """
        batch_status = str(payload.get("status", "")).upper()
        failed_step = str(payload.get("failed_step", "")).strip()

        if batch_status == "SUCCESS":
            return "SUCCESS"
        if failed_step == "run_detection":
            return "FAILED"
        if failed_step:
            return "NOT_RUN"
        return "UNKNOWN"

    def _resolve_pipeline_status(
        self,
        batch_status: str,
        detection_status: str,
        parse_error_count: int,
        failed_step: str,
    ) -> str:
        """
        根据批次结果计算整条监控链路的状态。

        含义：
        1. SUCCESS：解析、入库、检测链路已顺利完成。
        2. FAILED：链路在某一步明确失败。
        3. PARTIAL：主流程完成但存在解析异常或检测未执行。
        """
        if batch_status != "SUCCESS" or detection_status == "FAILED":
            return "FAILED"
        if failed_step:
            return "FAILED"
        if parse_error_count > 0 or detection_status == "NOT_RUN":
            return "PARTIAL"
        if batch_status == "SUCCESS":
            return "SUCCESS"
        return "UNKNOWN"

    def _infer_directory_name_from_batch(self, batch_id: str) -> str:
        """
        当 source_file 缺失时，从 batch_id 尝试推断目录名称。
        """
        configured_names = [Path(item).name for item in self._build_watch_directories()]
        for directory_name in configured_names:
            if directory_name and directory_name in batch_id:
                return directory_name
        return "unknown_source"

    def _resolve_adapter_metadata(self, source_directory_name: str) -> Dict[str, str]:
        """
        根据 source 目录名称映射适配器信息。
        """
        adapter_mapping = {
            "safeline_waf": {
                "adapter_id": "adapter_safeline_waf",
                "adapter_name": "雷池 WAF 适配器",
                "adapter_script": "safe_line_waf_adapter.py",
            },
            "n9e_waf": {
                "adapter_id": "adapter_generic_waf",
                "adapter_name": "通用 WAF 适配器",
                "adapter_script": "generic_waf_adapter.py",
            },
            "windows_firewall": {
                "adapter_id": "adapter_windows_firewall",
                "adapter_name": "Windows 防火墙适配器",
                "adapter_script": "windows_firewall_adapter.py",
            },
            "linux_firewall": {
                "adapter_id": "adapter_linux_firewall",
                "adapter_name": "Linux 防火墙适配器",
                "adapter_script": "linux_firewall_adapter.py",
            },
        }

        return adapter_mapping.get(
            source_directory_name,
            {
                "adapter_id": "adapter_unknown_source",
                "adapter_name": "通用日志适配器",
                "adapter_script": "generic_waf_adapter.py",
            },
        )

    def _build_monitor_topology(
        self,
        recent_batches: List[Dict[str, Any]],
        state_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        构造监控处理链路拓扑图。

        节点类型：
        1. incoming 根目录
        2. 监听子目录
        3. 最近处理文件
        4. 适配器
        5. Neo4j
        6. 检测引擎
        7. 告警
        8. 封禁动作
        """
        nodes_by_id: Dict[str, Dict[str, Any]] = {}
        links_by_key: Dict[str, Dict[str, Any]] = {}

        watch_directories = self._build_watch_directories()
        incoming_root_id = "node_incoming_root"
        neo4j_node_id = "node_neo4j"
        detection_node_id = "node_detection_engine"
        alert_node_id = "node_alert_center"
        ban_node_id = "node_ban_action"

        latest_success_batch_id = next(
            (item["batch_id"] for item in recent_batches if item["pipeline_status"] == "SUCCESS"),
            "",
        )
        latest_failed_batch_id = next(
            (item["batch_id"] for item in recent_batches if item["pipeline_status"] == "FAILED"),
            "",
        )

        def add_node(
            node_id: str,
            name: str,
            node_type: str,
            status: str,
            stage: int,
            lane: int = 0,
            symbol_size: int = 52,
            detail_lines: Optional[List[str]] = None,
        ) -> None:
            """
            向节点集合中写入节点。

            节点去重策略：
            1. 相同 node_id 只保留一个节点。
            2. 如果后续写入的状态更严重，则升级已有节点状态。
            """
            normalized_status = status or "UNKNOWN"
            existing_node = nodes_by_id.get(node_id)
            if not existing_node:
                nodes_by_id[node_id] = {
                    "id": node_id,
                    "name": name,
                    "type": node_type,
                    "status": normalized_status,
                    "stage": stage,
                    "lane": lane,
                    "symbolSize": symbol_size,
                    "detail_lines": detail_lines or [],
                }
                return

            if self._status_priority(normalized_status) > self._status_priority(existing_node.get("status", "UNKNOWN")):
                existing_node["status"] = normalized_status

            if detail_lines:
                existing_lines = existing_node.setdefault("detail_lines", [])
                for line in detail_lines:
                    if line not in existing_lines:
                        existing_lines.append(line)

        def add_link(
            source: str,
            target: str,
            relation: str,
            status: str,
            detail_lines: Optional[List[str]] = None,
            highlight: bool = False,
            dashed: bool = False,
        ) -> None:
            """
            向链路集合中写入关系边。

            边去重策略：
            1. source + target + relation 相同视为同一条业务边。
            2. 若后续状态更严重，则覆盖之前状态。
            """
            link_key = f"{source}|{target}|{relation}"
            normalized_status = status or "UNKNOWN"
            existing_link = links_by_key.get(link_key)
            if not existing_link:
                links_by_key[link_key] = {
                    "source": source,
                    "target": target,
                    "relation": relation,
                    "status": normalized_status,
                    "detail_lines": detail_lines or [],
                    "highlight": bool(highlight),
                    "dashed": bool(dashed),
                }
                return

            if self._status_priority(normalized_status) > self._status_priority(existing_link.get("status", "UNKNOWN")):
                existing_link["status"] = normalized_status
            if highlight:
                existing_link["highlight"] = True
            if dashed:
                existing_link["dashed"] = True
            if detail_lines:
                existing_lines = existing_link.setdefault("detail_lines", [])
                for line in detail_lines:
                    if line not in existing_lines:
                        existing_lines.append(line)

        add_node(
            node_id=incoming_root_id,
            name="incoming 根目录",
            node_type="incoming_root",
            status="ACTIVE" if state_data.get("running") else "IDLE",
            stage=0,
            lane=0,
            symbol_size=68,
            detail_lines=[
                f"目录路径：{self._incoming_root()}",
                f"当前状态：{'运行中' if state_data.get('running') else '未启动'}",
                f"监听目录数：{len(watch_directories)}",
            ],
        )

        for directory_index, directory_path in enumerate(watch_directories):
            directory_name = Path(directory_path).name
            directory_node_id = f"node_watch_directory::{directory_name}"
            add_node(
                node_id=directory_node_id,
                name=directory_name,
                node_type="watch_directory",
                status="ACTIVE" if state_data.get("running") else "STANDBY",
                stage=1,
                lane=directory_index,
                symbol_size=54,
                detail_lines=[
                    f"监听目录：{directory_path}",
                    f"日志源类型：{directory_name}",
                ],
            )
            add_link(
                source=incoming_root_id,
                target=directory_node_id,
                relation="目录包含",
                status="ACTIVE" if state_data.get("running") else "STANDBY",
                detail_lines=[f"根目录持续扫描子目录：{directory_name}"],
            )

        add_node(
            node_id=neo4j_node_id,
            name="Neo4j",
            node_type="neo4j",
            status="ACTIVE" if state_data.get("running") else "STANDBY",
            stage=4,
            lane=0,
            symbol_size=72,
            detail_lines=[
                "作用：承载企业安全图谱节点与关系",
                "当前链路：解析后的结构化数据写入图数据库",
            ],
        )
        add_node(
            node_id=detection_node_id,
            name="检测引擎",
            node_type="detection_engine",
            status="ACTIVE" if state_data.get("running") else "STANDBY",
            stage=5,
            lane=0,
            symbol_size=68,
            detail_lines=[
                "作用：执行 detection_service 风险检测与评分",
                "当前脚本：scripts/run_detection.py",
            ],
        )
        add_node(
            node_id=alert_node_id,
            name="告警",
            node_type="alert",
            status="ACTIVE" if recent_batches else "STANDBY",
            stage=6,
            lane=0,
            symbol_size=62,
            detail_lines=[
                "作用：汇聚检测输出并提供告警展示",
                "当前前端：告警管理页与仪表盘都可查看",
            ],
        )
        add_node(
            node_id=ban_node_id,
            name="封禁动作",
            node_type="ban_action",
            status="READY" if recent_batches else "STANDBY",
            stage=7,
            lane=0,
            symbol_size=58,
            detail_lines=[
                "作用：表示告警后的联动封禁环节",
                "当前阶段：监控拓扑中展示预留闭环，不在本轮执行真实自动封禁",
            ],
        )

        add_link(
            source=neo4j_node_id,
            target=detection_node_id,
            relation="触发检测",
            status="ACTIVE" if state_data.get("running") else "STANDBY",
            detail_lines=["Neo4j 中的新入库数据会被检测脚本进一步分析"],
        )
        add_link(
            source=detection_node_id,
            target=alert_node_id,
            relation="生成告警",
            status="ACTIVE" if recent_batches else "STANDBY",
            detail_lines=["风险评分与规则命中结果会写回 Alert 节点"],
        )
        add_link(
            source=alert_node_id,
            target=ban_node_id,
            relation="联动封禁",
            status="READY" if recent_batches else "STANDBY",
            detail_lines=["当前作为闭环预留节点，用于展示后续自动封禁能力"],
            dashed=True,
        )

        for lane_index, batch_item in enumerate(recent_batches):
            batch_id = batch_item["batch_id"]
            source_directory_name = batch_item["source_directory_name"] or "unknown_source"
            directory_node_id = f"node_watch_directory::{source_directory_name}"
            file_node_id = f"node_log_file::{batch_id}"
            adapter_node_id = batch_item["adapter_id"]

            is_latest_success = batch_id == latest_success_batch_id
            is_latest_failed = batch_id == latest_failed_batch_id
            link_highlight = is_latest_success or is_latest_failed

            file_status = batch_item["pipeline_status"]
            adapter_status = "FAILED" if batch_item["pipeline_status"] == "FAILED" else "SUCCESS"
            neo4j_status = "FAILED" if batch_item["failed_step"] == "import_to_neo4j" else (
                "SUCCESS" if batch_item["batch_status"] == "SUCCESS" else batch_item["pipeline_status"]
            )
            detection_status = (
                "FAILED"
                if batch_item["detection_status"] == "FAILED"
                else "SUCCESS"
                if batch_item["detection_status"] == "SUCCESS"
                else "PARTIAL"
            )

            add_node(
                node_id=file_node_id,
                name=batch_item["source_file_name"] or batch_id,
                node_type="log_file",
                status=file_status,
                stage=2,
                lane=lane_index,
                symbol_size=48,
                detail_lines=[
                    f"批次编号：{batch_id}",
                    f"原始文件：{batch_item['source_file'] or '-'}",
                    f"处理时间：{batch_item['processed_at']}",
                    f"处理状态：{batch_item['batch_status']}",
                    f"检测状态：{batch_item['detection_status']}",
                    f"解析异常数：{batch_item['parse_error_count']}",
                    f"失败步骤：{batch_item['failed_step'] or '-'}",
                ],
            )
            add_node(
                node_id=adapter_node_id,
                name=batch_item["adapter_name"],
                node_type="adapter",
                status=adapter_status,
                stage=3,
                lane=lane_index,
                symbol_size=56,
                detail_lines=[
                    f"适配器脚本：scripts/adapters/{batch_item['adapter_script']}",
                    f"适配目录：{source_directory_name}",
                ],
            )

            add_link(
                source=directory_node_id,
                target=file_node_id,
                relation="目录包含文件",
                status=file_status,
                detail_lines=[
                    f"批次编号：{batch_id}",
                    f"最近处理文件：{batch_item['source_file_name'] or batch_id}",
                ],
                highlight=link_highlight,
            )
            add_link(
                source=file_node_id,
                target=adapter_node_id,
                relation="文件由适配器解析",
                status=file_status,
                detail_lines=[
                    f"适配器：{batch_item['adapter_name']}",
                    f"解析异常数：{batch_item['parse_error_count']}",
                ],
                highlight=link_highlight,
            )
            add_link(
                source=adapter_node_id,
                target=neo4j_node_id,
                relation="解析结果写入 Neo4j",
                status=neo4j_status,
                detail_lines=[
                    f"标准化文件：{batch_item['normalized_file'] or '-'}",
                    f"失败步骤：{batch_item['failed_step'] or '-'}",
                ],
                highlight=link_highlight,
            )
            add_link(
                source=neo4j_node_id,
                target=detection_node_id,
                relation="Neo4j 数据触发检测",
                status=detection_status,
                detail_lines=[
                    f"批次编号：{batch_id}",
                    f"检测状态：{batch_item['detection_status']}",
                ],
                highlight=link_highlight,
            )
            add_link(
                source=detection_node_id,
                target=alert_node_id,
                relation="检测生成告警",
                status=detection_status,
                detail_lines=[
                    f"批次编号：{batch_id}",
                    f"链路状态：{batch_item['pipeline_status']}",
                ],
                highlight=link_highlight,
            )

            if batch_item["pipeline_status"] == "SUCCESS":
                add_link(
                    source=alert_node_id,
                    target=ban_node_id,
                    relation="告警联动封禁",
                    status="READY",
                    detail_lines=[
                        f"最近成功批次：{batch_id}",
                        "说明：当前页面展示封禁闭环的业务位置，真实自动封禁仍作为后续阶段能力",
                    ],
                    highlight=is_latest_success,
                    dashed=True,
                )

        categories = [
            {"name": "incoming_root", "label": "Incoming 根目录"},
            {"name": "watch_directory", "label": "监听目录"},
            {"name": "log_file", "label": "最近处理文件"},
            {"name": "adapter", "label": "日志适配器"},
            {"name": "neo4j", "label": "Neo4j"},
            {"name": "detection_engine", "label": "检测引擎"},
            {"name": "alert", "label": "告警"},
            {"name": "ban_action", "label": "封禁动作"},
        ]

        success_count = sum(1 for item in recent_batches if item["pipeline_status"] == "SUCCESS")
        failed_count = sum(1 for item in recent_batches if item["pipeline_status"] == "FAILED")
        partial_count = sum(1 for item in recent_batches if item["pipeline_status"] == "PARTIAL")

        return {
            "nodes": list(nodes_by_id.values()),
            "links": list(links_by_key.values()),
            "categories": categories,
            "summary": {
                "displayed_batch_count": len(recent_batches),
                "success_batch_count": success_count,
                "failed_batch_count": failed_count,
                "partial_batch_count": partial_count,
                "latest_success_batch_id": latest_success_batch_id,
                "latest_failed_batch_id": latest_failed_batch_id,
                "running": bool(state_data.get("running")),
            },
        }

    def _status_priority(self, status: str) -> int:
        """
        返回状态优先级，用于节点和边合并时决定覆盖顺序。
        """
        return STATUS_PRIORITY.get(str(status or "UNKNOWN").upper(), 0)


monitor_service = MonitorService()
