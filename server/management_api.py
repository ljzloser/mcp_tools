"""MCP Tool Hub — FastAPI HTTP 管理 API"""

from __future__ import annotations

import asyncio
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from api.protocol import (
    LogClearResponse,
    LogItem,
    LogListResponse,
    LogPruneResponse,
    LogRetentionConfig,
    McpToggleRequest,
    PluginConfigResponse,
    PluginConfigUpdate,
    PluginDetail,
    PluginInvokeRequest,
    PluginInvokeResponse,
    PluginListResponse,
    PluginSummary,
    PluginToolItem,
    ServerStatus,
    SimpleResponse,
)
from api.routes import Routes
from api.types import PluginStatus

from .database import Database
from .plugin_manager import PluginManager
from .registry import ToolRegistry
from .router import ToolRouter


class ResponseGuardMiddleware:
    """防止 http.response.start 被重复发送的中间件

    当异常在响应体序列化阶段发生时，ExceptionMiddleware 可能尝试发送
    新的 http.response.start，导致 ASGI 协议错误。此中间件拦截重复的
    http.response.start，确保协议完整性。
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        response_started = False

        async def _send(message: Message) -> None:
            nonlocal response_started
            if message["type"] == "http.response.start":
                if response_started:
                    logger.warning("拦截重复的 http.response.start，跳过")
                    return
                response_started = True
            await send(message)

        try:
            await self.app(scope, receive, _send)
        except Exception:
            if not response_started:
                raise
            # 响应头已发送但未完成，发送空 body 终止响应
            try:
                await send({"type": "http.response.body", "body": b"", "more_body": False})
            except Exception:
                pass


class ManagementAPI:
    """
    FastAPI HTTP 管理 API 服务

    与 MCP Server 共享 PluginManager 和 Database 实例。
    所有端点均为 async，框架自动处理并发。
    """

    def __init__(
        self,
        plugin_manager: PluginManager,
        database: Database,
        registry: ToolRegistry,
        router: ToolRouter,
        host: str = "127.0.0.1",
        port: int = 9020,
    ) -> None:
        self.plugin_manager = plugin_manager
        self.database = database
        self.registry = registry
        self.router = router
        self.host = host
        self.port = port

        self.app = FastAPI(
            title="MCP Tool Hub API",
            version="0.1.0",
            description="MCP Tool Hub 管理 API",
        )

        # 防止双重 http.response.start 的保护中间件（最外层）
        self.app.add_middleware(ResponseGuardMiddleware)

        # CORS（允许 UI 界面跨域访问）
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_methods=["*"],
            allow_headers=["*"],
        )

        # 全局异常处理
        @self.app.exception_handler(Exception)
        async def global_exception_handler(request: Request, exc: Exception):
            logger.error(f"API 未处理异常 [{request.method} {request.url}]: {exc}", exc_info=True)
            return JSONResponse(
                status_code=500,
                content={"detail": f"内部服务器错误: {str(exc)}"},
            )

        self._server: uvicorn.Server | None = None
        self._task: asyncio.Task | None = None

        # MCP 开关追踪（默认所有插件 MCP 开启）
        self._mcp_disabled: set[str] = set()
        self._mcp_callback: Any = None

        self._register_routes()

    def set_mcp_callback(self, callback: Any) -> None:
        """设置 MCP 状态变更回调，用于同步 FastMCP 工具注册/注销"""
        self._mcp_callback = callback

    def _register_routes(self) -> None:
        """注册所有路由"""
        app = self.app

        @app.get(Routes.HEALTH)
        async def health():
            return {"status": "ok"}

        @app.get(Routes.SERVER_STATUS, response_model=ServerStatus)
        async def server_status():
            statuses = self.plugin_manager.get_all_statuses()
            loaded = sum(
                1 for s in statuses.values() if s == PluginStatus.LOADED
            )
            total = len(self.plugin_manager.list_discovered())
            return ServerStatus(
                running=True,
                plugins_loaded=loaded,
                plugins_total=total,
            )

        @app.post(Routes.SERVER_RELOAD, response_model=SimpleResponse)
        async def server_reload():
            """重新加载所有插件"""
            try:
                await self.plugin_manager.unload_all()
                self.registry.clear()

                self.plugin_manager.discover()
                disabled = []
                rows = await self.database.list_plugins()
                for r in rows:
                    if not r.get("enabled", True):
                        disabled.append(r["name"])

                await self.plugin_manager.load_all(skip=disabled)

                for plugin_name in self.plugin_manager.list_discovered():
                    plugin = self.plugin_manager.get_plugin(plugin_name)
                    if plugin is not None:
                        try:
                            self.registry.register_plugin(plugin)
                            await self.database.register_plugin(
                                plugin.meta.name,
                                plugin.meta.display_name,
                                plugin.meta.version,
                            )
                            await self.database.update_plugin_status(
                                plugin.meta.name, PluginStatus.LOADED.value
                            )
                        except ValueError as e:
                            logger.error(f"注册插件 [{plugin_name}] 失败: {e}")
                            await self.database.update_plugin_status(
                                plugin_name, PluginStatus.ERROR.value
                            )

                return SimpleResponse(ok=True, message="重载完成")
            except Exception as e:
                logger.error(f"服务重载失败: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @app.get(Routes.PLUGINS, response_model=PluginListResponse)
        async def list_plugins():
            result = []
            for name in self.plugin_manager.list_discovered():
                plugin = self.plugin_manager.get_plugin(name)
                status = self.plugin_manager.get_status(name)
                enabled = True
                mcp_enabled = True

                # 从 DB 获取启用状态
                db_plugin = await self.database.get_plugin(name)
                if db_plugin:
                    enabled = bool(db_plugin.get("enabled", True))
                    mcp_enabled = bool(db_plugin.get("mcp_enabled", True))

                if plugin:
                    tool_count = len(self.registry.get_plugin_tools(name))
                    has_widget = self.plugin_manager.get_widget(name) is not None
                    has_config = plugin.config_class is not None
                    result.append(
                        PluginSummary(
                            name=name,
                            display_name=plugin.meta.display_name,
                            version=plugin.meta.version,
                            status=status.value,
                            enabled=enabled,
                            tool_count=tool_count,
                            has_widget=has_widget,
                            has_config=has_config,
                            mcp_enabled=mcp_enabled,
                        )
                    )
                else:
                    display = db_plugin["display_name"] if db_plugin else name
                    version = db_plugin["version"] if db_plugin else "?"
                    result.append(
                        PluginSummary(
                            name=name,
                            display_name=display,
                            version=version,
                            status=status.value,
                            enabled=enabled,
                            tool_count=0,
                            has_widget=False,
                            has_config=False,
                            mcp_enabled=mcp_enabled,
                        )
                    )

            return PluginListResponse(plugins=result)

        @app.get(Routes.PLUGIN_DETAIL, response_model=PluginDetail)
        async def get_plugin(name: str):
            plugin = self.plugin_manager.get_plugin(name)
            status = self.plugin_manager.get_status(name)

            # 获取数据库信息
            db_plugin = await self.database.get_plugin(name)
            enabled = bool(db_plugin.get("enabled", True)) if db_plugin else True

            if plugin is not None:
                # 插件已加载，返回完整信息
                tools = self.registry.get_plugin_tools(name)
                config = await self.database.get_plugin_config(name)
                has_widget = self.plugin_manager.get_widget(name) is not None
                has_config = plugin.config_class is not None
                mcp_enabled = await self.database.is_plugin_mcp_enabled(name)
                return PluginDetail(
                    name=name,
                    display_name=plugin.meta.display_name,
                    version=plugin.meta.version,
                    status=status.value,
                    enabled=enabled,
                    tools=[
                        PluginToolItem(name=t.name, description=t.description, input_schema=t.input_schema)
                        for t in tools
                    ],
                    config=config,
                    has_widget=has_widget,
                    has_config=has_config,
                    mcp_enabled=mcp_enabled,
                )
            else:
                # 插件未加载，返回基础信息
                if name not in self.plugin_manager.list_discovered():
                    raise HTTPException(status_code=404, detail=f"插件 [{name}] 未找到")

                display = db_plugin.get("display_name", name) if db_plugin else name
                version = db_plugin.get("version", "?") if db_plugin else "?"
                mcp_enabled = bool(db_plugin.get("mcp_enabled", True)) if db_plugin else True
                return PluginDetail(
                    name=name,
                    display_name=display,
                    version=version,
                    status=status.value,
                    enabled=enabled,
                    tools=[],
                    config={},
                    has_widget=False,
                    mcp_enabled=mcp_enabled,
                )

        @app.put(Routes.PLUGIN_ENABLE, response_model=SimpleResponse)
        async def enable_plugin(name: str):
            """启用插件：持久化 + 实际加载"""
            await self.database.set_plugin_enabled(name, True)

            # 如果插件已加载则跳过
            plugin = self.plugin_manager.get_plugin(name)
            if plugin is not None:
                return SimpleResponse(ok=True, message=f"插件 [{name}] 已启用（已加载）")

            try:
                plugin = await self.plugin_manager.load(name)
                self.registry.register_plugin(plugin)
                await self.database.register_plugin(
                    plugin.meta.name, plugin.meta.display_name, plugin.meta.version
                )
                await self.database.update_plugin_status(name, PluginStatus.LOADED.value)

                # 恢复 MCP 状态
                mcp_enabled = await self.database.is_plugin_mcp_enabled(name)
                if not mcp_enabled:
                    self._mcp_disabled.add(name)
                elif self._mcp_callback:
                    self._mcp_callback(name, True)

                return SimpleResponse(ok=True, message=f"插件 [{name}] 已启用并加载")
            except Exception as e:
                await self.database.update_plugin_status(name, PluginStatus.ERROR.value)
                raise HTTPException(status_code=500, detail=str(e))

        @app.put(Routes.PLUGIN_DISABLE, response_model=SimpleResponse)
        async def disable_plugin(name: str):
            """禁用插件：持久化 + 实际卸载"""
            await self.database.set_plugin_enabled(name, False)

            # 如果插件未加载则跳过
            plugin = self.plugin_manager.get_plugin(name)
            if plugin is None:
                return SimpleResponse(ok=True, message=f"插件 [{name}] 已禁用（未加载）")

            try:
                # 从 FastMCP 注销工具
                if self._mcp_callback:
                    self._mcp_callback(name, False)
                self._mcp_disabled.discard(name)

                await self.plugin_manager.unload(name)
                self.registry.unregister_plugin(name)
                await self.database.update_plugin_status(name, PluginStatus.UNLOADED.value)

                return SimpleResponse(ok=True, message=f"插件 [{name}] 已禁用并卸载")
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

        @app.get(Routes.PLUGIN_CONFIG, response_model=PluginConfigResponse)
        async def get_plugin_config(name: str):
            """获取插件配置及字段声明"""
            plugin = self.plugin_manager.get_plugin(name)
            config = await self.database.get_plugin_config(name)

            # 从 config_class 提取字段声明信息
            schema: dict[str, Any] = {}
            if plugin is not None and plugin.config_class is not None:
                for field_name, field in plugin.config_class.get_fields().items():
                    # 安全处理 default：确保 JSON 可序列化
                    try:
                        import json
                        safe_default = json.loads(json.dumps(field.default, default=str))
                    except (TypeError, ValueError):
                        safe_default = str(field.default)
                    schema[field_name] = {
                        "type": field.widget_type,
                        "label": field.label,
                        "description": field.description,
                        "default": safe_default,
                        "visible": field.visible,
                    }
                    # ChoiceField 额外信息
                    if hasattr(field, "choices") and field.choices:  # type: ignore[attr-defined]
                        schema[field_name]["choices"] = field.choices  # type: ignore[attr-defined]

            return PluginConfigResponse(name=name, config=config, schema_info=schema)

        @app.put(Routes.PLUGIN_CONFIG, response_model=SimpleResponse)
        async def update_plugin_config(name: str, body: PluginConfigUpdate):
            await self.database.set_plugin_config(name, body.config)
            # 通知插件重新加载配置
            plugin = self.plugin_manager.get_plugin(name)
            if plugin is not None:
                plugin._init_config(body.config)
                if plugin.config is not None:
                    plugin.on_config_changed(plugin.config)
            # 通知 Widget
            widget = self.plugin_manager.get_widget(name)
            if widget:
                widget.apply_config(body.config)
            return SimpleResponse(ok=True, message=f"插件 [{name}] 配置已更新")

        @app.put(Routes.PLUGIN_MCP, response_model=SimpleResponse)
        async def toggle_plugin_mcp(name: str, body: McpToggleRequest):
            """开启/关闭插件的 MCP 工具对外暴露

            关闭 MCP：插件保持加载，UI 和 invoke 通信正常，但 AI 客户端看不到工具。
            开启 MCP：恢复工具注册到 MCP Server。
            """
            plugin = self.plugin_manager.get_plugin(name)
            if plugin is None:
                raise HTTPException(status_code=404, detail=f"插件 [{name}] 未加载")

            if body.enabled:
                self._mcp_disabled.discard(name)
                action = "已开启"
                if self._mcp_callback:
                    self._mcp_callback(name, True)
            else:
                self._mcp_disabled.add(name)
                action = "已关闭"
                if self._mcp_callback:
                    self._mcp_callback(name, False)

            # 持久化到数据库
            await self.database.set_plugin_mcp_enabled(name, body.enabled)

            return SimpleResponse(ok=True, message=f"插件 [{name}] MCP 工具 {action}")

        @app.post(Routes.PLUGIN_INVOKE, response_model=PluginInvokeResponse)
        async def invoke_plugin_tool(name: str, body: PluginInvokeRequest):
            """插件前端 → 后端通用调用通道"""
            plugin = self.plugin_manager.get_plugin(name)
            if plugin is None:
                raise HTTPException(
                    status_code=404,
                    detail=f"插件 [{name}] 未加载，无法调用工具",
                )

            # 验证工具属于该插件（直接从插件实例获取，不受 MCP 开关影响）
            plugin_tools = plugin.get_tools()
            tool_names = [t.name for t in plugin_tools]
            if body.tool_name not in tool_names:
                raise HTTPException(
                    status_code=400,
                    detail=f"工具 '{body.tool_name}' 不属于插件 [{name}]，可用: {tool_names}",
                )

            try:
                result = await plugin.call_tool(body.tool_name, body.arguments)
                return PluginInvokeResponse(
                    ok=True,
                    content=result.content,
                    is_error=result.is_error,
                )
            except Exception as e:
                logger.error(f"插件 [{name}] 工具调用异常: {body.tool_name} - {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @app.get(Routes.LOGS, response_model=LogListResponse)
        async def get_logs(plugin: str | None = None, limit: int = 200):
            rows = await self.database.get_logs(plugin_name=plugin, limit=limit)
            return LogListResponse(logs=[LogItem(**r) for r in rows])

        @app.delete(Routes.LOGS, response_model=LogClearResponse)
        async def clear_logs(plugin: str | None = None):
            count = await self.database.clear_logs(plugin_name=plugin)
            return LogClearResponse(ok=True, deleted=count)

        @app.get(Routes.LOGS_CONFIG, response_model=LogRetentionConfig)
        async def get_log_config():
            """获取日志清理配置"""
            retention_days = int(await self.database.get_config("log_retention_days", "30"))
            max_records = int(await self.database.get_config("log_max_records", "10000"))
            total_count = await self.database.get_log_count()
            return LogRetentionConfig(
                retention_days=retention_days,
                max_records=max_records,
                total_count=total_count,
            )

        @app.put(Routes.LOGS_CONFIG, response_model=SimpleResponse)
        async def update_log_config(body: LogRetentionConfig):
            """更新日志清理配置"""
            await self.database.set_config("log_retention_days", str(body.retention_days))
            await self.database.set_config("log_max_records", str(body.max_records))
            return SimpleResponse(
                ok=True,
                message=f"日志清理配置已更新: 保留 {body.retention_days} 天 / 最多 {body.max_records} 条",
            )

        @app.post(Routes.LOGS_PRUNE, response_model=LogPruneResponse)
        async def prune_logs():
            """手动触发日志清理"""
            retention_days = int(await self.database.get_config("log_retention_days", "30"))
            max_records = int(await self.database.get_config("log_max_records", "10000"))
            deleted = await self.database.prune_logs(
                retention_days=retention_days,
                max_records=max_records,
            )
            return LogPruneResponse(ok=True, deleted=deleted)

    async def start(self) -> None:
        """启动 uvicorn 服务（后台任务），等待服务就绪"""
        config = uvicorn.Config(
            self.app,
            host=self.host,
            port=self.port,
            log_level="warning",
        )
        self._server = uvicorn.Server(config)
        self._task = asyncio.create_task(self._server.serve())

        # 等待服务就绪
        for _ in range(50):  # 最多等 5 秒
            if self._server.started:
                break
            await asyncio.sleep(0.1)
        else:
            logger.warning(f"管理 API 启动超时: http://{self.host}:{self.port}")

    async def stop(self) -> None:
        """停止 HTTP 服务"""
        if self._server:
            self._server.should_exit = True
            if self._task:
                try:
                    await asyncio.wait_for(self._task, timeout=5.0)
                except (asyncio.TimeoutError, asyncio.CancelledError):
                    self._task.cancel()
                    try:
                        await self._task
                    except (asyncio.CancelledError, Exception):
                        pass
            self._server = None
            self._task = None
