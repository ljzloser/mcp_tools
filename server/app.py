"""MCP Tool Hub — MCP Server 应用主类"""

from __future__ import annotations

import asyncio
from pathlib import Path

from loguru import logger
from mcp.server.fastmcp import FastMCP

from api.types import PluginStatus
from utils.paths import paths

from .database import Database
from .management_api import ManagementAPI
from .plugin_manager import PluginManager
from .registry import ToolRegistry
from .router import ToolRouter


class MCPServerApp:
    """
    MCP Server 应用主类

    支持两种传输模式：
    - stdio：由 AI 客户端启动，通过 stdin/stdout 通信
    - sse：后台常驻服务，AI 客户端通过 HTTP SSE 连接

    持有：
    - FastMCP（MCP 协议层）
    - FastAPI ManagementAPI（HTTP 管理接口）
    - Database（aiosqlite）
    - PluginManager / ToolRegistry / ToolRouter
    """

    def __init__(
        self,
        name: str = "mcp-tool-hub",
        plugins_dir: Path | str | None = None,
        db_path: Path | str | None = None,
        api_host: str = "127.0.0.1",
        api_port: int = 9020,
        transport: str = "stdio",
        sse_host: str = "127.0.0.1",
        sse_port: int = 9021,
    ) -> None:
        self.name = name
        self.plugins_dir = Path(plugins_dir) if plugins_dir else paths.plugins_dir
        self.db_path = Path(db_path) if db_path else paths.db_path
        self.transport = transport
        self.sse_host = sse_host
        self.sse_port = sse_port

        # 核心组件
        self.database = Database(db_path)
        self.plugin_manager = PluginManager(self.plugins_dir)
        self.plugin_manager.set_database(self.database)
        self.registry = ToolRegistry()
        self.router = ToolRouter(self.registry, self.plugin_manager)
        self.management_api = ManagementAPI(
            plugin_manager=self.plugin_manager,
            database=self.database,
            registry=self.registry,
            router=self.router,
            host=api_host,
            port=api_port,
        )

        # FastMCP 实例（SSE 模式需要 host/port）
        mcp_kwargs: dict = {"name": name}
        if transport == "sse":
            mcp_kwargs["host"] = sse_host
            mcp_kwargs["port"] = sse_port
        self.mcp = FastMCP(**mcp_kwargs)

        # 设置 MCP 回调：MCP 开关变更时同步 FastMCP 工具注册/注销
        self.management_api.set_mcp_callback(self._on_mcp_toggled)

        self._running = False

    def _on_mcp_toggled(self, plugin_name: str, enabled: bool) -> None:
        """MCP 开关回调 — 同步 FastMCP 工具注册/注销

        注意：registry 是内部调用和 MCP 共用的，禁用 MCP 只从 FastMCP 注销工具，
        不从 registry 移除（invoke 端点依赖 registry）。
        """
        if enabled:
            # 重新注册工具到 FastMCP
            plugin = self.plugin_manager.get_plugin(plugin_name)
            if plugin is not None:
                for tool_def in plugin.get_tools():
                    self._register_single_tool(tool_def)
        else:
            # 仅从 FastMCP 注销工具，插件保持加载，registry 保持不变
            tools = self.registry.get_plugin_tools(plugin_name)
            for t in tools:
                self.mcp._tool_manager._tools.pop(t.name, None)

    async def _register_dynamic_tools(self) -> None:
        """
        根据已加载的插件动态注册工具到 FastMCP

        FastMCP 使用装饰器注册工具，我们需要手动将插件定义的工具
        注册为 MCP 可调用的工具。
        """
        tools = self.registry.list_all_tools()
        for tool_def in tools:
            # 为每个工具创建闭包并注册
            self._register_single_tool(tool_def)

        logger.info(f"已向 MCP Server 注册 {len(tools)} 个工具")

    def _register_single_tool(self, tool_def) -> None:
        """注册单个工具到 FastMCP

        关键：FastMCP 通过函数签名推断 input_schema，因此不能用 **kwargs
        （否则 schema 会变成 {"kwargs": "string"}），必须根据插件的
        input_schema 动态生成 Pydantic arg_model，替换 Tool 的 parameters
        和 fn_metadata，使参数校验和 schema 暴露都正确。
        """
        from pydantic import create_model

        from mcp.server.fastmcp.tools import Tool
        from mcp.server.fastmcp.utilities.func_metadata import ArgModelBase, FuncMetadata

        tool_name = tool_def.name
        tool_desc = tool_def.description
        input_schema = tool_def.input_schema

        # 创建异步处理函数（使用 **kwargs 接收，但注册时替换 schema）
        async def tool_handler(**kwargs) -> str:
            try:
                result = await self.router.call_tool(tool_name, kwargs)
                # 将 MCPToolResult 转为字符串
                texts = []
                for item in result.content:
                    if item.get("type") == "text":
                        texts.append(item.get("text", ""))
                return "\n".join(texts) if not result.is_error else f"[ERROR] {'; '.join(texts)}"
            except Exception as e:
                logger.error(f"工具 [{tool_name}] 执行异常: {e}")
                return f"[ERROR] {e}"

        tool_handler.__name__ = tool_name
        tool_handler.__doc__ = tool_desc

        try:
            # 1. 用 from_function 创建 Tool（拿到基础结构）
            mcp_tool = Tool.from_function(
                tool_handler,
                name=tool_name,
                description=tool_desc,
            )

            # 2. 根据 input_schema 动态创建 Pydantic arg_model
            type_map = {
                "string": str, "number": float, "integer": int,
                "boolean": bool, "object": dict, "array": list,
            }

            def _resolve_type(prop: dict) -> type:
                """从 JSON Schema 属性推断 Python 类型，支持 anyOf/oneOf"""
                t = prop.get("type")
                if t:
                    return type_map.get(t, str)
                for key in ("anyOf", "oneOf"):
                    variants = prop.get(key, [])
                    for v in variants:
                        vt = v.get("type")
                        if vt and vt != "null":
                            return type_map.get(vt, str)
                return str

            required = set(input_schema.get("required", []))
            fields: dict = {}
            for pname, prop in input_schema.get("properties", {}).items():
                py_type = _resolve_type(prop)
                if pname in required:
                    fields[pname] = (py_type, ...)
                else:
                    fields[pname] = (py_type, None)

            ArgModel = create_model(
                f"{tool_name}Arguments",
                __base__=ArgModelBase,
                **fields,
            )

            # 3. 替换 parameters 和 fn_metadata
            mcp_tool.parameters = input_schema
            mcp_tool.fn_metadata = FuncMetadata(arg_model=ArgModel)

            # 4. 手动注入到 FastMCP 的工具管理器
            self.mcp._tool_manager._tools[tool_name] = mcp_tool
            logger.debug(f"注册工具 [{tool_name}] 成功，schema: {list(input_schema.get('properties', {}).keys())}")
        except Exception as e:
            logger.error(f"注册工具 [{tool_name}] 到 FastMCP 失败: {e}")

    async def start(self) -> None:
        """启动服务：初始化数据库 → 加载插件 → 启动管理 API → 启动 MCP"""
        logger.info(f"MCP Tool Hub [{self.name}] 启动中...")

        # 1. 数据库
        await self.database.connect()
        await self.database.init_tables()
        logger.info("数据库初始化完成")

        # 启用数据库日志 sink
        from utils.logger import setup_db_sink
        setup_db_sink(self.database)

        # 启动时自动清理过期日志
        await self._prune_logs_on_startup()

        # 2. 发现并加载插件
        self.plugin_manager.discover()

        # 从 DB 读取禁用插件列表
        disabled_plugins = await self._load_disabled_plugins()

        await self.plugin_manager.load_all(skip=disabled_plugins)

        # 3. 将插件工具注册到 registry
        for plugin_name in self.plugin_manager.list_discovered():
            plugin = self.plugin_manager.get_plugin(plugin_name)
            if plugin is not None:
                try:
                    self.registry.register_plugin(plugin)
                    # 更新 DB 中的插件状态
                    await self.database.register_plugin(
                        plugin.meta.name,
                        plugin.meta.display_name,
                        plugin.meta.version,
                    )
                    await self.database.update_plugin_status(
                        plugin.meta.name, PluginStatus.LOADED.value
                    )
                except ValueError as e:
                    logger.error(f"注册插件 [{plugin_name}] 工具失败: {e}")
                    await self.database.update_plugin_status(
                        plugin_name, PluginStatus.ERROR.value
                    )

        # 4. 向 FastMCP 动态注册工具
        await self._register_dynamic_tools()

        # 4.5 从 DB 恢复 MCP 禁用状态
        await self._load_mcp_disabled()

        # 5. 启动管理 API
        await self.management_api.start()
        logger.info(f"管理 API 已启动: http://127.0.0.1:{self.management_api.port}")

        self._running = True
        logger.info(f"MCP Tool Hub [{self.name}] 启动完成，共加载 {len(self.plugin_manager._plugins)} 个插件")

        # 6. 启动 MCP 传输（阻塞）
        if self.transport == "sse":
            sse_url = f"http://{self.sse_host}:{self.sse_port}/sse"
            logger.info(f"MCP SSE 服务已启动: {sse_url}")
            logger.info(f"AI 客户端配置: {{\"url\": \"{sse_url}\"}}")
            await self.mcp.run_sse_async()
        else:
            await self.mcp.run_stdio_async()

    async def stop(self) -> None:
        """停止服务"""
        logger.info("MCP Tool Hub 停止中...")

        # 移除数据库日志 sink
        from utils.logger import remove_db_sink
        remove_db_sink()

        try:
            await self.management_api.stop()
        except (Exception, asyncio.CancelledError, KeyboardInterrupt) as e:
            logger.error(f"停止管理 API 异常: {e}")

        # 更新 DB 中所有插件状态
        for plugin in list(self.plugin_manager._plugins.values()):
            try:
                await self.database.update_plugin_status(
                    plugin.meta.name, PluginStatus.UNLOADED.value
                )
            except (Exception, asyncio.CancelledError, KeyboardInterrupt) as e:
                logger.debug(f"更新插件 [{plugin.meta.name}] 状态跳过: {e}")

        try:
            await self.plugin_manager.unload_all()
        except (Exception, asyncio.CancelledError, KeyboardInterrupt) as e:
            logger.error(f"卸载插件异常: {e}")

        self.registry.clear()

        try:
            await self.database.close()
        except (Exception, asyncio.CancelledError, KeyboardInterrupt) as e:
            logger.debug(f"关闭数据库跳过: {e}")

        self._running = False
        logger.info("MCP Tool Hub 已停止")

    async def _load_disabled_plugins(self) -> list[str]:
        """从数据库读取禁用的插件列表"""
        rows = await self.database.list_plugins()
        return [r["name"] for r in rows if not r.get("enabled", True)]

    async def _load_mcp_disabled(self) -> None:
        """从数据库恢复 MCP 禁用状态"""
        rows = await self.database.list_plugins()
        for r in rows:
            if not r.get("mcp_enabled", True):
                name = r["name"]
                self.management_api._mcp_disabled.add(name)
                # 从 FastMCP 注销该插件的工具
                tools = self.registry.get_plugin_tools(name)
                for t in tools:
                    self.mcp._tool_manager._tools.pop(t.name, None)
                logger.info(f"插件 [{name}] MCP 已禁用（从数据库恢复）")

    async def _prune_logs_on_startup(self) -> None:
        """启动时根据配置自动清理过期日志"""
        retention_days = int(await self.database.get_config("log_retention_days", "30"))
        max_records = int(await self.database.get_config("log_max_records", "10000"))
        deleted = await self.database.prune_logs(
            retention_days=retention_days,
            max_records=max_records,
        )
        if deleted > 0:
            logger.info(f"自动清理过期日志: 删除 {deleted} 条 (保留 {retention_days} 天 / 最多 {max_records} 条)")

    @property
    def is_running(self) -> bool:
        return self._running
