"""MCP Tool Hub — QR 码 / 条码生成插件"""

from .backend import QrBarcodeToolPlugin
from .widget import QrBarcodeToolWidget

PLUGIN_CLASS = QrBarcodeToolPlugin
WIDGET_CLASS = QrBarcodeToolWidget
