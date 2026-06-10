"""MCP Tool Hub — HTTP 请求插件管理界面

通过 invoke() 调用后端 http_get / http_post 工具发送请求。
使用 ToolDef 引用和 Pydantic 参数模型，避免字符串硬编码。
"""

from __future__ import annotations

import json

from qfluentwidgets import (
    BodyLabel,
    StrongBodyLabel,
    PrimaryPushButton,
    PushButton,
    FluentIcon,
    LineEdit,
    TextEdit,
    ComboBox,
    SimpleCardWidget,
    InfoBar,
    InfoBarPosition,
    ProgressRing,
)
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
)

from api.base_widget import BasePluginWidget
from api.protocol import PluginInvokeResponse
from .backend import HttpGetArgs, HttpPostArgs, HttpToolPlugin


class HttpToolWidget(BasePluginWidget):
    """HTTP 请求工具的管理界面"""

    def get_name(self) -> str:
        return "http_tool"

    def create_widget(self, parent: QWidget | None = None) -> QWidget:
        self._container = QWidget(parent)

        layout = QVBoxLayout(self._container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # 请求表单
        form_card = SimpleCardWidget()
        form_layout = QVBoxLayout(form_card)
        form_layout.setContentsMargins(20, 16, 20, 16)
        form_layout.setSpacing(12)

        # 方法 + URL
        url_row = QHBoxLayout()
        self.combo_method = ComboBox()
        self.combo_method.addItems(["GET", "POST", "PUT", "DELETE"])
        self.combo_method.setFixedWidth(100)
        self.input_url = LineEdit()
        self.input_url.setPlaceholderText("输入请求 URL，例如 https://httpbin.org/get")
        self.input_url.setClearButtonEnabled(True)
        url_row.addWidget(self.combo_method)
        url_row.addWidget(self.input_url, 1)
        form_layout.addLayout(url_row)

        # 请求体
        body_row = QHBoxLayout()
        body_row.addWidget(BodyLabel("请求体 (JSON):"))
        body_row.addStretch()
        form_layout.addLayout(body_row)
        self.input_body = TextEdit()
        self.input_body.setPlaceholderText('{"key": "value"}')
        self.input_body.setMaximumHeight(100)
        form_layout.addWidget(self.input_body)

        # 发送按钮
        btn_row = QHBoxLayout()
        self.btn_send = PrimaryPushButton(FluentIcon.SEND, "发送请求")
        self.btn_clear = PushButton(FluentIcon.CANCEL, "清空")
        self._loading = ProgressRing()
        self._loading.setFixedSize(24, 24)
        self._loading.setVisible(False)
        btn_row.addWidget(self.btn_send)
        btn_row.addWidget(self.btn_clear)
        btn_row.addWidget(self._loading)
        btn_row.addStretch()
        form_layout.addLayout(btn_row)

        layout.addWidget(form_card)

        # 响应区
        resp_header = QHBoxLayout()
        resp_header.addWidget(StrongBodyLabel("响应"))
        self._status_label = BodyLabel("")
        self._status_label.setStyleSheet("color: #888;")
        resp_header.addStretch()
        resp_header.addWidget(self._status_label)
        layout.addLayout(resp_header)

        self.response_card = SimpleCardWidget()
        resp_layout = QVBoxLayout(self.response_card)
        resp_layout.setContentsMargins(2, 2, 2, 2)
        self.response_text = TextEdit()
        self.response_text.setReadOnly(True)
        self.response_text.setMinimumHeight(200)
        self.response_text.setPlaceholderText("等待请求...")
        self.response_text.setStyleSheet("""
            TextEdit {
                font-family: 'Cascadia Code', 'Consolas', 'Courier New', monospace;
                font-size: 13px;
                padding: 12px;
                border: none;
            }
        """)
        resp_layout.addWidget(self.response_text)
        layout.addWidget(self.response_card, 1)

        # 连接信号
        self.btn_send.clicked.connect(self._on_send)
        self.btn_clear.clicked.connect(self._on_clear)

        return self._container

    def _on_send(self) -> None:
        """发送 HTTP 请求（通过类型化 invoke 调用后端）"""
        url = self.input_url.text().strip()
        if not url:
            InfoBar.warning(
                title="URL 不能为空",
                content="请输入请求 URL",
                parent=self._container,
                position=InfoBarPosition.TOP,
                duration=2000,
            )
            return

        method = self.combo_method.currentText()
        body: dict | None = None
        if method in ("POST", "PUT") and self.input_body.toPlainText().strip():
            try:
                body = json.loads(self.input_body.toPlainText())
            except json.JSONDecodeError:
                InfoBar.error(
                    title="JSON 格式错误",
                    content="请检查请求体 JSON 格式",
                    parent=self._container,
                    position=InfoBarPosition.TOP,
                    duration=2000,
                )
                return

        # 显示 loading
        self._loading.setVisible(True)
        self.btn_send.setEnabled(False)
        self.response_text.setPlainText("请求中...")

        # 根据方法使用类型化 invoke
        if method == "GET":
            self._current_invoke = self.invoke(
                HttpToolPlugin.http_get,
                HttpGetArgs(url=url),
            )
        elif method in ("POST", "PUT"):
            self._current_invoke = self.invoke(
                HttpToolPlugin.http_post,
                HttpPostArgs(url=url, body=body),
            )
        else:
            # DELETE — 复用 http_get
            self._current_invoke = self.invoke(
                HttpToolPlugin.http_get,
                HttpGetArgs(url=url),
            )

    def on_invoke_result(self, invoke_id: int, result: dict) -> None:
        """后端工具调用成功回调"""
        if invoke_id != getattr(self, "_current_invoke", -1):
            return

        self._loading.setVisible(False)
        self.btn_send.setEnabled(True)

        # 类型化解析
        resp = PluginInvokeResponse(**result)

        # 提取文本
        text_parts = []
        for item in resp.content:
            if isinstance(item, dict) and item.get("type") == "text":
                text_parts.append(item.get("text", ""))

        raw_text = "\n".join(text_parts) if text_parts else str(resp.content)

        # 尝试格式化 JSON
        try:
            data = json.loads(raw_text)
            formatted = json.dumps(data, indent=2, ensure_ascii=False)
        except (json.JSONDecodeError, TypeError):
            formatted = raw_text

        # 状态标签
        if resp.is_error:
            self._status_label.setStyleSheet("color: #d13438; font-weight: 500;")
            self._status_label.setText("请求失败")
        else:
            self._status_label.setStyleSheet("color: #107c10; font-weight: 500;")
            self._status_label.setText(f"响应长度: {len(formatted)} 字符")

        self.response_text.setPlainText(formatted)

    def on_invoke_error(self, invoke_id: int, error: str) -> None:
        """后端工具调用失败回调"""
        if invoke_id != getattr(self, "_current_invoke", -1):
            return

        self._loading.setVisible(False)
        self.btn_send.setEnabled(True)
        self._status_label.setStyleSheet("color: #d13438; font-weight: 500;")
        self._status_label.setText("调用失败")
        self.response_text.setPlainText(f"错误: {error}")

    def _on_clear(self) -> None:
        """清空表单和响应"""
        self.input_url.clear()
        self.input_body.clear()
        self.response_text.clear()
        self._status_label.setText("")

    def on_status_changed(self, status: str) -> None:
        """插件状态变化回调"""
        pass
