#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
文件路径：backend/app/services/__init__.py

文件作用：
1. 导出图谱查询服务单例。
2. 导出检测与评分服务单例。
3. 供路由层和脚本层统一复用业务逻辑。
"""

from app.services.graph_service import graph_service
from app.services.detection_service import detection_service

__all__ = ["graph_service", "detection_service"]
