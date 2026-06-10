"""MCP Tool Hub — 概览页

显示服务状态卡片、插件数量统计、快捷操作。
"""

from __future__ import annotations

from qfluentwidgets import (
    CardWidget,
    StrongBodyLabel,
    BodyLabel,
    SubtitleLabel,
    TitleLabel,
    PrimaryPushButton,
    PushButton,
    FluentIcon,
    IconWidget,
    ProgressRing,
    InfoBar,
    InfoBarPosition,
    HeaderCardWidget,
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QShowEvent
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QSizePolicy,
)

from api.protocol import PluginListResponse, ServerStatus, SimpleResponse
from api.routes import Routes
from api.types import PluginStatus

from ..http_client import AsyncHttpClient


class StatCard(CardWidget):
    """统计卡片 — 带图标和数值"""

    def __init__(
        self,
        title: str,
        value: str = "—",
        icon: FluentIcon = FluentIcon.INFO,
        accent_color: str = "#483DDB",
        parent=None,
    ):
        super().__init__(parent)
        self.setFixedHeight(130)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)

        # 左侧：标题 + 值
        left = QVBoxLayout()
        left.setSpacing(6)
        self.title_label = BodyLabel(title)
        self.title_label.setStyleSheet("color: #666; font-size: 13px;")
        self.value_label = TitleLabel(value)
        left.addWidget(self.title_label)
        left.addWidget(self.value_label)
        left.addStretch()
        layout.addLayout(left, 1)

        # 右侧：图标背景圆
        icon_bg = QWidget()
        icon_bg.setFixedSize(48, 48)
        icon_bg.setStyleSheet(f"background: {accent_color}15; border-radius: 24px;")
        icon_layout = QHBoxLayout(icon_bg)
        icon_layout.setContentsMargins(0, 0, 0, 0)
        icon_w = IconWidget(icon, icon_bg)
        icon_w.setFixedSize(24, 24)
        icon_layout.addWidget(icon_w, 0, Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon_bg, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

    def set_value(self, value: str) -> None:
        self.value_label.setText(value)


class OverviewPage(QWidget):
    """概览页"""

    def __init__(self, http: AsyncHttpClient, parent=None):
        super().__init__(parent)
        self.http = http
        self.setObjectName("overviewPage")
        self._setup_ui()
        self._connect_signals()

        # 连续失败计数，用于暂停自动刷新
        self._fail_count = 0

        # 定时刷新
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self.refresh)
        self._refresh_timer.start(15000)

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 28, 36, 28)
        layout.setSpacing(20)

        # 标题
        title = SubtitleLabel("服务概览")
        title.setStyleSheet("font-size: 18px;")
        layout.addWidget(title)

        # 统计卡片
        cards_layout = QGridLayout()
        cards_layout.setSpacing(16)

        self.card_status = StatCard("服务状态", "检测中...", FluentIcon.CLOUD, "#107c10")
        self.card_plugins = StatCard("已加载插件", "—", FluentIcon.APPLICATION, "#483DDB")
        self.card_tools = StatCard("可用工具", "—", FluentIcon.DEVELOPER_TOOLS, "#e68a00")
        self.card_health = StatCard("健康检查", "—", FluentIcon.HEART, "#d13438")

        cards_layout.addWidget(self.card_status, 0, 0)
        cards_layout.addWidget(self.card_plugins, 0, 1)
        cards_layout.addWidget(self.card_tools, 1, 0)
        cards_layout.addWidget(self.card_health, 1, 1)
        layout.addLayout(cards_layout)

        # 操作区
        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(12)

        self.btn_reload = PrimaryPushButton(FluentIcon.SYNC, "重载插件")
        self.btn_refresh = PushButton(FluentIcon.SYNC, "刷新状态")
        actions_layout.addWidget(self.btn_reload)
        actions_layout.addWidget(self.btn_refresh)
        actions_layout.addStretch()
        layout.addLayout(actions_layout)

        layout.addStretch()

    def _connect_signals(self) -> None:
        self.btn_reload.clicked.connect(self._on_reload)
        self.btn_refresh.clicked.connect(self.refresh)
        self.http.request_finished.connect(self._on_http_response)
        self.http.request_failed.connect(self._on_http_error)

    def showEvent(self, event: QShowEvent) -> None:
        """页面显示时恢复定时刷新并立即刷新数据"""
        super().showEvent(event)
        if not self._refresh_timer.isActive():
            self._refresh_timer.start(15000)
        self.refresh()

    def hideEvent(self, event: QShowEvent) -> None:
        """页面隐藏时暂停定时刷新"""
        super().hideEvent(event)
        self._refresh_timer.stop()

    def refresh(self) -> None:
        """刷新服务状态"""
        self._status_req = self.http.get(Routes.SERVER_STATUS)
        self._health_req = self.http.get(Routes.HEALTH)
        self._plugins_req = self.http.get(Routes.PLUGINS)

    def _on_reload(self) -> None:
        """重载插件"""
        self._refresh_timer.stop()
        self.card_status.set_value("重载中...")
        self._reload_req = self.http.post(Routes.SERVER_RELOAD)

    def _on_http_response(self, request_id: int, status_code: int, data: dict) -> None:
        # 任何成功响应都重置失败计数并恢复刷新频率
        if status_code < 500:
            self._fail_count = 0
            if self._refresh_timer.interval() > 15000:
                self._refresh_timer.setInterval(15000)

        # 服务状态
        if hasattr(self, "_status_req") and request_id == self._status_req:
            resp = ServerStatus(**data)
            self.card_status.set_value("运行中" if resp.running else "已停止")
            self.card_plugins.set_value(f"{resp.plugins_loaded} / {resp.plugins_total}")

        # 健康检查
        if hasattr(self, "_health_req") and request_id == self._health_req:
            ok = data.get("status") == "ok"
            self.card_health.set_value("正常" if ok else "异常")

        # 插件列表（统计工具数）
        if hasattr(self, "_plugins_req") and request_id == self._plugins_req:
            resp = PluginListResponse(**data)
            total_tools = sum(
                p.tool_count for p in resp.plugins
                if p.status == PluginStatus.LOADED.value
            )
            self.card_tools.set_value(str(total_tools))

        # 重载结果
        if hasattr(self, "_reload_req") and request_id == self._reload_req:
            self._refresh_timer.start(15000)
            resp = SimpleResponse(**data)
            if resp.ok:
                InfoBar.success(
                    title="重载完成",
                    content="所有插件已重新加载",
                    parent=self,
                    position=InfoBarPosition.TOP,
                    duration=2000,
                )
                self.refresh()

    def _on_http_error(self, request_id: int, error: str) -> None:
        """HTTP 请求失败处理"""
        if hasattr(self, "_reload_req") and request_id == self._reload_req:
            self._refresh_timer.start(15000)

        self._fail_count += 1
        self.card_status.set_value("连接失败")
        if self._fail_count >= 3 and self._refresh_timer.interval() < 60000:
            self._refresh_timer.setInterval(60000)
        elif self._fail_count < 3 and self._refresh_timer.interval() > 15000:
            self._refresh_timer.setInterval(15000)
