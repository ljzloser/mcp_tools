"""示例插件 — 管理界面"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFormLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from api.base_widget import BasePluginWidget


class TemplateWidget(BasePluginWidget):
    """模板插件的管理界面"""

    def get_name(self) -> str:
        return "template"

    def create_widget(self, parent: QWidget | None = None) -> QWidget:
        container = QWidget(parent)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(20, 20, 20, 20)

        # 标题
        title = QLabel("模板插件配置")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title)

        # 表单
        form = QFormLayout()
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("输入名称...")
        form.addRow("名称:", self.name_edit)
        layout.addLayout(form)

        # 状态
        self.status_label = QLabel("状态：未加载")
        layout.addWidget(self.status_label)

        layout.addStretch()
        return container

    def on_status_changed(self, status: str) -> None:
        self.status_label.setText(f"状态：{status}")
