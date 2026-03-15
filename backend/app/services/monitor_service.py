#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
文件路径：backend/app/services/monitor_service.py

文件作用：
1. 提供“日志监控控制中心”的核心服务逻辑。
2. 负责启动与停止 scripts/log_watcher.py 监听进程。
3. 将监控运行状态持久化到 data/runtime/monitor_state.json，尽量降低 Flask Debug 重载造成的状态丢失问题。
4. 复用 data/runtime/batches/*/status.json，汇总最近处理记录、最近检测状态与处理统计信息。

设计说明：
1. 当前轮次优先实现“最小可运行版本”，因此仍沿用 subprocess 启动现有 log_watcher.py，而不是重写为复杂线程或任务队列。
2. 服务层尽量保持“无状态”，所有关键状态均落盘到 monitor_state.json，便于接口在应用重载后恢复判断。
3. 为兼容 Windows 本地演示环境，启动与停止进程时同时考虑 Windows 和 Linux 的差异。
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


def build_now_text() -> str:
    """
    生成带时区信息的当前时间字符串。

    说明：
    1. 统一使用 ISO 8601 格式，便于前端展示、日志排查和论文截图。
    2. 使用本地时区时间，贴合 Windows 本地演示环境的直观感受。
    """
    return datetime.now().astimezone().isoformat(timespec="seconds")


class MonitorService:
    """
    日志监控服务。

    核心职责：
    1. 管理 log_watcher.py 的启动、停止与状态查询。
    2. 读取批次执行结果，向前端提供“最近处理记录”与“最近检测状态”。
    3. 将监控进程状态写入 monitor_state.json，作为前后端联调的稳定状态源。
    """

    def get_monitor_config(self) -> Dict[str, Any]:
        """
        返回监控配置。

        接口用途：
        1. 供前端“日志监控中心”展示当前监听根目录和子目录。
        2. 供前端获知默认轮询间隔、状态文件位置和 watcher 日志文件位置。
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

        返回内容：
        1. 监控是否正在运行、当前 watcher PID、启动时间和轮询间隔。
        2. 监听目录列表。
        3. 复用 data/runtime/batches 下的状态文件，整理最近处理记录和最近检测状态。
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

    def start_monitor(self, interval_seconds: Optional[int] = None) -> Dict[str, Any]:
        """
        启动日志监听任务。

        实现策略：
        1. 通过 subprocess 启动现有 scripts/log_watcher.py。
        2. 监听模式使用 --interval N，不改写 watcher 主流程。
        3. 启动成功后把进程 PID 与配置写入 monitor_state.json。
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

        # 等待极短时间，确认进程没有启动即退出。
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
                message="日志监控任务启动失败，请检查 log_watcher.py 或 Neo4j 环境配置",
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

        实现策略：
        1. 优先读取 monitor_state.json 中记录的 PID。
        2. Windows 下使用 taskkill，Linux / macOS 下使用 kill/killpg。
        3. 停止后更新 monitor_state.json，避免前端仍显示为运行中。
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

        monitor_service.py 位于 backend/app/services 下，因此回溯三级即可到达项目根目录。
        """
        return Path(__file__).resolve().parents[3]

    def _incoming_root(self) -> Path:
        """
        返回 incoming 根目录。
        """
        return Path(current_app.config["MONITOR_INCOMING_ROOT"])

    def _batch_root(self) -> Path:
        """
        返回 log_watcher 批次输出目录。
        """
        return Path(current_app.config["MONITOR_BATCH_ROOT"])

    def _state_file_path(self) -> Path:
        """
        返回监控状态文件路径。
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
        返回最近记录返回数量限制。
        """
        return int(current_app.config["MONITOR_RECENT_RECORD_LIMIT"])

    def _build_watch_directories(self) -> List[str]:
        """
        根据配置生成完整监听目录列表。

        说明：
        1. 配置中保存的是子目录名称，便于部署时替换 incoming 根路径。
        2. 返回时统一展开为绝对路径，便于前端直接展示。
        """
        incoming_root = self._incoming_root()
        directory_names = list(current_app.config.get("MONITOR_WATCH_DIRECTORIES", []))
        return [str(incoming_root / item_name) for item_name in directory_names]

    def _ensure_runtime_environment(self) -> None:
        """
        确保运行期目录存在。

        当前最小可运行版本至少需要：
        1. data/runtime/
        2. data/runtime/batches/
        3. data/runtime/monitor_state.json 所在目录
        4. data/runtime/monitor_watcher.log 所在目录
        """
        self._incoming_root().mkdir(parents=True, exist_ok=True)
        self._batch_root().mkdir(parents=True, exist_ok=True)
        self._state_file_path().parent.mkdir(parents=True, exist_ok=True)
        self._watcher_log_file_path().parent.mkdir(parents=True, exist_ok=True)

    def _build_default_state(self) -> Dict[str, Any]:
        """
        构造默认监控状态结构。
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

        容错说明：
        1. 如果文件不存在，则返回默认状态。
        2. 如果文件损坏，则记录日志并回退到默认状态，避免状态接口直接崩溃。
        """
        state_file_path = self._state_file_path()
        if not state_file_path.exists():
            return self._build_default_state()

        try:
            loaded_data = json.loads(state_file_path.read_text(encoding="utf-8"))
        except Exception as exc:
            current_app.logger.warning("读取监控状态文件失败，已回退默认状态：%s", exc)
            return self._build_default_state()

        if not isinstance(loaded_data, dict):
            return self._build_default_state()

        default_state = self._build_default_state()
        default_state.update(loaded_data)
        return default_state

    def _write_state_file(self, state_data: Dict[str, Any]) -> None:
        """
        将状态写回 monitor_state.json。
        """
        state_file_path = self._state_file_path()
        state_file_path.parent.mkdir(parents=True, exist_ok=True)
        state_file_path.write_text(
            json.dumps(state_data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _sync_process_state(self, state_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        校正 monitor_state.json 中的运行状态。

        作用：
        1. 如果 state 文件记录为 running，但 PID 实际已不存在，则自动纠正为未运行。
        2. 这样即使 Flask Debug 重载或 watcher 异常退出，状态接口仍能尽量给出准确结果。
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
        判断进程是否仍在运行。

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
        2. 字符串返回停止过程中的关键信息，便于接口报错排查。
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
        except Exception as exc:
            return False, str(exc)

        # 给子进程一个短暂的退出时间窗口，再次确认是否停止。
        for _ in range(8):
            if not self._is_process_running(pid):
                return True, message_text
            time.sleep(0.25)

        return False, message_text or "进程停止超时"

    def _tail_log_file(self, log_file_path: Path, max_lines: int = 20) -> str:
        """
        读取 watcher 日志文件的最后若干行。

        用途：
        1. 当 watcher 启动失败时，把最后的错误片段放回接口响应。
        2. 便于前端联调和答辩演示时快速定位问题。
        """
        if not log_file_path.exists():
            return ""

        try:
            log_lines = log_file_path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except Exception:
            return ""

        return "\n".join(log_lines[-max_lines:])

    def _collect_recent_records(self) -> Dict[str, Any]:
        """
        扫描 data/runtime/batches/*/status.json 并汇总最近处理记录。

        说明：
        1. 不另建数据库表或缓存文件，优先复用 log_watcher.py 已经产出的批次状态文件。
        2. recent_records 默认按处理时间倒序返回。
        """
        batch_root = self._batch_root()
        if not batch_root.exists():
            return {
                "processed_file_count": 0,
                "latest_processed_at": "",
                "latest_detection_status": "IDLE",
                "recent_records": [],
            }

        all_records: List[Dict[str, Any]] = []
        status_files = sorted(
            batch_root.rglob("status.json"),
            key=lambda item: item.stat().st_mtime,
            reverse=True,
        )

        for status_file_path in status_files:
            try:
                payload = json.loads(status_file_path.read_text(encoding="utf-8"))
            except Exception as exc:
                current_app.logger.warning("读取批次状态文件失败：%s", exc)
                continue

            if not isinstance(payload, dict):
                continue

            processed_at = datetime.fromtimestamp(
                status_file_path.stat().st_mtime
            ).astimezone().isoformat(timespec="seconds")

            detection_status = self._resolve_detection_status(payload)
            record_item = {
                "batch_id": status_file_path.parent.name,
                "source_file": payload.get("source_file", ""),
                "status": payload.get("status", "UNKNOWN"),
                "processed_at": processed_at,
                "failed_step": payload.get("failed_step", ""),
                "parse_error_count": int(payload.get("parse_error_count", 0) or 0),
                "detection_status": detection_status,
            }
            all_records.append(record_item)

        latest_record = all_records[0] if all_records else {}
        return {
            "processed_file_count": len(all_records),
            "latest_processed_at": latest_record.get("processed_at", ""),
            "latest_detection_status": latest_record.get("detection_status", "IDLE"),
            "recent_records": all_records[: self._recent_record_limit()],
        }

    def _resolve_detection_status(self, payload: Dict[str, Any]) -> str:
        """
        根据批次 status.json 推断检测执行状态。

        判定策略：
        1. 整个批次 SUCCESS，则视为检测成功。
        2. failed_step 为 run_detection，则视为检测失败。
        3. 其他失败一般代表还未进入检测步骤，返回 NOT_RUN。
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


monitor_service = MonitorService()

