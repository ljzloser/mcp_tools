"""示例插件 — 后端

演示如何使用 ToolDef 类属性声明工具，使用 Pydantic 模型声明参数。
演示自定义 ConfigField 子类：ColorField 用颜色选择器替代文本框。
"""

from pydantic import BaseModel, Field

from api.base_plugin import BasePlugin
from api.config import ConfigField, ConfigModel, ConfigWidgetBase, IntField, BoolField, StringField
from api.tool import ToolDef
from api.types import MCPToolResult, PluginMeta


# ── 工具参数模型 ──


class EchoArgs(BaseModel):
    """回显工具参数"""

    message: str = Field(description="要回显的消息")


# ── 自定义配置字段：颜色选择器 ──


class ColorField(ConfigField[str]):
    """颜色选择字段

    自定义 ConfigField 子类，重写 create_widget() 用颜色选择器替代文本框。
    存储格式为 "#RRGGBB" 字符串。
    """

    widget_type = "color"

    def create_widget(self, parent=None) -> ConfigWidgetBase:
        """重写 create_widget：颜色选择器 + 色块预览"""
        from PySide6.QtCore import Signal
        from PySide6.QtGui import QColor
        from PySide6.QtWidgets import QHBoxLayout, QWidget
        from qfluentwidgets import BodyLabel, PushButton, FluentIcon

        field = self

        class _Widget(QWidget):
            value_change = Signal(object)

            def __init__(self, parent=None):
                super().__init__(parent)
                layout = QHBoxLayout(self)
                layout.setContentsMargins(0, 0, 0, 0)

                if field.label:
                    lbl = BodyLabel(field.label)
                    lbl.setFixedWidth(120)
                    layout.addWidget(lbl)

                # 色块预览
                self._preview = QWidget()
                self._preview.setFixedSize(32, 32)
                self._preview.setStyleSheet(
                    f"background-color: {field.default}; border: 1px solid #ccc; border-radius: 4px;"
                )
                layout.addWidget(self._preview)

                # 颜色值文本
                self._text = str(field.default)
                layout.addStretch()

                # 选择按钮
                self._btn = PushButton(FluentIcon.PALETTE, "选择颜色")
                self._btn.setFixedWidth(100)
                self._btn.clicked.connect(self._pick_color)
                layout.addWidget(self._btn)

            def _pick_color(self) -> None:
                from PySide6.QtWidgets import QColorDialog
                initial = QColor(self._text) if self._text else QColor(field.default)
                color = QColorDialog.getColor(initial, self, "选择颜色")
                if color.isValid():
                    self._text = color.name()  # "#RRGGBB"
                    self._preview.setStyleSheet(
                        f"background-color: {self._text}; border: 1px solid #ccc; border-radius: 4px;"
                    )
                    self.value_change.emit(self._text)

            def get_value(self) -> str:
                return self._text

            def set_value(self, value: str) -> None:
                self._text = str(value) if value else field.default
                self._preview.setStyleSheet(
                    f"background-color: {self._text}; border: 1px solid #ccc; border-radius: 4px;"
                )

        return _Widget(parent)


# ── 插件配置模型 ──


class TemplateConfig(ConfigModel):
    """模板插件配置

    包含自定义 ColorField 演示：用颜色选择器替代文本框。
    """

    greeting = StringField(default="Hello", label="问候语", description="回显时添加的前缀")
    repeat_count = IntField(default=1, label="重复次数", min_value=1, max_value=10)
    uppercase = BoolField(default=False, label="转为大写")
    text_color = ColorField(default="#0078d4", label="文本颜色", description="回显文本的颜色")


# ── 插件实现 ──


class TemplatePlugin(BasePlugin[TemplateConfig]):
    """模板插件：演示如何开发一个 MCP 工具插件"""

    # ── 配置声明 ──
    config_class = TemplateConfig

    # ── 工具声明（类属性，既是元数据又是引用）──
    template_echo = ToolDef("template_echo", EchoArgs, description="回显输入内容（模板示例）")

    @property
    def meta(self) -> PluginMeta:
        return PluginMeta(
            name="template",
            display_name="模板插件",
            version="0.1.0",
            description="开发模板，演示插件结构",
            author="MCP Tool Hub",
            icon="📦",
        )

    # ── 工具实现（handle_{tool_name}，接收类型化参数）──

    async def handle_template_echo(self, args: EchoArgs) -> MCPToolResult:
        # 读取配置
        prefix = self.config.greeting if self.config else ""
        count = self.config.repeat_count if self.config else 1
        upper = self.config.uppercase if self.config else False
        color = self.config.text_color if self.config else "#000000"

        text = f"{prefix} {args.message}" if prefix else args.message
        if upper:
            text = text.upper()

        content = "\n".join([text] * count)
        return MCPToolResult(
            content=[{"type": "text", "text": content}]
        )

    async def on_load(self) -> None:
        print("TemplatePlugin 加载完成")

    async def on_unload(self) -> None:
        print("TemplatePlugin 已卸载")
