"""MCP Tool Hub — HTTP 请求插件后端

提供 http_get / http_post 两个 MCP 工具。
使用 ToolDef 类属性声明工具，Pydantic 模型声明参数。
配置通过 ConfigModel 声明，包含自定义 HeaderField。
"""

from __future__ import annotations

import json
from typing import Any

import httpx
from loguru import logger
from pydantic import BaseModel, Field

from api.base_plugin import BasePlugin
from api.config import BoolField, ConfigField, ConfigModel, ConfigWidgetBase, IntField, StringField
from api.tool import ToolDef
from api.types import MCPToolResult, PluginMeta


# ── 自定义配置字段：HTTP 请求头编辑器 ──


class HeaderField(ConfigField[dict[str, str]]):
    """HTTP 请求头字段

    自定义 ConfigField 子类，存储为 dict，UI 展示为多行 key: value 编辑器。
    演示插件如何继承 ConfigField 并重写 create_widget() 实现自定义控件。
    """

    widget_type = "header"

    def __init__(
        self,
        default: dict[str, str] | None = None,
        label: str = "",
        description: str = "",
        visible: bool = True,
    ) -> None:
        super().__init__(default or {}, label, description, visible)
        self._default = default or {}

    def create_widget(self, parent=None) -> ConfigWidgetBase:
        """重写 create_widget：多行 key:value 请求头编辑器"""
                from PySide6.QtCore import Signal
                from PySide6.QtWidgets import QVBoxLayout, QWidget
        from qfluentwidgets import BodyLabel, TextEdit

        field = self

        class _Widget(QWidget, ConfigWidgetBase):
            value_change = Signal(object)

            def __init__(self, parent=None):
                super().__init__(parent)
                layout = QVBoxLayout(self)
                layout.setContentsMargins(0, 0, 0, 0)
                layout.setSpacing(4)

                if field.label:
                    lbl = BodyLabel(field.label)
                    layout.addWidget(lbl)

                self._edit = TextEdit()
                self._edit.setMaximumHeight(120)
                self._edit.setPlaceholderText(
                    "每行一个请求头，格式: Key: Value\n例如:\nAccept: application/json\nAuthorization: Bearer xxx")
                if field.description:
                    self._edit.setToolTip(field.description)
                # 填充默认值
                default_text = "\n".join(
                    f"{k}: {v}" for k, v in field._default.items())
                if default_text:
                    self._edit.setPlainText(default_text)
                self._edit.textChanged.connect(
                    lambda: self.value_change.emit(self.get_value())
                )
                layout.addWidget(self._edit)

            def get_value(self) -> dict[str, str]:
                """从文本解析为 dict"""
                text = self._edit.toPlainText().strip()
                result: dict[str, str] = {}
                for line in text.splitlines():
                    line = line.strip()
                    if ":" in line:
                        key, _, val = line.partition(":")
                        key = key.strip()
                        val = val.strip()
                        if key:
                            result[key] = val
                return result

            def set_value(self, value: dict[str, str]) -> None:
                """从 dict 设置文本"""
                if isinstance(value, dict):
                    text = "\n".join(f"{k}: {v}" for k, v in value.items())
                    self._edit.setPlainText(text)

        return _Widget(parent)

    def to_storage(self, value: dict[str, str]) -> dict[str, str]:
        return value if isinstance(value, dict) else {}

    def from_storage(self, data: Any) -> dict[str, str]:
        if isinstance(data, dict):
            return {str(k): str(v) for k, v in data.items()}
        return {}


# ── 工具参数模型（Pydantic，自动生成 JSON Schema）──


class HttpGetArgs(BaseModel):
    """HTTP GET 请求参数"""

    url: str = Field(description="请求 URL")
    headers: dict[str, str] | None = Field(
        default=None, description="自定义请求头（可选）")
    timeout: float = Field(default=30, description="超时秒数（默认 30）")


class HttpPostArgs(BaseModel):
    """HTTP POST 请求参数"""

    url: str = Field(description="请求 URL")
    body: dict[str, Any] | None = Field(default=None, description="请求体（JSON）")
    headers: dict[str, str] | None = Field(
        default=None, description="自定义请求头（可选）")
    timeout: float = Field(default=30, description="超时秒数（默认 30）")


# ── 插件配置模型 ──


class HttpToolConfig(ConfigModel):
    """HTTP 工具配置

    包含自定义 HeaderField 演示：默认请求头以多行 key:value 方式编辑。
    """

    default_timeout = IntField(
        default=30, label="默认超时(秒)", description="请求超时时间", min_value=1, max_value=300)
    user_agent = StringField(
        default="MCP-Tools/1.0", label="User-Agent", description="HTTP 请求 User-Agent")
    verify_ssl = BoolField(default=True, label="验证SSL证书",
                           description="是否验证 HTTPS 证书")
    default_headers = HeaderField(
        default={"Accept": "application/json"},
        label="默认请求头",
        description="每次请求自动附加的请求头（每行 Key: Value）",
    )


# ── 插件实现 ──


class HttpToolPlugin(BasePlugin[HttpToolConfig]):
    """HTTP 请求工具插件"""

    # ── 配置声明 ──
    config_class = HttpToolConfig

    # ── 工具声明（类属性，既是元数据又是引用）──
    http_get = ToolDef("http_get", HttpGetArgs,
                       description="发送 HTTP GET 请求并返回响应内容")
    http_post = ToolDef("http_post", HttpPostArgs,
                        description="发送 HTTP POST 请求并返回响应内容")

    @property
    def meta(self) -> PluginMeta:
        return PluginMeta(
            name="http_tool",
            display_name="HTTP 请求工具",
            version="1.0.0",
            description="提供 HTTP GET/POST 请求能力",
            author="MCP Tool Hub",
        )

    def _build_client_kwargs(self, timeout: float | None = None) -> dict:
        """根据配置构建 httpx.AsyncClient 参数"""
        assert self.config is not None
        kwargs: dict[str, Any] = {}
        # 超时：参数优先，否则用配置
        kwargs["timeout"] = timeout if timeout is not None else self.config.default_timeout
        # SSL
        kwargs["verify"] = self.config.verify_ssl
        return kwargs

    def _build_headers(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        """合并默认请求头和额外请求头"""
        assert self.config is not None
        headers: dict[str, str] = {}
        # 默认请求头
        if self.config.default_headers:
            headers.update(self.config.default_headers)
        # User-Agent
        if self.config.user_agent:
            headers["User-Agent"] = self.config.user_agent
        # 调用时传入的额外头（覆盖默认）
        if extra:
            headers.update(extra)
        return headers

    # ── 工具实现（handle_{tool_name}，接收类型化参数）──

    async def handle_http_get(self, args: HttpGetArgs) -> MCPToolResult:
        """发送 HTTP GET 请求"""
        try:
            async with httpx.AsyncClient(**self._build_client_kwargs(args.timeout)) as client:
                headers = self._build_headers(args.headers)
                r = await client.get(args.url, headers=headers)
                return MCPToolResult(
                    content=[{
                        "type": "text",
                        "text": json.dumps({
                            "status_code": r.status_code,
                            "headers": dict(r.headers),
                            "body": r.text[:5000],
                        }, ensure_ascii=False, indent=2),
                    }]
                )
        except httpx.ConnectError:
            return MCPToolResult(
                content=[{"type": "text", "text": f"连接失败: {args.url}"}],
                is_error=True,
            )
        except httpx.TimeoutException:
            return MCPToolResult(
                content=[{"type": "text", "text": f"请求超时: {args.url}"}],
                is_error=True,
            )
        except Exception as e:
            return MCPToolResult(
                content=[{"type": "text", "text": f"请求异常: {e}"}],
                is_error=True,
            )

    async def handle_http_post(self, args: HttpPostArgs) -> MCPToolResult:
        """发送 HTTP POST 请求"""
        try:
            async with httpx.AsyncClient(**self._build_client_kwargs(args.timeout)) as client:
                headers = self._build_headers(args.headers)
                r = await client.post(args.url, json=args.body, headers=headers)
                return MCPToolResult(
                    content=[{
                        "type": "text",
                        "text": json.dumps({
                            "status_code": r.status_code,
                            "headers": dict(r.headers),
                            "body": r.text[:5000],
                        }, ensure_ascii=False, indent=2),
                    }]
                )
        except httpx.ConnectError:
            return MCPToolResult(
                content=[{"type": "text", "text": f"连接失败: {args.url}"}],
                is_error=True,
            )
        except httpx.TimeoutException:
            return MCPToolResult(
                content=[{"type": "text", "text": f"请求超时: {args.url}"}],
                is_error=True,
            )
        except Exception as e:
            return MCPToolResult(
                content=[{"type": "text", "text": f"请求异常: {e}"}],
                is_error=True,
            )

    async def on_load(self) -> None:
        logger.info("HttpToolPlugin 已加载")

    async def on_unload(self) -> None:
        logger.info("HttpToolPlugin 已卸载")

    async def health_check(self) -> bool:
        return True
