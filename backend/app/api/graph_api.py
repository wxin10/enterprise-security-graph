#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
文件路径：backend/app/api/graph_api.py

文件作用：
1. 提供图谱相关接口蓝图。
2. 复用已有的 graph_service 服务层方法。
3. 对外暴露图谱总览、图谱统计和用户图谱详情接口。
"""

from __future__ import annotations

from flask import Blueprint

from app.core.errors import ValidationError
from app.core.response import success_response
from app.services import graph_service


# 图谱查询蓝图。
# 当前蓝图只负责图谱类接口，后续如果新增攻击路径、关系追踪等接口，也可以继续挂在该蓝图下。
graph_api_bp = Blueprint("graph_api", __name__)


@graph_api_bp.get("/graph/overview")
def get_graph_overview():
    """
    接口：GET /api/graph/overview

    作用：
    1. 返回图谱总览数据。
    2. 适合首页概览、论文答辩首页、仪表盘卡片展示。
    3. 包括节点总量、关系总量、告警总量、封禁数量及高风险排行。
    """
    overview_data = graph_service.get_graph_overview()
    return success_response(data=overview_data, message="图谱总览数据获取成功")


@graph_api_bp.get("/graph/stats")
def get_graph_stats():
    """
    接口：GET /api/graph/stats

    作用：
    1. 返回图谱统计数据。
    2. 主要包括节点分类统计、关系分类统计、告警状态分布和告警等级分布。
    3. 适合后续图表组件和论文统计章节使用。
    """
    stats_data = graph_service.get_graph_stats()
    return success_response(data=stats_data, message="图谱统计数据获取成功")


@graph_api_bp.get("/graph/user/<user_id>")
def get_user_graph(user_id: str):
    """
    接口：GET /api/graph/user/<user_id>

    作用：
    1. 返回指定用户的图谱详情。
    2. 展示用户、会话、IP、主机、事件、告警和处置动作之间的关联关系。
    3. 适合后续用户画像、攻击链追踪、图谱详情弹窗展示。
    """
    if not user_id or not user_id.strip():
        raise ValidationError("user_id 不能为空")

    user_graph_data = graph_service.get_user_graph(user_id=user_id.strip().upper())
    return success_response(data=user_graph_data, message="用户图谱详情获取成功")
