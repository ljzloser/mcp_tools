"""MCP Tool Hub — 管理界面启动入口"""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon
from PySide6.QtCore import Qt

from client.main_window import MainWindow
from utils.paths import paths


def main() -> None:
    # 高 DPI 支持
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("MCP Tool Hub")
    app.setOrganizationName("MCP Tool Hub")

    # 设置应用图标
    if paths.icon_path.exists():
        app.setWindowIcon(QIcon(str(paths.icon_path)))

    # Windows 任务栏 AppUserModelID（确保任务栏正确显示图标）
    try:
        from PySide6.QtWinExtras import QWinTaskbarButton  # noqa
    except ImportError:
        pass
    if sys.platform == "win32":
        import ctypes
        app_id = "MCPToolHub.Application.1"
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)

    window = MainWindow()
    window.show()

    # 启动后刷新概览页（其他页面在首次显示时自动初始化和刷新）
    window.overview_page.refresh()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
