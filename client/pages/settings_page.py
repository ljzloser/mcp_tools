"""MCP Tool Hub — 设置页

全局配置表单（管理端口、日志级别等）+ Windows 服务管理 + MCP 客户端一键配置。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from loguru import logger
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
    HyperlinkButton,
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QClipboard
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QScrollArea,
    QApplication,
    QGridLayout,
)

from api.protocol import LogPruneResponse, LogRetentionConfig, SimpleResponse
from api.routes import Routes

from ..http_client import AsyncHttpClient
from ..service_manager import ServiceManager, SERVICE_RUNNING, SERVICE_STOPPED, SERVICE_NOT_INSTALLED, SERVICE_UNKNOWN


class SettingsPage(QWidget):
    """设置页"""

    def __init__(self, http: AsyncHttpClient, parent=None):
        super().__init__(parent)
        self.http = http
        self.setObjectName("settings")
        self.is_windows = sys.platform == "win32"

        # 服务管理器
        self.service_mgr = ServiceManager(parent=self)
        self._setup_service_paths()
        self.service_mgr.status_changed.connect(
            self._on_service_status_changed)
        self.service_mgr.action_finished.connect(
            self._on_service_action_finished)

        self._setup_ui()
        self._connect_signals()
        self.http.request_finished.connect(self._on_http_response)
        self._on_load_log_config()

        if self.is_windows:
            # 延迟刷新服务状态
            QTimer.singleShot(500, self.service_mgr.refresh_status)
        else:
            self._on_service_status_changed(SERVICE_UNKNOWN)

        # 立即填充 MCP JSON 预览
        try:
            self.mcp_config_text.setPlainText(self._generate_mcp_config())
        except Exception:
            pass

    def _setup_service_paths(self) -> None:
        """设置 NSSM 和 server 路径"""
        if not self.is_windows:
            self.service_mgr.setup_paths(nssm_path="", server_path="")
            return

        if getattr(sys, "frozen", False):
            app_dir = Path(sys.executable).parent
            self.service_mgr.setup_paths(
                nssm_path=str(app_dir / "nssm.exe"),
                server_path=str(app_dir / "mcp-server.exe"),
            )
        else:
            # 开发模式：尝试从项目目录查找
            project_root = Path(__file__).resolve().parent.parent.parent
            nssm_path = project_root / "dist" / "mcp-tool-hub" / "nssm.exe"
            server_path = project_root / "dist" / "mcp-tool-hub" / "mcp-server.exe"
            self.service_mgr.setup_paths(
                nssm_path=str(nssm_path),
                server_path=str(server_path),
            )

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

        self.input_api_port = LineEdit()
        self.input_api_port.setText("9020")
        self.input_api_port.setPlaceholderText("管理 API 端口")
        self.input_api_port.setClearButtonEnabled(True)
        form.addRow("服务端口：", self.input_api_port)

        self.input_mcp_port = LineEdit()
        self.input_mcp_port.setText("9021")
        self.input_mcp_port.setPlaceholderText("MCP SSE 端口")
        self.input_mcp_port.setClearButtonEnabled(True)
        form.addRow("MCP 端口：", self.input_mcp_port)

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

        # ── Windows 服务管理卡片 ──
        svc_card = SimpleCardWidget()
        svc_layout = QVBoxLayout(svc_card)
        svc_layout.setContentsMargins(24, 20, 24, 20)
        svc_layout.setSpacing(16)

        svc_header = QHBoxLayout()
        svc_icon = IconWidget(FluentIcon.CLOUD, svc_card)
        svc_icon.setFixedSize(20, 20)
        svc_header.addWidget(svc_icon)
        svc_header.addWidget(StrongBodyLabel("服务管理"))
        svc_header.addStretch()
        svc_layout.addLayout(svc_header)

        sep_svc = QWidget()
        sep_svc.setFixedHeight(1)
        sep_svc.setStyleSheet("background: #e0e0e0;")
        svc_layout.addWidget(sep_svc)

        # 状态行
        status_row = QHBoxLayout()
        status_row.addWidget(BodyLabel("服务状态："))
        self.lbl_service_status = BodyLabel("检测中...")
        self.lbl_service_status.setStyleSheet("font-weight: bold;")
        status_row.addWidget(self.lbl_service_status)
        status_row.addStretch()
        svc_layout.addLayout(status_row)

        # 服务按钮行（与外部 ServiceManager 连接）
        svc_btn_row = QHBoxLayout()
        self.btn_svc_install = PrimaryPushButton(FluentIcon.SAVE, "安装服务")
        self.btn_svc_uninstall = PushButton(FluentIcon.CANCEL, "卸载服务")
        self.btn_svc_start = PushButton(FluentIcon.PLAY, "启动")
        self.btn_svc_stop = PushButton(FluentIcon.PAUSE, "停止")
        self.btn_svc_refresh = PushButton(FluentIcon.SYNC, "刷新")

        svc_btn_row.addWidget(self.btn_svc_install)
        svc_btn_row.addWidget(self.btn_svc_uninstall)
        svc_btn_row.addWidget(self.btn_svc_start)
        svc_btn_row.addWidget(self.btn_svc_stop)
        svc_btn_row.addWidget(self.btn_svc_refresh)
        svc_layout.addLayout(svc_btn_row)

        if not self.service_mgr.is_supported:
            self.btn_svc_install.setEnabled(False)
            self.btn_svc_uninstall.setEnabled(False)
            self.btn_svc_start.setEnabled(False)
            self.btn_svc_stop.setEnabled(False)
            self.btn_svc_refresh.setEnabled(False)
            self.lbl_service_status.setText("当前平台不支持服务管理")
            self.lbl_service_status.setStyleSheet(
                "font-weight: bold; color: #888888;")

        inner.addWidget(svc_card)

        # ── MCP 客户端一键配置卡片 ──
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

        mcp_hint = CaptionLabel("以下 JSON 可用于 MCP 客户端，支持复制到剪贴板：")
        mcp_layout.addWidget(mcp_hint)

        from ..theme import is_dark_theme

        self.mcp_config_text = TextEdit()
        self.mcp_config_text.setReadOnly(True)
        self.mcp_config_text.setFixedHeight(140)
        # 使用透明背景并根据主题调整前景/边框色，避免在暗色主题下出现白色块
        if is_dark_theme():
            fg = "#e6e6e6"
            border = "#444444"
            bg = "transparent"
        else:
            fg = "#111111"
            border = "#e0e0e0"
            bg = "transparent"

        self.mcp_config_text.setStyleSheet(
            f"TextEdit {{ font-family: 'Cascadia Code', 'Consolas', monospace; font-size: 13px; "
            f"background-color: {bg}; color: {fg}; border: 1px solid {border}; border-radius: 6px; padding: 8px; "
            f"selection-color: #ffffff; selection-background-color: #5a5a5a; }}"
        )
        mcp_layout.addWidget(self.mcp_config_text)

        mcp_btn_row = QHBoxLayout()
        mcp_btn_row.addStretch()
        self.btn_copy_mcp = PushButton(FluentIcon.COPY, "复制配置")
        mcp_btn_row.addWidget(self.btn_copy_mcp)
        mcp_layout.addLayout(mcp_btn_row)

        inner.addWidget(mcp_card)

        # 日志清理卡片（初始化）
        log_card = SimpleCardWidget()
        log_layout = QVBoxLayout(log_card)
        log_layout.setContentsMargins(24, 20, 24, 20)
        log_layout.setSpacing(12)

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
        about_layout.addWidget(CaptionLabel(
            "基于 MCP SDK + FastAPI + PySide6-Fluent-Widgets"))
        inner.addWidget(about_card)

        inner.addStretch()

        scroll.setWidget(content)
        layout.addWidget(scroll, 1)

        sep_btn = QWidget()
        sep_btn.setFixedHeight(1)
        sep_btn.setStyleSheet("background: #e0e0e0;")
        layout.addWidget(sep_btn)

        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(36, 16, 36, 16)
        btn_layout.setSpacing(12)
        btn_layout.addStretch()
        self.btn_save = PrimaryPushButton(FluentIcon.SAVE, "保存设置")
        self.btn_reset = PushButton(FluentIcon.CANCEL, "重置")
        btn_layout.addWidget(self.btn_reset)
        btn_layout.addWidget(self.btn_save)
        layout.addLayout(btn_layout)

    def _connect_signals(self) -> None:
        self.btn_save.clicked.connect(self._on_save)
        self.btn_reset.clicked.connect(self._on_reset)
        self.btn_prune_now.clicked.connect(self._on_prune_now)
        self.btn_load_log_config.clicked.connect(self._on_load_log_config)
        self.btn_copy_mcp.clicked.connect(self._on_copy_mcp_config)

        # 服务管理
        self.btn_svc_install.clicked.connect(self.service_mgr.install)
        self.btn_svc_uninstall.clicked.connect(self.service_mgr.uninstall)
        self.btn_svc_start.clicked.connect(self.service_mgr.start)
        self.btn_svc_stop.clicked.connect(self.service_mgr.stop)
        self.btn_svc_refresh.clicked.connect(self.service_mgr.refresh_status)

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
        self.input_api_port.setText("9020")
        self.input_mcp_port.setText("9021")
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
        # 不再自动写入或检查外部客户端配置，仅保留 JSON 预览

    def _generate_mcp_config(self) -> str:
        """生成 MCP 客户端配置 JSON"""
        host = self.input_host.text().strip() or "127.0.0.1"
        mcp_port = self.input_mcp_port.text().strip() or "9021"
        config = {
            "mcpServers": {
                "mcp-tool-hub": {
                    "url": f"http://{host}:{mcp_port}/sse"
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

    # ── 服务管理回调 ──

    def _on_service_status_changed(self, status: str) -> None:
        """服务状态变化，更新 UI"""
        status_map = {
            SERVICE_RUNNING: ("● 运行中", "#107c10"),
            SERVICE_STOPPED: ("● 已停止", "#d83b01"),
            SERVICE_NOT_INSTALLED: ("○ 未安装", "#666666"),
            SERVICE_UNKNOWN: ("● 未知", "#888888"),
        }
        text, color = status_map.get(status, ("● 未知", "#888888"))
        self.lbl_service_status.setText(text)
        self.lbl_service_status.setStyleSheet(
            f"font-weight: bold; color: {color};")

        # 根据状态启用/禁用按钮
        is_installed = status in (SERVICE_RUNNING, SERVICE_STOPPED)
        is_running = status == SERVICE_RUNNING
        is_stopped = status == SERVICE_STOPPED

        self.btn_svc_install.setEnabled(not is_installed)
        self.btn_svc_uninstall.setEnabled(is_installed)
        self.btn_svc_start.setEnabled(is_stopped)
        self.btn_svc_stop.setEnabled(is_running)

    def _on_service_action_finished(self, action: str, success: bool, message: str) -> None:
        """服务操作完成"""
        action_names = {
            "install": "安装",
            "uninstall": "卸载",
            "start": "启动",
            "stop": "停止",
        }
        name = action_names.get(action, action)
        if success:
            InfoBar.success(
                title=f"服务{name}",
                content=message,
                parent=self,
                position=InfoBarPosition.TOP,
                duration=3000,
            )
        else:
            InfoBar.error(
                title=f"服务{name}失败",
                content=message,
                parent=self,
                position=InfoBarPosition.TOP,
                duration=5000,
            )
    # 不再支持写入/移除外部客户端配置，相关回调已移除
