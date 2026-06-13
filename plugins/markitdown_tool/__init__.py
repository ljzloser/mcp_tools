"""MCP Tool Hub — MarkItDown 文档转换插件"""

from .backend import MarkitdownToolPlugin
from .widget import MarkitdownToolWidget

PLUGIN_CLASS = MarkitdownToolPlugin
WIDGET_CLASS = MarkitdownToolWidget
