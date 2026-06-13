"""MCP Tool Hub — MarkItDown 文档转换管理界面"""

from __future__ import annotations

from pathlib import Path

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
)
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QFileDialog,
    QSplitter,
)
from PySide6.QtCore import Qt

from api.base_widget import BasePluginWidget
from api.protocol import PluginInvokeResponse
from .backend import MarkitdownToolPlugin, ConvertArgs, ConvertUrlArgs


class MarkitdownToolWidget(BasePluginWidget):
    """MarkItDown 文档转换管理界面"""

    def get_name(self) -> str:
        return "markitdown_tool"

    def create_widget(self, parent: QWidget | None = None) -> QWidget:
        scroll = SmoothScrollArea(parent)
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # ── 模式选择 ──
        mode_card = SimpleCardWidget()
        mode_layout = QHBoxLayout(mode_card)
        mode_layout.setContentsMargins(16, 12, 16, 12)
        mode_layout.addWidget(BodyLabel("转换模式:"))
        self._mode = ComboBox()
        self._mode.addItems(["本地文件", "URL 网页"])
        self._mode.setFixedWidth(120)
        self._mode.currentIndexChanged.connect(self._on_mode_changed)
        mode_layout.addWidget(self._mode)
        mode_layout.addStretch()
        layout.addWidget(mode_card)

        # ── 本地文件 ──
        self._local_card = SimpleCardWidget()
        local_layout = QVBoxLayout(self._local_card)
        local_layout.setContentsMargins(16, 12, 16, 12)
        local_layout.setSpacing(10)

        # 输入
        in_row = QHBoxLayout()
        in_row.addWidget(BodyLabel("输入文件:"))
        self._input = LineEdit()
        self._input.setPlaceholderText("选择要转换的文档...")
        self._input.setClearButtonEnabled(True)
        in_row.addWidget(self._input, 1)
        btn = PushButton(FluentIcon.FOLDER, "浏览")
        btn.clicked.connect(self._browse_input)
        in_row.addWidget(btn)
        local_layout.addLayout(in_row)

        # 输出
        out_row = QHBoxLayout()
        out_row.addWidget(BodyLabel("输出路径:"))
        self._output = LineEdit()
        self._output.setPlaceholderText("留空则生成同名 .md 文件")
        self._output.setClearButtonEnabled(True)
        out_row.addWidget(self._output, 1)
        btn = PushButton(FluentIcon.FOLDER, "浏览")
        btn.clicked.connect(self._browse_output)
        out_row.addWidget(btn)
        local_layout.addLayout(out_row)

        # 转换按钮
        btn_row = QHBoxLayout()
        self._btn_convert = PrimaryPushButton(FluentIcon.SYNC, "转换")
        self._btn_convert.clicked.connect(self._on_convert_local)
        btn_row.addWidget(self._btn_convert)
        btn_row.addStretch()
        local_layout.addLayout(btn_row)

        layout.addWidget(self._local_card)

        # ── URL ──
        self._url_card = SimpleCardWidget()
        url_layout = QVBoxLayout(self._url_card)
        url_layout.setContentsMargins(16, 12, 16, 12)
        url_layout.setSpacing(10)

        url_row = QHBoxLayout()
        url_row.addWidget(BodyLabel("网页 URL:"))
        self._url_input = LineEdit()
        self._url_input.setPlaceholderText("输入网页或文件 URL...")
        self._url_input.setClearButtonEnabled(True)
        url_row.addWidget(self._url_input, 1)
        url_layout.addLayout(url_row)

        url_out_row = QHBoxLayout()
        url_out_row.addWidget(BodyLabel("保存路径:"))
        self._url_output = LineEdit()
        self._url_output.setPlaceholderText("留空则仅预览不保存")
        self._url_output.setClearButtonEnabled(True)
        url_out_row.addWidget(self._url_output, 1)
        url_layout.addLayout(url_out_row)

        btn_row2 = QHBoxLayout()
        self._btn_url = PrimaryPushButton(FluentIcon.SYNC, "转换")
        self._btn_url.clicked.connect(self._on_convert_url)
        btn_row2.addWidget(self._btn_url)
        btn_row2.addStretch()
        url_layout.addLayout(btn_row2)

        layout.addWidget(self._url_card)
        self._url_card.setVisible(False)

        # ── 预览区 ──
        preview_card = SimpleCardWidget()
        preview_layout = QVBoxLayout(preview_card)
        preview_layout.setContentsMargins(16, 12, 16, 12)
        preview_layout.setSpacing(8)

        preview_layout.addWidget(StrongBodyLabel("转换结果"))

        self._preview = TextEdit()
        self._preview.setReadOnly(True)
        self._preview.setMinimumHeight(200)
        self._preview.setPlaceholderText("转换后的内容将显示在这里...")
        self._preview.setStyleSheet("font-family: Consolas, monospace; font-size: 13px;")
        preview_layout.addWidget(self._preview)

        layout.addWidget(preview_card, 1)
        layout.addStretch()

        scroll.setWidget(container)
        return scroll

    def _on_mode_changed(self, index: int) -> None:
        is_url = index == 1
        self._local_card.setVisible(not is_url)
        self._url_card.setVisible(is_url)

    # ── 文件浏览 ──

    def _browse_input(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            None, "选择文档", "",
            "所有支持格式 (*.pdf *.docx *.doc *.pptx *.ppt *.xlsx *.xls *.csv *.html *.htm *.epub *.txt *.md *.json *.xml);;所有文件 (*)",
        )
        if path:
            self._input.setText(path)

    def _browse_output(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            None, "保存 Markdown", "", "Markdown 文件 (*.md)"
        )
        if path:
            self._output.setText(path)

    # ── 操作 ──

    def _on_convert_local(self) -> None:
        input_path = self._input.text().strip()
        if not input_path:
            InfoBar.warning(title="请选择文件", content="先选择要转换的文档",
                            position=InfoBarPosition.TOP, duration=2000)
            return

        self._btn_convert.setEnabled(False)
        self._preview.setPlainText("转换中...")

        self._current_invoke = self.invoke(
            MarkitdownToolPlugin.markitdown_convert,
            ConvertArgs(
                input_path=input_path,
                output_path=self._output.text().strip(),
            ),
        )

    def _on_convert_url(self) -> None:
        url = self._url_input.text().strip()
        if not url:
            InfoBar.warning(title="请输入 URL", content="URL 不能为空",
                            position=InfoBarPosition.TOP, duration=2000)
            return

        self._btn_url.setEnabled(False)
        self._preview.setPlainText("转换中...")

        self._current_invoke = self.invoke(
            MarkitdownToolPlugin.markitdown_convert_url,
            ConvertUrlArgs(
                url=url,
                output_path=self._url_output.text().strip(),
            ),
        )

    # ── 回调 ──

    def on_invoke_result(self, invoke_id: int, result: dict) -> None:
        if invoke_id != getattr(self, "_current_invoke", -1):
            return

        self._btn_convert.setEnabled(True)
        self._btn_url.setEnabled(True)

        resp = PluginInvokeResponse(**result)
        text_parts = []
        for item in resp.content:
            if isinstance(item, dict) and item.get("type") == "text":
                text_parts.append(item.get("text", ""))
        text = "\n".join(text_parts) if text_parts else str(resp.content)

        if resp.is_error:
            self._preview.setPlainText(text)
            self._preview.setStyleSheet(
                "font-family: Consolas, monospace; font-size: 13px; color: #d13438;"
            )
            InfoBar.error(title="转换失败", content=text[:200],
                          position=InfoBarPosition.TOP, duration=3000)
        else:
            # 提取 markdown 内容（跳过标题行）
            lines = text.split("\n")
            md_start = 0
            for i, line in enumerate(lines):
                if line.strip() == "" and i > 0:
                    md_start = i + 1
                    break
            md_content = "\n".join(lines[md_start:]) if md_start > 0 else text

            self._preview.setPlainText(md_content)
            self._preview.setStyleSheet(
                "font-family: Consolas, monospace; font-size: 13px;"
            )
            # 提取标题行作为提示
            title_line = lines[0] if lines else "转换成功"
            InfoBar.success(title="转换成功", content=title_line,
                            position=InfoBarPosition.TOP, duration=2000)

    def on_invoke_error(self, invoke_id: int, error: str) -> None:
        if invoke_id != getattr(self, "_current_invoke", -1):
            return

        self._btn_convert.setEnabled(True)
        self._btn_url.setEnabled(True)
        self._preview.setPlainText(f"转换失败: {error}")
        self._preview.setStyleSheet(
            "font-family: Consolas, monospace; font-size: 13px; color: #d13438;"
        )

    def on_status_changed(self, status: str) -> None:
        pass
