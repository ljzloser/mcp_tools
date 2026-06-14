"""MCP Tool Hub — 工具页

左侧插件列表，右侧插件管理界面。
只显示已加载且有 Widget 的插件。
"""

from __future__ import annotations

from qfluentwidgets import (
    CardWidget,
    StrongBodyLabel,
    BodyLabel,
    SubtitleLabel,
    CaptionLabel,
    FluentIcon,
    IconWidget,
    SimpleCardWidget,
    InfoBar,
    InfoBarPosition,
)
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QSplitter,
    QScrollArea,
    QStackedWidget,
    QLabel,
)

from api.protocol import PluginListResponse, PluginSummary
from api.routes import Routes
from api.types import PluginStatus
from ..http_client import AsyncHttpClient

STATUS_COLORS: dict[str, str] = {
    PluginStatus.LOADED.value: "#107c10",
    PluginStatus.LOADING.value: "#ff8c00",
    PluginStatus.ERROR.value: "#d13438",
    PluginStatus.UNLOADED.value: "#8a8a8a",
}


class ToolPluginCard(CardWidget):
    """工具页插件卡片 — 点击选中并加载 Widget"""

    plugin_selected = Signal(str)  # plugin_name

    def __init__(self, summary: PluginSummary, parent=None):
        super().__init__(parent)
        self.plugin_name = summary.name
        self.setFixedHeight(64)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(10)

        # 图标
        icon = IconWidget(FluentIcon.APPLICATION, self)
        icon.setFixedSize(22, 22)
        layout.addWidget(icon)

        # 名称 + 状态
        text_layout = QVBoxLayout()
        text_layout.setSpacing(4)
        name = StrongBodyLabel(summary.display_name or summary.name)
        name.setStyleSheet("font-size: 14px;")
        status = CaptionLabel(
            f"v{summary.version}  ·  {summary.tool_count} 个工具"
        )
        status.setStyleSheet("color: #888;")
        text_layout.addWidget(name)
        text_layout.addWidget(status)
        layout.addLayout(text_layout, 1)

        # 状态点
        self.status_dot = QLabel("●")
        color = STATUS_COLORS.get(summary.status, "#8a8a8a")
        self.status_dot.setStyleSheet(f"color: {color}; font-size: 12px;")
        layout.addWidget(self.status_dot)

        # 连接父类 CardWidget 的 clicked 信号
        self.clicked.connect(self._on_card_clicked)

    def _on_card_clicked(self) -> None:
        self.plugin_selected.emit(self.plugin_name)

    def mouseReleaseEvent(self, event):
        self.clicked.emit()


class ToolPage(QWidget):
    """工具页 — 左侧列表 + 右侧界面"""

    def __init__(self, http: AsyncHttpClient, parent=None):
        super().__init__(parent)
        self.http = http
        self.setObjectName("tools")
        self._plugin_cards: dict[str, ToolPluginCard] = {}
        self._selected_name: str | None = None
        self._widget_instance = None
        self._widget_qwidget: QWidget | None = None
        self._setup_ui()
        self._connect_signals()

        # 定时刷新插件列表
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(10000)
        self._refresh_timer.timeout.connect(self.refresh)

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 28, 36, 28)
        layout.setSpacing(16)

        # 标题
        title = SubtitleLabel("工具")
        title.setStyleSheet("font-size: 18px;")
        layout.addWidget(title)

        # 左右分割
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(1)

        # ── 左侧：插件列表 ──
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(6)

        self.left_scroll = QScrollArea()
        self.left_scroll.setWidgetResizable(True)
        self.left_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.left_scroll.setStyleSheet(
            "QScrollArea { background: transparent; } QScrollBar:vertical { width: 8px; } QScrollBar::handle:vertical { background: #ccc; border-radius: 4px; min-height: 30px; }")
        left_container = QWidget()
        self.plugin_list_layout = QVBoxLayout(left_container)
        self.plugin_list_layout.setContentsMargins(0, 0, 0, 0)
        self.plugin_list_layout.setSpacing(4)
        self.plugin_list_layout.addStretch()
        self.left_scroll.setWidget(left_container)
        left_layout.addWidget(self.left_scroll)
        splitter.addWidget(left_widget)

        # ── 右侧：插件界面 ──
        self.right_stack = QStackedWidget()
        self.right_stack.setStyleSheet("background: transparent;")

        # 空状态
        self._empty_page = QWidget()
        empty_layout = QVBoxLayout(self._empty_page)
        empty_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_label = BodyLabel("选择一个插件以显示工具界面")
        empty_label.setStyleSheet("color: #888; font-size: 15px;")
        empty_layout.addWidget(
            empty_label, alignment=Qt.AlignmentFlag.AlignCenter)
        self.right_stack.addWidget(self._empty_page)

        # Widget 容器
        self._widget_page = QWidget()
        self._widget_page_layout = QVBoxLayout(self._widget_page)
        self._widget_page_layout.setContentsMargins(12, 0, 12, 0)
        self.right_stack.addWidget(self._widget_page)

        self.right_stack.setCurrentWidget(self._empty_page)
        splitter.addWidget(self.right_stack)

        splitter.setSizes([260, 700])
        layout.addWidget(splitter, 1)

    def _connect_signals(self) -> None:
        self.http.request_finished.connect(self._on_http_response)

    # ── 公开方法 ──

    def refresh(self) -> None:
        """刷新插件列表"""
        self._list_req = self.http.get(Routes.PLUGINS)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if not self._refresh_timer.isActive():
            self._refresh_timer.start()
            self.refresh()

    def hideEvent(self, event) -> None:
        super().hideEvent(event)
        self._refresh_timer.stop()

    # ── HTTP 回调 ──

    def _on_http_response(self, request_id: int, status_code: int, data: dict) -> None:
        if status_code != 200:
            return

        # 插件列表
        if hasattr(self, "_list_req") and request_id == self._list_req:
            resp = PluginListResponse(**data)
            self._update_plugin_list(resp.plugins)

    def _update_plugin_list(self, plugins: list[PluginSummary]) -> None:
        """更新左侧插件列表，只显示已加载且有 Widget 的插件"""
        # 清空旧列表
        while self.plugin_list_layout.count():
            child = self.plugin_list_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        self._plugin_cards.clear()

        has_widget_plugins = [
            p for p in plugins
            if p.has_widget and p.status == PluginStatus.LOADED.value
        ]

        if not has_widget_plugins:
            empty = CaptionLabel("  暂无可用工具插件")
            empty.setStyleSheet("color: #888; padding: 12px;")
            self.plugin_list_layout.addWidget(empty)
            self._show_empty()
        else:
            for s in has_widget_plugins:
                card = ToolPluginCard(s)
                card.plugin_selected.connect(self._on_plugin_selected)
                self.plugin_list_layout.addWidget(card)
                self._plugin_cards[s.name] = card

        self.plugin_list_layout.addStretch()

        # 如果当前选中插件已不可用，回退到空状态
        if self._selected_name not in self._plugin_cards:
            self._show_empty()

    def _on_plugin_selected(self, name: str) -> None:
        """选中插件，右侧加载其 Widget"""
        if self._selected_name == name:
            return

        self._selected_name = name
        self._load_plugin_widget(name)

    def _load_plugin_widget(self, name: str) -> None:
        """加载插件 Widget 到右侧"""
        # 清除旧 Widget
        if self._widget_qwidget is not None:
            self._widget_page_layout.removeWidget(self._widget_qwidget)
            self._widget_qwidget.deleteLater()
            self._widget_qwidget = None
            self._widget_instance = None

        try:
            module = __import__(f"plugins.{name}", fromlist=["WIDGET_CLASS"])
            widget_class = getattr(module, "WIDGET_CLASS", None)
            if widget_class is not None:
                widget_instance = widget_class()
                widget_instance.set_http_client(self.http)
                self._widget_qwidget = widget_instance.create_widget(
                    self._widget_page)
                self._widget_instance = widget_instance
                self._widget_page_layout.addWidget(self._widget_qwidget, 1)
                self.right_stack.setCurrentWidget(self._widget_page)
            else:
                self._show_empty()
                InfoBar.warning(
                    title="无管理界面",
                    content=f"插件 {name} 没有提供管理界面",
                    parent=self,
                    position=InfoBarPosition.TOP,
                    duration=2000,
                )
        except Exception as e:
            self._show_empty()
            InfoBar.error(
                title="加载失败",
                content=f"无法加载插件界面: {e}",
                parent=self,
                position=InfoBarPosition.TOP,
                duration=2000,
            )

    def _show_empty(self) -> None:
        """显示空状态"""
        self._selected_name = None
        self.right_stack.setCurrentWidget(self._empty_page)
