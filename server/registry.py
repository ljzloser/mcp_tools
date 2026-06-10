"""MCP Tool Hub — 工具注册表"""

from __future__ import annotations

from loguru import logger

from api.base_plugin import BasePlugin
from api.tool import ToolDef


class ToolRegistry:
    """
    工具名 → 插件 的映射表

    职责：
    - 注册/注销插件提供的所有工具
    - 提供 tool_name → plugin 的快速查找
    - 对外提供聚合的 tools/list
    """

    def __init__(self) -> None:
        self._tool_to_plugin: dict[str, BasePlugin] = {}  # tool_name → plugin
        self._plugin_tools: dict[str, list[ToolDef]] = {}  # plugin_name → tools

    def register_plugin(self, plugin: BasePlugin) -> None:
        """注册一个插件的所有工具"""
        plugin_name = plugin.meta.name
        tools = plugin.get_tools()

        # 检查工具名是否冲突
        for tool in tools:
            if tool.name in self._tool_to_plugin:
                existing = self._tool_to_plugin[tool.name].meta.name
                raise ValueError(
                    f"工具名冲突: '{tool.name}' 已被插件 '{existing}' 注册，"
                    f"无法再注册到插件 '{plugin_name}'"
                )

        # 注册
        for tool in tools:
            self._tool_to_plugin[tool.name] = plugin
        self._plugin_tools[plugin_name] = tools

        logger.info(
            f"插件 [{plugin_name}] 注册了 {len(tools)} 个工具: "
            f"{[t.name for t in tools]}"
        )

    def unregister_plugin(self, plugin_name: str) -> None:
        """注销一个插件的所有工具"""
        tools = self._plugin_tools.pop(plugin_name, [])
        for tool in tools:
            self._tool_to_plugin.pop(tool.name, None)
        if tools:
            logger.info(f"插件 [{plugin_name}] 已注销 {len(tools)} 个工具")

    def find_plugin(self, tool_name: str) -> BasePlugin | None:
        """根据工具名查找所属插件"""
        return self._tool_to_plugin.get(tool_name)

    def list_all_tools(self) -> list[ToolDef]:
        """返回所有已注册工具的聚合列表"""
        return [
            tool
            for tools in self._plugin_tools.values()
            for tool in tools
        ]

    def get_plugin_tools(self, plugin_name: str) -> list[ToolDef]:
        """获取指定插件的所有工具"""
        return self._plugin_tools.get(plugin_name, [])

    def get_tool_def(self, tool_name: str) -> ToolDef | None:
        """获取指定工具的定义"""
        for tools in self._plugin_tools.values():
            for tool in tools:
                if tool.name == tool_name:
                    return tool
        return None

    def clear(self) -> None:
        """清空所有注册"""
        self._tool_to_plugin.clear()
        self._plugin_tools.clear()
