"""MCP Tool Hub — 通用类型定义

工具定义已迁移到 api/tool.py 的 ToolDef 类，
使用 Pydantic 模型声明参数，自动生成 JSON Schema。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class PluginStatus(Enum):
    """插件运行状态"""

    UNLOADED = "unloaded"
    LOADING = "loading"
    LOADED = "loaded"
    ERROR = "error"


@dataclass
class PluginMeta:
    """插件元数据（自描述）"""

    name: str  # 唯一标识，如 "http_tool"
    display_name: str  # 显示名称，如 "HTTP 请求工具"
    version: str  # 语义化版本
    description: str  # 功能简述
    author: str = ""
    icon: str = ""  # 图标路径或 emoji


@dataclass
class MCPToolResult:
    """MCP 工具调用结果"""

    content: list[dict[str, Any]]  # [{"type": "text", "text": "..."}]
    is_error: bool = False
