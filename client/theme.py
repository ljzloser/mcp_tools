"""MCP Tool Hub — 全局主题与样式配置"""

from qfluentwidgets import Theme, setTheme, setThemeColor
from PySide6.QtGui import QColor


# 主题色（MCP 品牌色：深蓝紫）
PRIMARY_COLOR = QColor(72, 61, 219)


def apply_theme(theme: Theme = Theme.LIGHT) -> None:
    """应用全局主题"""
    setTheme(theme)
    setThemeColor(PRIMARY_COLOR)
