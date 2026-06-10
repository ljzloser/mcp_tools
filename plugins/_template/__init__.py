"""MCP Tool Hub — 示例插件模板"""

from .backend import TemplatePlugin
from .widget import TemplateWidget

# 必需：后端插件类
PLUGIN_CLASS = TemplatePlugin

# 可选：管理界面类，无界面则设为 None
WIDGET_CLASS = TemplateWidget
