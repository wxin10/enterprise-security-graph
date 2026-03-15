#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
文件路径：backend/app/db/neo4j_client.py

文件作用：
1. 封装 Neo4j Python 驱动。
2. 统一管理连接创建、只读查询执行和资源关闭。
3. 对底层驱动异常进行统一包装，向上层暴露更清晰的业务错误。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from neo4j import GraphDatabase
from neo4j.exceptions import AuthError, Neo4jError, ServiceUnavailable

from app.core.errors import DatabaseError


class Neo4jClient:
    """
    Neo4j 客户端封装类。

    设计目标：
    1. 将数据库连接逻辑从业务代码中抽离。
    2. 让服务层只关心 Cypher 和返回结果，不关心驱动细节。
    3. 便于后续扩展写入事务、健康检查和连接池配置。
    """

    def __init__(self):
        self._driver = None
        self._config: Dict[str, Any] = {}

    def init_app(self, app) -> None:
        """
        读取 Flask 配置并保存 Neo4j 连接参数。

        这里不立即连接数据库，而是采用懒加载策略，
        避免因为 Neo4j 暂未启动导致 Flask 服务无法启动。
        """
        self._config = {
            "uri": app.config.get("NEO4J_URI"),
            "username": app.config.get("NEO4J_USERNAME"),
            "password": app.config.get("NEO4J_PASSWORD"),
            "database": app.config.get("NEO4J_DATABASE"),
            "verify_connectivity": app.config.get("NEO4J_VERIFY_CONNECTIVITY", False),
            "connection_timeout": app.config.get("NEO4J_CONNECTION_TIMEOUT", 15),
            "max_connection_lifetime": app.config.get("NEO4J_MAX_CONNECTION_LIFETIME", 3600),
            "max_connection_pool_size": app.config.get("NEO4J_MAX_CONNECTION_POOL_SIZE", 50),
        }

    def _build_driver(self):
        """
        创建底层 Neo4j 驱动实例。
        """
        uri = self._config.get("uri")
        username = self._config.get("username")
        password = self._config.get("password")

        if not uri or not username or not password:
            raise DatabaseError("Neo4j 连接配置不完整，请设置 NEO4J_URI、NEO4J_USERNAME、NEO4J_PASSWORD")

        try:
            driver = GraphDatabase.driver(
                uri,
                auth=(username, password),
                connection_timeout=self._config.get("connection_timeout", 15),
                max_connection_lifetime=self._config.get("max_connection_lifetime", 3600),
                max_connection_pool_size=self._config.get("max_connection_pool_size", 50),
            )

            if self._config.get("verify_connectivity", False):
                driver.verify_connectivity()

            return driver
        except AuthError as exc:
            raise DatabaseError(f"Neo4j 认证失败：{exc}") from exc
        except ServiceUnavailable as exc:
            raise DatabaseError(f"Neo4j 服务不可用：{exc}") from exc
        except Neo4jError as exc:
            raise DatabaseError(f"Neo4j 初始化失败：{exc}") from exc

    def get_driver(self):
        """
        获取 Neo4j 驱动实例。

        如果驱动尚未创建，则在第一次使用时再建立连接。
        """
        if self._driver is None:
            self._driver = self._build_driver()
        return self._driver

    def execute_read(self, query: str, parameters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        执行只读查询并返回结果列表。

        返回格式：
        1. 每一条记录会被转换为字典。
        2. 标量类型会直接变成 Python 原生类型。
        3. Neo4j 的节点和关系对象会原样保留，便于服务层进一步加工成图结构。
        """
        driver = self.get_driver()

        try:
            with driver.session(database=self._config.get("database")) as session:
                result = session.run(query, parameters or {})
                return [record.data() for record in result]
        except AuthError as exc:
            raise DatabaseError(f"Neo4j 认证失败：{exc}") from exc
        except ServiceUnavailable as exc:
            raise DatabaseError(f"Neo4j 服务不可用：{exc}") from exc
        except Neo4jError as exc:
            raise DatabaseError(f"Neo4j 查询失败：{exc}") from exc

    def execute_write(self, query: str, parameters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        执行写入类 Cypher 并返回结果列表。

        设计原因：
        1. 当前系统已经具备图数据查询能力，但“检测 -> 评分 -> 告警回写”流程需要写事务支持。
        2. 将写入能力统一收口到 Neo4jClient，可以避免服务层直接接触驱动细节。
        3. 返回值依旧统一转换为字典列表，便于后续扩展返回写入统计信息。
        """
        driver = self.get_driver()

        try:
            with driver.session(database=self._config.get("database")) as session:
                result = session.run(query, parameters or {})
                records = [record.data() for record in result]
                result.consume()
                return records
        except AuthError as exc:
            raise DatabaseError(f"Neo4j 认证失败：{exc}") from exc
        except ServiceUnavailable as exc:
            raise DatabaseError(f"Neo4j 服务不可用：{exc}") from exc
        except Neo4jError as exc:
            raise DatabaseError(f"Neo4j 写入失败：{exc}") from exc

    def close(self) -> None:
        """
        关闭底层驱动连接。
        """
        if self._driver is not None:
            self._driver.close()
            self._driver = None


neo4j_client = Neo4jClient()
