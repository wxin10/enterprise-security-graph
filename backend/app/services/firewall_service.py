#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
文件路径：backend/app/services/firewall_service.py

文件作用：
1. 提供封禁执行模式抽象，统一封装 MOCK 与 Windows 防火墙真实执行逻辑。
2. 对指定源 IP 执行最小可运行的真实封禁、放行和规则校验。
3. 为 ban_service 提供稳定的“执行结果 + 校验结果”结构，避免业务层直接拼接 PowerShell 命令。

设计说明：
1. 当前项目的真实演示环境是 Windows 宿主机，因此本轮优先实现 Windows 防火墙后端。
2. 为避免误删系统其他规则，所有真实规则都使用本项目独立命名前缀，并且只按该规则名做删除与校验。
3. 默认模式仍为 MOCK，只有显式把环境变量切到 REAL 时才会真正下发系统防火墙规则。
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from datetime import datetime
from typing import Any, Dict, List, Optional

from flask import current_app


class FirewallService:
    """
    Windows 防火墙执行服务。

    目前支持两类执行模式：
    1. MOCK / SIMULATE：只返回模拟执行结果，不修改宿主机规则。
    2. REAL：调用 Windows PowerShell 的 NetSecurity 模块创建、删除和校验规则。
    """

    MODE_REAL = "REAL"
    MODE_MOCK = "MOCK"

    BACKEND_WINDOWS_FIREWALL = "WINDOWS_FIREWALL"
    BACKEND_MOCK = "MOCK"

    STATUS_APPLIED = "APPLIED"
    STATUS_REMOVED = "REMOVED"
    STATUS_FAILED = "FAILED"
    STATUS_PENDING = "PENDING"
    STATUS_SIMULATED = "SIMULATED"

    VERIFY_VERIFIED = "VERIFIED"
    VERIFY_NOT_VERIFIED = "NOT_VERIFIED"
    VERIFY_MISSING = "MISSING"
    VERIFY_FAILED = "FAILED"

    def get_enforcement_profile(self) -> Dict[str, Any]:
        """
        返回当前系统封禁执行配置。

        该配置会直接返回给前端封禁管理页，便于答辩时说明当前是模拟模式还是真实模式。
        """
        mode = self._resolve_mode(current_app.config.get("BAN_ENFORCEMENT_MODE"))
        backend = self._resolve_backend(mode)
        local_ports = list(current_app.config.get("BAN_WINDOWS_FIREWALL_LOCAL_PORTS", []))

        if mode == self.MODE_REAL and backend == self.BACKEND_WINDOWS_FIREWALL:
            scope_text = (
                f"仅阻断宿主机本地端口 {', '.join(local_ports)} 的入站访问"
                if local_ports
                else "阻断指定源 IP 的入站访问"
            )
        else:
            scope_text = "仅更新业务状态和图数据库状态，不真正修改宿主机防火墙"

        return {
            "mode": mode,
            "backend": backend,
            "host_platform": "WINDOWS" if os.name == "nt" else "NON_WINDOWS",
            "supports_real_execution": os.name == "nt",
            "rule_prefix": current_app.config.get("BAN_WINDOWS_FIREWALL_RULE_PREFIX", "ESG"),
            "local_ports": local_ports,
            "scope_description": scope_text,
        }

    def build_rule_name(self, ban_id: str, target_ip: str) -> str:
        """
        构造当前项目专用的防火墙规则名。

        规则名中保留：
        1. 项目前缀，便于统一检索和清理。
        2. ban_id，便于和业务记录一一对应。
        3. 目标 IP，便于人工排查规则。
        """
        prefix = current_app.config.get("BAN_WINDOWS_FIREWALL_RULE_PREFIX", "ESG")
        sanitized_ip = re.sub(r"[^0-9A-Za-z]+", "_", str(target_ip or "UNKNOWN"))
        sanitized_id = re.sub(r"[^0-9A-Za-z_-]+", "_", str(ban_id or "UNKNOWN"))
        return f"{prefix}-BAN-{sanitized_id}-{sanitized_ip}"

    def apply_block(self, ban_id: str, target_ip: str) -> Dict[str, Any]:
        """
        执行封禁。

        返回统一结构：
        1. enforcement_status：规则下发结果。
        2. verification_status：规则校验结果。
        3. enforcement_rule_name：规则名称。
        4. verification_message：校验说明。
        """
        profile = self.get_enforcement_profile()
        rule_name = self.build_rule_name(ban_id, target_ip)

        if profile["mode"] != self.MODE_REAL:
            return self._build_mock_result(
                rule_name=rule_name,
                target_ip=target_ip,
                action_name="封禁",
                enforcement_status=self.STATUS_SIMULATED,
                verification_status=self.VERIFY_NOT_VERIFIED,
                verification_message="当前为模拟执行模式，未真正下发 Windows 防火墙规则",
            )

        return self._apply_windows_block(rule_name=rule_name, target_ip=target_ip)

    def remove_block(self, ban_id: str, target_ip: str) -> Dict[str, Any]:
        """
        执行放行 / 解封。
        """
        profile = self.get_enforcement_profile()
        rule_name = self.build_rule_name(ban_id, target_ip)

        if profile["mode"] != self.MODE_REAL:
            return self._build_mock_result(
                rule_name=rule_name,
                target_ip=target_ip,
                action_name="放行",
                enforcement_status=self.STATUS_REMOVED,
                verification_status=self.VERIFY_NOT_VERIFIED,
                verification_message="当前为模拟执行模式，未真正删除 Windows 防火墙规则",
            )

        return self._remove_windows_block(rule_name=rule_name, target_ip=target_ip)

    def verify_rule(self, ban_id: str, target_ip: str, expected_state: str) -> Dict[str, Any]:
        """
        校验当前规则是否符合预期状态。

        expected_state：
        1. BLOCKED：预期规则存在并处于启用状态。
        2. RELEASED：预期规则已经不存在或已失效。
        """
        profile = self.get_enforcement_profile()
        rule_name = self.build_rule_name(ban_id, target_ip)

        if profile["mode"] != self.MODE_REAL:
            return self._build_mock_result(
                rule_name=rule_name,
                target_ip=target_ip,
                action_name="校验",
                enforcement_status=self.STATUS_SIMULATED,
                verification_status=self.VERIFY_NOT_VERIFIED,
                verification_message="当前为模拟执行模式，不执行宿主机防火墙校验",
            )

        return self._verify_windows_rule(
            rule_name=rule_name,
            target_ip=target_ip,
            expected_state=str(expected_state or "").upper(),
        )

    def _apply_windows_block(self, rule_name: str, target_ip: str) -> Dict[str, Any]:
        """
        在 Windows 上真实创建阻断规则。
        """
        if os.name != "nt":
            return self._build_failure_result(
                rule_name=rule_name,
                target_ip=target_ip,
                message="当前宿主环境不是 Windows，无法执行 Windows 防火墙真实封禁",
            )

        local_ports = list(current_app.config.get("BAN_WINDOWS_FIREWALL_LOCAL_PORTS", []))
        protocol = current_app.config.get("BAN_WINDOWS_FIREWALL_PROTOCOL", "TCP")
        direction = current_app.config.get("BAN_WINDOWS_FIREWALL_DIRECTION", "Inbound")

        script_lines = [
            "$ErrorActionPreference = 'Stop'",
            f"$displayName = '{rule_name}'",
            "$existing = Get-NetFirewallRule -DisplayName $displayName -ErrorAction SilentlyContinue",
            "if ($existing) {",
            "  $existing | Remove-NetFirewallRule | Out-Null",
            "}",
            "$params = @{",
            "  DisplayName = $displayName",
            f"  Direction = '{direction}'",
            "  Action = 'Block'",
            "  Enabled = 'True'",
            "  Profile = 'Any'",
            f"  RemoteAddress = '{target_ip}'",
            "}",
        ]

        if local_ports:
            port_text = ",".join(local_ports)
            script_lines.extend(
                [
                    f"$params['Protocol'] = '{protocol}'",
                    f"$params['LocalPort'] = '{port_text}'",
                ]
            )

        script_lines.extend(
            [
                "$rule = New-NetFirewallRule @params",
                "$rule | Select-Object DisplayName, Name, Enabled, Direction, Action, Profile | ConvertTo-Json -Compress",
            ]
        )

        command_result = self._run_powershell("\n".join(script_lines))
        if not command_result["success"]:
            return self._build_failure_result(
                rule_name=rule_name,
                target_ip=target_ip,
                message=f"Windows 防火墙规则创建失败：{command_result['message']}",
            )

        verify_result = self._verify_windows_rule(rule_name=rule_name, target_ip=target_ip, expected_state="BLOCKED")
        verify_result["enforcement_status"] = (
            self.STATUS_APPLIED if verify_result["verification_status"] == self.VERIFY_VERIFIED else self.STATUS_FAILED
        )
        verify_result["message"] = (
            "Windows 防火墙规则已下发并校验通过"
            if verify_result["verification_status"] == self.VERIFY_VERIFIED
            else "规则已创建，但校验未通过"
        )
        return verify_result

    def _remove_windows_block(self, rule_name: str, target_ip: str) -> Dict[str, Any]:
        """
        在 Windows 上真实删除当前项目创建的阻断规则。
        """
        if os.name != "nt":
            return self._build_failure_result(
                rule_name=rule_name,
                target_ip=target_ip,
                message="当前宿主环境不是 Windows，无法执行 Windows 防火墙真实放行",
            )

        script = "\n".join(
            [
                "$ErrorActionPreference = 'Stop'",
                f"$displayName = '{rule_name}'",
                "$existing = Get-NetFirewallRule -DisplayName $displayName -ErrorAction SilentlyContinue",
                "if (-not $existing) {",
                "  @{ removed = $true; existed = $false; message = '规则不存在，按已放行处理'; } | ConvertTo-Json -Compress",
                "} else {",
                "  $existing | Remove-NetFirewallRule | Out-Null",
                "  @{ removed = $true; existed = $true; message = '规则已删除'; } | ConvertTo-Json -Compress",
                "}",
            ]
        )

        command_result = self._run_powershell(script)
        if not command_result["success"]:
            return self._build_failure_result(
                rule_name=rule_name,
                target_ip=target_ip,
                message=f"Windows 防火墙规则删除失败：{command_result['message']}",
            )

        verify_result = self._verify_windows_rule(rule_name=rule_name, target_ip=target_ip, expected_state="RELEASED")
        verify_result["enforcement_status"] = (
            self.STATUS_REMOVED if verify_result["verification_status"] == self.VERIFY_VERIFIED else self.STATUS_FAILED
        )
        verify_result["message"] = (
            "Windows 防火墙规则已移除并校验通过"
            if verify_result["verification_status"] == self.VERIFY_VERIFIED
            else "规则删除命令已执行，但校验未通过"
        )
        return verify_result

    def _verify_windows_rule(self, rule_name: str, target_ip: str, expected_state: str) -> Dict[str, Any]:
        """
        查询当前规则是否存在，并根据预期状态给出校验结论。
        """
        if os.name != "nt":
            return self._build_failure_result(
                rule_name=rule_name,
                target_ip=target_ip,
                message="当前宿主环境不是 Windows，无法校验 Windows 防火墙规则",
            )

        script = "\n".join(
            [
                "$ErrorActionPreference = 'Stop'",
                f"$displayName = '{rule_name}'",
                "$rule = Get-NetFirewallRule -DisplayName $displayName -ErrorAction SilentlyContinue | Select-Object -First 1",
                "if (-not $rule) {",
                "  @{ exists = $false; enabled = $false; rule_name = $displayName; } | ConvertTo-Json -Compress",
                "} else {",
                "  $address = $rule | Get-NetFirewallAddressFilter | Select-Object -First 1",
                "  $port = $rule | Get-NetFirewallPortFilter | Select-Object -First 1",
                "  @{",
                "     exists = $true;",
                "     enabled = [string]$rule.Enabled;",
                "     display_name = $rule.DisplayName;",
                "     name = $rule.Name;",
                "     direction = [string]$rule.Direction;",
                "     action = [string]$rule.Action;",
                "     remote_address = [string]$address.RemoteAddress;",
                "     local_port = [string]$port.LocalPort;",
                "     protocol = [string]$port.Protocol;",
                "  } | ConvertTo-Json -Compress",
                "}",
            ]
        )

        command_result = self._run_powershell(script)
        if not command_result["success"]:
            return self._build_failure_result(
                rule_name=rule_name,
                target_ip=target_ip,
                message=f"Windows 防火墙规则校验失败：{command_result['message']}",
            )

        payload = command_result.get("json") or {}
        exists = bool(payload.get("exists"))
        verified_at = self._build_now_text()

        if expected_state == "BLOCKED":
            if exists:
                local_port = self._normalize_text(payload.get("local_port"))
                protocol = self._normalize_text(payload.get("protocol"))
                message = "已检测到对应的 Windows 防火墙阻断规则"
                if local_port:
                    message += f"，本地端口：{local_port}"
                if protocol:
                    message += f"，协议：{protocol}"

                return {
                    "success": True,
                    "mode": self.MODE_REAL,
                    "backend": self.BACKEND_WINDOWS_FIREWALL,
                    "rule_name": rule_name,
                    "enforcement_rule_name": rule_name,
                    "enforcement_status": self.STATUS_APPLIED,
                    "verification_status": self.VERIFY_VERIFIED,
                    "verified_at": verified_at,
                    "verification_message": message,
                    "message": message,
                    "rule_exists": True,
                    "rule_detail": payload,
                }

            return {
                "success": False,
                "mode": self.MODE_REAL,
                "backend": self.BACKEND_WINDOWS_FIREWALL,
                "rule_name": rule_name,
                "enforcement_rule_name": rule_name,
                "enforcement_status": self.STATUS_FAILED,
                "verification_status": self.VERIFY_MISSING,
                "verified_at": verified_at,
                "verification_message": "未找到预期的 Windows 防火墙阻断规则",
                "message": "未找到预期的 Windows 防火墙阻断规则",
                "rule_exists": False,
                "rule_detail": payload,
            }

        if not exists:
            return {
                "success": True,
                "mode": self.MODE_REAL,
                "backend": self.BACKEND_WINDOWS_FIREWALL,
                "rule_name": rule_name,
                "enforcement_rule_name": rule_name,
                "enforcement_status": self.STATUS_REMOVED,
                "verification_status": self.VERIFY_VERIFIED,
                "verified_at": verified_at,
                "verification_message": "未检测到对应规则，说明规则已删除或当前未生效",
                "message": "未检测到对应规则，说明规则已删除或当前未生效",
                "rule_exists": False,
                "rule_detail": payload,
            }

        return {
            "success": False,
            "mode": self.MODE_REAL,
            "backend": self.BACKEND_WINDOWS_FIREWALL,
            "rule_name": rule_name,
            "enforcement_rule_name": rule_name,
            "enforcement_status": self.STATUS_FAILED,
            "verification_status": self.VERIFY_FAILED,
            "verified_at": verified_at,
            "verification_message": "规则仍然存在，放行校验未通过",
            "message": "规则仍然存在，放行校验未通过",
            "rule_exists": True,
            "rule_detail": payload,
        }

    def _run_powershell(self, script: str) -> Dict[str, Any]:
        """
        执行 PowerShell，并尝试解析 JSON 输出。

        设计原因：
        1. Windows 防火墙命令适合在 PowerShell 中执行。
        2. 统一把 stdout / stderr / returncode 收口到一个结构里，方便 ban_service 记录执行结果。
        """
        command = [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            script,
        ]

        creation_flags = 0
        if os.name == "nt" and hasattr(subprocess, "CREATE_NO_WINDOW"):
            creation_flags = subprocess.CREATE_NO_WINDOW

        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="ignore",
                timeout=20,
                creationflags=creation_flags,
            )
        except FileNotFoundError:
            return {
                "success": False,
                "message": "当前系统找不到 powershell.exe，无法调用 Windows 防火墙命令",
            }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "message": "执行 Windows 防火墙命令超时，请检查宿主机 PowerShell 响应情况",
            }
        except Exception as exc:  # pragma: no cover - 兜底保护
            return {
                "success": False,
                "message": str(exc),
            }

        stdout_text = (completed.stdout or "").strip()
        stderr_text = (completed.stderr or "").strip()
        message = stdout_text or stderr_text or f"PowerShell 返回码：{completed.returncode}"
        parsed_json = None

        if stdout_text:
            try:
                parsed_json = json.loads(stdout_text)
            except json.JSONDecodeError:
                parsed_json = None

        return {
            "success": completed.returncode == 0,
            "message": message,
            "stdout": stdout_text,
            "stderr": stderr_text,
            "json": parsed_json,
        }

    def _build_mock_result(
        self,
        rule_name: str,
        target_ip: str,
        action_name: str,
        enforcement_status: str,
        verification_status: str,
        verification_message: str,
    ) -> Dict[str, Any]:
        """
        构造模拟模式结果。
        """
        now_text = self._build_now_text()
        return {
            "success": True,
            "mode": self.MODE_MOCK,
            "backend": self.BACKEND_MOCK,
            "rule_name": rule_name,
            "enforcement_rule_name": rule_name,
            "enforcement_status": enforcement_status,
            "verification_status": verification_status,
            "verified_at": now_text,
            "verification_message": verification_message,
            "message": f"已完成模拟{action_name}：{target_ip}",
            "rule_exists": enforcement_status == self.STATUS_SIMULATED,
            "rule_detail": {
                "display_name": rule_name,
                "target_ip": target_ip,
                "mode": self.MODE_MOCK,
            },
        }

    def _build_failure_result(self, rule_name: str, target_ip: str, message: str) -> Dict[str, Any]:
        """
        构造统一失败结果。
        """
        return {
            "success": False,
            "mode": self._resolve_mode(current_app.config.get("BAN_ENFORCEMENT_MODE")),
            "backend": self._resolve_backend(self._resolve_mode(current_app.config.get("BAN_ENFORCEMENT_MODE"))),
            "rule_name": rule_name,
            "enforcement_rule_name": rule_name,
            "enforcement_status": self.STATUS_FAILED,
            "verification_status": self.VERIFY_FAILED,
            "verified_at": self._build_now_text(),
            "verification_message": message,
            "message": message,
            "rule_exists": False,
            "rule_detail": {
                "display_name": rule_name,
                "target_ip": target_ip,
            },
        }

    def _resolve_mode(self, raw_mode: Any) -> str:
        """
        解析封禁执行模式。
        """
        normalized = self._normalize_text(raw_mode).upper()
        if normalized in {"REAL", "WINDOWS_FIREWALL"}:
            return self.MODE_REAL
        return self.MODE_MOCK

    def _resolve_backend(self, mode: str) -> str:
        """
        根据模式推导后端类型。
        """
        return self.BACKEND_WINDOWS_FIREWALL if mode == self.MODE_REAL else self.BACKEND_MOCK

    def _build_now_text(self) -> str:
        """
        构造本地时区时间字符串。
        """
        return datetime.now().astimezone().isoformat(timespec="seconds")

    def _normalize_text(self, value: Any) -> str:
        """
        统一规范化字符串，避免 None 干扰。
        """
        return str(value or "").strip()


firewall_service = FirewallService()
