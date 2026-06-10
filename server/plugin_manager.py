"""MCP Tool Hub — 插件管理器"""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import TYPE_CHECKING, Any

from loguru import logger

from api.base_plugin import BasePlugin
from api.base_widget import BasePluginWidget
from api.types import PluginMeta, PluginStatus
from utils.paths import paths

if TYPE_CHECKING:
    from .database import Database


class PluginManager:
    """
    插件管理器

    职责：
    - 扫描 plugins/ 目录，发现可用插件
    - 加载/卸载插件（实例化 + 生命周期管理）
    - 管理插件状态
    - 提供插件实例和 Widget 实例的查询
    """

    def __init__(self, plugins_dir: Path | str | None = None) -> None:
        self.plugins_dir = Path(plugins_dir) if plugins_dir else paths.plugins_dir
        self._plugins: dict[str, BasePlugin] = {}  # name → instance
        self._widgets: dict[str, BasePluginWidget] = {}  # name → instance
        self._statuses: dict[str, PluginStatus] = {}  # name → status
        self._discovered: list[str] = []  # 已发现的插件名
        self._database: Database | None = None  # 注入后使用

    def set_database(self, database: Database) -> None:
        """注入数据库实例（用于配置读写）"""
        self._database = database

    def discover(self) -> list[str]:
        """扫描目录，返回发现的插件名列表（不加载）"""
        self._discovered = []

        if not self.plugins_dir.exists():
            logger.warning(f"插件目录不存在: {self.plugins_dir}")
            return self._discovered

        for item in sorted(self.plugins_dir.iterdir()):
            # 跳过 _template 和非目录
            if not item.is_dir():
                continue
            if item.name.startswith("_") or item.name.startswith("."):
                continue
            # 检查是否有 __init__.py
            if not (item / "__init__.py").exists():
                continue

            self._discovered.append(item.name)

        logger.info(f"发现 {len(self._discovered)} 个插件: {self._discovered}")
        return self._discovered

    async def load(self, name: str) -> BasePlugin:
        """加载指定插件，返回后端实例"""
        if name in self._plugins:
            logger.warning(f"插件 [{name}] 已加载，跳过")
            return self._plugins[name]

        self._statuses[name] = PluginStatus.LOADING

        try:
            plugin_module = importlib.import_module(f"plugins.{name}")
        except ImportError as e:
            self._statuses[name] = PluginStatus.ERROR
            logger.error(f"插件 [{name}] 导入失败: {e}")
            raise

        plugin_class = getattr(plugin_module, "PLUGIN_CLASS", None)
        if plugin_class is None:
            self._statuses[name] = PluginStatus.ERROR
            raise AttributeError(f"插件 [{name}] 缺少 PLUGIN_CLASS 导出")

        # 实例化后端插件（注入数据目录）
        plugin_instance: BasePlugin = plugin_class()
        plugin_instance._set_data_dir(paths.plugin_data(name))

        # 初始化配置（从数据库加载）
        if plugin_instance.config_class is not None:
            config_data: dict[str, Any] = {}
            if self._database is not None:
                config_data = await self._database.get_plugin_config(name)
            plugin_instance._init_config(config_data)

            # 注入保存回调
            db = self._database
            if db is not None:
                plugin_instance._set_save_config_callback(
                    lambda data, n=name: db.set_plugin_config(n, data)
                )

            logger.info(f"插件 [{name}] 配置已加载: {list(plugin_instance.config_class.get_fields().keys())}")

        await plugin_instance.on_load()

        # 尝试加载 Widget
        widget_class = getattr(plugin_module, "WIDGET_CLASS", None)
        if widget_class is not None:
            try:
                self._widgets[name] = widget_class()
            except Exception as e:
                logger.warning(f"插件 [{name}] Widget 初始化失败: {e}")

        self._plugins[name] = plugin_instance
        self._statuses[name] = PluginStatus.LOADED

        logger.info(f"插件 [{name}] v{plugin_instance.meta.version} 加载成功")
        return plugin_instance

    async def unload(self, name: str) -> None:
        """卸载指定插件"""
        plugin = self._plugins.pop(name, None)
        if plugin is None:
            logger.warning(f"插件 [{name}] 未加载，无法卸载")
            return

        try:
            await plugin.on_unload()
        except Exception as e:
            logger.error(f"插件 [{name}] 卸载异常: {e}")

        self._widgets.pop(name, None)
        self._statuses[name] = PluginStatus.UNLOADED
        logger.info(f"插件 [{name}] 已卸载")

    def get_plugin(self, name: str) -> BasePlugin | None:
        """获取已加载的后端插件实例"""
        return self._plugins.get(name)

    def get_widget(self, name: str) -> BasePluginWidget | None:
        """获取已加载的管理界面实例"""
        return self._widgets.get(name)

    def get_status(self, name: str) -> PluginStatus:
        """获取插件状态"""
        return self._statuses.get(name, PluginStatus.UNLOADED)

    def list_plugins(self) -> list[PluginMeta]:
        """列出所有已加载插件的元数据"""
        return [p.meta for p in self._plugins.values()]

    def list_discovered(self) -> list[str]:
        """列出所有已发现的插件名"""
        return list(self._discovered)

    async def load_all(self, skip: list[str] | None = None) -> None:
        """加载所有发现的插件（跳过 skip 列表中的）"""
        skip_set = set(skip or [])
        for name in self._discovered:
            if name in skip_set:
                logger.info(f"插件 [{name}] 在跳过列表中，不加载")
                self._statuses[name] = PluginStatus.UNLOADED
                continue
            try:
                await self.load(name)
            except Exception as e:
                logger.error(f"插件 [{name}] 加载失败: {e}")
                self._statuses[name] = PluginStatus.ERROR

    async def unload_all(self) -> None:
        """卸载所有已加载的插件"""
        names = list(self._plugins.keys())
        for name in names:
            await self.unload(name)
        logger.info("所有插件已卸载")

    def get_all_statuses(self) -> dict[str, PluginStatus]:
        """获取所有插件的状态"""
        return dict(self._statuses)
