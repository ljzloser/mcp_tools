"""MCP Tool Hub — QR 码 / 条码 生成 + 解码 插件

QR 码使用 Qt 绘制，条码使用 PIL ImageWriter（python-barcode 官方 Writer），
解码使用 pyzbar + PIL。

工具：
  - qrbarcode_generate_qr:      生成 QR 码
  - qrbarcode_generate_barcode:  生成条码
  - qrbarcode_decode:            识别 QR 码 / 条码
"""

from __future__ import annotations

import os
import sys
import base64
from io import BytesIO
from pathlib import Path

import barcode.writer
from loguru import logger
from pydantic import BaseModel, Field

from api.base_plugin import BasePlugin
from api.tool import ToolDef
from api.types import MCPToolResult, PluginMeta


# ── Qt 环境初始化 ──


def _ensure_qapp() -> None:
    """确保 QApplication 实例存在（QImage 依赖）"""
    from PySide6.QtWidgets import QApplication

    if QApplication.instance() is None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        QApplication(sys.argv)


# ── 辅助：QImage → base64 ──


def _qimage_to_base64(img: "PySide6.QtGui.QImage") -> str:
    """将 QImage 编码为 base64 PNG 字符串"""
    from PySide6.QtCore import QBuffer, QIODevice

    buf = QBuffer()
    buf.open(QIODevice.OpenModeFlag.ReadWrite)
    img.save(buf, "PNG")  # type: ignore[call-overload]
    data = bytes(buf.data().data())
    buf.close()
    return base64.b64encode(data).decode()


# ── 辅助：PIL Image → base64 ──


def _pil_to_base64(img: "PIL.Image.Image") -> str:
    """将 PIL Image 编码为 base64 PNG 字符串"""
    buf = BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


# ── 辅助：QImage → 文件 ──


def _qimage_save(img: "PySide6.QtGui.QImage", path: str) -> None:
    """将 QImage 保存到文件"""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    if not img.save(str(out)):
        raise RuntimeError(f"无法保存图片: {out}")


# ── 工具参数模型 ──


class QRArgs(BaseModel):
    """QR 码参数"""

    content: str = Field(description="QR 码内容（文本/URL）")
    output_path: str = Field(default="", description="保存路径（留空则返回 base64）")
    size: int = Field(default=256, description="图片尺寸（像素），默认 256")
    fill_color: str = Field(
        default="black", description="前景色，如 black, #000000")
    back_color: str = Field(
        default="white", description="背景色，如 white, #ffffff")


class BarcodeArgs(BaseModel):
    """条码参数"""

    content: str = Field(description="条码内容（数字）")
    barcode_type: str = Field(
        default="code128",
        description="条码类型: code128, code39, ean13, ean8, upca, itf, codabar",
    )
    output_path: str = Field(default="", description="保存路径（留空则返回 base64）")


class DecodeArgs(BaseModel):
    """解码参数"""

    image_path: str = Field(description="图片文件路径")


# 支持的条码类型
BARCODE_TYPES = {
    "code128": "Code128",
    "code39": "Code39",
    "ean13": "EAN13",
    "ean8": "EAN8",
    "upca": "UPCA",
    "itf": "ITF",
    "codabar": "CODABAR",
}


# ── QR 码绘制（Qt） ──


def _render_qr_matrix(
    matrix: list[list[bool]],
    size: int,
    fill_color: str,
    back_color: str,
) -> "PySide6.QtGui.QImage":
    """将 QR 码矩阵渲染为 QImage"""
    from PySide6.QtGui import QImage, QPainter, QColor
    from PySide6.QtCore import Qt

    _ensure_qapp()

    rows = len(matrix)
    cols = len(matrix[0]) if rows else 0
    if rows == 0 or cols == 0:
        raise ValueError("QR 矩阵为空")

    box = size / cols  # 每个模块的像素大小
    img = QImage(size, size, QImage.Format.Format_ARGB32)
    img.fill(QColor(back_color))

    painter = QPainter(img)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
    painter.setBrush(QColor(fill_color))
    painter.setPen(Qt.PenStyle.NoPen)

    for row in range(rows):
        for col in range(cols):
            if matrix[row][col]:
                x = int(col * box)
                y = int(row * box)
                w = int((col + 1) * box) - x
                h = int((row + 1) * box) - y
                painter.drawRect(x, y, w, h)

    painter.end()
    return img


class QrBarcodeToolPlugin(BasePlugin):
    """QR 码 / 条码生成插件"""

    qrbarcode_generate_qr = ToolDef(
        "qrbarcode_generate_qr", QRArgs,
        description="生成 QR 码图片（支持保存为 PNG 或返回 base64）",
    )
    qrbarcode_generate_barcode = ToolDef(
        "qrbarcode_generate_barcode", BarcodeArgs,
        description="生成条码图片（Code128/Code39/EAN13/EAN8 等）",
    )
    qrbarcode_decode = ToolDef(
        "qrbarcode_decode", DecodeArgs,
        description="识别图片中的 QR 码或条码内容",
    )

    @property
    def meta(self) -> PluginMeta:
        return PluginMeta(
            name="qrbarcode_tool",
            display_name="QR 码 / 条码生成",
            version="1.0.0",
            description="生成 QR 码和条码图片",
            author="MCP Tool Hub",
            icon="📷",
        )

    async def handle_qrbarcode_generate_qr(self, args: QRArgs) -> MCPToolResult:
        try:
            import qrcode

            qr = qrcode.QRCode(
                version=None,
                error_correction=qrcode.constants.ERROR_CORRECT_H,
                box_size=10,
                border=2,
            )
            qr.add_data(args.content)
            qr.make(fit=True)

            # 获取矩阵数据，用 Qt 绘制（不依赖 Pillow）
            matrix = qr.get_matrix()
            img = _render_qr_matrix(
                matrix, args.size, args.fill_color, args.back_color)

            if args.output_path:
                _qimage_save(img, args.output_path)
                return MCPToolResult(
                    content=[{
                        "type": "text",
                        "text": f"QR 码已保存: {args.output_path}\n尺寸: {args.size}x{args.size}\n内容: {args.content[:100]}",
                    }]
                )
            else:
                b64 = _qimage_to_base64(img)
                return MCPToolResult(
                    content=[{
                        "type": "text",
                        "text": f"QR 码生成成功（base64）\n尺寸: {args.size}x{args.size}\n内容: {args.content[:100]}\n\ndata:image/png;base64,{b64}",
                    }]
                )
        except Exception as e:
            logger.error(f"QR 码生成失败: {e}")
            return MCPToolResult(
                content=[{"type": "text", "text": f"QR 码生成失败: {e}"}],
                is_error=True,
            )

    async def handle_qrbarcode_generate_barcode(self, args: BarcodeArgs) -> MCPToolResult:
        try:
            import barcode
            from barcode.writer import ImageWriter

            bc_type = BARCODE_TYPES.get(args.barcode_type.lower())
            if not bc_type:
                supported = ", ".join(BARCODE_TYPES.keys())
                return MCPToolResult(
                    content=[
                        {"type": "text", "text": f"不支持的条码类型: {args.barcode_type}\n支持: {supported}"}],
                    is_error=True,
                )

            bc_class = barcode.get_barcode_class(bc_type)
            writer = ImageWriter()
            bc = bc_class(args.content, writer=writer)

            if args.output_path:
                saved = bc.save(str(Path(args.output_path).with_suffix("")))
                return MCPToolResult(
                    content=[{
                        "type": "text",
                        "text": f"条码已保存: {saved}\n类型: {bc_type}\n内容: {args.content}",
                    }]
                )
            else:
                # render 到 PIL Image，转 base64
                img = bc.render()
                b64 = _pil_to_base64(img)
                return MCPToolResult(
                    content=[{
                        "type": "text",
                        "text": f"条码生成成功（base64）\n类型: {bc_type}\n内容: {args.content}\n\ndata:image/png;base64,{b64}",
                    }]
                )
        except Exception as e:
            logger.error(f"条码生成失败: {e}")
            return MCPToolResult(
                content=[{"type": "text", "text": f"条码生成失败: {e}"}],
                is_error=True,
            )

    async def handle_qrbarcode_decode(self, args: DecodeArgs) -> MCPToolResult:
        try:
            from PIL import Image
            from pyzbar.pyzbar import decode as pyzbar_decode

            img = Image.open(args.image_path)
            results = pyzbar_decode(img)
            if not results:
                return MCPToolResult(
                    content=[{"type": "text", "text": "未识别到 QR 码或条码"}],
                    is_error=True,
                )

            lines = [f"共识别到 {len(results)} 个码："]
            for i, r in enumerate(results, 1):
                data = r.data.decode("utf-8", errors="replace")
                lines.append(f"\n{i}. 类型: {r.type}")
                lines.append(f"   内容: {data}")

            return MCPToolResult(content=[{"type": "text", "text": "\n".join(lines)}])
        except Exception as e:
            logger.error(f"解码失败: {e}")
            return MCPToolResult(
                content=[{"type": "text", "text": f"解码失败: {e}"}],
                is_error=True,
            )

    async def on_load(self) -> None:
        logger.info("QrBarcodeToolPlugin 已加载")

    async def on_unload(self) -> None:
        logger.info("QrBarcodeToolPlugin 已卸载")
