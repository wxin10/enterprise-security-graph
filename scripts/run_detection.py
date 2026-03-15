#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
文件路径：scripts/run_detection.py

脚本职责：
1. 作为“自动检测与风险评分”阶段的命令行执行入口。
2. 读取 backend/.env 或命令行参数，初始化 Neo4j 连接配置。
3. 调用 backend/app/services/detection_service.py 执行检测、评分和告警回写。
4. 将执行结果以中文摘要方式打印到终端，便于答辩演示与论文截图。

执行定位：
1. 本脚本属于“数据已导入 Neo4j 之后”的第二阶段能力扩展。
2. 当前只实现检测与评分，不执行真实自动封禁。
3. 后续如果需要增加定时任务、自动联动或审批流程，可继续复用本脚本输出。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Dict


BASE_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = BASE_DIR / "backend"
BACKEND_ENV_FILE = BACKEND_DIR / ".env"


def load_env_file(env_file: Path) -> None:
    """
    手动读取 .env 文件并注入到环境变量。

    设计原因：
    1. 当前项目未额外依赖 python-dotenv。
    2. 手动解析足以满足本地开发和论文演示环境。
    3. 若环境变量已存在，则优先保留外部显式传入值。
    """
    if not env_file.exists():
        return

    for line in env_file.read_text(encoding="utf-8").splitlines():
        stripped_line = line.strip()
        if not stripped_line or stripped_line.startswith("#") or "=" not in stripped_line:
            continue

        key, value = stripped_line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def ensure_backend_import_path() -> None:
    """
    将 backend 目录加入 Python 模块搜索路径。

    这样做的好处：
    1. 脚本位于项目根目录下的 scripts/，无法直接按包方式导入 backend/app。
    2. 只加入 backend 目录，而不把整个项目根目录塞入优先路径，可以降低本地 neo4j/ 目录与官方驱动重名的影响。
    """
    backend_path_text = str(BACKEND_DIR)
    if backend_path_text not in sys.path:
        sys.path.insert(0, backend_path_text)


def build_argument_parser() -> argparse.ArgumentParser:
    """
    构造命令行参数解析器。
    """
    parser = argparse.ArgumentParser(description="执行 Neo4j 图数据的恶意行为检测与风险评分。")
    parser.add_argument(
        "--config-name",
        default=os.getenv("FLASK_ENV", "development"),
        help="Flask 配置名称，默认读取环境变量 FLASK_ENV。",
    )
    parser.add_argument(
        "--uri",
        default=None,
        help="Neo4j 连接地址。若不传则优先读取 backend/.env 或系统环境变量。",
    )
    parser.add_argument(
        "--username",
        default=None,
        help="Neo4j 用户名。若不传则优先读取 backend/.env 或系统环境变量。",
    )
    parser.add_argument(
        "--password",
        default=None,
        help="Neo4j 密码。若不传则优先读取 backend/.env 或系统环境变量。",
    )
    parser.add_argument(
        "--database",
        default=None,
        help="Neo4j 数据库名。若不传则优先读取 backend/.env 或系统环境变量。",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只执行检测与评分，不将结果写回 Neo4j。",
    )
    parser.add_argument(
        "--json-output",
        action="store_true",
        help="以 JSON 格式输出结果，便于后续自动化处理。",
    )
    parser.add_argument(
        "--preview-size",
        type=int,
        default=10,
        help="终端中展示的结果预览数量，默认 10。",
    )
    return parser


def apply_cli_overrides(args: argparse.Namespace) -> None:
    """
    将命令行参数覆盖到环境变量。
    """
    override_mapping: Dict[str, str | None] = {
        "NEO4J_URI": args.uri,
        "NEO4J_USERNAME": args.username,
        "NEO4J_PASSWORD": args.password,
        "NEO4J_DATABASE": args.database,
        "FLASK_ENV": args.config_name,
    }

    for key, value in override_mapping.items():
        if value not in (None, ""):
            os.environ[key] = str(value)


def print_result_summary(result: Dict[str, object], preview_size: int) -> None:
    """
    使用中文摘要打印检测结果。
    """
    summary = result.get("summary", {}) or {}
    persist_stats = result.get("persist_stats", {}) or {}
    entity_updates = persist_stats.get("entity_updates", {}) or {}
    preview_items = list(result.get("results_preview", []) or [])[:preview_size]
    rule_stats = list(result.get("rule_match_stats", []) or [])

    print("[run_detection] 检测任务执行完成")
    print(f"  - 开始时间：{result.get('run_started_at')}")
    print(f"  - 结束时间：{result.get('run_finished_at')}")
    print(f"  - Dry Run：{'是' if result.get('dry_run') else '否'}")
    print(f"  - 会话上下文数量：{summary.get('session_context_count', 0)}")
    print(f"  - 核心规则命中数：{summary.get('core_match_count', 0)}")
    print(f"  - 聚合规则命中数：{summary.get('aggregate_match_count', 0)}")
    print(f"  - 总告警结果数：{summary.get('total_match_count', 0)}")

    if not result.get("dry_run"):
        print(f"  - 写入 Rule 数量：{persist_stats.get('rules_upserted', 0)}")
        print(f"  - 写入 Alert 数量：{persist_stats.get('alerts_upserted', 0)}")
        print(
            "  - 实体风险更新："
            f"User={entity_updates.get('User', 0)}，"
            f"IP={entity_updates.get('IP', 0)}，"
            f"Session={entity_updates.get('Session', 0)}，"
            f"Host={entity_updates.get('Host', 0)}"
        )

    print("[run_detection] 规则命中统计：")
    for item in rule_stats:
        print(
            f"  - {item.get('rule_id')} {item.get('rule_name')}："
            f"{item.get('match_count', 0)} 次"
        )

    print("[run_detection] 结果预览：")
    if not preview_items:
        print("  - 当前没有命中新的检测结果。")
        return

    for item in preview_items:
        print(
            f"  - {item.get('alert_id')} | {item.get('alert_name')} | "
            f"{item.get('anchor_type')}:{item.get('anchor_id')} | "
            f"得分={item.get('score')} | 等级={item.get('severity')}"
        )


def main() -> int:
    """
    程序主入口。
    """
    load_env_file(BACKEND_ENV_FILE)
    parser = build_argument_parser()
    args = parser.parse_args()
    apply_cli_overrides(args)
    ensure_backend_import_path()

    try:
        from app import create_app
        from app.db import neo4j_client
        from app.services import detection_service
    except Exception as exc:
        print(f"[run_detection] 导入后端模块失败：{exc}", file=sys.stderr)
        return 1

    try:
        app = create_app(args.config_name)
        with app.app_context():
            result = detection_service.run_detection(dry_run=args.dry_run)

        if args.json_output:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print_result_summary(result, args.preview_size)

        neo4j_client.close()
        return 0
    except Exception as exc:
        print(f"[run_detection] 执行失败：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
