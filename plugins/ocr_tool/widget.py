"""MCP Tool Hub — OCR 文字识别管理界面"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
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
    LineEdit as QLineEdit,
)

from api.base_widget import BasePluginWidget
from api.protocol import PluginInvokeResponse
from .backend import OcrToolPlugin, RecognizeArgs, LanguagesArgs


class OcrToolWidget(BasePluginWidget):
    """OCR 文字识别管理界面"""

    def get_name(self) -> str:
        return "ocr_tool"

    def create_widget(self, parent: QWidget | None = None) -> QWidget:
        scroll = SmoothScrollArea(parent)
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }")

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # ── 依赖说明 ──
        dep_card = SimpleCardWidget()
        dep_layout = QVBoxLayout(dep_card)
        dep_layout.setContentsMargins(16, 12, 16, 12)
        dep_layout.setSpacing(8)

        dep_title = StrongBodyLabel("⚠️ 依赖说明")
        dep_title.setStyleSheet("color: #d13438;")
        dep_layout.addWidget(dep_title)

        dep_text = BodyLabel(
            "本插件依赖 Tesseract OCR 引擎（系统级），必须单独安装：\n"
            "• Windows: 下载安装包 https://github.com/UB-Mannheim/tesseract/wiki\n"
            "• Linux: sudo apt install tesseract-ocr\n\n"
            "⚠️ 语言包：安装时勾选要用的语言（推荐勾选简体中文）。"
            "如果未安装，需要手动下载语言包放入 tessdata 目录：\n"
            "https://github.com/tesseract-ocr/tessdata\n"
            "常用：chi_sim（简体）, chi_tra（繁体）, jpn（日语）, kor（韩语）"
        )
        dep_text.setWordWrap(True)
        dep_layout.addWidget(dep_text)

        # 检查按钮
        check_row = QHBoxLayout()
        self._btn_check = PushButton(FluentIcon.INFO, "检查 Tesseract")
        self._btn_check.clicked.connect(self._on_check)
        check_row.addWidget(self._btn_check)
        check_row.addStretch()
        dep_layout.addLayout(check_row)

        self._check_result = BodyLabel("")
        dep_layout.addWidget(self._check_result)

        layout.addWidget(dep_card)

        # ── 识别功能 ──
        input_card = SimpleCardWidget()
        input_layout = QVBoxLayout(input_card)
        input_layout.setContentsMargins(16, 12, 16, 12)
        input_layout.setSpacing(10)

        input_layout.addWidget(StrongBodyLabel("图片 OCR 识别"))

        # 选择图片
        img_row = QHBoxLayout()
        img_row.addWidget(BodyLabel("图片路径:"))
        self._image_path = LineEdit()
        self._image_path.setPlaceholderText("选择要识别的图片...")
        self._image_path.setClearButtonEnabled(True)
        img_row.addWidget(self._image_path, 1)
        btn_browse = PushButton(FluentIcon.FOLDER, "浏览")
        btn_browse.clicked.connect(self._browse_image)
        img_row.addWidget(btn_browse)
        input_layout.addLayout(img_row)

        # 语言选择
        lang_row = QHBoxLayout()
        lang_row.addWidget(BodyLabel("识别语言:"))
        self._language = ComboBox()
        self._language.addItems([
            "chi_sim+eng (中英混合)",
            "eng (英语)",
            "chi_sim (简体中文)",
            "chi_tra (繁体中文)",
            "jpn (日语)",
            "kor (韩语)",
            "eng+chi_sim (英中)",
        ])
        self._language.setFixedWidth(200)
        lang_row.addWidget(self._language)
        lang_row.addStretch()
        input_layout.addLayout(lang_row)

        # 额外参数
        config_row = QHBoxLayout()
        config_row.addWidget(BodyLabel("额外参数:"))
        self._config = QLineEdit()
        self._config.setPlaceholderText("--psm 6 (页面分割模式，可留空)")
        self._config.setFixedWidth(250)
        config_row.addWidget(self._config)
        config_row.addStretch()
        input_layout.addLayout(config_row)

        # 识别按钮
        btn_row = QHBoxLayout()
        self._btn_recognize = PrimaryPushButton(FluentIcon.CAMERA, "开始识别")
        self._btn_recognize.clicked.connect(self._on_recognize)
        btn_row.addWidget(self._btn_recognize)
        btn_row.addStretch()
        input_layout.addLayout(btn_row)

        layout.addWidget(input_card)

        # ── 结果区 ──
        result_card = SimpleCardWidget()
        result_layout = QVBoxLayout(result_card)
        result_layout.setContentsMargins(16, 12, 16, 12)
        result_layout.setSpacing(8)

        result_layout.addWidget(StrongBodyLabel("识别结果"))
        self._result = TextEdit()
        self._result.setReadOnly(True)
        self._result.setMinimumHeight(200)
        self._result.setPlaceholderText("识别结果将显示在这里...")
        self._result.setStyleSheet(
            "font-family: Consolas, monospace; font-size: 13px;")
        result_layout.addWidget(self._result)

        layout.addWidget(result_card, 1)
        layout.addStretch()

        scroll.setWidget(container)
        return scroll

    def _browse_image(self) -> None:
        from PySide6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(
            None, "选择图片", "",
            "图片文件 (*.png *.jpg *.jpeg *.bmp *.tiff *.gif);;所有文件 (*)",
        )
        if path:
            self._image_path.setText(path)

    def _on_check(self) -> None:
        self._btn_check.setEnabled(False)
        self._check_result.setText("检查中...")
        self._check_result.setStyleSheet("color: #0078d4;")

        self._current_invoke = self.invoke(
            OcrToolPlugin.ocr_languages,
            LanguagesArgs(),
        )

    def _on_recognize(self) -> None:
        image_path = self._image_path.text().strip()
        if not image_path:
            InfoBar.warning(title="请选择图片", content="先选择要识别的图片",
                            position=InfoBarPosition.TOP, duration=2000)
            return

        self._btn_recognize.setEnabled(False)
        self._result.setPlainText("识别中，请稍候...")

        # 解析语言
        lang_map = {
            0: "chi_sim+eng",
            1: "eng",
            2: "chi_sim",
            3: "chi_tra",
            4: "jpn",
            5: "kor",
            6: "eng+chi_sim",
        }
        lang = lang_map.get(self._language.currentIndex(), "chi_sim+eng")

        self._current_invoke = self.invoke(
            OcrToolPlugin.ocr_recognize,
            RecognizeArgs(
                image_path=image_path,
                language=lang,
                config=self._config.text().strip(),
            ),
        )

    def on_invoke_result(self, invoke_id: int, result: dict) -> None:
        if invoke_id != getattr(self, "_current_invoke", -1):
            return

        self._btn_check.setEnabled(True)
        self._btn_recognize.setEnabled(True)

        resp = PluginInvokeResponse(**result)
        text_parts = []
        for item in resp.content:
            if isinstance(item, dict) and item.get("type") == "text":
                text_parts.append(item.get("text", ""))
        text = "\n".join(text_parts) if text_parts else str(resp.content)

        if resp.is_error:
            self._result.setPlainText(text)
            self._result.setStyleSheet(
                "font-family: Consolas, monospace; font-size: 13px; color: #d13438;")
            # 检查是否是 Tesseract 未安装
            if "Tesseract" in text and "未安装" in text:
                self._check_result.setText("❌ Tesseract 未安装")
                self._check_result.setStyleSheet("color: #d13438;")
            else:
                InfoBar.error(title="识别失败", content=text[:100],
                              position=InfoBarPosition.TOP, duration=3000)
        else:
            self._result.setPlainText(text)
            self._result.setStyleSheet(
                "font-family: Consolas, monospace; font-size: 13px;")
            # 检查结果
            if "检查" in str(getattr(self, "_current_invoke", "")):
                self._check_result.setText("✅ Tesseract 已安装")
                self._check_result.setStyleSheet("color: #107c10;")
            else:
                InfoBar.success(
                    title="识别成功", content="",
                    position=InfoBarPosition.TOP, duration=2000)

    def on_invoke_error(self, invoke_id: int, error: str) -> None:
        if invoke_id != getattr(self, "_current_invoke", -1):
            return

        self._btn_check.setEnabled(True)
        self._btn_recognize.setEnabled(True)
        self._result.setPlainText(f"[ERROR] {error}")
        self._result.setStyleSheet(
            "font-family: Consolas, monospace; font-size: 13px; color: #d13438;")

    def on_status_changed(self, status: str) -> None:
        pass
