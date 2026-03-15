#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
文件路径：backend/app/core/errors.py

文件作用：
1. 定义后端统一异常类型。
2. 提供统一异常处理注册函数。
3. 保证系统出现参数错误、资源不存在、数据库异常时都返回 JSON。
"""

from __future__ import annotations

from flask import Flask, current_app
from werkzeug.exceptions import HTTPException

from app.core.response import error_response


class APIError(Exception):
    """
    自定义业务异常基类。
    """

    def __init__(self, message: str, code: int = 4000, http_status: int = 400, data=None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.http_status = http_status
        self.data = data


class ValidationError(APIError):
    """
    参数校验异常。
    """

    def __init__(self, message: str = "请求参数不合法", data=None):
        super().__init__(message=message, code=4001, http_status=400, data=data)


class NotFoundError(APIError):
    """
    资源不存在异常。
    """

    def __init__(self, message: str = "目标资源不存在", data=None):
        super().__init__(message=message, code=4004, http_status=404, data=data)


class DatabaseError(APIError):
    """
    数据库访问异常。
    """

    def __init__(self, message: str = "数据库访问失败", data=None):
        super().__init__(message=message, code=5001, http_status=500, data=data)


def register_error_handlers(app: Flask) -> None:
    """
    注册全局异常处理器。
    """

    @app.errorhandler(APIError)
    def handle_api_error(error: APIError):
        return error_response(
            message=error.message,
            code=error.code,
            http_status=error.http_status,
            data=error.data,
        )

    @app.errorhandler(HTTPException)
    def handle_http_exception(error: HTTPException):
        return error_response(
            message=error.description or "HTTP 请求错误",
            code=error.code or 4000,
            http_status=error.code or 400,
            data={"name": error.name},
        )

    @app.errorhandler(Exception)
    def handle_unexpected_exception(error: Exception):
        current_app.logger.exception("未处理异常：%s", error)
        return error_response(
            message="服务器内部错误",
            code=5000,
            http_status=500,
            data={"detail": str(error)},
        )
