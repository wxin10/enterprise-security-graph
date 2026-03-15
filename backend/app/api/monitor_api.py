#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
文件路径：backend/app/api/monitor_api.py

文件作用：
1. 提供“日志监控中心”相关接口蓝图。
2. 通过 monitor_service 统一控制 log_watcher.py 的启动、停止与状态查询。
3. 保持当前项目“蓝图 + 服务层”的风格，不把监控逻辑直接堆在路由函数中。
"""

from __future__ import annotations

from flask import Blueprint, request

from app.core.errors import ValidationError
from app.core.response import success_response
from app.services import monitor_service


monitor_api_bp = Blueprint("monitor_api", __name__)


def parse_positive_interval(value: object, default_value: int) -> int:
    """
    解析监听间隔参数。

    设计说明：
    1. 监控启动接口允许前端传入 interval_seconds。
    2. 如果未传值，则回退为后端默认监听间隔。
    3. 若传值非法，则通过 ValidationError 统一返回 JSON 错误。
    """
    if value in (None, ""):
        return default_value

    try:
        parsed_value = int(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError("interval_seconds 必须是正整数") from exc

    if parsed_value <= 0:
        raise ValidationError("interval_seconds 必须大于 0")

    return parsed_value


@monitor_api_bp.post("/monitor/start")
def start_monitor():
    """
    接口：POST /api/monitor/start

    作用：
    1. 启动后台日志监听任务。
    2. 默认启动 scripts/log_watcher.py --interval 5。
    3. 可选支持前端传入自定义监听间隔，便于演示和调试。
    """
    request_payload = request.get_json(silent=True) or {}
    interval_seconds = parse_positive_interval(
        request_payload.get("interval_seconds"),
        default_value=monitor_service.get_monitor_config()["default_interval_seconds"],
    )
    monitor_status = monitor_service.start_monitor(interval_seconds=interval_seconds)
    return success_response(data=monitor_status, message="日志监控任务启动成功")


@monitor_api_bp.post("/monitor/stop")
def stop_monitor():
    """
    接口：POST /api/monitor/stop

    作用：
    1. 停止后台日志监听任务。
    2. 适用于前端“一键停止监控”的演示入口。
    """
    monitor_status = monitor_service.stop_monitor()
    return success_response(data=monitor_status, message="日志监控任务已停止")


@monitor_api_bp.get("/monitor/status")
def get_monitor_status():
    """
    接口：GET /api/monitor/status

    作用：
    1. 返回当前监控进程状态。
    2. 返回最近处理文件数、最近处理时间、最近检测状态和最近处理记录列表。
    """
    monitor_status = monitor_service.get_monitor_status()
    return success_response(data=monitor_status, message="日志监控状态获取成功")


@monitor_api_bp.get("/monitor/config")
def get_monitor_config():
    """
    接口：GET /api/monitor/config

    作用：
    1. 返回当前监听根目录、监听目录列表和运行时文件路径。
    2. 供前端“日志监控中心”展示配置信息。
    """
    monitor_config = monitor_service.get_monitor_config()
    return success_response(data=monitor_config, message="日志监控配置获取成功")

