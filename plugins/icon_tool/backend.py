"""MCP Tool Hub — 图标转换工具插件

使用 PySide6 的 QSvgRenderer 将 SVG 渲染为高质量光栅图，
支持输出 ICO（多尺寸）和 PNG 格式。

工具：
  - svg_to_ico: SVG → 多尺寸 ICO
  - svg_to_png: SVG → 指定尺寸 PNG
  - image_to_ico: 多张图片合并为 ICO
"""

from __future__ import annotations

import os
import struct
import sys
from pathlib import Path

from loguru import logger
from pydantic import BaseModel, Field

from api.base_plugin import BasePlugin
from api.tool import ToolDef
from api.types import MCPToolResult, PluginMeta


# ── 工具参数模型 ──


class SvgToIcoArgs(BaseModel):
    """SVG 转 ICO 参数"""

    svg_path: str = Field(description="SVG 文件路径")
    output_path: str = Field(description="输出 ICO 文件路径")
    sizes: list[int] = Field(
        default=[16, 32, 48, 64, 128, 256],
        description="ICO 包含的尺寸列表（像素）",
    )


class SvgToPngArgs(BaseModel):
    """SVG 转 PNG 参数"""

    svg_path: str = Field(description="SVG 文件路径")
    output_path: str = Field(description="输出 PNG 文件路径")
    size: int = Field(default=256, description="输出尺寸（像素，宽高相同）")


class ImageToIcoArgs(BaseModel):
    """多图合并 ICO 参数"""

    image_paths: list[str] = Field(description="图片文件路径列表（支持 PNG/JPEG/BMP/SVG）")
    output_path: str = Field(description="输出 ICO 文件路径")


# ── SVG 渲染引擎 ──


def _ensure_qapp() -> None:
    """确保 QApplication 实例存在（QSvgRenderer 依赖）"""
    from PySide6.QtWidgets import QApplication

    if QApplication.instance() is None:
        # 无头模式：使用 offscreen 平台插件
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        QApplication(sys.argv)


def _render_svg_to_png_bytes(svg_path: str, size: int) -> bytes:
    """使用 QSvgRenderer 将 SVG 渲染为 PNG 字节"""
    from PySide6.QtSvg import QSvgRenderer
    from PySide6.QtGui import QImage, QPainter
    from PySide6.QtCore import Qt, QByteArray

    svg_data = Path(svg_path).read_bytes()
    renderer = QSvgRenderer(QByteArray(svg_data))
    if not renderer.isValid():
        raise ValueError(f"无效的 SVG 文件: {svg_path}")

    img = QImage(size, size, QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.transparent)
    painter = QPainter(img)
    renderer.render(painter)
    painter.end()

    # QImage → PNG bytes
    from PySide6.QtCore import QBuffer, QIODevice

    qbuf = QBuffer()
    qbuf.open(QIODevice.OpenModeFlag.ReadWrite)
    img.save(qbuf, "PNG")  # type: ignore[call-overload]
    png_data = bytes(qbuf.data().data())
    qbuf.close()
    return png_data


def _load_image_to_png_bytes(image_path: str, size: int | None = None) -> bytes:
    """加载图片文件转为 PNG 字节（支持 SVG/PNG/JPEG/BMP）"""
    path = Path(image_path)
    if not path.exists():
        raise FileNotFoundError(f"文件不存在: {image_path}")

    suffix = path.suffix.lower()
    if suffix == ".svg":
        if size is None:
            size = 256
        return _render_svg_to_png_bytes(image_path, size)

    # 非 SVG：用 QImage 读取并缩放
    from PySide6.QtGui import QImage
    from PySide6.QtCore import Qt, QBuffer, QIODevice

    img = QImage(image_path)
    if img.isNull():
        raise ValueError(f"无法读取图片: {image_path}")
    img = img.convertToFormat(QImage.Format.Format_RGBA8888)
    if size is not None:
        img = img.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio,
                         Qt.TransformationMode.SmoothTransformation)
    qbuf = QBuffer()
    qbuf.open(QIODevice.OpenModeFlag.ReadWrite)
    img.save(qbuf, "PNG")  # type: ignore[call-overload]
    png_data = bytes(qbuf.data().data())
    qbuf.close()
    return png_data


# ── ICO 文件编码（纯 Python，无 Pillow 依赖）──


def _encode_ico(images_bgra: list[tuple[int, int, bytes]]) -> bytes:
    """将多张 BGRA 像素数据编码为 ICO 文件

    Args:
        images_bgra: 列表，每项为 (width, height, bgra_bytes)
            bgra_bytes 为从大到小排列的 BGRA 原始像素
    """
    # ICO header: reserved(2) + type(2) + count(2)
    header = struct.pack("<HHH", 0, 1, len(images_bgra))

    # 先构建所有 PNG 数据
    png_entries: list[tuple[int, int, bytes]] = []
    for w, h, bgra in images_bgra:
        from PySide6.QtGui import QImage
        img = QImage(bgra, w, h, w * 4, QImage.Format.Format_RGBA8888)
        from PySide6.QtCore import QBuffer, QIODevice
        qbuf = QBuffer()
        qbuf.open(QIODevice.OpenModeFlag.ReadWrite)
        img.save(qbuf, "PNG")  # type: ignore[call-overload]
        png_data = bytes(qbuf.data().data())
        qbuf.close()
        png_entries.append((w, h, png_data))

    # 计算目录偏移：header(6) + 每个目录项(16)
    dir_size = 6 + 16 * len(png_entries)
    offset = dir_size

    # 构建目录项 + 数据
    dir_entries = b""
    data_parts = b""
    for w, h, png_data in png_entries:
        # ICO 目录项：width(1) height(1) colors(1) reserved(1) planes(2) bpp(2) size(4) offset(4)
        width_byte = 0 if w >= 256 else w
        height_byte = 0 if h >= 256 else h
        dir_entries += struct.pack("<BBBBHHII",
                                   width_byte, height_byte, 0, 0,
                                   1, 32, len(png_data), offset)
        data_parts += png_data
        offset += len(png_data)

    return header + dir_entries + data_parts


# ── 插件实现 ──


class IconToolPlugin(BasePlugin):
    """图标转换工具插件 — SVG/PNG → ICO/PNG"""

    svg_to_ico = ToolDef("svg_to_ico", SvgToIcoArgs, description="将 SVG 文件转换为多尺寸 ICO 图标文件")
    svg_to_png = ToolDef("svg_to_png", SvgToPngArgs, description="将 SVG 文件渲染为指定尺寸的 PNG 图片")
    image_to_ico = ToolDef("image_to_ico", ImageToIcoArgs, description="将多张图片合并为一个多尺寸 ICO 图标文件")

    @property
    def meta(self) -> PluginMeta:
        return PluginMeta(
            name="icon_tool",
            display_name="图标转换工具",
            version="1.0.0",
            description="SVG/图片 → ICO/PNG 高质量转换，使用 Qt SVG 引擎渲染",
            author="MCP Tool Hub",
            icon="🎨",
        )

    # ── 工具实现 ──

    async def handle_svg_to_ico(self, args: SvgToIcoArgs) -> MCPToolResult:
        """SVG → 多尺寸 ICO"""
        try:
            _ensure_qapp()

            svg_path = Path(args.svg_path)
            if not svg_path.exists():
                return MCPToolResult(
                    content=[{"type": "text", "text": f"SVG 文件不存在: {args.svg_path}"}],
                    is_error=True,
                )

            # 渲染各尺寸 → BGRA 像素数据
            from PySide6.QtGui import QImage

            bgra_list: list[tuple[int, int, bytes]] = []
            for size in args.sizes:
                png_data = _render_svg_to_png_bytes(str(svg_path), size)
                img = QImage()
                img.loadFromData(png_data)
                img = img.convertToFormat(QImage.Format.Format_RGBA8888)
                w, h = img.width(), img.height()
                bgra = bytes(img.constBits()[:w * h * 4])
                bgra_list.append((w, h, bgra))

            # 从大到小排列
            bgra_list.sort(key=lambda x: x[0], reverse=True)

            # 编码 ICO
            ico_data = _encode_ico(bgra_list)
            output = Path(args.output_path)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(ico_data)

            file_size = output.stat().st_size
            return MCPToolResult(
                content=[{
                    "type": "text",
                    "text": (
                        f"ICO 生成成功: {output}\n"
                        f"包含尺寸: {args.sizes}\n"
                        f"文件大小: {file_size} 字节"
                    ),
                }]
            )

        except Exception as e:
            logger.error(f"svg_to_ico 失败: {e}")
            return MCPToolResult(
                content=[{"type": "text", "text": f"转换失败: {e}"}],
                is_error=True,
            )

    async def handle_svg_to_png(self, args: SvgToPngArgs) -> MCPToolResult:
        """SVG → 指定尺寸 PNG"""
        try:
            _ensure_qapp()

            svg_path = Path(args.svg_path)
            if not svg_path.exists():
                return MCPToolResult(
                    content=[{"type": "text", "text": f"SVG 文件不存在: {args.svg_path}"}],
                    is_error=True,
                )

            png_data = _render_svg_to_png_bytes(str(svg_path), args.size)

            output = Path(args.output_path)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(png_data)

            file_size = output.stat().st_size
            return MCPToolResult(
                content=[{
                    "type": "text",
                    "text": (
                        f"PNG 生成成功: {output}\n"
                        f"尺寸: {args.size}x{args.size}\n"
                        f"文件大小: {file_size} 字节"
                    ),
                }]
            )

        except Exception as e:
            logger.error(f"svg_to_png 失败: {e}")
            return MCPToolResult(
                content=[{"type": "text", "text": f"转换失败: {e}"}],
                is_error=True,
            )

    async def handle_image_to_ico(self, args: ImageToIcoArgs) -> MCPToolResult:
        """多图 → 多尺寸 ICO"""
        try:
            _ensure_qapp()

            if not args.image_paths:
                return MCPToolResult(
                    content=[{"type": "text", "text": "图片列表不能为空"}],
                    is_error=True,
                )

            from PySide6.QtGui import QImage

            bgra_list: list[tuple[int, int, bytes]] = []
            for p in args.image_paths:
                if not Path(p).exists():
                    return MCPToolResult(
                        content=[{"type": "text", "text": f"文件不存在: {p}"}],
                        is_error=True,
                    )
                png_data = _load_image_to_png_bytes(p)
                img = QImage()
                img.loadFromData(png_data)
                img = img.convertToFormat(QImage.Format.Format_RGBA8888)
                w, h = img.width(), img.height()
                bgra = bytes(img.constBits()[:w * h * 4])
                bgra_list.append((w, h, bgra))

            # 从大到小排列
            bgra_list.sort(key=lambda x: x[0], reverse=True)

            # 编码 ICO
            ico_data = _encode_ico(bgra_list)
            output = Path(args.output_path)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(ico_data)

            file_size = output.stat().st_size
            sizes_info = [f"{w}x{h}" for w, h, _ in bgra_list]
            return MCPToolResult(
                content=[{
                    "type": "text",
                    "text": (
                        f"ICO 生成成功: {output}\n"
                        f"包含尺寸: {sizes_info}\n"
                        f"文件大小: {file_size} 字节"
                    ),
                }]
            )

        except Exception as e:
            logger.error(f"image_to_ico 失败: {e}")
            return MCPToolResult(
                content=[{"type": "text", "text": f"转换失败: {e}"}],
                is_error=True,
            )

    async def on_load(self) -> None:
        logger.info("IconToolPlugin 已加载")

    async def on_unload(self) -> None:
        logger.info("IconToolPlugin 已卸载")
