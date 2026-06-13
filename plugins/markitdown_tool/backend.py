"""MCP Tool Hub — MarkItDown 文档转 Markdown 插件

基于 markitdown 库，支持 PDF / DOCX / PPTX / XLSX / HTML / EPUB / CSV / 图片等。

工具：
  - markitdown_convert: 本地文件转 Markdown
  - markitdown_convert_url: URL 转 Markdown
"""

from __future__ import annotations

from pathlib import Path

from loguru import logger
from pydantic import BaseModel, Field

from api.base_plugin import BasePlugin
from api.tool import ToolDef
from api.types import MCPToolResult, PluginMeta


class ConvertArgs(BaseModel):
    """本地文件转 Markdown"""

    input_path: str = Field(description="输入文件路径")
    output_path: str = Field(default="", description="输出文件路径（留空则仅返回内容，不保存文件）")


class ConvertUrlArgs(BaseModel):
    """URL 转 Markdown"""

    url: str = Field(description="网页或文件 URL")
    output_path: str = Field(default="", description="保存路径（留空则仅返回内容，不保存文件）")


class MarkitdownToolPlugin(BasePlugin):
    """MarkItDown 文档转 Markdown 插件"""

    markitdown_convert = ToolDef(
        "markitdown_convert", ConvertArgs,
        description="将本地文档转换为 Markdown（PDF/DOCX/PPTX/XLSX/XLS/HTML/EPUB/CSV/等）",
    )
    markitdown_convert_url = ToolDef(
        "markitdown_convert_url", ConvertUrlArgs,
        description="将网页或远程文件 URL 转换为 Markdown",
    )

    @property
    def meta(self) -> PluginMeta:
        return PluginMeta(
            name="markitdown_tool",
            display_name="文档转MD工具",
            version="1.0.0",
            description="多格式文档转 Markdown 工具 基于 markitdown 库",
            author="MCP Tool Hub",
            icon="📝",
        )

    def _get_converter(self):
        from markitdown import MarkItDown
        return MarkItDown()

    async def handle_markitdown_convert(self, args: ConvertArgs) -> MCPToolResult:
        try:
            p = Path(args.input_path)
            if not p.exists():
                return MCPToolResult(
                    content=[
                        {"type": "text", "text": f"文件不存在: {args.input_path}"}],
                    is_error=True,
                )

            mdt = self._get_converter()
            result = mdt.convert_local(str(p))

            saved = ""
            if args.output_path:
                out = Path(args.output_path)
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_text(result.text_content, encoding="utf-8")
                saved = f"\n已保存: {out}"

            return MCPToolResult(
                content=[{
                    "type": "text",
                    "text": f"标题: {result.title or '无'}{saved}\n\n{result.text_content}",
                }]
            )
        except Exception as e:
            logger.error(f"markitdown_convert 失败: {e}")
            return MCPToolResult(
                content=[{"type": "text", "text": f"转换失败: {e}"}],
                is_error=True,
            )
        except Exception as e:
            logger.error(f"markitdown_convert 失败: {e}")
            return MCPToolResult(
                content=[{"type": "text", "text": f"转换失败: {e}"}],
                is_error=True,
            )

    async def handle_markitdown_convert_url(self, args: ConvertUrlArgs) -> MCPToolResult:
        try:
            mdt = self._get_converter()
            result = mdt.convert_url(args.url)

            saved = ""
            if args.output_path:
                out = Path(args.output_path)
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_text(result.text_content, encoding="utf-8")
                saved = f"\n已保存: {out}"

            return MCPToolResult(
                content=[{
                    "type": "text",
                    "text": f"标题: {result.title or '无'}{saved}\n\n{result.text_content}",
                }]
            )
        except Exception as e:
            logger.error(f"markitdown_convert_url 失败: {e}")
            return MCPToolResult(
                content=[{"type": "text", "text": f"转换失败: {e}"}],
                is_error=True,
            )

    async def on_load(self) -> None:
        logger.info("MarkitdownToolPlugin 已加载")

    async def on_unload(self) -> None:
        logger.info("MarkitdownToolPlugin 已卸载")
