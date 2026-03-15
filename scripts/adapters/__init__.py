#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
文件路径：scripts/adapters/__init__.py

文件作用：
1. 汇总所有日志适配器。
2. 为 log_watcher.py 提供“目录 -> 适配器”的统一映射。
3. 保持适配器层结构清晰，便于后续继续扩展更多日志源。
"""

from adapters.generic_waf_adapter import ADAPTER_NAME as GENERIC_WAF_ADAPTER_NAME
from adapters.generic_waf_adapter import parse_file as parse_generic_waf_file
from adapters.linux_firewall_adapter import ADAPTER_NAME as LINUX_FIREWALL_ADAPTER_NAME
from adapters.linux_firewall_adapter import parse_file as parse_linux_firewall_file
from adapters.safe_line_waf_adapter import ADAPTER_NAME as SAFELINE_ADAPTER_NAME
from adapters.safe_line_waf_adapter import parse_file as parse_safeline_file
from adapters.windows_firewall_adapter import ADAPTER_NAME as WINDOWS_FIREWALL_ADAPTER_NAME
from adapters.windows_firewall_adapter import parse_file as parse_windows_firewall_file


ADAPTER_REGISTRY = {
    "safeline_waf": {
        "adapter_name": SAFELINE_ADAPTER_NAME,
        "parse_file": parse_safeline_file,
    },
    "n9e_waf": {
        "adapter_name": GENERIC_WAF_ADAPTER_NAME,
        "parse_file": parse_generic_waf_file,
    },
    "windows_firewall": {
        "adapter_name": WINDOWS_FIREWALL_ADAPTER_NAME,
        "parse_file": parse_windows_firewall_file,
    },
    "linux_firewall": {
        "adapter_name": LINUX_FIREWALL_ADAPTER_NAME,
        "parse_file": parse_linux_firewall_file,
    },
}


__all__ = ["ADAPTER_REGISTRY"]
