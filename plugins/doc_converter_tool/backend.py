"""MCP Tool Hub — 文档格式转换插件

基于 pypandoc 的文档格式转换工具，支持：
  - md_to_docx: Markdown 转 Word DOCX
  - docx_to_pdf: Word DOCX 转 PDF
  - md_to_pdf: Markdown 转 PDF

PDF 转换使用 wkhtmltopdf 作为 PDF 引擎。
"""

from __future__ import annotations

import shutil
from pathlib import Path

from loguru import logger
from pydantic import BaseModel, Field

from api.base_plugin import BasePlugin
from api.tool import ToolDef
from api.types import MCPToolResult, PluginMeta


# ── 工具参数模型 ──


class MdToDocxArgs(BaseModel):
    """Markdown 转 DOCX 参数"""

    input_path: str = Field(description="输入的 Markdown 文件路径")
    output_path: str = Field(description="输出的 DOCX 文件路径")


class DocxToPdfArgs(BaseModel):
    """DOCX 转 PDF 参数"""

    input_path: str = Field(description="输入的 DOCX 文件路径")
    output_path: str = Field(description="输出的 PDF 文件路径")


class MdToPdfArgs(BaseModel):
    """Markdown 转 PDF 参数"""

    input_path: str = Field(description="输入的 Markdown 文件路径")
    output_path: str = Field(description="输出的 PDF 文件路径")


# ── 插件实现 ──


class DocConverterPlugin(BasePlugin):
    """文档格式转换插件：基于 pypandoc 实现 MD/DOCX/PDF 互转"""

    # ── 工具声明 ──
    md_to_docx = ToolDef(
        "md_to_docx",
        MdToDocxArgs,
        description="将 Markdown 文件转换为 Word DOCX 格式",
    )
    docx_to_pdf = ToolDef(
        "docx_to_pdf",
        DocxToPdfArgs,
        description="将 Word DOCX 文件转换为 PDF 格式",
    )
    md_to_pdf = ToolDef(
        "md_to_pdf",
        MdToPdfArgs,
        description="将 Markdown 文件转换为 PDF 格式",
    )

    @property
    def meta(self) -> PluginMeta:
        return PluginMeta(
            name="doc_converter_tool",
            display_name="文档格式转换",
            version="1.0.0",
            description="基于 pypandoc 的文档格式转换工具，支持 Markdown/DOCX/PDF 互转",
            author="MCP Tool Hub",
            icon="📄",
        )

    # ── 依赖检查 ──

    @staticmethod
    def _check_pandoc() -> MCPToolResult | None:
        """检查 pandoc 是否已安装，未安装则返回错误结果"""
        pandoc_path = shutil.which("pandoc")
        if pandoc_path is None:
            return MCPToolResult(
                content=[{
                    "type": "text",
                    "text": (
                        "pandoc 未安装。请先安装 pandoc：\n"
                        "  Windows: choco install pandoc 或从 https://pandoc.org/installing.html 下载\n"
                        "  macOS: brew install pandoc\n"
                        "  Linux: sudo apt install pandoc"
                    ),
                }],
                is_error=True,
            )
        return None

    @staticmethod
    def _check_wkhtmltopdf() -> MCPToolResult | None:
        """检查 wkhtmltopdf 是否已安装，未安装则返回错误结果"""
        wk_path = shutil.which("wkhtmltopdf")
        if wk_path is None:
            return MCPToolResult(
                content=[{
                    "type": "text",
                    "text": (
                        "wkhtmltopdf 未安装，PDF 转换需要此工具。请先安装：\n"
                        "  Windows: 从 https://wkhtmltopdf.org/downloads.html 下载安装\n"
                        "  macOS: brew install wkhtmltopdf\n"
                        "  Linux: sudo apt install wkhtmltopdf"
                    ),
                }],
                is_error=True,
            )
        return None

    @staticmethod
    def _check_input_file(input_path: str) -> MCPToolResult | None:
        """检查输入文件是否存在，不存在则返回错误结果"""
        p = Path(input_path)
        if not p.exists():
            return MCPToolResult(
                content=[{"type": "text", "text": f"输入文件不存在: {input_path}"}],
                is_error=True,
            )
        if not p.is_file():
            return MCPToolResult(
                content=[{"type": "text", "text": f"输入路径不是文件: {input_path}"}],
                is_error=True,
            )
        return None

    @staticmethod
    def _ensure_output_dir(output_path: str) -> MCPToolResult | None:
        """确保输出目录存在，失败则返回错误结果"""
        out = Path(output_path)
        try:
            out.parent.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            return MCPToolResult(
                content=[{"type": "text", "text": f"无法创建输出目录: {e}"}],
                is_error=True,
            )
        return None

    # ── 工具实现 ──

    async def handle_md_to_docx(self, args: MdToDocxArgs) -> MCPToolResult:
        """Markdown 转 DOCX"""
        # 检查依赖
        err = self._check_pandoc()
        if err:
            return err

        # 检查输入文件
        err = self._check_input_file(args.input_path)
        if err:
            return err

        # 确保输出目录
        err = self._ensure_output_dir(args.output_path)
        if err:
            return err

        try:
            import pypandoc

            pypandoc.convert_file(
                args.input_path,
                "docx",
                outputfile=args.output_path,
            )

            out = Path(args.output_path)
            size_kb = out.stat().st_size / 1024
            logger.info(f"md_to_docx 转换成功: {args.input_path} → {args.output_path} ({size_kb:.1f} KB)")

            return MCPToolResult(
                content=[{
                    "type": "text",
                    "text": (
                        f"转换成功！\n"
                        f"输入: {args.input_path}\n"
                        f"输出: {args.output_path}\n"
                        f"大小: {size_kb:.1f} KB"
                    ),
                }],
            )
        except Exception as e:
            logger.error(f"md_to_docx 转换失败: {e}")
            return MCPToolResult(
                content=[{"type": "text", "text": f"Markdown 转 DOCX 失败: {e}"}],
                is_error=True,
            )

    async def handle_docx_to_pdf(self, args: DocxToPdfArgs) -> MCPToolResult:
        """DOCX 转 PDF"""
        # 检查依赖
        err = self._check_pandoc()
        if err:
            return err
        err = self._check_wkhtmltopdf()
        if err:
            return err

        # 检查输入文件
        err = self._check_input_file(args.input_path)
        if err:
            return err

        # 确保输出目录
        err = self._ensure_output_dir(args.output_path)
        if err:
            return err

        try:
            import pypandoc

            pypandoc.convert_file(
                args.input_path,
                "pdf",
                outputfile=args.output_path,
                extra_args=["--pdf-engine=wkhtmltopdf"],
            )

            out = Path(args.output_path)
            size_kb = out.stat().st_size / 1024
            logger.info(f"docx_to_pdf 转换成功: {args.input_path} → {args.output_path} ({size_kb:.1f} KB)")

            return MCPToolResult(
                content=[{
                    "type": "text",
                    "text": (
                        f"转换成功！\n"
                        f"输入: {args.input_path}\n"
                        f"输出: {args.output_path}\n"
                        f"大小: {size_kb:.1f} KB"
                    ),
                }],
            )
        except Exception as e:
            logger.error(f"docx_to_pdf 转换失败: {e}")
            return MCPToolResult(
                content=[{"type": "text", "text": f"DOCX 转 PDF 失败: {e}"}],
                is_error=True,
            )

    async def handle_md_to_pdf(self, args: MdToPdfArgs) -> MCPToolResult:
        """Markdown 转 PDF"""
        # 检查依赖
        err = self._check_pandoc()
        if err:
            return err
        err = self._check_wkhtmltopdf()
        if err:
            return err

        # 检查输入文件
        err = self._check_input_file(args.input_path)
        if err:
            return err

        # 确保输出目录
        err = self._ensure_output_dir(args.output_path)
        if err:
            return err

        try:
            import pypandoc

            pypandoc.convert_file(
                args.input_path,
                "pdf",
                outputfile=args.output_path,
                extra_args=["--pdf-engine=wkhtmltopdf"],
            )

            out = Path(args.output_path)
            size_kb = out.stat().st_size / 1024
            logger.info(f"md_to_pdf 转换成功: {args.input_path} → {args.output_path} ({size_kb:.1f} KB)")

            return MCPToolResult(
                content=[{
                    "type": "text",
                    "text": (
                        f"转换成功！\n"
                        f"输入: {args.input_path}\n"
                        f"输出: {args.output_path}\n"
                        f"大小: {size_kb:.1f} KB"
                    ),
                }],
            )
        except Exception as e:
            logger.error(f"md_to_pdf 转换失败: {e}")
            return MCPToolResult(
                content=[{"type": "text", "text": f"Markdown 转 PDF 失败: {e}"}],
                is_error=True,
            )

    # ── 生命周期 ──

    async def on_load(self) -> None:
        logger.info("DocConverterPlugin 已加载")

    async def on_unload(self) -> None:
        logger.info("DocConverterPlugin 已卸载")
