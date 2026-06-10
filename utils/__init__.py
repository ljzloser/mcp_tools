"""MCP Tool Hub — 工具模块"""

from .logger import setup_logger
from .paths import Paths, paths

__all__ = ["Paths", "paths", "setup_logger"]
