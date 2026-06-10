"""MCP Tool Hub — 设置页

全局配置表单（管理端口、日志级别等）。
"""

from __future__ import annotations

import json

from qfluentwidgets import (
    BodyLabel,
    SubtitleLabel,
    PrimaryPushButton,
    PushButton,
    FluentIcon,
    SimpleCardWidget,
    LineEdit,
    ComboBox,
    SwitchButton,
    StrongBodyLabel,
    SpinBox,
    InfoBar,
    InfoBarPosition,
    CaptionLabel,
    IconWidget,
    TextEdit,
    ToolButton,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QClipboard
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QScrollArea,
    QApplication,
)

from api.protocol import LogPruneResponse, LogRetentionConfig, SimpleResponse
from api.routes import Routes

from ..http_client import AsyncHttpClient


class SettingsPage(QWidget):
    """设置页"""

    def __init__(self, http: AsyncHttpClient, parent=None):
        super().__init__(parent)
        self.http = http
        self.setObjectName("settings")
        self._setup_ui()
        self._connect_signals()
        self.http.request_finished.connect(self._on_http_response)
        self._on_load_log_config()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; }")

        content = QWidget()
        inner = QVBoxLayout(content)
        inner.setContentsMargins(36, 28, 36, 28)
        inner.setSpacing(20)

        # 标题
        title = SubtitleLabel("全局设置")
        title.setStyleSheet("font-size: 18px;")
        inner.addWidget(title)

        # ── 服务配置卡片 ──
        server_card = SimpleCardWidget()
        server_layout = QVBoxLayout(server_card)
        server_layout.setContentsMargins(24, 20, 24, 20)
        server_layout.setSpacing(16)

        server_header = QHBoxLayout()
        server_icon = IconWidget(FluentIcon.SETTING, server_card)
        server_icon.setFixedSize(20, 20)
        server_header.addWidget(server_icon)
        server_header.addWidget(StrongBodyLabel("服务配置"))
        server_header.addStretch()
        server_layout.addLayout(server_header)

        sep = QWidget()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background: #e0e0e0;")
        server_layout.addWidget(sep)

        form = QFormLayout()
        form.setSpacing(14)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.input_host = LineEdit()
        self.input_host.setText("127.0.0.1")
        self.input_host.setPlaceholderText("管理 API 绑定地址")
        self.input_host.setClearButtonEnabled(True)
        form.addRow("绑定地址：", self.input_host)

        self.input_port = LineEdit()
        self.input_port.setText("9020")
        self.input_port.setPlaceholderText("管理 API 端口")
        self.input_port.setClearButtonEnabled(True)
        form.addRow("端口：", self.input_port)

        self.combo_log_level = ComboBox()
        self.combo_log_level.addItems(["DEBUG", "INFO", "WARNING", "ERROR"])
        self.combo_log_level.setCurrentText("INFO")
        form.addRow("日志级别：", self.combo_log_level)

        switch_row = QHBoxLayout()
        self.switch_auto_start = SwitchButton()
        self.switch_auto_start.setOnText("")
        self.switch_auto_start.setOffText("")
        self.switch_auto_start.setFixedWidth(44)
        self.switch_auto_start.setChecked(True)
        switch_row.addWidget(self.switch_auto_start)
        switch_row.addWidget(CaptionLabel("启用后服务启动时自动加载所有插件"))
        switch_row.addStretch()
        form.addRow("自动加载插件：", switch_row)

        server_layout.addLayout(form)
        inner.addWidget(server_card)

        # ── MCP 客户端配置卡片 ──
        mcp_card = SimpleCardWidget()
        mcp_layout = QVBoxLayout(mcp_card)
        mcp_layout.setContentsMargins(24, 20, 24, 20)
        mcp_layout.setSpacing(12)

        mcp_header = QHBoxLayout()
        mcp_icon = IconWidget(FluentIcon.LINK, mcp_card)
        mcp_icon.setFixedSize(20, 20)
        mcp_header.addWidget(mcp_icon)
        mcp_header.addWidget(StrongBodyLabel("MCP 客户端配置"))
        mcp_header.addStretch()
        mcp_layout.addLayout(mcp_header)

        sep_mcp = QWidget()
        sep_mcp.setFixedHeight(1)
        sep_mcp.setStyleSheet("background: #e0e0e0;")
        mcp_layout.addWidget(sep_mcp)

        mcp_hint = CaptionLabel("将以下 JSON 配置复制到 AI 客户端的 MCP 服务器设置中：")
        mcp_layout.addWidget(mcp_hint)

        self.mcp_config_text = TextEdit()
        self.mcp_config_text.setReadOnly(True)
        self.mcp_config_text.setFixedHeight(120)
        self.mcp_config_text.setStyleSheet(
            "TextEdit { font-family: 'Cascadia Code', 'Consolas', monospace; font-size: 13px; "
            "background: #fafafa; border: 1px solid #e0e0e0; border-radius: 6px; padding: 8px; }"
        )
        mcp_layout.addWidget(self.mcp_config_text)

        mcp_btn_row = QHBoxLayout()
        mcp_btn_row.addStretch()
        self.btn_copy_mcp = PushButton(FluentIcon.COPY, "复制配置")
        mcp_btn_row.addWidget(self.btn_copy_mcp)
        mcp_layout.addLayout(mcp_btn_row)

        inner.addWidget(mcp_card)

        # ── 日志清理配置卡片 ──
        log_card = SimpleCardWidget()
        log_layout = QVBoxLayout(log_card)
        log_layout.setContentsMargins(24, 20, 24, 20)
        log_layout.setSpacing(16)

        log_header = QHBoxLayout()
        log_icon = IconWidget(FluentIcon.DELETE, log_card)
        log_icon.setFixedSize(20, 20)
        log_header.addWidget(log_icon)
        log_header.addWidget(StrongBodyLabel("日志清理"))
        log_header.addStretch()
        log_layout.addLayout(log_header)

        sep2 = QWidget()
        sep2.setFixedHeight(1)
        sep2.setStyleSheet("background: #e0e0e0;")
        log_layout.addWidget(sep2)

        # 日志总条数
        log_count_row = QHBoxLayout()
        self.lbl_log_count = CaptionLabel("当前日志总条数：—")
        log_count_row.addWidget(self.lbl_log_count)
        log_count_row.addStretch()
        log_layout.addLayout(log_count_row)

        log_form = QFormLayout()
        log_form.setSpacing(14)
        log_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.spin_retention_days = SpinBox()
        self.spin_retention_days.setRange(1, 365)
        self.spin_retention_days.setValue(30)
        self.spin_retention_days.setSuffix(" 天")
        log_form.addRow("保留天数：", self.spin_retention_days)

        self.spin_max_records = SpinBox()
        self.spin_max_records.setRange(100, 1000000)
        self.spin_max_records.setValue(10000)
        self.spin_max_records.setSingleStep(1000)
        self.spin_max_records.setSuffix(" 条")
        log_form.addRow("最大条数：", self.spin_max_records)

        log_layout.addLayout(log_form)

        log_btn_layout = QHBoxLayout()
        self.btn_prune_now = PushButton(FluentIcon.DELETE, "立即清理")
        self.btn_load_log_config = PushButton(FluentIcon.SYNC, "刷新配置")
        log_btn_layout.addStretch()
        log_btn_layout.addWidget(self.btn_load_log_config)
        log_btn_layout.addWidget(self.btn_prune_now)
        log_layout.addLayout(log_btn_layout)

        inner.addWidget(log_card)

        # ── 关于卡片 ──
        about_card = SimpleCardWidget()
        about_layout = QVBoxLayout(about_card)
        about_layout.setContentsMargins(24, 20, 24, 20)
        about_layout.setSpacing(8)

        about_header = QHBoxLayout()
        about_icon = IconWidget(FluentIcon.INFO, about_card)
        about_icon.setFixedSize(20, 20)
        about_header.addWidget(about_icon)
        about_header.addWidget(StrongBodyLabel("关于"))
        about_header.addStretch()
        about_layout.addLayout(about_header)

        sep3 = QWidget()
        sep3.setFixedHeight(1)
        sep3.setStyleSheet("background: #e0e0e0;")
        about_layout.addWidget(sep3)

        about_layout.addWidget(BodyLabel("MCP Tool Hub v0.1.0"))
        about_layout.addWidget(CaptionLabel("集成式 MCP 工具管理平台"))
        about_layout.addWidget(CaptionLabel("基于 MCP SDK + FastAPI + PySide6-Fluent-Widgets"))
        inner.addWidget(about_card)

        # ── 保存按钮 ──
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.btn_save = PrimaryPushButton(FluentIcon.SAVE, "保存设置")
        self.btn_reset = PushButton(FluentIcon.CANCEL, "重置")
        btn_layout.addWidget(self.btn_reset)
        btn_layout.addWidget(self.btn_save)
        inner.addLayout(btn_layout)

        inner.addStretch()

        scroll.setWidget(content)
        layout.addWidget(scroll, 1)

    def _connect_signals(self) -> None:
        self.btn_save.clicked.connect(self._on_save)
        self.btn_reset.clicked.connect(self._on_reset)
        self.btn_prune_now.clicked.connect(self._on_prune_now)
        self.btn_load_log_config.clicked.connect(self._on_load_log_config)
        self.btn_copy_mcp.clicked.connect(self._on_copy_mcp_config)

    def _on_save(self) -> None:
        """保存设置"""
        body = LogRetentionConfig(
            retention_days=self.spin_retention_days.value(),
            max_records=self.spin_max_records.value(),
        )
        self.http.put(Routes.LOGS_CONFIG, body=body.model_dump())
        # 刷新 MCP 配置预览
        self.mcp_config_text.setPlainText(self._generate_mcp_config())
        InfoBar.success(
            title="保存成功",
            content="日志清理配置已保存，下次启动时生效",
            parent=self,
            position=InfoBarPosition.TOP,
            duration=3000,
        )

    def _on_reset(self) -> None:
        """重置为默认"""
        self.input_host.setText("127.0.0.1")
        self.input_port.setText("9020")
        self.combo_log_level.setCurrentText("INFO")
        self.switch_auto_start.setChecked(True)
        self.spin_retention_days.setValue(30)
        self.spin_max_records.setValue(10000)
        self.mcp_config_text.setPlainText(self._generate_mcp_config())

    def _on_prune_now(self) -> None:
        """手动触发日志清理"""
        self._prune_req = self.http.post(Routes.LOGS_PRUNE)

    def _on_load_log_config(self) -> None:
        """从后端刷新日志清理配置"""
        self._log_config_req = self.http.get(Routes.LOGS_CONFIG)

    def _generate_mcp_config(self) -> str:
        """生成 MCP 客户端配置 JSON"""
        host = self.input_host.text().strip() or "127.0.0.1"
        port = self.input_port.text().strip() or "9020"
        config = {
            "mcpServers": {
                "mcp-tool-hub": {
                    "url": f"http://{host}:{port}/sse"
                }
            }
        }
        return json.dumps(config, indent=2, ensure_ascii=False)

    def _on_copy_mcp_config(self) -> None:
        """复制 MCP 配置到剪贴板"""
        text = self._generate_mcp_config()
        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText(text)
        InfoBar.success(
            title="已复制",
            content="MCP 客户端配置已复制到剪贴板",
            parent=self,
            position=InfoBarPosition.TOP,
            duration=2000,
        )

    def _on_http_response(self, request_id: int, status_code: int, data: dict) -> None:
        """处理 HTTP 响应"""
        if status_code != 200:
            return

        # 日志配置
        if hasattr(self, "_log_config_req") and request_id == self._log_config_req:
            config = LogRetentionConfig(**data)
            self.spin_retention_days.setValue(config.retention_days)
            self.spin_max_records.setValue(config.max_records)
            self.lbl_log_count.setText(f"当前日志总条数：{config.total_count}")
            # 刷新 MCP 配置预览
            self.mcp_config_text.setPlainText(self._generate_mcp_config())

        # 日志清理结果
        if hasattr(self, "_prune_req") and request_id == self._prune_req:
            resp = LogPruneResponse(**data)
            InfoBar.success(
                title="清理完成",
                content=f"已删除 {resp.deleted} 条过期日志",
                parent=self,
                position=InfoBarPosition.TOP,
                duration=3000,
            )
            # 清理后刷新配置（含总条数）
            self._on_load_log_config()
