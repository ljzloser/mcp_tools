"""MCP Tool Hub — OCR 文字识别工具插件

基于 pytesseract + Pillow，提供图片文字识别能力。

工具：
  - ocr_recognize:  识别图片中的文字
  - ocr_languages: 查看 Tesseract 支持的语言

依赖：
  - pytesseract (pip)
  - Pillow (已有)
  - Tesseract OCR 引擎（系统级，必须安装）

配置：
  - tesseract_path: Tesseract 可执行文件路径（留空则从 PATH 查找）
"""

from __future__ import annotations

from pathlib import Path

from loguru import logger
from pydantic import BaseModel, Field

from api.base_plugin import BasePlugin
from api.config import ConfigModel, PathField
from api.tool import ToolDef
from api.types import MCPToolResult, PluginMeta


# ── 工具参数模型 ──


class RecognizeArgs(BaseModel):
    """OCR 识别参数"""

    image_path: str = Field(description="图片文件路径（支持 PNG/JPG/BMP/TIFF 等）")
    language: str = Field(
        default="chi_sim+eng",
        description="识别语言代码，多个用+连接，如 chi_sim+eng, eng, jpn+eng",
    )
    config: str = Field(
        default="",
        description="Tesseract 额外参数，如 --psm 6（页面分割模式）",
    )


class LanguagesArgs(BaseModel):
    """查看支持的语言"""

    pass


# ── 配置模型 ──


class OcrToolConfig(ConfigModel):
    """OCR 工具配置"""

    tesseract_path = PathField(
        default="",
        label="Tesseract 路径",
        description="Tesseract 可执行文件路径，留空则从 PATH 环境变量查找。"
        "Windows 示例: C:\\Program Files\\Tesseract-OCR\\tesseract.exe",
    )


# ── 插件实现 ──


class OcrToolPlugin(BasePlugin[OcrToolConfig]):
    """OCR 文字识别工具插件"""

    config_class = OcrToolConfig

    ocr_recognize = ToolDef("ocr_recognize", RecognizeArgs,
                            description="识别图片中的文字，支持多语言")
    ocr_languages = ToolDef("ocr_languages", LanguagesArgs,
                            description="查看 Tesseract OCR 支持的语言列表")

    @property
    def meta(self) -> PluginMeta:
        return PluginMeta(
            name="ocr_tool",
            display_name="OCR文字识别",
            version="1.0.0",
            description="图片文字识别（基于 Tesseract OCR）",
            author="MCP Tool Hub",
            icon="📷",
        )

    def _check_tesseract(self) -> str | None:
        """检查 Tesseract 是否可用，返回错误信息或 None"""
        import os
        import pytesseract
        import platform

        # 设置自定义路径（如果配置了）
        tesseract_path = self.config.tesseract_path
        if tesseract_path:
            pytesseract.pytesseract.tesseract_cmd = tesseract_path
            # 自动设置 TESSDATA_PREFIX（从 tesseract.exe 推出 tessdata 目录）
            tesseract_dir = Path(tesseract_path).resolve().parent
            tessdata_dir = tesseract_dir / "tessdata"
            if tessdata_dir.exists():
                prefix = str(tessdata_dir.resolve())
                if platform.system() == "Windows":
                    prefix = prefix.replace("/", "\\")
                os.environ["TESSDATA_PREFIX"] = prefix
        else:
            # 未配置路径时，检查是否已有 TESSDATA_PREFIX
            if "TESSDATA_PREFIX" not in os.environ:
                # 尝试从常见位置推断
                common_paths = [
                    r"C:\Program Files\Tesseract-OCR",
                    r"C:\Program Files (x86)\Tesseract-OCR",
                ]
                for p in common_paths:
                    pp = Path(p).resolve()
                    if (pp / "tessdata").exists():
                        prefix = str((pp / "tessdata").resolve())
                        if platform.system() == "Windows":
                            prefix = prefix.replace("/", "\\")
                        os.environ["TESSDATA_PREFIX"] = prefix
                        break

        try:
            # 尝试获取版本
            version = pytesseract.get_tesseract_version()
            return None
        except pytesseract.TesseractNotFoundError:
            return "Tesseract OCR 引擎未安装。请参考文档安装：\n- Windows: https://github.com/UB-Mannheim/tesseract/wiki\n- Linux: sudo apt install tesseract-ocr"
        except Exception as e:
            return f"Tesseract 检查失败: {e}"

    # ── ocr_recognize ──

    async def handle_ocr_recognize(self, args: RecognizeArgs) -> MCPToolResult:
        # 先检查 Tesseract
        error = self._check_tesseract()
        if error:
            return MCPToolResult(content=[{"type": "text", "text": error}], is_error=True)

        try:
            from PIL import Image
            import pytesseract

            p = Path(args.image_path)
            if not p.exists():
                return MCPToolResult(
                    content=[
                        {"type": "text", "text": f"图片不存在: {args.image_path}"}],
                    is_error=True,
                )

            img = Image.open(p)

            # 构建 Tesseract 配置
            cfg = args.config.strip() if args.config.strip() else "--oem 3 --psm 6"
            lang = args.language.strip() if args.language.strip() else "chi_sim+eng"

            # 执行识别
            text = pytesseract.image_to_string(img, lang=lang, config=cfg)

            if not text.strip():
                return MCPToolResult(
                    content=[{"type": "text", "text": "未识别到文字"}],
                    is_error=True,
                )

            # 统计信息
            lines = text.split("\n")
            non_empty = [l for l in lines if l.strip()]
            info = f"[识别完成] {len(non_empty)} 行文字"

            return MCPToolResult(content=[{"type": "text", "text": f"{info}\n\n{text}"}])
        except Exception as e:
            logger.error(f"OCR 识别失败: {e}")
            return MCPToolResult(
                content=[{"type": "text", "text": f"识别失败: {e}"}],
                is_error=True,
            )

    # ── ocr_languages ──

    async def handle_ocr_languages(self, args: LanguagesArgs) -> MCPToolResult:
        error = self._check_tesseract()
        if error:
            return MCPToolResult(content=[{"type": "text", "text": error}], is_error=True)

        try:
            import pytesseract

            langs = pytesseract.get_languages()
            lines = ["## Tesseract 支持的语言", ""]
            for lang in sorted(langs):
                lines.append(f"- `{lang}`")

            return MCPToolResult(content=[{"type": "text", "text": "\n".join(lines)}])
        except Exception as e:
            return MCPToolResult(
                content=[{"type": "text", "text": f"获取语言列表失败: {e}"}],
                is_error=True,
            )

    async def on_load(self) -> None:
        logger.info("OcrToolPlugin 已加载")

    async def on_unload(self) -> None:
        logger.info("OcrToolPlugin 已卸载")
