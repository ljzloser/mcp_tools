"""MCP Tool Hub — 工具路由器"""

from __future__ import annotations

from loguru import logger

from api.tool import ToolDef
from api.types import MCPToolResult
from .plugin_manager import PluginManager
from .registry import ToolRegistry


class ToolRouter:
    """
    工具路由器（供 MCP Server 使用）

    职责：
    - 封装 tools/list → 从 ToolRegistry 聚合
    - 封装 tools/call → 查找插件 → 调用 PluginManager.dispatch
    """

    def __init__(
        self, registry: ToolRegistry, plugin_manager: PluginManager
    ) -> None:
        self.registry = registry
        self.plugin_manager = plugin_manager

    def list_tools(self) -> list[ToolDef]:
        """聚合所有已注册工具（对应 MCP tools/list）"""
        return self.registry.list_all_tools()

    async def call_tool(
        self, tool_name: str, arguments: dict
    ) -> MCPToolResult:
        """路由到对应插件执行（对应 MCP tools/call）"""
        plugin = self.registry.find_plugin(tool_name)
        if plugin is None:
            logger.warning(f"未找到工具: {tool_name}")
            return MCPToolResult(
                content=[{"type": "text", "text": f"未知工具: {tool_name}"}],
                is_error=True,
            )

        logger.debug(f"路由工具调用: {tool_name} → 插件 [{plugin.meta.name}]")
        try:
            result = await plugin.call_tool(tool_name, arguments)
            return result
        except Exception as e:
            logger.error(f"工具调用异常: {tool_name} - {e}")
            return MCPToolResult(
                content=[{"type": "text", "text": f"工具调用失败: {e}"}],
                is_error=True,
            )
