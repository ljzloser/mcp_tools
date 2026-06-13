"""MCP Tool Hub — QR 码 / 条码生成管理界面

上下两个区域（QR码 / 条码），每个区域左右布局：左侧输入参数，右侧图片预览
"""

from __future__ import annotations

import base64

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
    ComboBox,
    SpinBox,
    CheckBox,
)
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QFileDialog,
    QLabel,
)
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt

from api.base_widget import BasePluginWidget
from api.protocol import PluginInvokeResponse
from .backend import QrBarcodeToolPlugin, QRArgs, BarcodeArgs


class QrBarcodeToolWidget(BasePluginWidget):
    """QR 码 / 条码生成管理界面"""

    def get_name(self) -> str:
        return "qrbarcode_tool"

    def create_widget(self, parent: QWidget | None = None) -> QWidget:
        container = QWidget(parent)
        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # ══ QR 码区域 ══
        qr_card = SimpleCardWidget()
        qr_card_layout = QHBoxLayout(qr_card)
        qr_card_layout.setContentsMargins(16, 12, 16, 12)
        qr_card_layout.setSpacing(16)

        # 左侧：输入
        qr_left = QVBoxLayout()
        qr_left.setSpacing(8)
        qr_left.addWidget(StrongBodyLabel("QR 码生成"))

        content_row = QHBoxLayout()
        content_row.addWidget(BodyLabel("内容:"))
        self._qr_content = LineEdit()
        self._qr_content.setPlaceholderText("输入文本或 URL...")
        content_row.addWidget(self._qr_content, 1)
        qr_left.addLayout(content_row)

        opt_row = QHBoxLayout()
        opt_row.addWidget(BodyLabel("尺寸:"))
        self._qr_size = SpinBox()
        self._qr_size.setRange(64, 2048)
        self._qr_size.setValue(256)
        self._qr_size.setSuffix(" px")
        self._qr_size.setMinimumWidth(130)
        opt_row.addWidget(self._qr_size)

        self._qr_save_file = CheckBox("保存为文件")
        self._qr_save_file.stateChanged.connect(self._on_qr_save_changed)
        opt_row.addWidget(self._qr_save_file)
        opt_row.addStretch()
        qr_left.addLayout(opt_row)

        self._qr_output = LineEdit()
        self._qr_output.setPlaceholderText("输出路径（如 qr.png）")
        self._qr_output.setVisible(False)
        self._qr_output_btn = PushButton(FluentIcon.FOLDER, "")
        self._qr_output_btn.setVisible(False)
        self._qr_output_btn.clicked.connect(self._browse_qr_output)
        qr_out_row = QHBoxLayout()
        qr_out_row.addWidget(self._qr_output, 1)
        qr_out_row.addWidget(self._qr_output_btn)
        qr_left.addLayout(qr_out_row)

        self._btn_qr = PrimaryPushButton(FluentIcon.SYNC, "生成 QR 码")
        self._btn_qr.clicked.connect(self._on_generate_qr)
        qr_left.addWidget(self._btn_qr)
        qr_left.addStretch()

        # 右侧：预览
        self._qr_preview = QLabel("QR 码预览")
        self._qr_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._qr_preview.setMinimumSize(300, 250)
        self._qr_preview.setStyleSheet(
            "color: #888; border: 1px dashed #ccc; border-radius: 8px;")

        qr_card_layout.addLayout(qr_left, 1)
        qr_card_layout.addWidget(self._qr_preview)

        main_layout.addWidget(qr_card)

        # ══ 条码区域 ══
        bc_card = SimpleCardWidget()
        bc_card_layout = QHBoxLayout(bc_card)
        bc_card_layout.setContentsMargins(16, 12, 16, 12)
        bc_card_layout.setSpacing(16)

        # 左侧：输入
        bc_left = QVBoxLayout()
        bc_left.setSpacing(8)
        bc_left.addWidget(StrongBodyLabel("条码生成"))

        bc_content_row = QHBoxLayout()
        bc_content_row.addWidget(BodyLabel("内容:"))
        self._bc_content = LineEdit()
        self._bc_content.setPlaceholderText("输入条码内容...")
        bc_content_row.addWidget(self._bc_content, 1)
        bc_left.addLayout(bc_content_row)

        type_row = QHBoxLayout()
        type_row.addWidget(BodyLabel("类型:"))
        self._bc_type = ComboBox()
        self._bc_type.addItems(
            ["Code128", "Code39", "EAN13", "EAN8", "UPCA", "ITF", "CODABAR"])
        self._bc_type.setFixedWidth(120)
        type_row.addWidget(self._bc_type)

        self._bc_save_file = CheckBox("保存为文件")
        self._bc_save_file.stateChanged.connect(self._on_bc_save_changed)
        type_row.addWidget(self._bc_save_file)
        type_row.addStretch()
        bc_left.addLayout(type_row)

        self._bc_output = LineEdit()
        self._bc_output.setPlaceholderText("输出路径（如 barcode.png）")
        self._bc_output.setVisible(False)
        self._bc_output_btn = PushButton(FluentIcon.FOLDER, "")
        self._bc_output_btn.setVisible(False)
        self._bc_output_btn.clicked.connect(self._browse_bc_output)
        bc_out_row = QHBoxLayout()
        bc_out_row.addWidget(self._bc_output, 1)
        bc_out_row.addWidget(self._bc_output_btn)
        bc_left.addLayout(bc_out_row)

        self._btn_bc = PrimaryPushButton(FluentIcon.SYNC, "生成条码")
        self._btn_bc.clicked.connect(self._on_generate_barcode)
        bc_left.addWidget(self._btn_bc)
        bc_left.addStretch()

        # 右侧：预览
        self._bc_preview = QLabel("条码预览")
        self._bc_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._bc_preview.setMinimumSize(300, 150)
        self._bc_preview.setStyleSheet(
            "color: #888; border: 1px dashed #ccc; border-radius: 8px;")

        bc_card_layout.addLayout(bc_left, 1)
        bc_card_layout.addWidget(self._bc_preview)

        main_layout.addWidget(bc_card)
        main_layout.addStretch()

        return container

    # ── 保存文件切换 ──

    def _on_qr_save_changed(self, state: int) -> None:
        visible = state == 2  # Qt.Checked
        self._qr_output.setVisible(visible)
        self._qr_output_btn.setVisible(visible)

    def _on_bc_save_changed(self, state: int) -> None:
        visible = state == 2
        self._bc_output.setVisible(visible)
        self._bc_output_btn.setVisible(visible)

    # ── 浏览 ──

    def _browse_qr_output(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            None, "保存 QR 码", "qrcode.png", "PNG 文件 (*.png)")
        if path:
            self._qr_output.setText(path)

    def _browse_bc_output(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            None, "保存条码", "barcode.png", "PNG 文件 (*.png)")
        if path:
            self._bc_output.setText(path)

    # ── 生成 ──

    def _on_generate_qr(self) -> None:
        content = self._qr_content.text().strip()
        if not content:
            InfoBar.warning(title="请输入内容", content="QR 码内容不能为空",
                            position=InfoBarPosition.TOP, duration=2000)
            return

        self._btn_qr.setEnabled(False)
        self._current_type = "qr"
        self._current_invoke = self.invoke(
            QrBarcodeToolPlugin.qrbarcode_generate_qr,
            QRArgs(
                content=content,
                size=self._qr_size.value(),
                output_path=self._qr_output.text().strip(
                ) if self._qr_save_file.isChecked() else "",
            ),
        )

    def _on_generate_barcode(self) -> None:
        content = self._bc_content.text().strip()
        if not content:
            InfoBar.warning(title="请输入内容", content="条码内容不能为空",
                            position=InfoBarPosition.TOP, duration=2000)
            return

        self._btn_bc.setEnabled(False)
        self._current_type = "barcode"
        self._current_invoke = self.invoke(
            QrBarcodeToolPlugin.qrbarcode_generate_barcode,
            BarcodeArgs(
                content=content,
                barcode_type=self._bc_type.currentText().lower(),
                output_path=self._bc_output.text().strip(
                ) if self._bc_save_file.isChecked() else "",
            ),
        )

    # ── 回调 ──

    def _set_preview(self, label: QLabel, text: str, is_error: bool = False) -> None:
        """设置预览标签内容"""
        if is_error:
            label.setText(text)
            label.setStyleSheet(
                "color: #d13438; border: 1px dashed #ccc; border-radius: 8px; padding: 12px;"
            )
            return

        if "data:image" in text:
            try:
                b64 = text.split("base64,")[1].strip()
                img_data = base64.b64decode(b64)
                pm = QPixmap()
                pm.loadFromData(img_data)
                # 使用 label 的最小尺寸作为最大缩放边界
                max_w = max(label.minimumWidth() - 10, 200)
                max_h = max(label.minimumHeight() - 10, 80)
                # 小图放大到合适大小，大图缩小适配
                if pm.width() < max_w and pm.height() < max_h:
                    pm = pm.scaled(max_w, max_h, Qt.AspectRatioMode.KeepAspectRatio,
                                   Qt.TransformationMode.SmoothTransformation)
                elif pm.width() > max_w or pm.height() > max_h:
                    pm = pm.scaled(max_w, max_h, Qt.AspectRatioMode.KeepAspectRatio,
                                   Qt.TransformationMode.SmoothTransformation)
                label.setPixmap(pm)
                label.setStyleSheet("border: none;")
            except Exception:
                label.setText("预览加载失败")
                label.setStyleSheet(
                    "color: #d13438; border: 1px dashed #ccc; border-radius: 8px;")
        else:
            label.setText(text)
            label.setStyleSheet(
                "color: #107c10; border: 1px dashed #ccc; border-radius: 8px; padding: 12px;"
            )

    def on_invoke_result(self, invoke_id: int, result: dict) -> None:
        if invoke_id != getattr(self, "_current_invoke", -1):
            return

        self._btn_qr.setEnabled(True)
        self._btn_bc.setEnabled(True)

        resp = PluginInvokeResponse(**result)
        text_parts = []
        for item in resp.content:
            if isinstance(item, dict) and item.get("type") == "text":
                text_parts.append(item.get("text", ""))
        text = "\n".join(text_parts) if text_parts else str(resp.content)

        current_type = getattr(self, "_current_type", "qr")
        preview = self._qr_preview if current_type == "qr" else self._bc_preview

        if resp.is_error:
            self._set_preview(preview, text, is_error=True)
            InfoBar.error(title="生成失败", content=text[:200],
                          position=InfoBarPosition.TOP, duration=3000)
        else:
            self._set_preview(preview, text)
            InfoBar.success(title="生成成功", content="",
                            position=InfoBarPosition.TOP, duration=1500)

    def on_invoke_error(self, invoke_id: int, error: str) -> None:
        if invoke_id != getattr(self, "_current_invoke", -1):
            return

        self._btn_qr.setEnabled(True)
        self._btn_bc.setEnabled(True)

        current_type = getattr(self, "_current_type", "qr")
        preview = self._qr_preview if current_type == "qr" else self._bc_preview
        self._set_preview(preview, f"生成失败: {error}", is_error=True)

    def on_status_changed(self, status: str) -> None:
        pass
