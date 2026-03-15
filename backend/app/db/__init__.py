#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
文件路径：backend/app/db/__init__.py

文件作用：
1. 导出 Neo4j 客户端单例。
2. 供服务层统一复用数据库连接封装。
"""

from app.db.neo4j_client import neo4j_client

__all__ = ["neo4j_client"]
