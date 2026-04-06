#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
文件路径：scripts/bootstrap_demo_data.py

脚本职责：
本脚本为项目答辩演示和快速交付验证提供“一键式数据初始化”能力。
1. 将内置的真实攻击链样本数据 (data/sample) 复制为原始流水线输入 (data/raw)。
2. 调用 clean_logs.py 对原始数据进行标准化处理。
3. 调用 extract_entities.py 从清洗后的数据中提取 Neo4j 可识别的节点与边缘实体。
4. 调用 import_to_neo4j.py 将提取结果批量注入到预先拉起的 Neo4j 图谱并建立约束。

使用场景：
- 新环境初次部署后的数据填充。
- 毕业答辩前的现场图谱重建与链路演示。
- 测试过程中的环境一键还原。
"""

import sys
import shutil
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
SAMPLE_DIR = BASE_DIR / "data" / "sample"
RAW_DIR = BASE_DIR / "data" / "raw"

# 定义核心流水线脚本所在路径
CLEAN_LOGS_PY = BASE_DIR / "scripts" / "clean_logs.py"
EXTRACT_ENTITIES_PY = BASE_DIR / "scripts" / "extract_entities.py"
IMPORT_TO_NEO4J_PY = BASE_DIR / "scripts" / "import_to_neo4j.py"

def print_step(step_num: int, title: str):
    print(f"\n[{step_num}/4] === {title} ===")

def check_script(script_path: Path):
    if not script_path.exists():
        print(f"错误: 找不到必要的流水线脚本 -> {script_path}", file=sys.stderr)
        sys.exit(1)

def run_command(cmd: list):
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        print(f"执行流水线中断，错误指令: {' '.join((str(x) for x in cmd))}", file=sys.stderr)
        sys.exit(e.returncode)

def copy_sample_to_raw():
    print_step(1, "加载高质量样本数据 (Sample -> Raw)")
    if not SAMPLE_DIR.exists():
        print(f"错误: 样本数据目录不存在 -> {SAMPLE_DIR}", file=sys.stderr)
        sys.exit(1)
    
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    files_copied = 0
    for sample_file in SAMPLE_DIR.glob("*.csv"):
        dest_file = RAW_DIR / sample_file.name
        shutil.copy2(sample_file, dest_file)
        print(f"  - 挂载样本: {sample_file.name} -> data/raw/")
        files_copied += 1
    
    if files_copied == 0:
        print(f"错误: 没有在 {SAMPLE_DIR} 找到任何 CSV 样本文件", file=sys.stderr)
        sys.exit(1)
    print("[SUCCESS] 样本加载完成")

def main():
    print("======================================================")
    print("  企业级网络恶意行为图谱分析系统 - 启动演示初始化")
    print("======================================================")

    check_script(CLEAN_LOGS_PY)
    check_script(EXTRACT_ENTITIES_PY)
    check_script(IMPORT_TO_NEO4J_PY)

    # 步骤 1：挂载样本数据
    copy_sample_to_raw()
    
    # 步骤 2：清洗数据
    print_step(2, "对原始样本执行数据清洗与标准化转换 (Data Cleaning)")
    run_command([sys.executable, str(CLEAN_LOGS_PY)])
    
    # 步骤 3：抽取实体
    print_step(3, "根据图谱建模定义抽取阶段性知识 (Entity Extraction)")
    run_command([sys.executable, str(EXTRACT_ENTITIES_PY)])
    
    # 步骤 4：入图
    print_step(4, "执行 Neo4j 高性能图数据初始化灌装 (Graph Ingestion)")
    run_command([sys.executable, str(IMPORT_TO_NEO4J_PY)])
    
    print("\n======================================================")
    print("[SUCCESS] 全部演示环境数据加载完成！")
    print("您现在可以：")
    print(" 1. 登录控制台查看【工作台】的宏观监控与告警分类统计。")
    print(" 2. 进入【告警中心】查看这批样本中的“暴力破解”与“跨域横向移动”高危预警。")
    print(" 3. 在【图谱分析】搜索或顺藤摸瓜看到 203.0.113.42 这一外部 IP 究竟是如何攻陷内部账号并渗透 DB/DC 的。")
    print(" 4. 跳转【封禁管理】确认该外部威胁已触发全网安全策略联动下发阻断。")
    print("======================================================")

if __name__ == "__main__":
    main()
