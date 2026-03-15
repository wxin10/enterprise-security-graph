#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
文件路径：backend/app.py

文件作用：
1. 作为 Flask 后端启动入口。
2. 调用应用工厂创建 Flask 实例。
3. 供命令行直接运行或供 WSGI 服务加载。
"""

from __future__ import annotations

from app import create_app


app = create_app()


if __name__ == "__main__":
    app.run(
        host=app.config["HOST"],
        port=app.config["PORT"],
        debug=app.config["DEBUG"],
    )
