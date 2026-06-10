"""MCP Tool Hub — 图标转换工具管理界面

提供可视化的 SVG → ICO/PNG 转换操作：
- SVG 文件选择 & 实时预览
- 输出格式（ICO / PNG）
- ICO 尺寸勾选
- 转换 & 结果展示
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
)
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QScrollArea,
    QFileDialog,
    QLabel,
)
from PySide6.QtGui import QPixmap, QImage, QPainter
from PySide6.QtCore import Qt

from api.base_widget import BasePluginWidget
from api.protocol import PluginInvokeResponse
from .backend import IconToolPlugin, SvgToIcoArgs, SvgToPngArgs


class IconToolWidget(BasePluginWidget):
    """图标转换工具的管理界面"""

    def get_name(self) -> str:
        return "icon_tool"

    def create_widget(self, parent: QWidget | None = None) -> QWidget:
        scroll = QScrollArea(parent)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # ── 输入区 ──
        input_card = SimpleCardWidget()
        input_layout = QVBoxLayout(input_card)
        input_layout.setContentsMargins(20, 16, 20, 16)
        input_layout.setSpacing(12)

        # SVG 文件选择
        svg_row = QHBoxLayout()
        svg_row.addWidget(BodyLabel("SVG 文件:"))
        self.input_svg = LineEdit()
        self.input_svg.setPlaceholderText("选择或输入 SVG 文件路径...")
        self.input_svg.setClearButtonEnabled(True)
        svg_row.addWidget(self.input_svg, 1)
        self.btn_browse = PushButton(FluentIcon.FOLDER, "浏览")
        self.btn_browse.clicked.connect(self._on_browse_svg)
        svg_row.addWidget(self.btn_browse)
        input_layout.addLayout(svg_row)

        # SVG 预览
        preview_row = QHBoxLayout()
        preview_row.addWidget(BodyLabel("预览:"))
        self._svg_preview = QLabel("未选择文件")
        self._svg_preview.setStyleSheet("color: #888;")
        self._svg_preview.setFixedSize(64, 64)
        self._svg_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        preview_row.addWidget(self._svg_preview)
        preview_row.addStretch()
        input_layout.addLayout(preview_row)

        layout.addWidget(input_card)

        # ── 设置区 ──
        settings_card = SimpleCardWidget()
        settings_layout = QVBoxLayout(settings_card)
        settings_layout.setContentsMargins(20, 16, 20, 16)
        settings_layout.setSpacing(12)

        # 输出格式
        format_row = QHBoxLayout()
        format_row.addWidget(BodyLabel("输出格式:"))
        self.combo_format = ComboBox()
        self.combo_format.addItems(["ICO", "PNG"])
        self.combo_format.setCurrentIndex(0)
        self.combo_format.setFixedWidth(120)
        self.combo_format.currentIndexChanged.connect(self._on_format_changed)
        format_row.addWidget(self.combo_format)
        format_row.addStretch()
        settings_layout.addLayout(format_row)

        # 输出路径
        out_row = QHBoxLayout()
        out_row.addWidget(BodyLabel("输出路径:"))
        self.input_output = LineEdit()
        self.input_output.setPlaceholderText("输出文件路径（自动根据 SVG 路径生成）...")
        self.input_output.setClearButtonEnabled(True)
        out_row.addWidget(self.input_output, 1)
        self.btn_browse_out = PushButton(FluentIcon.FOLDER, "浏览")
        self.btn_browse_out.clicked.connect(self._on_browse_output)
        out_row.addWidget(self.btn_browse_out)
        settings_layout.addLayout(out_row)

        # ICO 尺寸选择
        self._sizes_widget = QWidget()
        sizes_layout = QVBoxLayout(self._sizes_widget)
        sizes_layout.setContentsMargins(0, 0, 0, 0)
        sizes_layout.setSpacing(8)
        sizes_layout.addWidget(BodyLabel("ICO 包含尺寸:"))

        sizes_grid = QGridLayout()
        sizes_grid.setSpacing(8)
        self._size_checks: dict[int, CheckBox] = {}
        default_sizes = [16, 32, 48, 64, 128, 256]
        for i, size in enumerate(default_sizes):
            cb = CheckBox(f"{size}x{size}")
            cb.setChecked(True)
            self._size_checks[size] = cb
            sizes_grid.addWidget(cb, i // 3, i % 3)
        sizes_layout.addLayout(sizes_grid)
        settings_layout.addWidget(self._sizes_widget)

        # PNG 尺寸
        self._png_size_widget = QWidget()
        png_size_layout = QHBoxLayout(self._png_size_widget)
        png_size_layout.setContentsMargins(0, 0, 0, 0)
        png_size_layout.addWidget(BodyLabel("PNG 尺寸:"))
        self.spin_png_size = SpinBox()
        self.spin_png_size.setRange(16, 1024)
        self.spin_png_size.setValue(256)
        self.spin_png_size.setSingleStep(16)
        self.spin_png_size.setSuffix(" px")
        png_size_layout.addWidget(self.spin_png_size)
        png_size_layout.addStretch()
        self._png_size_widget.setVisible(False)
        settings_layout.addWidget(self._png_size_widget)

        layout.addWidget(settings_card)

        # ── 操作区 ──
        action_row = QHBoxLayout()
        self.btn_convert = PrimaryPushButton(FluentIcon.SYNC, "转换")
        self.btn_convert.clicked.connect(self._on_convert)
        action_row.addWidget(self.btn_convert)
        action_row.addStretch()
        layout.addLayout(action_row)

        # ── 结果区 ──
        result_card = SimpleCardWidget()
        result_layout = QVBoxLayout(result_card)
        result_layout.setContentsMargins(20, 16, 20, 16)
        result_layout.setSpacing(8)

        result_header = QHBoxLayout()
        result_header.addWidget(StrongBodyLabel("转换结果"))
        result_header.addStretch()
        result_layout.addLayout(result_header)

        self._result_label = BodyLabel("等待转换...")
        self._result_label.setWordWrap(True)
        self._result_label.setStyleSheet("color: #888;")
        result_layout.addWidget(self._result_label)

        self._result_preview = QLabel()
        self._result_preview.setFixedSize(128, 128)
        self._result_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._result_preview.setVisible(False)
        result_layout.addWidget(self._result_preview, alignment=Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(result_card)
        layout.addStretch()

        scroll.setWidget(container)
        return scroll

    # ── 事件处理 ──

    def _on_browse_svg(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            None, "选择 SVG 文件", "", "SVG 文件 (*.svg);;所有文件 (*)"
        )
        if path:
            self.input_svg.setText(path)
            self._update_svg_preview(path)
            self._auto_output_path(path)

    def _on_browse_output(self) -> None:
        fmt = self.combo_format.currentText()
        filter_str = "ICO 文件 (*.ico)" if fmt == "ICO" else "PNG 文件 (*.png)"
        path, _ = QFileDialog.getSaveFileName(None, "保存文件", "", filter_str)
        if path:
            self.input_output.setText(path)

    def _on_format_changed(self, index: int) -> None:
        is_ico = index == 0
        self._sizes_widget.setVisible(is_ico)
        self._png_size_widget.setVisible(not is_ico)
        # 更新输出路径扩展名
        current = self.input_output.text().strip()
        if current:
            p = Path(current)
            ext = ".ico" if is_ico else ".png"
            self.input_output.setText(str(p.with_suffix(ext)))

    def _on_convert(self) -> None:
        svg_path = self.input_svg.text().strip()
        if not svg_path:
            InfoBar.warning(
                title="请选择文件", content="先选择要转换的 SVG 文件",
                position=InfoBarPosition.TOP, duration=2000,
            )
            return

        output_path = self.input_output.text().strip()
        if not output_path:
            InfoBar.warning(
                title="请指定输出路径", content="输出文件路径不能为空",
                position=InfoBarPosition.TOP, duration=2000,
            )
            return

        self.btn_convert.setEnabled(False)
        self._result_label.setText("转换中...")
        self._result_label.setStyleSheet("color: #666;")
        self._result_preview.setVisible(False)

        if self.combo_format.currentText() == "ICO":
            sizes = [s for s, cb in self._size_checks.items() if cb.isChecked()]
            if not sizes:
                sizes = [16, 32, 48, 64, 128, 256]
            self._current_invoke = self.invoke(
                IconToolPlugin.svg_to_ico,
                SvgToIcoArgs(svg_path=svg_path, output_path=output_path, sizes=sizes),
            )
        else:
            self._current_invoke = self.invoke(
                IconToolPlugin.svg_to_png,
                SvgToPngArgs(
                    svg_path=svg_path, output_path=output_path,
                    size=self.spin_png_size.value(),
                ),
            )

    # ── 回调 ──

    def on_invoke_result(self, invoke_id: int, result: dict) -> None:
        if invoke_id != getattr(self, "_current_invoke", -1):
            return

        self.btn_convert.setEnabled(True)
        resp = PluginInvokeResponse(**result)

        text_parts = []
        for item in resp.content:
            if isinstance(item, dict) and item.get("type") == "text":
                text_parts.append(item.get("text", ""))
        text = "\n".join(text_parts) if text_parts else str(resp.content)

        if resp.is_error:
            self._result_label.setText(text)
            self._result_label.setStyleSheet("color: #d13438;")
            self._result_preview.setVisible(False)
        else:
            self._result_label.setText(text)
            self._result_label.setStyleSheet("color: #107c10;")
            self._show_output_preview()

    def on_invoke_error(self, invoke_id: int, error: str) -> None:
        if invoke_id != getattr(self, "_current_invoke", -1):
            return

        self.btn_convert.setEnabled(True)
        self._result_label.setText(f"转换失败: {error}")
        self._result_label.setStyleSheet("color: #d13438;")
        self._result_preview.setVisible(False)

    # ── 辅助 ──

    def _update_svg_preview(self, svg_path: str) -> None:
        """用 QSvgRenderer 渲染 SVG 预览"""
        from PySide6.QtSvg import QSvgRenderer
        from PySide6.QtCore import QByteArray

        if not Path(svg_path).exists():
            self._svg_preview.setText("文件不存在")
            return

        try:
            data = Path(svg_path).read_bytes()
            renderer = QSvgRenderer(QByteArray(data))
            if not renderer.isValid():
                self._svg_preview.setText("无效 SVG")
                return

            pm = QPixmap(64, 64)
            pm.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pm)
            renderer.render(painter)
            painter.end()
            self._svg_preview.setPixmap(pm)
        except Exception as e:
            self._svg_preview.setText(f"预览失败")

    def _auto_output_path(self, svg_path: str) -> None:
        """根据 SVG 路径自动生成输出路径"""
        p = Path(svg_path)
        ext = ".ico" if self.combo_format.currentText() == "ICO" else ".png"
        self.input_output.setText(str(p.with_suffix(ext)))

    def _show_output_preview(self) -> None:
        """显示输出文件的图片预览"""
        output = self.input_output.text().strip()
        if not output or not Path(output).exists():
            return

        try:
            suffix = Path(output).suffix.lower()
            if suffix in (".ico", ".png"):
                pm = QPixmap(output)
                if pm.width() > 128 or pm.height() > 128:
                    pm = pm.scaled(128, 128, Qt.AspectRatioMode.KeepAspectRatio,
                                  Qt.TransformationMode.SmoothTransformation)
            else:
                return

            self._result_preview.setPixmap(pm)
            self._result_preview.setVisible(True)
        except Exception:
            pass

    def on_status_changed(self, status: str) -> None:
        pass
