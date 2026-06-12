"""MCP Tool Hub — 全局主题与样式配置"""

from qfluentwidgets import Theme, setTheme, setThemeColor
from PySide6.QtGui import QColor, QGuiApplication, QPalette


# 主题色（MCP 品牌色：深蓝紫）
PRIMARY_COLOR = QColor(72, 61, 219)


def apply_theme(theme: Theme | None = None) -> None:
    """应用全局主题。

    如果未传入 `theme`，将基于系统窗口背景颜色自动判断亮/暗主题，
    以便跟随操作系统的深色模式设置。
    """
    if theme is None:
        try:
            palette = QGuiApplication.palette()
            bg = palette.color(QPalette.Window)
            # 计算亮度（感知亮度加权）
            brightness = (bg.red() * 299 + bg.green() *
                          587 + bg.blue() * 114) / 1000
            theme = Theme.DARK if brightness < 128 else Theme.LIGHT
        except Exception:
            theme = Theme.LIGHT

    setTheme(theme)
    setThemeColor(PRIMARY_COLOR)


def is_dark_theme() -> bool:
    """返回当前自动检测的主题是否为暗色（True = 暗色）。"""
    try:
        palette = QGuiApplication.palette()
        bg = palette.color(QPalette.Window)
        brightness = (bg.red() * 299 + bg.green() *
                      587 + bg.blue() * 114) / 1000
        return brightness < 128
    except Exception:
        return False
