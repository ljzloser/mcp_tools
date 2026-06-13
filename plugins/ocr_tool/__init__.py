"""MCP Tool Hub — OCR 文字识别工具插件"""

from .backend import OcrToolPlugin
from .widget import OcrToolWidget

PLUGIN_CLASS = OcrToolPlugin
WIDGET_CLASS = OcrToolWidget
