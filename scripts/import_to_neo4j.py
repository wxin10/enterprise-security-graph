#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
文件路径：scripts/import_to_neo4j.py

脚本职责：
1. 读取 data/processed/ 下的节点 CSV 和关系 CSV。
2. 可选执行 neo4j/init_schema.cypher，先创建约束和索引。
3. 使用 Neo4j Python 驱动将结构化数据导入图数据库。

设计说明：
1. 本脚本默认采用 Python 驱动导入，而不是直接依赖 LOAD CSV。
   这样可以减少 Neo4j import 目录配置带来的环境差异，便于答辩现场直接演示。
2. 为兼顾教学和验证场景，项目同时额外提供 neo4j/import_data.cypher 作为手工导入方案。
3. 本脚本不执行清空数据库等破坏性操作，默认只做 MERGE 导入。
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
from pathlib import Path
from typing import Dict, List

BASE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_PROCESSED_DIR = BASE_DIR / "data" / "processed"
DEFAULT_SCHEMA_FILE = BASE_DIR / "neo4j" / "init_schema.cypher"


# 节点导入配置。
NODE_IMPORTS = [
    {
        "name": "User",
        "file": "users.csv",
        "types": {
            "privilege_level": "int",
            "is_whitelisted": "bool",
            "risk_score": "float",
        },
        "query": """
UNWIND $rows AS row
MERGE (n:User {user_id: row.user_id})
SET n.username = row.username,
    n.display_name = row.display_name,
    n.department = row.department,
    n.role = row.role,
    n.privilege_level = row.privilege_level,
    n.status = row.status,
    n.is_whitelisted = row.is_whitelisted,
    n.risk_score = row.risk_score,
    n.created_at = row.created_at
""",
    },
    {
        "name": "Host",
        "file": "hosts.csv",
        "types": {
            "critical_level": "int",
            "risk_score": "float",
        },
        "query": """
UNWIND $rows AS row
MERGE (n:Host {host_id: row.host_id})
SET n.hostname = row.hostname,
    n.asset_type = row.asset_type,
    n.os_name = row.os_name,
    n.critical_level = row.critical_level,
    n.owner_department = row.owner_department,
    n.status = row.status,
    n.risk_score = row.risk_score,
    n.created_at = row.created_at
""",
    },
    {
        "name": "IP",
        "file": "ips.csv",
        "types": {
            "is_blocked": "bool",
            "risk_score": "float",
        },
        "query": """
UNWIND $rows AS row
MERGE (n:IP {ip_id: row.ip_id})
SET n.ip_address = row.ip_address,
    n.ip_type = row.ip_type,
    n.geo_location = row.geo_location,
    n.reputation_level = row.reputation_level,
    n.is_blocked = row.is_blocked,
    n.risk_score = row.risk_score,
    n.created_at = row.created_at
""",
    },
    {
        "name": "Session",
        "file": "sessions.csv",
        "types": {
            "duration_seconds": "int",
            "src_port": "int",
            "dst_port": "int",
            "risk_score": "float",
        },
        "query": """
UNWIND $rows AS row
MERGE (n:Session {session_id: row.session_id})
SET n.protocol = row.protocol,
    n.login_result = row.login_result,
    n.start_time = row.start_time,
    n.end_time = row.end_time,
    n.duration_seconds = row.duration_seconds,
    n.auth_method = row.auth_method,
    n.src_port = row.src_port,
    n.dst_port = row.dst_port,
    n.risk_score = row.risk_score
""",
    },
    {
        "name": "Event",
        "file": "events.csv",
        "types": {
            "confidence": "float",
            "risk_score": "float",
        },
        "query": """
UNWIND $rows AS row
MERGE (n:Event {event_id: row.event_id})
SET n.event_type = row.event_type,
    n.event_level = row.event_level,
    n.event_time = row.event_time,
    n.action = row.action,
    n.result = row.result,
    n.log_source = row.log_source,
    n.raw_log_id = row.raw_log_id,
    n.confidence = row.confidence,
    n.risk_score = row.risk_score,
    n.detail = row.detail
""",
    },
    {
        "name": "Rule",
        "file": "rules.csv",
        "types": {
            "enabled": "bool",
        },
        "query": """
UNWIND $rows AS row
MERGE (n:Rule {rule_id: row.rule_id})
SET n.rule_name = row.rule_name,
    n.rule_category = row.rule_category,
    n.rule_level = row.rule_level,
    n.threshold_desc = row.threshold_desc,
    n.description = row.description,
    n.enabled = row.enabled
""",
    },
    {
        "name": "Alert",
        "file": "alerts.csv",
        "types": {
            "score": "float",
        },
        "query": """
UNWIND $rows AS row
MERGE (n:Alert {alert_id: row.alert_id})
SET n.alert_name = row.alert_name,
    n.severity = row.severity,
    n.score = row.score,
    n.status = row.status,
    n.first_seen = row.first_seen,
    n.last_seen = row.last_seen,
    n.description = row.description,
    n.suggestion = row.suggestion
""",
    },
    {
        "name": "BlockAction",
        "file": "block_actions.csv",
        "types": {
            "rollback_supported": "bool",
        },
        "query": """
UNWIND $rows AS row
MERGE (n:BlockAction {action_id: row.action_id})
SET n.action_type = row.action_type,
    n.target_type = row.target_type,
    n.status = row.status,
    n.executed_at = row.executed_at,
    n.executor = row.executor,
    n.ticket_no = row.ticket_no,
    n.rollback_supported = row.rollback_supported,
    n.remark = row.remark
""",
    },
]


# 关系导入配置。
RELATION_IMPORTS = [
    {
        "name": "INITIATES",
        "file": "rel_user_initiates_session.csv",
        "query": """
UNWIND $rows AS row
MATCH (a:User {user_id: row.user_id})
MATCH (b:Session {session_id: row.session_id})
MERGE (a)-[r:INITIATES]->(b)
SET r.relation_time = row.relation_time
""",
    },
    {
        "name": "USES_SOURCE_IP",
        "file": "rel_session_uses_source_ip.csv",
        "query": """
UNWIND $rows AS row
MATCH (a:Session {session_id: row.session_id})
MATCH (b:IP {ip_id: row.ip_id})
MERGE (a)-[r:USES_SOURCE_IP]->(b)
SET r.relation_time = row.relation_time
""",
    },
    {
        "name": "ACCESSES",
        "file": "rel_session_accesses_host.csv",
        "query": """
UNWIND $rows AS row
MATCH (a:Session {session_id: row.session_id})
MATCH (b:Host {host_id: row.host_id})
MERGE (a)-[r:ACCESSES]->(b)
SET r.relation_time = row.relation_time
""",
    },
    {
        "name": "GENERATES",
        "file": "rel_session_generates_event.csv",
        "query": """
UNWIND $rows AS row
MATCH (a:Session {session_id: row.session_id})
MATCH (b:Event {event_id: row.event_id})
MERGE (a)-[r:GENERATES]->(b)
SET r.relation_time = row.relation_time
""",
    },
    {
        "name": "TRIGGERS",
        "file": "rel_event_triggers_alert.csv",
        "query": """
UNWIND $rows AS row
MATCH (a:Event {event_id: row.event_id})
MATCH (b:Alert {alert_id: row.alert_id})
MERGE (a)-[r:TRIGGERS]->(b)
SET r.relation_time = row.relation_time
""",
    },
    {
        "name": "HIT_RULE",
        "file": "rel_alert_hit_rule.csv",
        "query": """
UNWIND $rows AS row
MATCH (a:Alert {alert_id: row.alert_id})
MATCH (b:Rule {rule_id: row.rule_id})
MERGE (a)-[r:HIT_RULE]->(b)
SET r.relation_time = row.relation_time
""",
    },
    {
        "name": "DISPOSES",
        "file": "rel_block_disposes_alert.csv",
        "query": """
UNWIND $rows AS row
MATCH (a:BlockAction {action_id: row.action_id})
MATCH (b:Alert {alert_id: row.alert_id})
MERGE (a)-[r:DISPOSES]->(b)
SET r.relation_time = row.relation_time
""",
    },
    {
        "name": "TARGETS_IP",
        "file": "rel_block_targets_ip.csv",
        "query": """
UNWIND $rows AS row
MATCH (a:BlockAction {action_id: row.action_id})
MATCH (b:IP {ip_id: row.ip_id})
MERGE (a)-[r:TARGETS_IP]->(b)
SET r.relation_time = row.relation_time
""",
    },
]


def load_graph_database():
    """
    延迟导入 Neo4j 驱动。

    为什么要这样处理：
    1. 当前项目根目录下有一个名为 neo4j/ 的文件夹，用于存放 Cypher 文件。
    2. 在 Python 的模块查找过程中，本地这个同名目录可能会遮蔽官方 neo4j 驱动包。
    3. 因此这里在导入驱动时暂时移除项目根目录，避免命名冲突。
    """
    original_sys_path = list(sys.path)
    filtered_sys_path = []

    for path_item in original_sys_path:
        try:
            resolved_path = Path(path_item).resolve()
        except Exception:
            filtered_sys_path.append(path_item)
            continue

        if resolved_path == BASE_DIR:
            continue

        filtered_sys_path.append(path_item)

    try:
        sys.path[:] = filtered_sys_path
        from neo4j import GraphDatabase  # type: ignore

        return GraphDatabase
    except Exception as exc:
        raise RuntimeError(
            "无法导入官方 neo4j Python 驱动。"
            "请先执行 `pip install neo4j`，并确认当前 Python 环境可用。"
        ) from exc
    finally:
        sys.path[:] = original_sys_path


def parse_value(value: str, value_type: str):
    """
    按字段类型解析 CSV 字段。
    """
    if value is None:
        return None

    text = str(value).strip()
    if text == "":
        return None

    if value_type == "int":
        return int(float(text))

    if value_type == "float":
        return float(text)

    if value_type == "bool":
        lowered = text.lower()
        if lowered == "true":
            return True
        if lowered == "false":
            return False
        raise ValueError(f"无法解析布尔值：{value}")

    return text


def read_csv_rows(file_path: Path, type_map: Dict[str, str]) -> List[Dict[str, object]]:
    """
    读取 CSV 并根据字段类型进行转换。
    """
    if not file_path.exists():
        raise FileNotFoundError(f"未找到导入文件：{file_path}")

    rows: List[Dict[str, object]] = []
    with file_path.open("r", encoding="utf-8", newline="") as file_obj:
        reader = csv.DictReader(file_obj)
        for row in reader:
            parsed_row: Dict[str, object] = {}
            for field_name, field_value in row.items():
                if field_name in type_map:
                    parsed_row[field_name] = parse_value(field_value, type_map[field_name])
                else:
                    parsed_row[field_name] = parse_value(field_value, "str")
            rows.append(parsed_row)

    return rows


def run_in_batches(session, query: str, rows: List[Dict[str, object]], batch_size: int) -> None:
    """
    按批次执行 Cypher 导入，避免一次提交过多数据。
    """
    if not rows:
        return

    for start in range(0, len(rows), batch_size):
        batch_rows = rows[start : start + batch_size]
        session.run(query, rows=batch_rows).consume()


def load_schema_statements(schema_file: Path) -> List[str]:
    """
    从 schema 文件中读取并拆分 Cypher 语句。
    """
    if not schema_file.exists():
        raise FileNotFoundError(f"未找到 Schema 文件：{schema_file}")

    content = schema_file.read_text(encoding="utf-8")
    effective_lines = []
    for line in content.splitlines():
        if line.strip().startswith("//"):
            continue
        effective_lines.append(line)

    effective_content = "\n".join(effective_lines)
    return [statement.strip() for statement in effective_content.split(";") if statement.strip()]


def verify_processed_files(processed_dir: Path) -> None:
    """
    检查导入所需 CSV 是否全部存在。
    """
    expected_files = [item["file"] for item in NODE_IMPORTS] + [item["file"] for item in RELATION_IMPORTS]
    missing_files = [file_name for file_name in expected_files if not (processed_dir / file_name).exists()]

    if missing_files:
        missing_text = "、".join(missing_files)
        raise FileNotFoundError(f"以下导入文件不存在：{missing_text}。请先执行 clean_logs.py 和 extract_entities.py。")


def build_argument_parser() -> argparse.ArgumentParser:
    """
    构造命令行参数。
    """
    parser = argparse.ArgumentParser(description="将 data/processed/ 下的节点和关系 CSV 导入 Neo4j。")
    parser.add_argument(
        "--processed-dir",
        default=str(DEFAULT_PROCESSED_DIR),
        help="节点和关系 CSV 所在目录，默认使用 data/processed。",
    )
    parser.add_argument(
        "--schema-file",
        default=str(DEFAULT_SCHEMA_FILE),
        help="Neo4j Schema 文件路径，默认使用 neo4j/init_schema.cypher。",
    )
    parser.add_argument(
        "--uri",
        default=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        help="Neo4j 连接地址，默认读取环境变量 NEO4J_URI，未设置时使用 bolt://localhost:7687。",
    )
    parser.add_argument(
        "--username",
        default=os.getenv("NEO4J_USERNAME", "neo4j"),
        help="Neo4j 用户名，默认读取环境变量 NEO4J_USERNAME，未设置时使用 neo4j。",
    )
    parser.add_argument(
        "--password",
        default=os.getenv("NEO4J_PASSWORD", "neo4j123456"),
        help="Neo4j 密码，默认读取环境变量 NEO4J_PASSWORD。",
    )
    parser.add_argument(
        "--database",
        default=os.getenv("NEO4J_DATABASE", "neo4j"),
        help="Neo4j 数据库名，默认读取环境变量 NEO4J_DATABASE，未设置时使用 neo4j。",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=500,
        help="批量导入大小，默认 500。",
    )
    parser.add_argument(
        "--skip-schema",
        action="store_true",
        help="跳过 schema 初始化，仅执行数据导入。",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只验证文件和配置，不连接 Neo4j。",
    )
    return parser


def main() -> int:
    """
    程序主入口。
    """
    parser = build_argument_parser()
    args = parser.parse_args()

    processed_dir = Path(args.processed_dir).resolve()
    schema_file = Path(args.schema_file).resolve()

    try:
        verify_processed_files(processed_dir)
    except Exception as exc:
        print(f"[import_to_neo4j] 预检查失败：{exc}", file=sys.stderr)
        return 1

    if args.dry_run:
        print("[import_to_neo4j] Dry Run 验证通过。以下文件已准备完成：")
        for item in NODE_IMPORTS:
            file_path = processed_dir / item["file"]
            row_count = len(read_csv_rows(file_path, item["types"]))
            print(f"  - 节点文件 {item['file']}：{row_count} 行")
        for item in RELATION_IMPORTS:
            file_path = processed_dir / item["file"]
            row_count = len(read_csv_rows(file_path, {}))
            print(f"  - 关系文件 {item['file']}：{row_count} 行")
        return 0

    if not args.password:
        print("[import_to_neo4j] 缺少 Neo4j 密码，请通过 --password 或环境变量 NEO4J_PASSWORD 提供。", file=sys.stderr)
        return 1

    try:
        graph_database = load_graph_database()
        driver = graph_database.driver(args.uri, auth=(args.username, args.password))
        driver.verify_connectivity()
    except Exception as exc:
        print(f"[import_to_neo4j] Neo4j 连接失败：{exc}", file=sys.stderr)
        return 1

    try:
        with driver.session(database=args.database) as session:
            if not args.skip_schema:
                schema_statements = load_schema_statements(schema_file)
                for statement in schema_statements:
                    session.run(statement).consume()
                print("[import_to_neo4j] Schema 初始化完成。")

            for item in NODE_IMPORTS:
                rows = read_csv_rows(processed_dir / item["file"], item["types"])
                run_in_batches(session, item["query"], rows, args.batch_size)
                print(f"[import_to_neo4j] 节点导入完成：{item['name']}，共 {len(rows)} 行。")

            for item in RELATION_IMPORTS:
                rows = read_csv_rows(processed_dir / item["file"], {})
                run_in_batches(session, item["query"], rows, args.batch_size)
                print(f"[import_to_neo4j] 关系导入完成：{item['name']}，共 {len(rows)} 行。")
    except Exception as exc:
        print(f"[import_to_neo4j] 导入失败：{exc}", file=sys.stderr)
        return 1
    finally:
        driver.close()

    print("[import_to_neo4j] 全部导入完成。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
