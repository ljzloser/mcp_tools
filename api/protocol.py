"""MCP Tool Hub — 前后端共享协议模型

所有 Pydantic 模型集中定义于此，后端 API 和前端 UI 共用。
前端使用这些模型解析 HTTP 响应，避免 dict.get() 硬编码字段名。
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


# ── 通用 ──


class SimpleResponse(BaseModel):
    ok: bool
    message: str = ""


# ── 服务 ──


class ServerStatus(BaseModel):
    running: bool
    plugins_loaded: int
    plugins_total: int


# ── 插件 ──


class PluginSummary(BaseModel):
    name: str
    display_name: str
    version: str
    status: str
    enabled: bool
    mcp_enabled: bool = True  # MCP 工具是否对外暴露
    tool_count: int = 0
    has_widget: bool = False
    has_config: bool = False


class PluginToolItem(BaseModel):
    """插件工具项"""
    name: str
    description: str
    input_schema: dict[str, Any] = {}


class PluginDetail(PluginSummary):
    tools: list[PluginToolItem] = []
    config: dict[str, Any] = {}


class McpToggleRequest(BaseModel):
    """MCP 开关请求"""
    enabled: bool


class PluginInvokeRequest(BaseModel):
    tool_name: str
    arguments: dict[str, Any] = {}


class PluginInvokeResponse(BaseModel):
    ok: bool
    content: list[dict[str, Any]]
    is_error: bool = False


class PluginConfigUpdate(BaseModel):
    config: dict[str, Any]


class PluginConfigResponse(BaseModel):
    """插件配置响应"""
    name: str
    config: dict[str, Any]
    schema_info: dict[str, Any] = {}  # 字段声明信息（label, type, choices 等）


# ── 插件列表响应 ──


class PluginListResponse(BaseModel):
    plugins: list[PluginSummary] = []


# ── 日志 ──


class LogItem(BaseModel):
    id: int = 0
    plugin_name: str = ""
    level: str = "INFO"
    message: str = ""
    created_at: str = ""


class LogListResponse(BaseModel):
    logs: list[LogItem] = []


class LogRetentionConfig(BaseModel):
    retention_days: int = 30
    max_records: int = 10000
    total_count: int = 0  # 当前日志总条数


class LogPruneResponse(BaseModel):
    ok: bool = True
    deleted: int = 0


class LogClearResponse(BaseModel):
    ok: bool = True
    deleted: int = 0
