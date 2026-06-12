"""MCP Tool Hub — 日志页

实时日志查看、筛选、清空。
"""

from __future__ import annotations

import html

from qfluentwidgets import (
    BodyLabel,
    SubtitleLabel,
    PrimaryPushButton,
    PushButton,
    FluentIcon,
    ComboBox,
    SimpleCardWidget,
    TextEdit,
    LineEdit,
    CaptionLabel,
)
from PySide6.QtCore import QDate, QDateTime, QTime
from PySide6.QtGui import QShowEvent
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QDateTimeEdit,
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

        self._last_logs: list[LogItem] = []

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
        filter_layout = QVBoxLayout()
        filter_layout.setSpacing(8)

        row1 = QHBoxLayout()
        row1.setSpacing(8)
        filter_label = BodyLabel("插件")
        filter_label.setStyleSheet("color: #666;")
        row1.addWidget(filter_label)

        self.combo_plugin = ComboBox()
        self.combo_plugin.addItem("全部", userData=None)
        self.combo_plugin.setMinimumWidth(140)
        self.combo_plugin.setPlaceholderText("选择插件...")
        row1.addWidget(self.combo_plugin)

        level_label = BodyLabel("级别")
        level_label.setStyleSheet("color: #666;")
        row1.addWidget(level_label)

        self.combo_level = ComboBox()
        self.combo_level.addItem("全部", userData=None)
        self.combo_level.addItem("INFO", userData="INFO")
        self.combo_level.addItem("WARNING", userData="WARNING")
        self.combo_level.addItem("ERROR", userData="ERROR")
        self.combo_level.addItem("DEBUG", userData="DEBUG")
        self.combo_level.setMinimumWidth(120)
        row1.addWidget(self.combo_level)

        self.input_search = LineEdit()
        self.input_search.setPlaceholderText("关键词 / 内容搜索")
        self.input_search.setMinimumWidth(180)
        row1.addWidget(self.input_search)
        row1.addStretch()
        filter_layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.setSpacing(8)
        start_label = BodyLabel("开始")
        start_label.setStyleSheet("color: #666;")
        row2.addWidget(start_label)

        self.start_datetime = QDateTimeEdit(self)
        self.start_datetime.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        self.start_datetime.setMinimumWidth(160)
        self.start_datetime.setCalendarPopup(True)
        today = QDate.currentDate()
        self.start_datetime.setDateTime(QDateTime(today, QTime(0, 0, 0)))
        row2.addWidget(self.start_datetime)

        end_label = BodyLabel("结束")
        end_label.setStyleSheet("color: #666;")
        row2.addWidget(end_label)

        self.end_datetime = QDateTimeEdit(self)
        self.end_datetime.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        self.end_datetime.setMinimumWidth(160)
        self.end_datetime.setCalendarPopup(True)
        self.end_datetime.setDateTime(QDateTime(today, QTime(23, 59, 59)))
        row2.addWidget(self.end_datetime)

        row2.addStretch()
        self.btn_refresh = PushButton(FluentIcon.SYNC, "查询")
        self.btn_clear = PrimaryPushButton(FluentIcon.DELETE, "清空")
        row2.addWidget(self.btn_refresh)
        row2.addWidget(self.btn_clear)
        filter_layout.addLayout(row2)

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
        from ..theme import is_dark_theme

        # 根据主题选择文本颜色（HTML 内联样式将使用这些颜色）
        self._is_dark = is_dark_theme()
        self.log_text.setStyleSheet("""
            TextEdit {
                font-family: 'Cascadia Code', 'Consolas', 'Courier New', monospace;
                font-size: 13px;
                line-height: 1.5;
                padding: 12px;
                border: none;
                background-color: transparent;
                white-space: pre-wrap;
                selection-color: #ffffff;
                selection-background-color: #5a5a5a;
            }
        """)
        log_layout.addWidget(self.log_text)
        layout.addWidget(self.log_card, 1)

    def _connect_signals(self) -> None:
        self.btn_refresh.clicked.connect(self.refresh)
        self.btn_clear.clicked.connect(self._on_clear)
        self.combo_plugin.currentIndexChanged.connect(self._apply_filters)
        self.combo_level.currentIndexChanged.connect(self._apply_filters)
        self.input_search.returnPressed.connect(self._apply_filters)
        self.start_datetime.dateTimeChanged.connect(self._apply_filters)
        self.end_datetime.dateTimeChanged.connect(self._apply_filters)

    def refresh(self) -> None:
        """查询日志"""
        plugin = self.combo_plugin.currentData()
        params = {"limit": 200}
        if plugin:
            params["plugin"] = plugin

        params["start_at"] = self.start_datetime.dateTime().toString(
            "yyyy-MM-dd HH:mm:ss")
        params["end_at"] = self.end_datetime.dateTime().toString(
            "yyyy-MM-dd HH:mm:ss")

        self._logs_req = self.http.get(Routes.LOGS, params=params)

    def _on_clear(self) -> None:
        """清空日志"""
        plugin = self.combo_plugin.currentData()
        params = {}
        if plugin:
            params["plugin"] = plugin
        self._clear_req = self.http.delete(
            Routes.LOGS, params=params if params else None)

    def _apply_filters(self) -> None:
        """根据当前查询条件过滤已加载日志"""
        filtered = []
        plugin = self.combo_plugin.currentData()
        level = self.combo_level.currentData()
        keyword = self.input_search.text().strip().lower()

        for log in self._last_logs:
            if plugin and log.plugin_name != plugin:
                continue
            if level and log.level != level:
                continue
            if keyword:
                text = f"{log.created_at} {log.plugin_name} {log.level} {log.message}".lower(
                )
                if keyword not in text:
                    continue
            filtered.append(log)

        self._display_logs(filtered)
        self._update_stats(filtered)

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        if self.combo_plugin.count() <= 1 and not self._last_logs:
            self.refresh()

    def _on_http_response(self, request_id: int, status_code: int, data: dict) -> None:
        if status_code != 200:
            return

        # 日志列表
        if hasattr(self, "_logs_req") and request_id == self._logs_req:
            resp = LogListResponse(**data)
            self._last_logs = resp.logs
            self._apply_filters()

            # 更新插件筛选下拉
            plugins = sorted(
                {l.plugin_name for l in resp.logs if l.plugin_name})
            existing = {self.combo_plugin.itemData(
                i) for i in range(self.combo_plugin.count())}
            for p in plugins:
                if p not in existing:
                    self.combo_plugin.addItem(p, userData=p)

        # 清空结果
        if hasattr(self, "_clear_req") and request_id == self._clear_req:
            resp = LogClearResponse(**data)
            if resp.ok:
                self._last_logs = []
                self.log_text.clear()
                self._update_stats([])

    def _display_logs(self, logs: list[LogItem]) -> None:
        """显示日志（带颜色标记）"""
        lines = []
        for log in logs:
            # 用 HTML 着色
            if self._is_dark:
                level_colors = {
                    "ERROR": "#ff6b6b",
                    "WARNING": "#ffb86b",
                    "INFO": "#7efc7e",
                    "DEBUG": "#9a9aa6",
                }
                timestamp = "#aaaaaa"
                plugin_color = "#b9a8ff"
                message_color = "#e6e6e6"
            else:
                level_colors = {
                    "ERROR": "#d13438",
                    "WARNING": "#e68a00",
                    "INFO": "#107c10",
                    "DEBUG": "#8a8a8a",
                }
                timestamp = "#888"
                plugin_color = "#483DDB"
                message_color = "#333"

            color = level_colors.get(log.level, "#666")
            lines.append(
                f'<span style="color:{timestamp};">[{html.escape(log.created_at)}]</span> '
                f'<span style="color:{color};font-weight:bold;">[{html.escape(log.level)}]</span> '
                f'<span style="color:{plugin_color};">[{html.escape(log.plugin_name)}]</span> '
                f'<span style="color:{message_color};">{html.escape(log.message)}</span>'
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
        # 当前仅丢弃失败，不再自动重试。用户可点击“查询”重新请求。
        # 如果日志请求失败，不清除当前显示内容。
        return
