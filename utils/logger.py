"""MCP Tool Hub — 日志配置"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from loguru import logger

from .paths import paths

# 全局引用，由 MCPServerApp.start() 设置
_db_sink_id: int | None = None


def _db_sink(message: Any) -> None:
    """loguru sink：将日志写入数据库"""
    from server.database import Database  # 延迟导入避免循环

    # _db_sink 在 loguru 线程中执行，需获取当前数据库实例
    db: Database | None = getattr(_db_sink, "_db", None)
    if db is None:
        return

    record = message.record
    level = record["level"].name
    text = str(record["message"]).strip()

    # 从模块名推断插件名（格式：plugins.xxx 或 server.xxx 等）
    module = record.get("name", "") or ""
    plugin_name = "system"
    if module.startswith("plugins."):
        parts = module.split(".")
        if len(parts) >= 2:
            plugin_name = parts[1]

    import asyncio

    try:
        loop = asyncio.get_running_loop()
        loop.create_task(db.add_log(plugin_name, level, text))
    except RuntimeError:
        pass  # 无事件循环时跳过


def setup_logger(level: str = "INFO") -> None:
    """配置 loguru 日志"""
    logger.remove()
    logger.add(
        sys.stderr,
        level=level,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
            "<level>{message}</level>"
        ),
        colorize=True,
    )
    log_path = paths.logs_dir / "mcp_tools_{time:YYYY-MM-DD}.log"
    logger.add(
        str(log_path),
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}",
        rotation="1 day",
        retention="7 days",
        compression="zip",
    )


def setup_db_sink(db) -> None:
    """启用数据库日志 sink（在 MCPServerApp.start() 中调用）"""
    global _db_sink_id
    _db_sink._db = db
    _db_sink_id = logger.add(
        _db_sink,
        level="INFO",
        format="{message}",
        filter=lambda record: not record["name"].startswith("aiosqlite"),
    )


def remove_db_sink() -> None:
    """禁用数据库日志 sink"""
    global _db_sink_id
    if _db_sink_id is not None:
        logger.remove(_db_sink_id)
        _db_sink_id = None
