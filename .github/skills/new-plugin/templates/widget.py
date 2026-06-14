"""{{ display_name }} Plugin — Management UI"""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFormLayout, QLabel, QLineEdit, QVBoxLayout, QWidget

from api.base_widget import BasePluginWidget
from api.types import MCPToolResult


class {{widget_class_name}}(BasePluginWidget):
    """Management interface for {{ display_name }} plugin"""

    # Signal to notify status changes
    status_changed = Signal(str)

    def get_name(self) -> str:
        return "{{ plugin_name }}"

    def create_widget(self, parent: QWidget | None = None) -> QWidget:
        container = QWidget(parent)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(20, 20, 20, 20)

        # Title
        title = QLabel("{{ display_name }}")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title)

        # Form
        form = QFormLayout()
        self.input_edit = QLineEdit()
        self.input_edit.setPlaceholderText("Enter input...")
        form.addRow("Input:", self.input_edit)
        layout.addLayout(form)

        # Execute button
        from qfluentwidgets import PrimaryPushButton
        self.execute_btn = PrimaryPushButton("Execute")
        self.execute_btn.clicked.connect(self._on_execute)
        layout.addWidget(self.execute_btn)

        # Result label
        self.result_label = QLabel("Result will appear here")
        self.result_label.setWordWrap(True)
        layout.addWidget(self.result_label)

        layout.addStretch()
        return container

    def _on_execute(self):
        input_text = self.input_edit.text()
        if not input_text:
            self.result_label.setText("Please enter input text")
            return

        # Use typed invoke instead of string
        from .backend import {{plugin_class_name}}, {{tools[0].args_model_name}}
        self.invoke(
            {{plugin_class_name}}.{{tools[0].name}},
            {{tools[0].args_model_name}}(input_text=input_text)
        )

    def on_result(self, result: MCPToolResult):
        if result.is_error:
            self.result_label.setText(f"Error: {result.content[0]['text']}")
        else:
            self.result_label.setText(result.content[0]["text"])
