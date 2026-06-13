"""MCP Tool Hub — 图片互转工具插件

使用 PySide6 的 QImage / QImageReader / QImageWriter 实现全格式互转，
支持读取 22 种格式、写入 17 种格式，包括 ICO 多尺寸编码/解码。

工具：
  - image_convert: 通用图片格式互转 + 缩放
  - image_to_ico:  多图/多尺寸 → ICO
  - ico_to_images: ICO → 提取各帧 PNG
"""

from __future__ import annotations

import os
import struct
import sys
from pathlib import Path

import PySide6
from loguru import logger
from pydantic import BaseModel, Field

from api.base_plugin import BasePlugin
from api.tool import ToolDef
from api.types import MCPToolResult, PluginMeta


# ── 工具参数模型 ──


class ImageConvertArgs(BaseModel):
    """图片格式互转参数"""

    input_path: str = Field(description="输入图片文件路径")
    output_path: str = Field(description="输出图片文件路径")
    output_format: str = Field(
        default="",
        description="输出格式（png/jpeg/bmp/webp/tiff/ico 等），留空则根据 output_path 扩展名推断",
    )
    width: int | None = Field(default=None, description="输出宽度（像素），留空保持原始比例")
    height: int | None = Field(default=None, description="输出高度（像素），留空保持原始比例")
    quality: int = Field(
        default=-1, description="输出质量（0-100，-1 为默认），对 JPEG/WebP 有效")


class ImageToIcoArgs(BaseModel):
    """多图合并 ICO 参数"""

    image_paths: list[str] = Field(description="图片文件路径列表（支持 Qt 可读的所有格式）")
    output_path: str = Field(description="输出 ICO 文件路径")
    sizes: list[int] = Field(
        default=[16, 32, 48, 64, 128, 256],
        description="如果输入只有一张图，自动缩放到这些尺寸；多张图则按原尺寸合并",
    )


class IcoToImagesArgs(BaseModel):
    """ICO 提取参数"""

    ico_path: str = Field(description="ICO 文件路径")
    output_dir: str = Field(description="输出目录（各帧 PNG 将保存到此目录）")
    output_format: str = Field(
        default="png", description="输出格式（png/bmp/webp 等）")


# ── Qt 环境初始化 ──


def _ensure_qapp() -> None:
    """确保 QApplication 实例存在（QImage 依赖）"""
    from PySide6.QtWidgets import QApplication

    if QApplication.instance() is None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        QApplication(sys.argv)


# ── 图片加载 ──


def _load_image(path: str) -> "PySide6.QtGui.QImage":
    """加载图片文件，支持 Qt 可读的所有格式（含 SVG）"""
    from PySide6.QtGui import QImage

    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"文件不存在: {path}")

    suffix = p.suffix.lower()
    if suffix in (".svg", ".svgz"):
        return _render_svg(path)

    img = QImage(path)
    if img.isNull():
        raise ValueError(f"无法读取图片: {path}")
    return img


def _render_svg(svg_path: str, size: int | None = None) -> "PySide6.QtGui.QImage":
    """使用 QSvgRenderer 将 SVG 渲染为 QImage"""
    from PySide6.QtSvg import QSvgRenderer
    from PySide6.QtGui import QImage, QPainter
    from PySide6.QtCore import Qt, QByteArray

    svg_data = Path(svg_path).read_bytes()
    renderer = QSvgRenderer(QByteArray(svg_data))
    if not renderer.isValid():
        raise ValueError(f"无效的 SVG 文件: {svg_path}")

    if size is None:
        size = renderer.defaultSize().width() or 256

    img = QImage(size, size, QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.transparent)
    painter = QPainter(img)
    renderer.render(painter)
    painter.end()
    return img


# ── 图片缩放 ──


def _scale_image(
    img: "PySide6.QtGui.QImage",
    width: int | None,
    height: int | None,
) -> "PySide6.QtGui.QImage":
    """缩放图片，宽高任一为 None 时保持原始比例"""
    from PySide6.QtGui import QImage
    from PySide6.QtCore import Qt

    if width is None and height is None:
        return img

    orig_w, orig_h = img.width(), img.height()
    if width is not None and height is not None:
        target_w, target_h = width, height
    elif width is not None:
        ratio = width / orig_w
        target_w, target_h = width, int(orig_h * ratio)
    else:
        ratio = height / orig_h
        target_w, target_h = int(orig_w * ratio), height

    return img.scaled(
        target_w, target_h,
        Qt.AspectRatioMode.IgnoreAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )


# ── 格式推断 ──


# Qt 支持的写入格式
_WRITE_FORMATS = {
    "bmp", "cur", "icns", "ico", "jfif", "jpeg", "jpg",
    "pbm", "pgm", "png", "ppm", "tif", "tiff", "wbmp",
    "webp", "xbm", "xpm",
}

# 扩展名 → Qt 格式名映射
_EXT_TO_FORMAT: dict[str, str] = {
    ".bmp": "BMP",
    ".cur": "CUR",
    ".icns": "ICNS",
    ".ico": "ICO",
    ".jfif": "JPEG",
    ".jpeg": "JPEG",
    ".jpg": "JPEG",
    ".pbm": "PBM",
    ".pgm": "PGM",
    ".png": "PNG",
    ".ppm": "PPM",
    ".tif": "TIFF",
    ".tiff": "TIFF",
    ".wbmp": "WBMP",
    ".webp": "WEBP",
    ".xbm": "XBM",
    ".xpm": "XPM",
}


def _resolve_format(output_path: str, output_format: str) -> str:
    """推断输出格式：优先用显式指定，否则从扩展名推断"""
    if output_format:
        fmt = output_format.lower().lstrip(".")
        if fmt in _WRITE_FORMATS:
            return fmt.upper()
        raise ValueError(f"不支持的输出格式: {output_format}")

    ext = Path(output_path).suffix.lower()
    fmt = _EXT_TO_FORMAT.get(ext)
    if fmt is None:
        raise ValueError(f"无法从扩展名推断格式: {ext}，请显式指定 output_format")
    return fmt


# ── ICO 编码（纯 Python，Qt 不支持多尺寸 ICO 写入）──


def _encode_ico(images: list["PySide6.QtGui.QImage"]) -> bytes:
    """将多张 QImage 编码为 ICO 文件（PNG-based entries）"""
    from PySide6.QtGui import QImage
    from PySide6.QtCore import QBuffer, QIODevice

    png_entries: list[tuple[int, int, bytes]] = []
    for img in images:
        img = img.convertToFormat(QImage.Format.Format_RGBA8888)
        w, h = img.width(), img.height()
        qbuf = QBuffer()
        qbuf.open(QIODevice.OpenModeFlag.ReadWrite)
        img.save(qbuf, "PNG")  # type: ignore[call-overload]
        png_data = bytes(qbuf.data().data())
        qbuf.close()
        png_entries.append((w, h, png_data))

    # 从大到小排列
    png_entries.sort(key=lambda x: x[0], reverse=True)

    # ICO header: reserved(2) + type(2) + count(2)
    header = struct.pack("<HHH", 0, 1, len(png_entries))

    # 计算目录偏移
    dir_size = 6 + 16 * len(png_entries)
    offset = dir_size

    dir_entries = b""
    data_parts = b""
    for w, h, png_data in png_entries:
        width_byte = 0 if w >= 256 else w
        height_byte = 0 if h >= 256 else h
        dir_entries += struct.pack(
            "<BBBBHHII",
            width_byte, height_byte, 0, 0,
            1, 32, len(png_data), offset,
        )
        data_parts += png_data
        offset += len(png_data)

    return header + dir_entries + data_parts


# ── ICO 解码（使用 QImageReader 原生多帧读取）──


def _decode_ico(ico_path: str) -> list["PySide6.QtGui.QImage"]:
    """从 ICO 文件提取所有帧"""
    from PySide6.QtGui import QImageReader

    reader = QImageReader(ico_path)
    count = reader.imageCount()
    if count <= 0:
        # 单帧 fallback
        img = reader.read()
        if img.isNull():
            raise ValueError(f"无法读取 ICO: {ico_path}")
        return [img]

    frames: list = []
    for i in range(count):
        if i > 0:
            reader.jumpToImage(i)
        frame = reader.read()
        if not frame.isNull():
            frames.append(frame)
    return frames


# ── 插件实现 ──


class ImageToolPlugin(BasePlugin):
    """图片互转工具插件 — 全格式互转 + ICO 编解码"""

    image_convert = ToolDef(
        "image_convert", ImageConvertArgs, description="图片格式互转（支持缩放、质量调整）")
    image_to_ico = ToolDef("image_to_ico", ImageToIcoArgs,
                           description="将多张图片合并为多尺寸 ICO 图标文件")
    ico_to_images = ToolDef(
        "ico_to_images", IcoToImagesArgs, description="从 ICO 文件提取各帧图片")

    @property
    def meta(self) -> PluginMeta:
        return PluginMeta(
            name="image_tool",
            display_name="图片互转工具",
            version="1.0.0",
            description="全格式图片互转 + ICO 编解码，基于 Qt 图像引擎",
            author="MCP Tool Hub",
            icon="🖼",
        )

    # ── 工具实现 ──

    async def handle_image_convert(self, args: ImageConvertArgs) -> MCPToolResult:
        """通用图片格式互转 + 缩放"""
        try:
            _ensure_qapp()

            input_path = Path(args.input_path)
            if not input_path.exists():
                return MCPToolResult(
                    content=[
                        {"type": "text", "text": f"输入文件不存在: {args.input_path}"}],
                    is_error=True,
                )

            img = _load_image(args.input_path)
            img = _scale_image(img, args.width, args.height)

            fmt = _resolve_format(args.output_path, args.output_format)

            output = Path(args.output_path)
            output.parent.mkdir(parents=True, exist_ok=True)

            # 设置质量参数
            from PySide6.QtGui import QImageWriter
            from PySide6.QtCore import QBuffer, QIODevice

            writer = QImageWriter(str(output), fmt.encode())
            if args.quality >= 0:
                writer.setQuality(args.quality)

            if not writer.write(img):
                return MCPToolResult(
                    content=[
                        {"type": "text", "text": f"写入失败: {writer.errorString()}"}],
                    is_error=True,
                )

            file_size = output.stat().st_size
            return MCPToolResult(
                content=[{
                    "type": "text",
                    "text": (
                        f"转换成功: {output}\n"
                        f"格式: {fmt} | 尺寸: {img.width()}x{img.height()}\n"
                        f"文件大小: {file_size} 字节"
                    ),
                }]
            )

        except Exception as e:
            logger.error(f"image_convert 失败: {e}")
            return MCPToolResult(
                content=[{"type": "text", "text": f"转换失败: {e}"}],
                is_error=True,
            )

    async def handle_image_to_ico(self, args: ImageToIcoArgs) -> MCPToolResult:
        """多图/多尺寸 → ICO"""
        try:
            _ensure_qapp()

            if not args.image_paths:
                return MCPToolResult(
                    content=[{"type": "text", "text": "图片列表不能为空"}],
                    is_error=True,
                )

            for p in args.image_paths:
                if not Path(p).exists():
                    return MCPToolResult(
                        content=[{"type": "text", "text": f"文件不存在: {p}"}],
                        is_error=True,
                    )

            from PySide6.QtGui import QImage

            ico_images: list[QImage] = []

            if len(args.image_paths) == 1:
                # 单图 → 自动缩放到各尺寸
                img = _load_image(args.image_paths[0])
                for size in args.sizes:
                    scaled = _scale_image(img, size, size)
                    ico_images.append(scaled)
            else:
                # 多图 → 按原尺寸合并
                for p in args.image_paths:
                    img = _load_image(p)
                    ico_images.append(img)

            # 编码 ICO
            ico_data = _encode_ico(ico_images)
            output = Path(args.output_path)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(ico_data)

            file_size = output.stat().st_size
            sizes_info = [
                f"{img.width()}x{img.height()}" for img in ico_images]
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

    async def handle_ico_to_images(self, args: IcoToImagesArgs) -> MCPToolResult:
        """ICO → 提取各帧"""
        try:
            _ensure_qapp()

            ico_path = Path(args.ico_path)
            if not ico_path.exists():
                return MCPToolResult(
                    content=[
                        {"type": "text", "text": f"ICO 文件不存在: {args.ico_path}"}],
                    is_error=True,
                )

            frames = _decode_ico(args.ico_path)
            if not frames:
                return MCPToolResult(
                    content=[{"type": "text", "text": "ICO 文件中未找到有效帧"}],
                    is_error=True,
                )

            output_dir = Path(args.output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)

            fmt = args.output_format.lower().lstrip(".")
            ext = f".{fmt}"

            from PySide6.QtGui import QImageWriter

            saved: list[str] = []
            for i, frame in enumerate(frames):
                filename = f"frame_{i}_{frame.width()}x{frame.height()}{ext}"
                out_path = output_dir / filename

                writer = QImageWriter(str(out_path), fmt.encode())
                if not writer.write(frame):
                    logger.warning(f"帧 {i} 写入失败: {writer.errorString()}")
                    continue
                saved.append(str(out_path))

            return MCPToolResult(
                content=[{
                    "type": "text",
                    "text": (
                        f"ICO 提取成功: 共 {len(frames)} 帧，保存 {len(saved)} 个文件\n"
                        f"输出目录: {output_dir}\n"
                        + "\n".join(f"  - {Path(s).name}" for s in saved)
                    ),
                }]
            )

        except Exception as e:
            logger.error(f"ico_to_images 失败: {e}")
            return MCPToolResult(
                content=[{"type": "text", "text": f"提取失败: {e}"}],
                is_error=True,
            )

    async def on_load(self) -> None:
        logger.info("ImageToolPlugin 已加载")

    async def on_unload(self) -> None:
        logger.info("ImageToolPlugin 已卸载")
