"""MCP Tool Hub — 插件管理界面抽象基类

Widget 通过注入的 AsyncHttpClient 与后端通信：
- self.invoke(tool_name, arguments) → 调用后端插件工具
- self.http.get/post/put/delete → 调用任意管理 API

BasePluginWidget 继承 QObject，确保跨线程信号排队到主线程执行 UI 更新。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Union

from pydantic import BaseModel
from PySide6.QtCore import QObject
from PySide6.QtWidgets import QWidget

from .config import ConfigModel
from .tool import ToolDef
from .types import PluginMeta

if TYPE_CHECKING:
    from client.http_client import AsyncHttpClient

from .routes import Routes


class BasePluginWidget(QObject):
    """
    插件管理界面抽象基类

    每个插件提供一个 QWidget，嵌入到主界面的详情区域。
    Widget 可以包含：状态显示、配置表单、手动触发、日志查看等。

    前后端通信：
    - invoke(tool_name, arguments) → 调用后端插件工具，结果通过 on_invoke_result 回调
    - http 属性 → 直接访问 AsyncHttpClient，可调用任意管理 API
    """

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._invoke_counter = 0
        self._invoke_pending: dict[int, int] = {}  # request_id → invoke_id

    # ── 必须实现 ──

    def get_name(self) -> str:
        """返回关联的插件名（对应 PluginMeta.name）"""
        raise NotImplementedError

    def create_widget(self, parent: QWidget | None = None) -> QWidget:
        """创建并返回管理界面 QWidget"""
        raise NotImplementedError

    # ── 可选覆写 ──

    def on_status_changed(self, status: str) -> None:
        """插件状态变更时的回调"""
        pass

    def get_config_schema(self) -> dict[str, Any]:
        """返回可配置项的 JSON Schema"""
        return {}

    def apply_config(self, config: dict[str, Any]) -> None:
        """应用配置变更"""
        pass

    # ── 配置界面 ──

    def create_config_widget(self, parent: QWidget | None = None) -> QWidget | None:
        """创建配置界面（可选覆写）

        默认实现：如果关联插件有 config_class，自动生成配置表单。
        插件可覆写此方法提供完全自定义的配置界面。

        Returns:
            QWidget 或 None（无配置时返回 None）
        """
        config_model = self._get_config_model()
        if config_model is None:
            return None
        return config_model.create_form(parent)

    def _get_config_model(self) -> ConfigModel | None:
        """获取关联插件的 ConfigModel 实例（懒加载）

        尝试从插件模块导入 config_class 并创建实例。
        如果插件没有 config_class，返回 None。
        """
        if hasattr(self, "_config_model_cache"):
            return self._config_model_cache

        try:
            module = __import__(f"plugins.{self.get_name()}", fromlist=["PLUGIN_CLASS"])
            plugin_class = getattr(module, "PLUGIN_CLASS", None)
            if plugin_class is not None and hasattr(plugin_class, "config_class"):
                config_class = plugin_class.config_class
                if config_class is not None:
                    self._config_model_cache = config_class()
                    return self._config_model_cache
        except Exception:
            pass

        self._config_model_cache = None
        return None

    def load_config_to_form(self, form: QWidget) -> None:
        """从后端加载配置并填充到表单

        Args:
            form: create_config_widget() 或 create_form() 返回的表单
        """
        plugin_name = self.get_name()
        self._config_load_req = self.http.get(Routes.plugin_config(plugin_name))

    def save_config_from_form(self, form: QWidget) -> None:
        """从表单收集值并保存到后端

        Args:
            form: create_config_widget() 或 create_form() 返回的表单
        """
        if not hasattr(form, "get_values"):
            return
        values = form.get_values()  # type: ignore[union-attr]
        plugin_name = self.get_name()
        self._config_save_req = self.http.put(
            Routes.plugin_config(plugin_name),
            body={"config": values},
        )

    # ── 前后端通信 ──

    def set_http_client(self, http: AsyncHttpClient) -> None:
        """注入 HTTP 客户端（由框架在创建 Widget 后调用）"""
        self._http = http
        # 监听 HTTP 响应 — 因为 BasePluginWidget 是 QObject，
        # Qt 会自动将跨线程信号排队到主线程执行
        http.request_finished.connect(self._on_http_response)
        http.request_failed.connect(self._on_http_error)

    @property
    def http(self) -> AsyncHttpClient:
        """访问 HTTP 客户端，可调用任意管理 API"""
        return self._http

    def invoke(
        self,
        tool: ToolDef | str,
        arguments: BaseModel | dict[str, Any] | None = None,
    ) -> int:
        """调用后端插件工具（异步，结果通过 on_invoke_result 返回）

        Args:
            tool: 工具定义（ToolDef）或工具名（str）
            arguments: 工具参数（Pydantic 模型或 dict）

        Returns:
            invoke_id，用于在 on_invoke_result/on_invoke_error 中匹配结果

        用法::

            # 类型化调用（推荐）
            self.invoke(MyPlugin.http_get, GetArgs(url="..."))

            # 兼容旧方式
            self.invoke("http_get", {"url": "..."})
        """
        tool_name = tool.name if isinstance(tool, ToolDef) else tool
        if isinstance(arguments, BaseModel):
            args_dict = arguments.model_dump()
        else:
            args_dict = arguments or {}

        self._invoke_counter += 1
        invoke_id = self._invoke_counter
        plugin_name = self.get_name()
        req_id = self._http.post(
            Routes.plugin_invoke(plugin_name),
            body={"tool_name": tool_name, "arguments": args_dict},
        )
        self._invoke_pending[req_id] = invoke_id
        return invoke_id

    def on_invoke_result(self, invoke_id: int, result: dict) -> None:
        """invoke 调用成功回调，子类可覆写处理结果"""
        pass

    def on_invoke_error(self, invoke_id: int, error: str) -> None:
        """invoke 调用失败回调，子类可覆写处理错误"""
        pass

    # ── 内部实现（由 Qt 排队到主线程执行）──

    def _on_http_response(self, request_id: int, status_code: int, data: dict) -> None:
        """从 HTTP 响应中识别 invoke 请求并分发"""
        invoke_id = self._invoke_pending.pop(request_id, None)
        if invoke_id is None:
            return
        if status_code == 200:
            self.on_invoke_result(invoke_id, data)
        else:
            detail = data.get("detail", f"HTTP {status_code}")
            self.on_invoke_error(invoke_id, detail)

    def _on_http_error(self, request_id: int, error: str) -> None:
        """HTTP 请求失败"""
        invoke_id = self._invoke_pending.pop(request_id, None)
        if invoke_id is not None:
            self.on_invoke_error(invoke_id, error)
