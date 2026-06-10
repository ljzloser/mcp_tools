"""MCP Tool Hub — 全局路径管理

支持 development 和 PyInstaller 打包两种模式。
提供项目级路径和每个插件的独立数据目录。
"""

from __future__ import annotations

import sys
from pathlib import Path


class Paths:
    """全局路径管理器

    **开发模式**：所有路径相对于项目根目录
    **打包模式（PyInstaller）**：
      - 资源目录 = sys._MEIPASS（只读，含 plugins/ 等）
      - 数据目录 = exe 同级 data/ 目录（可写，含 db、logs、插件数据）
    """

    def __init__(self, data_dir: str | Path | None = None) -> None:
        self._frozen = getattr(sys, "_MEIPASS", None) is not None

        if self._frozen:
            self._resource_root = Path(sys._MEIPASS)  # type: ignore[arg-type]
            self._data_root = (
                Path(data_dir) if data_dir
                else Path(sys.executable).parent / "data"
            )
        else:
            self._resource_root = Path.cwd()
            self._data_root = (
                Path(data_dir) if data_dir
                else self._resource_root / "data"
            )

    # ── 项目级目录 ──

    @property
    def root(self) -> Path:
        """项目根 / 资源根（dev 为 cwd，打包为 _MEIPASS）"""
        return self._resource_root

    @property
    def data_dir(self) -> Path:
        """可写数据根目录（自动创建）"""
        self._data_root.mkdir(parents=True, exist_ok=True)
        return self._data_root

    @property
    def assets_dir(self) -> Path:
        """静态资源目录（图标等）"""
        return self._resource_root / "assets"

    @property
    def icon_path(self) -> Path:
        """应用图标 ICO 路径"""
        return self.assets_dir / "icon.ico"

    @property
    def icon_svg_path(self) -> Path:
        """应用图标 SVG 路径"""
        return self.assets_dir / "icon.svg"

    @property
    def plugins_dir(self) -> Path:
        """插件源码目录"""
        return self._resource_root / "plugins"

    @property
    def db_path(self) -> Path:
        """SQLite 数据库文件路径"""
        return self.data_dir / "mcp_tools.db"

    @property
    def logs_dir(self) -> Path:
        """日志目录"""
        p = self.data_dir / "logs"
        p.mkdir(parents=True, exist_ok=True)
        return p

    # ── 插件级目录 ──

    def plugin_data(self, plugin_name: str) -> Path:
        """每个插件独立的数据目录（自动创建）

        插件可在该目录下自由读写文件。
        路径示例: data/plugins/http_tool/
        """
        p = self.data_dir / "plugins" / plugin_name
        p.mkdir(parents=True, exist_ok=True)
        return p

    # ── 辅助 ──

    @property
    def is_frozen(self) -> bool:
        """是否在 PyInstaller 打包模式下运行"""
        return self._frozen


# ── 全局单例 ──
paths = Paths()
