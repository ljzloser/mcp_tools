"""MCP Tool Hub — 图片互转工具管理界面

提供可视化的图片格式互转、ICO 合并/提取操作：
- 图片格式互转 + 缩放 + 质量调整
- 多图合并为多尺寸 ICO
- ICO 提取各帧为图片
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
    CheckBox,
    SpinBox,
    ComboBox,
    SmoothScrollArea,
)
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QFileDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
)
from PySide6.QtCore import Qt

from api.base_widget import BasePluginWidget
from api.protocol import PluginInvokeResponse
from .backend import (
    ImageToolPlugin,
    ImageConvertArgs,
    ImageToIcoArgs,
    IcoToImagesArgs,
)


class ImageToolWidget(BasePluginWidget):
    """图片互转工具的管理界面"""

    def get_name(self) -> str:
        return "图片互转工具"

    def create_widget(self, parent: QWidget | None = None) -> QWidget:
        scroll = SmoothScrollArea(parent)
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        self._create_convert_section(layout)
        self._create_to_ico_section(layout)
        self._create_from_ico_section(layout)

        layout.addStretch()

        scroll.setWidget(container)
        return scroll

    # ── 图片格式互转 ──

    def _create_convert_section(self, parent_layout: QVBoxLayout) -> None:
        card = SimpleCardWidget()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        layout.addWidget(StrongBodyLabel("图片格式互转"))

        # 输入文件
        in_row = QHBoxLayout()
        in_row.addWidget(BodyLabel("输入文件:"))
        self._conv_input = LineEdit()
        self._conv_input.setPlaceholderText("选择或输入图片文件路径...")
        self._conv_input.setClearButtonEnabled(True)
        in_row.addWidget(self._conv_input, 1)
        btn = PushButton(FluentIcon.FOLDER, "浏览")
        btn.clicked.connect(self._browse_conv_input)
        in_row.addWidget(btn)
        layout.addLayout(in_row)

        # 输出文件
        out_row = QHBoxLayout()
        out_row.addWidget(BodyLabel("输出文件:"))
        self._conv_output = LineEdit()
        self._conv_output.setPlaceholderText("输出图片文件路径...")
        self._conv_output.setClearButtonEnabled(True)
        out_row.addWidget(self._conv_output, 1)
        btn = PushButton(FluentIcon.FOLDER, "浏览")
        btn.clicked.connect(self._browse_conv_output)
        out_row.addWidget(btn)
        layout.addLayout(out_row)

        # 格式
        fmt_row = QHBoxLayout()
        fmt_row.addWidget(BodyLabel("输出格式:"))
        self._conv_format = ComboBox()
        self._conv_format.addItems([
            "自动（根据扩展名）", "PNG", "JPEG", "BMP", "WEBP",
            "TIFF", "ICO", "GIF", "PBM", "PGM", "PPM",
        ])
        self._conv_format.setMinimumWidth(160)
        self._conv_format.currentIndexChanged.connect(self._on_conv_format_changed)
        fmt_row.addWidget(self._conv_format)
        fmt_row.addStretch()
        layout.addLayout(fmt_row)

        # 缩放
        size_row = QHBoxLayout()
        size_row.addWidget(BodyLabel("缩放:"))
        self._conv_width = SpinBox()
        self._conv_width.setRange(0, 10000)
        self._conv_width.setValue(0)
        self._conv_width.setSpecialValueText("自动")
        self._conv_width.setSuffix(" px")
        self._conv_width.setFixedWidth(160)
        size_row.addWidget(self._conv_width)
        size_row.addWidget(BodyLabel("x"))
        self._conv_height = SpinBox()
        self._conv_height.setRange(0, 10000)
        self._conv_height.setValue(0)
        self._conv_height.setSpecialValueText("自动")
        self._conv_height.setSuffix(" px")
        self._conv_height.setFixedWidth(160)
        size_row.addWidget(self._conv_height)
        size_row.addStretch()
        layout.addLayout(size_row)

        # 质量
        qual_row = QHBoxLayout()
        qual_row.addWidget(BodyLabel("质量:"))
        self._conv_quality = SpinBox()
        self._conv_quality.setRange(-1, 100)
        self._conv_quality.setValue(-1)
        self._conv_quality.setSpecialValueText("默认")
        self._conv_quality.setFixedWidth(160)
        qual_row.addWidget(self._conv_quality)
        qual_row.addWidget(BodyLabel("（0-100，-1 为默认，对 JPEG/WebP 有效）"))
        qual_row.addStretch()
        layout.addLayout(qual_row)

        # 转换按钮
        btn_row = QHBoxLayout()
        self._btn_convert = PrimaryPushButton(FluentIcon.SYNC, "转换")
        self._btn_convert.clicked.connect(self._on_convert)
        btn_row.addWidget(self._btn_convert)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        parent_layout.addWidget(card)

    # ── 多图合并 ICO ──

    def _create_to_ico_section(self, parent_layout: QVBoxLayout) -> None:
        card = SimpleCardWidget()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        layout.addWidget(StrongBodyLabel("多图合并 ICO"))

        # 文件列表
        list_header = QHBoxLayout()
        list_header.addWidget(BodyLabel("图片列表:"))
        list_header.addStretch()
        btn_add = PushButton(FluentIcon.ADD, "添加")
        btn_add.clicked.connect(self._browse_ico_input)
        list_header.addWidget(btn_add)
        btn_clear = PushButton(FluentIcon.DELETE, "清空")
        btn_clear.clicked.connect(self._clear_ico_list)
        list_header.addWidget(btn_clear)
        layout.addLayout(list_header)

        self._ico_list = QListWidget()
        self._ico_list.setMaximumHeight(120)
        self._ico_list.setAlternatingRowColors(True)
        layout.addWidget(self._ico_list)

        # 输出路径
        out_row = QHBoxLayout()
        out_row.addWidget(BodyLabel("输出 ICO:"))
        self._ico_output = LineEdit()
        self._ico_output.setPlaceholderText("输出 ICO 文件路径...")
        self._ico_output.setClearButtonEnabled(True)
        out_row.addWidget(self._ico_output, 1)
        btn = PushButton(FluentIcon.FOLDER, "浏览")
        btn.clicked.connect(self._browse_ico_output)
        out_row.addWidget(btn)
        layout.addLayout(out_row)

        # 尺寸选择
        layout.addWidget(BodyLabel("ICO 包含尺寸:"))
        sizes_grid = QGridLayout()
        sizes_grid.setSpacing(8)
        self._ico_size_checks: dict[int, CheckBox] = {}
        default_sizes = [16, 32, 48, 64, 128, 256]
        for i, size in enumerate(default_sizes):
            cb = CheckBox(f"{size}x{size}")
            cb.setChecked(True)
            self._ico_size_checks[size] = cb
            sizes_grid.addWidget(cb, i // 3, i % 3)
        layout.addLayout(sizes_grid)

        # 转换按钮
        btn_row = QHBoxLayout()
        self._btn_to_ico = PrimaryPushButton(FluentIcon.SYNC, "生成 ICO")
        self._btn_to_ico.clicked.connect(self._on_to_ico)
        btn_row.addWidget(self._btn_to_ico)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        parent_layout.addWidget(card)

    # ── ICO 提取 ──

    def _create_from_ico_section(self, parent_layout: QVBoxLayout) -> None:
        card = SimpleCardWidget()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        layout.addWidget(StrongBodyLabel("ICO 提取"))

        # ICO 文件
        ico_row = QHBoxLayout()
        ico_row.addWidget(BodyLabel("ICO 文件:"))
        self._ext_ico_input = LineEdit()
        self._ext_ico_input.setPlaceholderText("选择 ICO 文件路径...")
        self._ext_ico_input.setClearButtonEnabled(True)
        ico_row.addWidget(self._ext_ico_input, 1)
        btn = PushButton(FluentIcon.FOLDER, "浏览")
        btn.clicked.connect(self._browse_ext_ico)
        ico_row.addWidget(btn)
        layout.addLayout(ico_row)

        # 输出目录
        dir_row = QHBoxLayout()
        dir_row.addWidget(BodyLabel("输出目录:"))
        self._ext_output_dir = LineEdit()
        self._ext_output_dir.setPlaceholderText("提取的图片保存到此目录...")
        self._ext_output_dir.setClearButtonEnabled(True)
        dir_row.addWidget(self._ext_output_dir, 1)
        btn = PushButton(FluentIcon.FOLDER, "浏览")
        btn.clicked.connect(self._browse_ext_dir)
        dir_row.addWidget(btn)
        layout.addLayout(dir_row)

        # 输出格式
        fmt_row = QHBoxLayout()
        fmt_row.addWidget(BodyLabel("输出格式:"))
        self._ext_format = ComboBox()
        self._ext_format.addItems(["PNG", "BMP", "WEBP", "JPEG"])
        self._ext_format.setMinimumWidth(120)
        fmt_row.addWidget(self._ext_format)
        fmt_row.addStretch()
        layout.addLayout(fmt_row)

        # 提取按钮
        btn_row = QHBoxLayout()
        self._btn_extract = PrimaryPushButton(FluentIcon.SYNC, "提取")
        self._btn_extract.clicked.connect(self._on_extract)
        btn_row.addWidget(self._btn_extract)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        parent_layout.addWidget(card)

    # ── 格式映射 ──

    _FORMAT_EXT: dict[str, str] = {
        "PNG": ".png", "JPEG": ".jpg", "BMP": ".bmp", "WEBP": ".webp",
        "TIFF": ".tiff", "ICO": ".ico", "GIF": ".gif",
        "PBM": ".pbm", "PGM": ".pgm", "PPM": ".ppm",
    }

    def _on_conv_format_changed(self, index: int) -> None:
        """格式下拉框变化时，自动更新输出路径后缀"""
        fmt_text = self._conv_format.currentText()
        ext = self._FORMAT_EXT.get(fmt_text)
        if ext is None:
            return
        current = self._conv_output.text().strip()
        if current:
            self._conv_output.setText(str(Path(current).with_suffix(ext)))

    # ── 文件浏览 ──

    def _browse_conv_input(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            None, "选择图片文件", "",
            "图片文件 (*.png *.jpg *.jpeg *.bmp *.webp *.tiff *.ico *.gif *.svg);;所有文件 (*)",
        )
        if path:
            self._conv_input.setText(path)
            p = Path(path)
            fmt_text = self._conv_format.currentText()
            ext = self._FORMAT_EXT.get(fmt_text, ".png")
            self._conv_output.setText(str(p.with_suffix(ext)))

    def _browse_conv_output(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            None, "保存图片", "",
            "PNG 文件 (*.png);;JPEG 文件 (*.jpg);;BMP 文件 (*.bmp);;所有文件 (*)",
        )
        if path:
            self._conv_output.setText(path)

    def _browse_ico_input(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            None, "选择图片文件", "",
            "图片文件 (*.png *.jpg *.jpeg *.bmp *.webp *.tiff *.ico *.gif *.svg);;所有文件 (*)",
        )
        for p in paths:
            item = QListWidgetItem(p)
            item.setData(Qt.ItemDataRole.UserRole, p)
            self._ico_list.addItem(item)

    def _clear_ico_list(self) -> None:
        self._ico_list.clear()

    def _browse_ico_output(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            None, "保存 ICO", "", "ICO 文件 (*.ico)",
        )
        if path:
            self._ico_output.setText(path)

    def _browse_ext_ico(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            None, "选择 ICO 文件", "", "ICO 文件 (*.ico);;所有文件 (*)",
        )
        if path:
            self._ext_ico_input.setText(path)
            p = Path(path)
            if not self._ext_output_dir.text().strip():
                self._ext_output_dir.setText(str(p.parent / p.stem))

    def _browse_ext_dir(self) -> None:
        from PySide6.QtWidgets import QFileDialog as FD
        d = FD.getExistingDirectory(None, "选择输出目录")
        if d:
            self._ext_output_dir.setText(d)

    # ── 操作 ──

    def _on_convert(self) -> None:
        input_path = self._conv_input.text().strip()
        output_path = self._conv_output.text().strip()
        if not input_path:
            InfoBar.warning(
                title="请选择文件", content="先选择要转换的图片文件",
                position=InfoBarPosition.TOP, duration=2000,
            )
            return
        if not output_path:
            InfoBar.warning(
                title="请指定输出路径", content="输出文件路径不能为空",
                position=InfoBarPosition.TOP, duration=2000,
            )
            return

        fmt_text = self._conv_format.currentText()
        output_format = "" if fmt_text.startswith("自动") else fmt_text.lower()
        width = self._conv_width.value() or None
        height = self._conv_height.value() or None
        quality = self._conv_quality.value()

        self._btn_convert.setEnabled(False)

        self._current_invoke = self.invoke(
            ImageToolPlugin.image_convert,
            ImageConvertArgs(
                input_path=input_path,
                output_path=output_path,
                output_format=output_format,
                width=width,
                height=height,
                quality=quality,
            ),
        )

    def _on_to_ico(self) -> None:
        if self._ico_list.count() == 0:
            InfoBar.warning(
                title="请添加图片", content="至少选择一张图片",
                position=InfoBarPosition.TOP, duration=2000,
            )
            return
        output_path = self._ico_output.text().strip()
        if not output_path:
            InfoBar.warning(
                title="请指定输出路径", content="ICO 输出路径不能为空",
                position=InfoBarPosition.TOP, duration=2000,
            )
            return

        image_paths = []
        for i in range(self._ico_list.count()):
            item = self._ico_list.item(i)
            image_paths.append(item.data(Qt.ItemDataRole.UserRole))

        sizes = [s for s, cb in self._ico_size_checks.items() if cb.isChecked()]
        if not sizes:
            sizes = [16, 32, 48, 64, 128, 256]

        self._btn_to_ico.setEnabled(False)

        self._current_invoke = self.invoke(
            ImageToolPlugin.image_to_ico,
            ImageToIcoArgs(
                image_paths=image_paths,
                output_path=output_path,
                sizes=sizes,
            ),
        )

    def _on_extract(self) -> None:
        ico_path = self._ext_ico_input.text().strip()
        output_dir = self._ext_output_dir.text().strip()
        if not ico_path:
            InfoBar.warning(
                title="请选择文件", content="先选择要提取的 ICO 文件",
                position=InfoBarPosition.TOP, duration=2000,
            )
            return
        if not output_dir:
            InfoBar.warning(
                title="请指定输出目录", content="输出目录不能为空",
                position=InfoBarPosition.TOP, duration=2000,
            )
            return

        output_format = self._ext_format.currentText().lower()

        self._btn_extract.setEnabled(False)

        self._current_invoke = self.invoke(
            ImageToolPlugin.ico_to_images,
            IcoToImagesArgs(
                ico_path=ico_path,
                output_dir=output_dir,
                output_format=output_format,
            ),
        )

    # ── 回调 ──

    def on_invoke_result(self, invoke_id: int, result: dict) -> None:
        if invoke_id != getattr(self, "_current_invoke", -1):
            return

        self._btn_convert.setEnabled(True)
        self._btn_to_ico.setEnabled(True)
        self._btn_extract.setEnabled(True)

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

        self._btn_convert.setEnabled(True)
        self._btn_to_ico.setEnabled(True)
        self._btn_extract.setEnabled(True)

        InfoBar.error(title="操作失败", content=error,
                      position=InfoBarPosition.TOP, duration=5000)

    def on_status_changed(self, status: str) -> None:
        pass
