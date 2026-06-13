"""MCP Tool Hub — 插件管理页

左列表右详情的插件管理界面，支持加载/卸载/启用/禁用操作。
插件的工具界面在「工具」页签中独立显示。
"""

from __future__ import annotations

from qfluentwidgets import (
    CardWidget,
    StrongBodyLabel,
    BodyLabel,
    SubtitleLabel,
    CaptionLabel,
    PrimaryPushButton,
    PushButton,
    FluentIcon,
    SwitchButton,
    SimpleCardWidget,
    InfoBar,
    InfoBarPosition,
    ToolButton,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QShowEvent
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QSplitter,
    QLabel,
    QScrollArea,
    QDialog,
    QTextBrowser,
)

from api.protocol import (
    PluginDetail,
    PluginListResponse,
    PluginSummary,
    SimpleResponse,
)
from api.routes import Routes
from api.types import PluginStatus

from ..http_client import AsyncHttpClient


# ── 状态颜色映射 ──

STATUS_COLORS = {
    PluginStatus.LOADED.value: "#107c10",
    PluginStatus.UNLOADED.value: "#8a8a8a",
    PluginStatus.LOADING.value: "#ff8c00",
    PluginStatus.ERROR.value: "#d13438",
}

STATUS_LABELS = {
    PluginStatus.LOADED.value: "已加载",
    PluginStatus.UNLOADED.value: "未加载",
    PluginStatus.LOADING.value: "加载中",
    PluginStatus.ERROR.value: "错误",
}


class PluginCard(CardWidget):
    """插件列表卡片项"""

    enabled_changed = Signal(str, bool)
    plugin_clicked = Signal(str)
    plugin_clicked = Signal(str)

    def __init__(self, summary: PluginSummary, parent=None):
        super().__init__(parent)
        self.plugin_name = summary.name
        self._status = summary.status
        self._enabled = summary.enabled
        self._setup_ui(summary)

    def _setup_ui(self, s: PluginSummary) -> None:
        self.setFixedHeight(64)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 10, 16, 10)

        # 状态指示灯
        self.status_dot = QLabel("●")
        color = STATUS_COLORS.get(s.status, "#8a8a8a")
        self.status_dot.setStyleSheet(f"color: {color}; font-size: 14px;")
        self.status_dot.setFixedWidth(16)
        layout.addWidget(self.status_dot)

        # 名称 + 标识
        info = QVBoxLayout()
        info.setSpacing(2)
        self.name_label = StrongBodyLabel(s.display_name)
        id_row = QHBoxLayout()
        id_row.setSpacing(6)
        self.id_label = CaptionLabel(s.name)
        self.id_label.setStyleSheet("color: #999;")
        id_row.addWidget(self.id_label)
        id_row.addStretch()
        info.addWidget(self.name_label)
        info.addLayout(id_row)
        layout.addLayout(info, 1)

        # 启用开关
        self.switch = SwitchButton()
        self.switch.setChecked(s.enabled)
        self.switch.setOnText("")
        self.switch.setOffText("")
        self.switch.setFixedWidth(44)
        self.switch.checkedChanged.connect(self._on_switch_changed)
        layout.addWidget(self.switch)

    def _on_switch_changed(self, checked: bool) -> None:
        self._enabled = checked
        self.enabled_changed.emit(self.plugin_name, checked)

    def mouseReleaseEvent(self, event):
        self.plugin_clicked.emit(self.plugin_name)

    def set_enabled(self, enabled: bool) -> None:
        """外部更新开关状态（不触发信号）"""
        if self._enabled != enabled:
            self._enabled = enabled
            self.switch.blockSignals(True)
            self.switch.setChecked(enabled)
            self.switch.blockSignals(False)

    def update_status(self, status: str) -> None:
        """更新状态显示"""
        self._status = status
        color = STATUS_COLORS.get(status, "#8a8a8a")
        self.status_dot.setStyleSheet(f"color: {color}; font-size: 14px;")


class PluginDetailPanel(QWidget):
    """插件详情面板 — 显示插件信息和工具列表"""

    enabled_changed = Signal(str, bool)
    plugin_clicked = Signal(str)
    status_changed = Signal(str, str)

    STATUS_COLORS = {
        PluginStatus.LOADED.value: "#107c10",
        PluginStatus.LOADING.value: "#ff8c00",
        PluginStatus.ERROR.value: "#d13438",
        PluginStatus.UNLOADED.value: "#8a8a8a",
    }
    STATUS_LABELS = {
        PluginStatus.LOADED.value: "已加载",
        PluginStatus.LOADING.value: "加载中...",
        PluginStatus.ERROR.value: "错误",
        PluginStatus.UNLOADED.value: "未加载",
    }

    def __init__(self, http: AsyncHttpClient, parent=None):
        super().__init__(parent)
        self.http = http
        self._current_plugin: str | None = None
        self._current_status: str = PluginStatus.UNLOADED.value
        self._current_enabled: bool = True
        self._current_mcp_enabled: bool = True
        self._current_has_config: bool = False
        self._config_dialog: QDialog | None = None
        self._config_form = None
        self._config_plugin_name: str | None = None
        self._setup_ui()
        self.http.request_finished.connect(self._on_http_response)

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; }")

        self._content = QWidget()
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(24, 20, 24, 20)
        self._content_layout.setSpacing(16)

        # ── 标题行 ──
        header = QHBoxLayout()
        self.title_label = SubtitleLabel("选择一个插件查看详情")
        self.title_label.setStyleSheet("font-size: 17px;")
        header.addWidget(self.title_label)
        header.addStretch()
        self._content_layout.addLayout(header)

        # ── 信息卡片 ──
        self.info_card = SimpleCardWidget()
        info_layout = QVBoxLayout(self.info_card)
        info_layout.setSpacing(12)
        info_layout.setContentsMargins(20, 16, 20, 16)

        # 名称 + 版本
        name_row = QHBoxLayout()
        self.lbl_name = StrongBodyLabel("—")
        self.lbl_name.setStyleSheet("font-size: 17px;")
        self.lbl_version = CaptionLabel("v—")
        self.lbl_version.setStyleSheet("color: #888;")
        name_row.addWidget(self.lbl_name)
        name_row.addWidget(self.lbl_version)
        name_row.addStretch()
        info_layout.addLayout(name_row)

        # 状态行
        status_row = QHBoxLayout()
        self.status_dot = QLabel("●")
        self.status_dot.setFixedWidth(14)
        self.status_label = BodyLabel("未加载")
        status_row.addWidget(self.status_dot)
        status_row.addWidget(self.status_label)
        status_row.addStretch()

        # 启用开关
        status_row.addWidget(BodyLabel("启用"))
        self.switch = SwitchButton()
        self.switch.setOnText("")
        self.switch.setOffText("")
        self.switch.setFixedWidth(44)
        self.switch.checkedChanged.connect(self._on_switch_changed)
        status_row.addWidget(self.switch)

        # MCP 开关
        status_row.addSpacing(12)
        status_row.addWidget(BodyLabel("MCP"))
        self.mcp_switch = SwitchButton()
        self.mcp_switch.setOnText("")
        self.mcp_switch.setOffText("")
        self.mcp_switch.setFixedWidth(44)
        self.mcp_switch.checkedChanged.connect(self._on_mcp_changed)
        status_row.addWidget(self.mcp_switch)

        info_layout.addLayout(status_row)

        # 操作按钮
        self.btn_layout = QHBoxLayout()
        self.btn_layout.setSpacing(10)
        self.btn_config = PushButton(FluentIcon.SETTING, "设置")
        self.btn_config.clicked.connect(self._on_config)
        self.btn_layout.addStretch()
        info_layout.addLayout(self.btn_layout)

        self._content_layout.addWidget(self.info_card)

        # ── README ──
        readme_header = QHBoxLayout()
        self.readme_label = SubtitleLabel("插件说明")
        self.readme_label.setStyleSheet("font-size: 15px;")
        readme_header.addWidget(self.readme_label)
        readme_header.addStretch()
        self._content_layout.addLayout(readme_header)

        self.readme_browser = QTextBrowser()
        self.readme_browser.setOpenExternalLinks(True)
        self.readme_browser.setStyleSheet(
            "QTextBrowser { background: transparent; border: none; padding: 8px; }"
        )
        self._content_layout.addWidget(self.readme_browser, 1)

        self._content_layout.addStretch()
        scroll.setWidget(self._content)
        layout.addWidget(scroll, 1)

    def _update_action_buttons(self) -> None:
        """根据状态动态显示操作按钮"""
        while self.btn_layout.count():
            child = self.btn_layout.takeAt(0)
            if child.widget():
                child.widget().setParent(None)

        # 有配置时显示设置按钮
        if self._current_has_config:
            self.btn_layout.addWidget(self.btn_config)

        self.btn_layout.addStretch()

    def set_plugin(self, name: str) -> None:
        """设置当前查看的插件"""
        self._current_plugin = name
        self.title_label.setText("插件详情")
        self._detail_req = self.http.get(Routes.plugin(name))

    def set_enabled(self, enabled: bool) -> None:
        """外部更新开关状态（不触发信号）"""
        if self._current_enabled != enabled:
            self._current_enabled = enabled
            self.switch.blockSignals(True)
            self.switch.setChecked(enabled)
            self.switch.blockSignals(False)

    def _on_switch_changed(self, checked: bool) -> None:
        """启用/禁用开关（启用=加载，禁用=卸载）"""
        if not self._current_plugin:
            return
        self._current_enabled = checked
        self.enabled_changed.emit(self._current_plugin, checked)
        if checked:
            self._enable_req = self.http.put(
                Routes.plugin_enable(self._current_plugin))
        else:
            self._disable_req = self.http.put(
                Routes.plugin_disable(self._current_plugin))

    def _on_mcp_changed(self, checked: bool) -> None:
        """MCP 开关 — 控制工具的 MCP 对外暴露"""
        if not self._current_plugin:
            return
        self._current_mcp_enabled = checked
        self._mcp_req = self.http.put(
            Routes.plugin_mcp(self._current_plugin),
            body={"enabled": checked},
        )

    # ── 配置对话框 ──

    def _on_config(self) -> None:
        """打开插件配置对话框"""
        if not self._current_plugin:
            return
        self._config_plugin_name = self._current_plugin
        self._config_load_req = self.http.get(
            Routes.plugin_config(self._current_plugin))

    def _show_config_dialog(self, name: str, config_data: dict, schema: dict) -> None:
        """展示配置对话框"""
        # 尝试从插件的 config_class 生成表单
        config_form = None
        error_msg = None
        try:
            module = __import__(f"plugins.{name}", fromlist=["PLUGIN_CLASS"])
            plugin_class = getattr(module, "PLUGIN_CLASS", None)
            if plugin_class is not None and hasattr(plugin_class, "config_class"):
                config_class = plugin_class.config_class
                if config_class is not None:
                    model = config_class()
                    model.load_dict(config_data)
                    config_form = model.create_form()
                    # 用已加载的数据回填表单（create_form 用 default 初始化）
                    config_form.set_values(model._data)
        except Exception as e:
            error_msg = str(e)

        if config_form is None:
            content = f"插件 {name} 没有可配置的项"
            if error_msg:
                content = f"插件 {name} 配置加载失败: {error_msg}"
            InfoBar.info(
                title="无配置项" if not error_msg else "配置加载失败",
                content=content,
                parent=self,
                position=InfoBarPosition.TOP,
                duration=2000,
            )
            return

        # 创建对话框
        dialog = QDialog(self)
        dialog.setWindowTitle(f"插件设置 — {name}")
        dialog.setMinimumWidth(480)
        dialog.setMinimumHeight(320)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # 标题
        title = SubtitleLabel("插件配置")
        layout.addWidget(title)

        # 表单
        layout.addWidget(config_form, 1)
        self._config_form = config_form

        # 按钮
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_save = PrimaryPushButton(FluentIcon.SAVE, "保存")
        btn_cancel = PushButton(FluentIcon.CANCEL, "取消")
        btn_save.clicked.connect(lambda: self._save_config(dialog, name))
        btn_cancel.clicked.connect(dialog.reject)
        btn_row.addWidget(btn_save)
        btn_row.addWidget(btn_cancel)
        layout.addLayout(btn_row)

        self._config_dialog = dialog
        dialog.exec()
        self._config_dialog = None
        self._config_form = None

    def _save_config(self, dialog: QDialog, name: str) -> None:
        """从表单收集值并保存到后端"""
        if self._config_form is None:
            return
        values = self._config_form.get_values() if hasattr(
            self._config_form, "get_values") else {}
        self._config_save_req = self.http.put(
            Routes.plugin_config(name),
            body={"config": values},
        )
        dialog.accept()
        InfoBar.success(
            title="保存成功",
            content=f"插件 {name} 配置已保存",
            parent=self,
            position=InfoBarPosition.TOP,
            duration=2000,
        )

    def _on_http_response(self, request_id: int, status_code: int, data: dict) -> None:
        if status_code != 200:
            return

        # 插件详情
        if hasattr(self, "_detail_req") and request_id == self._detail_req:
            detail = PluginDetail(**data)
            self._current_status = detail.status
            self._current_enabled = detail.enabled
            self._current_mcp_enabled = detail.mcp_enabled
            self._current_has_config = detail.has_config

            self.lbl_name.setText(detail.name)
            self.lbl_version.setText(f"v{detail.version}")

            # 更新状态显示
            color = self.STATUS_COLORS.get(detail.status, "#8a8a8a")
            label = self.STATUS_LABELS.get(detail.status, detail.status)
            self.status_dot.setStyleSheet(f"color: {color}; font-size: 14px;")
            self.status_label.setText(label)
            self.status_label.setStyleSheet(
                f"color: {color}; font-weight: 500;")

            # 更新开关（不触发信号）
            self.switch.blockSignals(True)
            self.switch.setChecked(detail.enabled)
            self.switch.blockSignals(False)

            self.mcp_switch.blockSignals(True)
            self.mcp_switch.setChecked(detail.mcp_enabled)
            self.mcp_switch.blockSignals(False)

            # 更新操作按钮
            self._update_action_buttons()

            # 更新 README
            if detail.readme:
                self.readme_browser.setMarkdown(detail.readme)

            else:
                self.readme_browser.setPlainText("暂无说明文档")
            self.readme_browser.setVisible(True)
            self.readme_label.setVisible(True)

        # MCP 开关响应
        if hasattr(self, "_mcp_req") and request_id == self._mcp_req:
            resp = SimpleResponse(**data)
            if resp.ok:
                label = "已开启" if self._current_mcp_enabled else "已关闭"
                InfoBar.success(
                    title="MCP 已更新",
                    content=f"插件 {self._current_plugin} MCP 工具{label}",
                    parent=self,
                    position=InfoBarPosition.TOP,
                    duration=2000,
                )

        # 配置加载响应
        if hasattr(self, "_config_load_req") and request_id == self._config_load_req:
            from api.protocol import PluginConfigResponse
            resp = PluginConfigResponse(**data)
            if self._config_plugin_name:
                self._show_config_dialog(
                    self._config_plugin_name, resp.config, resp.schema_info
                )

        # 启用/禁用响应 → 刷新详情
        enable_ok = hasattr(
            self, "_enable_req") and request_id == self._enable_req and SimpleResponse(**data).ok
        disable_ok = hasattr(
            self, "_disable_req") and request_id == self._disable_req and SimpleResponse(**data).ok

        if enable_ok or disable_ok:
            action = "启用" if enable_ok else "禁用"
            new_status = PluginStatus.LOADED.value if enable_ok else PluginStatus.UNLOADED.value
            InfoBar.success(
                title="操作成功",
                content=f"插件 {self._current_plugin} {action}完成",
                parent=self,
                position=InfoBarPosition.TOP,
                duration=2000,
            )
            if self._current_plugin:
                self.status_changed.emit(self._current_plugin, new_status)
            if self._current_plugin:
                self.set_plugin(self._current_plugin)


class PluginListPage(QWidget):
    """插件管理页"""

    def __init__(self, http: AsyncHttpClient, parent=None):
        super().__init__(parent)
        self.http = http
        self.setObjectName("plugins")
        self._plugin_cards: dict[str, PluginCard] = {}
        self._selected_name: str | None = None
        self._setup_ui()
        self._connect_signals()

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        self.refresh()

    def hideEvent(self, event: QShowEvent) -> None:
        super().hideEvent(event)

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 28, 36, 28)
        layout.setSpacing(16)

        # 标题 + 刷新
        header = QHBoxLayout()
        title = SubtitleLabel("插件管理")
        title.setStyleSheet("font-size: 18px;")
        self.btn_refresh = ToolButton(FluentIcon.SYNC)
        self.btn_refresh.setToolTip("刷新插件列表")
        header.addWidget(title)
        header.addStretch()
        header.addWidget(self.btn_refresh)
        layout.addLayout(header)

        # 分割：左列表 + 右详情
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # 左侧：插件列表
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 8, 0)
        self.plugin_list = QVBoxLayout()
        self.plugin_list.setSpacing(6)
        left_layout.addLayout(self.plugin_list)
        left_layout.addStretch()
        splitter.addWidget(left_widget)

        # 右侧：详情
        self.detail_panel = PluginDetailPanel(self.http)
        splitter.addWidget(self.detail_panel)

        # 详情面板信号 → 同步左侧卡片
        self.detail_panel.enabled_changed.connect(
            self._on_detail_enabled_changed)
        self.detail_panel.status_changed.connect(
            self._on_detail_status_changed)

        splitter.setSizes([300, 600])
        layout.addWidget(splitter, 1)

    def _connect_signals(self) -> None:
        self.btn_refresh.clicked.connect(self.refresh)
        self.http.request_finished.connect(self._on_http_response)

    def refresh(self) -> None:
        """刷新插件列表"""
        self._plugins_req = self.http.get(Routes.PLUGINS)

    def _on_http_response(self, request_id: int, status_code: int, data: dict) -> None:
        if status_code != 200:
            return

        if hasattr(self, "_plugins_req") and request_id == self._plugins_req:
            resp = PluginListResponse(**data)
            self._update_plugin_list(resp.plugins)

    def _update_plugin_list(self, plugins: list[PluginSummary]) -> None:
        """更新插件列表 UI"""
        while self.plugin_list.count():
            child = self.plugin_list.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        self._plugin_cards.clear()

        for s in plugins:
            card = PluginCard(s)
            card.enabled_changed.connect(self._on_card_enabled_changed)
            card.plugin_clicked.connect(
                lambda name=s.name: self._on_plugin_click(name)
            )
            self.plugin_list.addWidget(card)
            self._plugin_cards[s.name] = card

        # 保持选中状态：刷新右侧详情面板
        if self._selected_name and self._selected_name in self._plugin_cards:
            self.detail_panel.set_plugin(self._selected_name)
        elif not self._selected_name and plugins:
            self._on_plugin_click(plugins[0].name)

    def _on_plugin_click(self, name: str) -> None:
        """点击插件卡片"""
        self._selected_name = name
        self.detail_panel.set_plugin(name)

    def _on_card_enabled_changed(self, name: str, enabled: bool) -> None:
        """左侧卡片开关变化 → 同步右侧详情面板"""
        if self._selected_name == name:
            self.detail_panel.set_enabled(enabled)
        if enabled:
            self.http.put(Routes.plugin_enable(name))
        else:
            self.http.put(Routes.plugin_disable(name))

    def _on_detail_enabled_changed(self, name: str, enabled: bool) -> None:
        """右侧详情面板开关变化 → 同步左侧卡片"""
        card = self._plugin_cards.get(name)
        if card:
            card.set_enabled(enabled)

    def _on_detail_status_changed(self, name: str, status: str) -> None:
        """右侧详情面板状态变化（加载/卸载）→ 同步左侧卡片"""
        card = self._plugin_cards.get(name)
        if card:
            card.update_status(status)
