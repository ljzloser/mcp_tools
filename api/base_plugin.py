"""MCP Tool Hub — 后端插件抽象基类

插件通过 ToolDef 类属性声明工具，通过 handle_{name} 方法实现工具逻辑。
BasePlugin 自动发现 ToolDef 属性并分派调用，无需手动字符串匹配。

插件通过 config_class 声明配置模型，框架自动从数据库加载/保存。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Awaitable, Callable, Generic, TypeVar

from .config import ConfigModel
from .tool import ToolDef
from .types import MCPToolResult, PluginMeta

CM = TypeVar("CM", bound=ConfigModel)


class BasePlugin(ABC, Generic[CM]):
    """
    后端插件抽象基类

    每个插件实例化后：
    1. 调用 on_load() 进行初始化
    2. 通过 get_tools() 获取工具列表，注册到转发层
    3. 通过 call_tool() 响应外部工具调用（自动分派到 handle_{name}）
    4. 调用 on_unload() 进行清理

    工具声明（推荐方式）::

        class MyPlugin(BasePlugin):
            my_tool = ToolDef("my_tool", MyToolArgs, description="...")

            async def handle_my_tool(self, args: MyToolArgs) -> MCPToolResult:
                ...

    框架自动：
    - get_tools() 收集所有 ToolDef 类属性
    - call_tool() 分派到对应的 handle_{name} 方法，传入类型化参数

    配置声明::

        class MyConfig(ConfigModel):
            api_key = StringField(default="", label="API Key")
            timeout = IntField(default=30, label="超时(秒)")

        class MyPlugin(BasePlugin):
            config_class = MyConfig

            async def handle_my_tool(self, args):
                key = self.config.api_key  # 直接读取配置

    插件数据目录：
    - self.data_dir → 插件专属的可写目录（自动创建）
    - 可在 on_load() 中使用，存放插件运行时数据
    """

    # ── 配置声明（子类覆写）──
    config_class: type[CM] | None = None

    def __init__(self) -> None:
        super().__init__()
        self._data_dir: Path | None = None
        self._config: CM | None = None
        self._save_config_callback: Callable[[dict[str, Any]], Awaitable[None]] | None = None

    @property
    def data_dir(self) -> Path:
        """插件专属数据目录（由框架注入，自动创建）"""
        if self._data_dir is None:
            raise RuntimeError(
                "插件数据目录未初始化，请在 on_load() 中使用 data_dir"
            )
        return self._data_dir

    def _set_data_dir(self, path: Path) -> None:
        """框架内部调用，设置插件数据目录"""
        path.mkdir(parents=True, exist_ok=True)
        self._data_dir = path

    # ── 配置管理 ──

    @property
    def config(self) -> CM | None:
        """当前配置实例，可通过 self.config.key 直接读取"""
        return self._config

    def _init_config(self, data: dict[str, Any] | None = None) -> None:
        """框架内部调用，初始化配置并从数据库数据加载

        Args:
            data: 数据库中的配置 dict，为 None 或空则使用默认值
        """
        if self.config_class is None:
            return
        self._config = self.config_class()
        if data:
            self._config.load_dict(data)

    def _set_save_config_callback(
        self, callback: Callable[[dict[str, Any]], Awaitable[None]]
    ) -> None:
        """框架内部调用，注入配置保存回调"""
        self._save_config_callback = callback

    async def save_config(self) -> None:
        """将当前配置保存到数据库"""
        if self._config is None:
            return
        if self._save_config_callback is None:
            raise RuntimeError("配置保存回调未初始化")
        await self._save_config_callback(self._config.to_dict())

    def on_config_changed(self, config: ConfigModel) -> None:
        """配置变更回调，子类可覆写以响应配置变更

        当通过 API 更新配置时，框架调用此方法通知插件。
        """
        pass

    # ── 必须实现 ──

    @property
    @abstractmethod
    def meta(self) -> PluginMeta:
        """返回插件元数据"""
        ...

    # ── 工具发现（自动收集 ToolDef 类属性）──

    _tool_defs_cache: list[ToolDef] | None

    def get_tools(self) -> list[ToolDef]:
        """返回本插件提供的所有工具定义

        默认实现：自动收集类上的 ToolDef 属性。
        子类也可覆写此方法手动返回列表。
        """
        if hasattr(self, "_tool_defs_cache") and self._tool_defs_cache is not None:
            return self._tool_defs_cache

        tools: list[ToolDef] = []
        # 遍历类 MRO，收集所有 ToolDef 类属性
        seen_names: set[str] = set()
        for cls in type(self).__mro__:
            for attr_name, attr_value in vars(cls).items():
                if isinstance(attr_value, ToolDef) and attr_name not in seen_names:
                    seen_names.add(attr_name)
                    tools.append(attr_value)

        self._tool_defs_cache = tools  # type: ignore[assignment]
        return tools

    # ── 工具调用（自动分派）──

    async def call_tool(self, tool_name: str, arguments: dict) -> MCPToolResult:
        """执行指定的工具调用（自动分派到 handle_{name} 方法）

        查找与 tool_name 匹配的 ToolDef，用其 input_type 验证参数，
        然后调用 self.handle_{tool_name}(typed_args)。
        """
        for tool_def in self.get_tools():
            if tool_def.name == tool_name:
                # 验证并反序列化参数
                try:
                    typed_args = tool_def.validate(arguments)
                except Exception as e:
                    return MCPToolResult(
                        content=[{"type": "text", "text": f"参数验证失败: {e}"}],
                        is_error=True,
                    )

                # 分派到 handle_{name} 方法
                handler_name = f"handle_{tool_name}"
                handler = getattr(self, handler_name, None)
                if handler is not None:
                    try:
                        return await handler(typed_args)
                    except Exception as e:
                        return MCPToolResult(
                            content=[{"type": "text", "text": f"工具执行异常: {e}"}],
                            is_error=True,
                        )

                # 没有 handle 方法，尝试旧式 _do_{name}
                legacy_name = f"_do_{tool_name}"
                legacy = getattr(self, legacy_name, None)
                if legacy is not None:
                    try:
                        return await legacy(typed_args)
                    except Exception as e:
                        return MCPToolResult(
                            content=[{"type": "text", "text": f"工具执行异常: {e}"}],
                            is_error=True,
                        )

                return MCPToolResult(
                    content=[{"type": "text", "text": f"工具 '{tool_name}' 缺少处理方法 handle_{tool_name}"}],
                    is_error=True,
                )

        return MCPToolResult(
            content=[{"type": "text", "text": f"未知工具: {tool_name}"}],
            is_error=True,
        )

    # ── 生命周期钩子（可选覆写）──

    async def on_load(self) -> None:
        """插件加载时调用"""
        pass

    async def on_unload(self) -> None:
        """插件卸载时调用（清理资源）"""
        pass

    async def health_check(self) -> bool:
        """健康检查，返回 True 表示正常"""
        return True
