"""MCP Tool Hub — 日志页

实时日志查看、筛选、清空。
"""

from __future__ import annotations

from qfluentwidgets import (
    BodyLabel,
    SubtitleLabel,
    StrongBodyLabel,
    PrimaryPushButton,
    PushButton,
    FluentIcon,
    ComboBox,
    SimpleCardWidget,
    TextEdit,
    CaptionLabel,
    IconWidget,
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QShowEvent
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
)

from api.protocol import LogClearResponse, LogItem, LogListResponse
from api.routes import Routes

from ..http_client import AsyncHttpClient


class LogPage(QWidget):
    """日志页"""

    def __init__(self, http: AsyncHttpClient, parent=None):
        super().__init__(parent)
        self.http = http
        self.setObjectName("logs")
        self._setup_ui()
        self._connect_signals()
        self.http.request_finished.connect(self._on_http_response)
        self.http.request_failed.connect(self._on_http_error)

        # 连续失败计数
        self._fail_count = 0

        # 定时刷新
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self.refresh)
        self._refresh_timer.start(10000)

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        if not self._refresh_timer.isActive():
            self._refresh_timer.start(10000)
        self.refresh()

    def hideEvent(self, event: QShowEvent) -> None:
        super().hideEvent(event)
        self._refresh_timer.stop()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 28, 36, 28)
        layout.setSpacing(16)

        # 标题 + 操作
        header = QHBoxLayout()
        title = SubtitleLabel("运行日志")
        title.setStyleSheet("font-size: 18px;")
        header.addWidget(title)
        header.addStretch()

        # 筛选栏
        filter_layout = QHBoxLayout()
        filter_layout.setSpacing(8)
        filter_label = BodyLabel("插件筛选")
        filter_label.setStyleSheet("color: #666;")
        filter_layout.addWidget(filter_label)
        self.combo_plugin = ComboBox()
        self.combo_plugin.addItem("全部", userData=None)
        self.combo_plugin.setMinimumWidth(180)
        self.combo_plugin.setPlaceholderText("选择插件...")
        filter_layout.addWidget(self.combo_plugin)
        filter_layout.addStretch()

        self.btn_refresh = PushButton(FluentIcon.SYNC, "刷新")
        self.btn_clear = PrimaryPushButton(FluentIcon.DELETE, "清空")
        filter_layout.addWidget(self.btn_refresh)
        filter_layout.addWidget(self.btn_clear)

        header.addLayout(filter_layout)
        layout.addLayout(header)

        # 日志统计
        self.stats_row = QHBoxLayout()
        self.stats_row.setSpacing(16)
        self.lbl_total = CaptionLabel("共 0 条日志")
        self.lbl_total.setStyleSheet("color: #888;")
        self.lbl_level_info = CaptionLabel("INFO: 0")
        self.lbl_level_info.setStyleSheet("color: #107c10;")
        self.lbl_level_warning = CaptionLabel("WARNING: 0")
        self.lbl_level_warning.setStyleSheet("color: #e68a00;")
        self.lbl_level_error = CaptionLabel("ERROR: 0")
        self.lbl_level_error.setStyleSheet("color: #d13438;")
        self.stats_row.addWidget(self.lbl_total)
        self.stats_row.addWidget(self.lbl_level_info)
        self.stats_row.addWidget(self.lbl_level_warning)
        self.stats_row.addWidget(self.lbl_level_error)
        self.stats_row.addStretch()
        layout.addLayout(self.stats_row)

        # 日志文本区域
        self.log_card = SimpleCardWidget()
        log_layout = QVBoxLayout(self.log_card)
        log_layout.setContentsMargins(2, 2, 2, 2)
        self.log_text = TextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMinimumHeight(400)
        self.log_text.setStyleSheet("""
            TextEdit {
                font-family: 'Cascadia Code', 'Consolas', 'Courier New', monospace;
                font-size: 13px;
                line-height: 1.5;
                padding: 12px;
                border: none;
            }
        """)
        log_layout.addWidget(self.log_text)
        layout.addWidget(self.log_card, 1)

    def _connect_signals(self) -> None:
        self.btn_refresh.clicked.connect(self.refresh)
        self.btn_clear.clicked.connect(self._on_clear)
        self.combo_plugin.currentIndexChanged.connect(self._on_filter_changed)

    def refresh(self) -> None:
        """刷新日志"""
        plugin = self.combo_plugin.currentData()
        params = {"limit": 200}
        if plugin:
            params["plugin"] = plugin
        self._logs_req = self.http.get(Routes.LOGS, params=params)

    def _on_clear(self) -> None:
        """清空日志"""
        plugin = self.combo_plugin.currentData()
        params = {}
        if plugin:
            params["plugin"] = plugin
        self._clear_req = self.http.delete(Routes.LOGS, params=params if params else None)

    def _on_filter_changed(self) -> None:
        self.refresh()

    def _on_http_response(self, request_id: int, status_code: int, data: dict) -> None:
        # 成功响应恢复刷新频率
        if status_code < 500:
            self._fail_count = 0
            if self._refresh_timer.interval() > 10000:
                self._refresh_timer.setInterval(10000)

        if status_code != 200:
            return

        # 日志列表
        if hasattr(self, "_logs_req") and request_id == self._logs_req:
            resp = LogListResponse(**data)
            self._display_logs(resp.logs)
            self._update_stats(resp.logs)

            # 更新筛选下拉
            if self.combo_plugin.count() <= 1:
                plugins = sorted({l.plugin_name for l in resp.logs if l.plugin_name})
                for p in plugins:
                    self.combo_plugin.addItem(p, userData=p)

        # 清空结果
        if hasattr(self, "_clear_req") and request_id == self._clear_req:
            resp = LogClearResponse(**data)
            if resp.ok:
                self.log_text.clear()

    def _display_logs(self, logs: list[LogItem]) -> None:
        """显示日志（带颜色标记）"""
        lines = []
        for log in logs:
            # 用 HTML 着色
            level_colors = {
                "ERROR": "#d13438",
                "WARNING": "#e68a00",
                "INFO": "#107c10",
                "DEBUG": "#8a8a8a",
            }
            color = level_colors.get(log.level, "#666")
            lines.append(
                f'<span style="color:#888;">[{log.created_at}]</span> '
                f'<span style="color:{color};font-weight:bold;">[{log.level}]</span> '
                f'<span style="color:#483DDB;">[{log.plugin_name}]</span> '
                f'<span style="color:#333;">{log.message}</span>'
            )

        self.log_text.setHtml("<br>".join(lines))
        cursor = self.log_text.textCursor()
        cursor.movePosition(cursor.MoveOperation.Start)
        self.log_text.setTextCursor(cursor)

    def _update_stats(self, logs: list[LogItem]) -> None:
        """更新日志统计"""
        total = len(logs)
        info = sum(1 for l in logs if l.level == "INFO")
        warn = sum(1 for l in logs if l.level == "WARNING")
        error = sum(1 for l in logs if l.level == "ERROR")
        self.lbl_total.setText(f"共 {total} 条日志")
        self.lbl_level_info.setText(f"INFO: {info}")
        self.lbl_level_warning.setText(f"WARNING: {warn}")
        self.lbl_level_error.setText(f"ERROR: {error}")

    def _on_http_error(self, request_id: int, error: str) -> None:
        """HTTP 请求失败处理"""
        self._fail_count += 1
        if self._fail_count >= 3 and self._refresh_timer.interval() < 60000:
            self._refresh_timer.setInterval(30000)
