"""MCP Tool Hub — JSON 工具管理界面"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QSplitter,
)
from qfluentwidgets import (
    BodyLabel,
    StrongBodyLabel,
    PrimaryPushButton,
    PushButton,
    FluentIcon,
    LineEdit,
    SimpleCardWidget,
    InfoBar,
    InfoBarPosition,
    SmoothScrollArea,
    TextEdit,
    ComboBox,
    SpinBox,
    SwitchButton,
)

from api.base_widget import BasePluginWidget
from api.protocol import PluginInvokeResponse
from .backend import (
    JsonToolPlugin,
    FormatArgs,
    ValidateArgs,
    QueryArgs,
    ToCsvArgs,
    FlattenArgs,
    DiffArgs,
)


class JsonToolWidget(BasePluginWidget):
    """JSON 工具管理界面"""

    def get_name(self) -> str:
        return "json_tool"

    def create_widget(self, parent: QWidget | None = None) -> QWidget:
        scroll = SmoothScrollArea(parent)
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }")

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # ── 功能选择 ──
        mode_card = SimpleCardWidget()
        mode_layout = QHBoxLayout(mode_card)
        mode_layout.setContentsMargins(16, 12, 16, 12)
        mode_layout.addWidget(BodyLabel("功能:"))
        self._mode = ComboBox()
        self._mode.addItems([
            "格式化", "校验", "JMESPath 查询", "转 CSV",
            "扁平化", "对比",
        ])
        self._mode.setFixedWidth(150)
        self._mode.currentIndexChanged.connect(self._on_mode_changed)
        mode_layout.addWidget(self._mode)
        mode_layout.addStretch()
        layout.addWidget(mode_card)

        # ── 输入区 ──
        input_card = SimpleCardWidget()
        input_layout = QVBoxLayout(input_card)
        input_layout.setContentsMargins(16, 12, 16, 12)
        input_layout.setSpacing(10)

        # 通用 JSON 输入
        input_layout.addWidget(StrongBodyLabel("JSON 输入"))
        self._json_input = TextEdit()
        self._json_input.setMinimumHeight(150)
        self._json_input.setPlaceholderText(
            '粘贴 JSON，如 {"name": "test", "value": 42}')
        self._json_input.setStyleSheet(
            "font-family: Consolas, monospace; font-size: 13px;")
        input_layout.addWidget(self._json_input)

        # 第二个 JSON 输入（对比用）
        self._json_input_b_label = StrongBodyLabel("JSON 输入 B")
        self._json_input_b = TextEdit()
        self._json_input_b.setMinimumHeight(120)
        self._json_input_b.setPlaceholderText('粘贴第二个 JSON 用于对比')
        self._json_input_b.setStyleSheet(
            "font-family: Consolas, monospace; font-size: 13px;")
        input_layout.addWidget(self._json_input_b_label)
        input_layout.addWidget(self._json_input_b)
        self._json_input_b_label.setVisible(False)
        self._json_input_b.setVisible(False)

        # JMESPath 表达式
        self._query_label = BodyLabel("JMESPath 表达式")
        self._query_input = LineEdit()
        self._query_input.setPlaceholderText("如: people[?age > `20`].name")
        self._query_input.setClearButtonEnabled(True)
        input_layout.addWidget(self._query_label)
        input_layout.addWidget(self._query_input)
        self._query_label.setVisible(False)
        self._query_input.setVisible(False)

        # 格式化选项
        self._format_opts = QWidget()
        opts_layout = QHBoxLayout(self._format_opts)
        opts_layout.setContentsMargins(0, 0, 0, 0)
        opts_layout.addWidget(BodyLabel("缩进:"))
        self._indent = SpinBox()
        self._indent.setRange(0, 8)
        self._indent.setValue(2)
        self._indent.setFixedWidth(80)
        opts_layout.addWidget(self._indent)
        opts_layout.addWidget(BodyLabel("排序键:"))
        self._sort_keys = SwitchButton()
        opts_layout.addWidget(self._sort_keys)
        opts_layout.addStretch()
        input_layout.addWidget(self._format_opts)

        # CSV 选项
        self._csv_opts = QWidget()
        csv_layout = QHBoxLayout(self._csv_opts)
        csv_layout.setContentsMargins(0, 0, 0, 0)
        csv_layout.addWidget(BodyLabel("分隔符:"))
        self._delimiter = ComboBox()
        self._delimiter.addItems([", (逗号)", "\t (制表符)", "; (分号)"])
        self._delimiter.setFixedWidth(120)
        csv_layout.addWidget(self._delimiter)
        csv_layout.addWidget(BodyLabel("包含表头:"))
        self._include_header = SwitchButton()
        self._include_header.setChecked(True)
        csv_layout.addWidget(self._include_header)
        csv_layout.addStretch()
        input_layout.addWidget(self._csv_opts)
        self._csv_opts.setVisible(False)

        # 扁平化选项
        self._flatten_opts = QWidget()
        flatten_layout = QHBoxLayout(self._flatten_opts)
        flatten_layout.setContentsMargins(0, 0, 0, 0)
        flatten_layout.addWidget(BodyLabel("分隔符:"))
        self._flat_sep = LineEdit()
        self._flat_sep.setText(".")
        self._flat_sep.setFixedWidth(60)
        flatten_layout.addWidget(self._flat_sep)
        flatten_layout.addStretch()
        input_layout.addWidget(self._flatten_opts)
        self._flatten_opts.setVisible(False)

        # 执行按钮
        btn_row = QHBoxLayout()
        self._btn_exec = PrimaryPushButton(FluentIcon.SYNC, "执行")
        self._btn_exec.clicked.connect(self._on_execute)
        btn_row.addWidget(self._btn_exec)
        btn_row.addStretch()
        input_layout.addLayout(btn_row)

        layout.addWidget(input_card)

        # ── 结果区 ──
        result_card = SimpleCardWidget()
        result_layout = QVBoxLayout(result_card)
        result_layout.setContentsMargins(16, 12, 16, 12)
        result_layout.setSpacing(8)

        result_layout.addWidget(StrongBodyLabel("结果"))
        self._result = TextEdit()
        self._result.setReadOnly(True)
        self._result.setMinimumHeight(200)
        self._result.setPlaceholderText("结果将显示在这里...")
        self._result.setStyleSheet(
            "font-family: Consolas, monospace; font-size: 13px;")
        result_layout.addWidget(self._result)

        layout.addWidget(result_card, 1)
        layout.addStretch()

        scroll.setWidget(container)
        return scroll

    def _on_mode_changed(self, index: int) -> None:
        # 0=格式化, 1=校验, 2=查询, 3=转CSV, 4=扁平化, 5=对比
        self._format_opts.setVisible(index == 0)
        self._query_label.setVisible(index == 2)
        self._query_input.setVisible(index == 2)
        self._csv_opts.setVisible(index == 3)
        self._flatten_opts.setVisible(index == 4)
        self._json_input_b_label.setVisible(index == 5)
        self._json_input_b.setVisible(index == 5)

    def _on_execute(self) -> None:
        json_str = self._json_input.toPlainText().strip()
        if not json_str:
            InfoBar.warning(title="请输入 JSON", content="在输入框中粘贴 JSON 数据",
                            position=InfoBarPosition.TOP, duration=2000)
            return

        mode = self._mode.currentIndex()
        self._btn_exec.setEnabled(False)
        self._result.setPlainText("处理中...")

        if mode == 0:  # 格式化
            self._current_invoke = self.invoke(
                JsonToolPlugin.json_format,
                FormatArgs(
                    json_str=json_str,
                    indent=self._indent.value(),
                    sort_keys=self._sort_keys.isChecked(),
                ),
            )
        elif mode == 1:  # 校验
            self._current_invoke = self.invoke(
                JsonToolPlugin.json_validate,
                ValidateArgs(json_str=json_str),
            )
        elif mode == 2:  # 查询
            expr = self._query_input.text().strip()
            if not expr:
                InfoBar.warning(title="请输入表达式", content="JMESPath 表达式不能为空",
                                position=InfoBarPosition.TOP, duration=2000)
                self._btn_exec.setEnabled(True)
                return
            self._current_invoke = self.invoke(
                JsonToolPlugin.json_query,
                QueryArgs(json_str=json_str, expression=expr),
            )
        elif mode == 3:  # 转 CSV
            delim_map = {0: ",", 1: "\t", 2: ";"}
            self._current_invoke = self.invoke(
                JsonToolPlugin.json_to_csv,
                ToCsvArgs(
                    json_str=json_str,
                    delimiter=delim_map.get(
                        self._delimiter.currentIndex(), ","),
                    include_header=self._include_header.isChecked(),
                ),
            )
        elif mode == 4:  # 扁平化
            self._current_invoke = self.invoke(
                JsonToolPlugin.json_flatten,
                FlattenArgs(
                    json_str=json_str,
                    separator=self._flat_sep.text() or ".",
                ),
            )
        elif mode == 5:  # 对比
            json_b = self._json_input_b.toPlainText().strip()
            if not json_b:
                InfoBar.warning(title="请输入第二个 JSON", content="对比需要两个 JSON",
                                position=InfoBarPosition.TOP, duration=2000)
                self._btn_exec.setEnabled(True)
                return
            self._current_invoke = self.invoke(
                JsonToolPlugin.json_diff,
                DiffArgs(json_str_a=json_str, json_str_b=json_b),
            )

    def on_invoke_result(self, invoke_id: int, result: dict) -> None:
        if invoke_id != getattr(self, "_current_invoke", -1):
            return

        self._btn_exec.setEnabled(True)
        resp = PluginInvokeResponse(**result)
        text_parts = []
        for item in resp.content:
            if isinstance(item, dict) and item.get("type") == "text":
                text_parts.append(item.get("text", ""))
        text = "\n".join(text_parts) if text_parts else str(resp.content)

        if resp.is_error:
            self._result.setPlainText(text)
            InfoBar.error(title="执行失败", content=text[:200],
                          position=InfoBarPosition.TOP, duration=3000)
        else:
            self._result.setPlainText(text)
            InfoBar.success(
                title="执行成功", position=InfoBarPosition.TOP, duration=2000)

    def on_invoke_error(self, invoke_id: int, error: str) -> None:
        if invoke_id != getattr(self, "_current_invoke", -1):
            return

        self._btn_exec.setEnabled(True)
        self._result.setPlainText(f"[ERROR] {error}")
