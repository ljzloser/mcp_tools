"""MCP Tool Hub — 文档格式转换工具管理界面

提供可视化的文档格式转换操作：
- Markdown → Word DOCX
- Word DOCX → PDF
- Markdown → PDF
"""

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
)
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QFileDialog,
)
from PySide6.QtCore import Qt

from api.base_widget import BasePluginWidget
from api.protocol import PluginInvokeResponse
from .backend import (
    DocConverterPlugin,
    MdToDocxArgs,
    DocxToPdfArgs,
    MdToPdfArgs,
)


class DocConverterWidget(BasePluginWidget):
    """文档格式转换工具的管理界面"""

    def get_name(self) -> str:
        return "doc_converter_tool"

    def create_widget(self, parent: QWidget | None = None) -> QWidget:
        scroll = SmoothScrollArea(parent)
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        self._create_md_to_docx_section(layout)
        self._create_docx_to_pdf_section(layout)
        self._create_md_to_pdf_section(layout)

        layout.addStretch()

        scroll.setWidget(container)
        return scroll

    # ── Markdown → Word ──

    def _create_md_to_docx_section(self, parent_layout: QVBoxLayout) -> None:
        card = SimpleCardWidget()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        layout.addWidget(StrongBodyLabel("Markdown → Word"))

        # 输入文件
        in_row = QHBoxLayout()
        in_row.addWidget(BodyLabel("输入文件:"))
        self._md2docx_input = LineEdit()
        self._md2docx_input.setPlaceholderText("选择 Markdown 文件...")
        self._md2docx_input.setClearButtonEnabled(True)
        in_row.addWidget(self._md2docx_input, 1)
        btn = PushButton(FluentIcon.FOLDER, "浏览")
        btn.clicked.connect(self._browse_md2docx_input)
        in_row.addWidget(btn)
        layout.addLayout(in_row)

        # 输出文件
        out_row = QHBoxLayout()
        out_row.addWidget(BodyLabel("输出文件:"))
        self._md2docx_output = LineEdit()
        self._md2docx_output.setPlaceholderText("输出 DOCX 文件路径...")
        self._md2docx_output.setClearButtonEnabled(True)
        out_row.addWidget(self._md2docx_output, 1)
        btn = PushButton(FluentIcon.FOLDER, "浏览")
        btn.clicked.connect(self._browse_md2docx_output)
        out_row.addWidget(btn)
        layout.addLayout(out_row)

        # 转换按钮
        btn_row = QHBoxLayout()
        self._btn_md2docx = PrimaryPushButton(FluentIcon.SYNC, "转换")
        self._btn_md2docx.clicked.connect(self._on_md2docx)
        btn_row.addWidget(self._btn_md2docx)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        parent_layout.addWidget(card)

    # ── Word → PDF ──

    def _create_docx_to_pdf_section(self, parent_layout: QVBoxLayout) -> None:
        card = SimpleCardWidget()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        layout.addWidget(StrongBodyLabel("Word → PDF"))

        # 输入文件
        in_row = QHBoxLayout()
        in_row.addWidget(BodyLabel("输入文件:"))
        self._docx2pdf_input = LineEdit()
        self._docx2pdf_input.setPlaceholderText("选择 DOCX 文件...")
        self._docx2pdf_input.setClearButtonEnabled(True)
        in_row.addWidget(self._docx2pdf_input, 1)
        btn = PushButton(FluentIcon.FOLDER, "浏览")
        btn.clicked.connect(self._browse_docx2pdf_input)
        in_row.addWidget(btn)
        layout.addLayout(in_row)

        # 输出文件
        out_row = QHBoxLayout()
        out_row.addWidget(BodyLabel("输出文件:"))
        self._docx2pdf_output = LineEdit()
        self._docx2pdf_output.setPlaceholderText("输出 PDF 文件路径...")
        self._docx2pdf_output.setClearButtonEnabled(True)
        out_row.addWidget(self._docx2pdf_output, 1)
        btn = PushButton(FluentIcon.FOLDER, "浏览")
        btn.clicked.connect(self._browse_docx2pdf_output)
        out_row.addWidget(btn)
        layout.addLayout(out_row)

        # 转换按钮
        btn_row = QHBoxLayout()
        self._btn_docx2pdf = PrimaryPushButton(FluentIcon.SYNC, "转换")
        self._btn_docx2pdf.clicked.connect(self._on_docx2pdf)
        btn_row.addWidget(self._btn_docx2pdf)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        parent_layout.addWidget(card)

    # ── Markdown → PDF ──

    def _create_md_to_pdf_section(self, parent_layout: QVBoxLayout) -> None:
        card = SimpleCardWidget()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        layout.addWidget(StrongBodyLabel("Markdown → PDF"))

        # 输入文件
        in_row = QHBoxLayout()
        in_row.addWidget(BodyLabel("输入文件:"))
        self._md2pdf_input = LineEdit()
        self._md2pdf_input.setPlaceholderText("选择 Markdown 文件...")
        self._md2pdf_input.setClearButtonEnabled(True)
        in_row.addWidget(self._md2pdf_input, 1)
        btn = PushButton(FluentIcon.FOLDER, "浏览")
        btn.clicked.connect(self._browse_md2pdf_input)
        in_row.addWidget(btn)
        layout.addLayout(in_row)

        # 输出文件
        out_row = QHBoxLayout()
        out_row.addWidget(BodyLabel("输出文件:"))
        self._md2pdf_output = LineEdit()
        self._md2pdf_output.setPlaceholderText("输出 PDF 文件路径...")
        self._md2pdf_output.setClearButtonEnabled(True)
        out_row.addWidget(self._md2pdf_output, 1)
        btn = PushButton(FluentIcon.FOLDER, "浏览")
        btn.clicked.connect(self._browse_md2pdf_output)
        out_row.addWidget(btn)
        layout.addLayout(out_row)

        # 转换按钮
        btn_row = QHBoxLayout()
        self._btn_md2pdf = PrimaryPushButton(FluentIcon.SYNC, "转换")
        self._btn_md2pdf.clicked.connect(self._on_md2pdf)
        btn_row.addWidget(self._btn_md2pdf)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        parent_layout.addWidget(card)

    # ── 文件浏览 ──

    def _browse_md2docx_input(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            None, "选择 Markdown 文件", "",
            "Markdown 文件 (*.md);;所有文件 (*)",
        )
        if path:
            self._md2docx_input.setText(path)
            if not self._md2docx_output.text().strip():
                self._md2docx_output.setText(str(Path(path).with_suffix(".docx")))

    def _browse_md2docx_output(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            None, "保存 DOCX", "", "Word 文件 (*.docx)",
        )
        if path:
            self._md2docx_output.setText(path)

    def _browse_docx2pdf_input(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            None, "选择 DOCX 文件", "",
            "Word 文件 (*.docx);;所有文件 (*)",
        )
        if path:
            self._docx2pdf_input.setText(path)
            if not self._docx2pdf_output.text().strip():
                self._docx2pdf_output.setText(str(Path(path).with_suffix(".pdf")))

    def _browse_docx2pdf_output(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            None, "保存 PDF", "", "PDF 文件 (*.pdf)",
        )
        if path:
            self._docx2pdf_output.setText(path)

    def _browse_md2pdf_input(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            None, "选择 Markdown 文件", "",
            "Markdown 文件 (*.md);;所有文件 (*)",
        )
        if path:
            self._md2pdf_input.setText(path)
            if not self._md2pdf_output.text().strip():
                self._md2pdf_output.setText(str(Path(path).with_suffix(".pdf")))

    def _browse_md2pdf_output(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            None, "保存 PDF", "", "PDF 文件 (*.pdf)",
        )
        if path:
            self._md2pdf_output.setText(path)

    # ── 操作 ──

    def _on_md2docx(self) -> None:
        input_path = self._md2docx_input.text().strip()
        output_path = self._md2docx_output.text().strip()
        if not input_path:
            InfoBar.warning(
                title="请选择文件", content="先选择要转换的 Markdown 文件",
                position=InfoBarPosition.TOP, duration=2000,
            )
            return
        if not output_path:
            InfoBar.warning(
                title="请指定输出路径", content="输出文件路径不能为空",
                position=InfoBarPosition.TOP, duration=2000,
            )
            return

        self._btn_md2docx.setEnabled(False)
        self._current_invoke = self.invoke(
            DocConverterPlugin.md_to_docx,
            MdToDocxArgs(input_path=input_path, output_path=output_path),
        )

    def _on_docx2pdf(self) -> None:
        input_path = self._docx2pdf_input.text().strip()
        output_path = self._docx2pdf_output.text().strip()
        if not input_path:
            InfoBar.warning(
                title="请选择文件", content="先选择要转换的 DOCX 文件",
                position=InfoBarPosition.TOP, duration=2000,
            )
            return
        if not output_path:
            InfoBar.warning(
                title="请指定输出路径", content="输出文件路径不能为空",
                position=InfoBarPosition.TOP, duration=2000,
            )
            return

        self._btn_docx2pdf.setEnabled(False)
        self._current_invoke = self.invoke(
            DocConverterPlugin.docx_to_pdf,
            DocxToPdfArgs(input_path=input_path, output_path=output_path),
        )

    def _on_md2pdf(self) -> None:
        input_path = self._md2pdf_input.text().strip()
        output_path = self._md2pdf_output.text().strip()
        if not input_path:
            InfoBar.warning(
                title="请选择文件", content="先选择要转换的 Markdown 文件",
                position=InfoBarPosition.TOP, duration=2000,
            )
            return
        if not output_path:
            InfoBar.warning(
                title="请指定输出路径", content="输出文件路径不能为空",
                position=InfoBarPosition.TOP, duration=2000,
            )
            return

        self._btn_md2pdf.setEnabled(False)
        self._current_invoke = self.invoke(
            DocConverterPlugin.md_to_pdf,
            MdToPdfArgs(input_path=input_path, output_path=output_path),
        )

    # ── 回调 ──

    def on_invoke_result(self, invoke_id: int, result: dict) -> None:
        if invoke_id != getattr(self, "_current_invoke", -1):
            return

        self._btn_md2docx.setEnabled(True)
        self._btn_docx2pdf.setEnabled(True)
        self._btn_md2pdf.setEnabled(True)

        resp = PluginInvokeResponse(**result)
        text_parts = []
        for item in resp.content:
            if isinstance(item, dict) and item.get("type") == "text":
                text_parts.append(item.get("text", ""))
        text = "\n".join(text_parts) if text_parts else str(resp.content)

        if resp.is_error:
            InfoBar.error(title="操作失败", content=text,
                          position=InfoBarPosition.TOP, duration=5000)
        else:
            InfoBar.success(title="操作成功", content=text,
                            position=InfoBarPosition.TOP, duration=5000)

    def on_invoke_error(self, invoke_id: int, error: str) -> None:
        if invoke_id != getattr(self, "_current_invoke", -1):
            return

        self._btn_md2docx.setEnabled(True)
        self._btn_docx2pdf.setEnabled(True)
        self._btn_md2pdf.setEnabled(True)

        InfoBar.error(title="操作失败", content=error,
                      position=InfoBarPosition.TOP, duration=5000)

    def on_status_changed(self, status: str) -> None:
        pass
