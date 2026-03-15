#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
文件路径：backend/app/api/__init__.py

文件作用：
1. 导出 API 蓝图注册函数。
2. 导出当前阶段开放接口列表。
3. 便于应用工厂统一完成蓝图注册。
"""

from app.api.routes import AVAILABLE_API_ENDPOINTS, register_api_blueprints

__all__ = ["register_api_blueprints", "AVAILABLE_API_ENDPOINTS"]
