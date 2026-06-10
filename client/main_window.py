"""MCP Tool Hub — 主窗口 (MSFluentWindow)

带左侧导航栏的 Fluent Design 主窗口，管理各功能页面。
页面按需加载（懒加载）：首次显示时才创建真实页面内容。
"""

from __future__ import annotations

from qfluentwidgets import (
    MSFluentWindow,
    NavigationItemPosition,
    FluentIcon,
    InfoBar,
    InfoBarPosition,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QWidget, QVBoxLayout
from PySide6.QtGui import QShowEvent

from .http_client import AsyncHttpClient
from .theme import apply_theme
from utils.paths import paths


class LazyPage(QWidget):
    """懒加载占位页面 — 首次 showEvent 时才创建真实页面"""

    def __init__(self, key: str, create_fn, http: AsyncHttpClient, parent=None):
        super().__init__(parent)
        self._key = key
        self._create_fn = create_fn
        self._http = http
        self._real_page: QWidget | None = None
        self._initialized = False
        self.setObjectName(key)

    def _do_initialize(self) -> None:
        """创建并嵌入真实页面"""
        if self._initialized:
            return
        page = self._create_fn(self._http, parent=self)
        page.setObjectName(self._key)
        self._real_page = page
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(page)
        self._initialized = True

    def showEvent(self, event: QShowEvent) -> None:
        """首次显示时初始化"""
        if not self._initialized:
            self._do_initialize()
        super().showEvent(event)

    @property
    def real_page(self) -> QWidget | None:
        return self._real_page

    @property
    def is_initialized(self) -> bool:
        return self._initialized


class MainWindow(MSFluentWindow):
    """MCP Tool Hub 主窗口"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("MCP Tool Hub")
        self.resize(1100, 720)
        self.setMinimumSize(900, 600)

        # 设置窗口图标
        if paths.icon_path.exists():
            self.setWindowIcon(QIcon(str(paths.icon_path)))

        # 应用主题
        apply_theme()

        # HTTP 客户端
        self.http = AsyncHttpClient("http://127.0.0.1:9020", parent=self)
        self.http.request_finished.connect(self._on_response)
        self.http.request_failed.connect(self._on_error)

        # 页面懒加载注册
        self._lazy_pages: dict[str, LazyPage] = {}

        # 初始化页面
        self._init_pages()
        self._init_navigation()

    def _init_pages(self) -> None:
        """注册所有页面（懒加载，showEvent 时才真正创建）"""
        from .pages.overview_page import OverviewPage
        from .pages.plugin_list_page import PluginListPage
        from .pages.tool_page import ToolPage
        from .pages.log_page import LogPage
        from .pages.settings_page import SettingsPage

        page_defs = [
            ("overview", OverviewPage, FluentIcon.HOME, "概览", NavigationItemPosition.TOP),
            ("plugins", PluginListPage, FluentIcon.APPLICATION, "插件管理", NavigationItemPosition.TOP),
            ("tools", ToolPage, FluentIcon.COMMAND_PROMPT, "工具", NavigationItemPosition.TOP),
            ("logs", LogPage, FluentIcon.DOCUMENT, "日志", NavigationItemPosition.TOP),
            ("settings", SettingsPage, FluentIcon.SETTING, "设置", NavigationItemPosition.BOTTOM),
        ]

        for key, page_class, icon, text, position in page_defs:
            lazy = LazyPage(key, page_class, self.http, parent=self)
            self._lazy_pages[key] = lazy
            self.addSubInterface(lazy, icon, text, position=position)

    def _init_navigation(self) -> None:
        """左侧导航栏"""
        # 概览页作为默认页，立即初始化
        self._lazy_pages["overview"]._do_initialize()
        self.switchTo(self._lazy_pages["overview"])

    @property
    def overview_page(self):
        if not self._lazy_pages["overview"].is_initialized:
            self._lazy_pages["overview"]._do_initialize()
        return self._lazy_pages["overview"].real_page

    @property
    def plugin_page(self):
        if not self._lazy_pages["plugins"].is_initialized:
            self._lazy_pages["plugins"]._do_initialize()
        return self._lazy_pages["plugins"].real_page

    @property
    def tool_page(self):
        if not self._lazy_pages["tools"].is_initialized:
            self._lazy_pages["tools"]._do_initialize()
        return self._lazy_pages["tools"].real_page

    @property
    def log_page(self):
        if not self._lazy_pages["logs"].is_initialized:
            self._lazy_pages["logs"]._do_initialize()
        return self._lazy_pages["logs"].real_page

    @property
    def settings_page(self):
        if not self._lazy_pages["settings"].is_initialized:
            self._lazy_pages["settings"]._do_initialize()
        return self._lazy_pages["settings"].real_page

    def show_success(self, text: str) -> None:
        InfoBar.success(
            title="成功", content=text, parent=self,
            position=InfoBarPosition.TOP_RIGHT, duration=2000,
        )

    def show_error(self, text: str) -> None:
        InfoBar.error(
            title="错误", content=text, parent=self,
            position=InfoBarPosition.TOP_RIGHT, duration=3000,
        )

    def show_warning(self, text: str) -> None:
        InfoBar.warning(
            title="警告", content=text, parent=self,
            position=InfoBarPosition.TOP_RIGHT, duration=3000,
        )

    def _on_response(self, request_id: int, status_code: int, data: dict) -> None:
        if status_code >= 400:
            self.show_warning(f"请求返回 {status_code}: {data}")

    def _on_error(self, request_id: int, error: str) -> None:
        self.show_error(f"网络错误: {error}")

    def closeEvent(self, event) -> None:
        """窗口关闭时清理资源"""
        for key, lazy in self._lazy_pages.items():
            if lazy.is_initialized and lazy.real_page and hasattr(lazy.real_page, '_refresh_timer'):
                lazy.real_page._refresh_timer.stop()  # type: ignore[union-attr]
        self.http.close()
        super().closeEvent(event)
