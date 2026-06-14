"""MCP Tool Hub — 工具定义基类

插件通过 ToolDef 类属性声明提供的工具及其参数类型，
替代手写 JSON Schema 和字符串分派。
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class EmptyArgs(BaseModel):
    """空参数基类，用于无参数的工具"""


class ToolDef:
    """
    工具定义 — 插件用它声明提供的工具和参数类型

    用法::

        class GetArgs(BaseModel):
            url: str
            timeout: float = 30

        class MyPlugin(BasePlugin):
            http_get = ToolDef("http_get", GetArgs, description="发送 GET 请求")

            async def handle_http_get(self, args: GetArgs) -> MCPToolResult:
                ...

    前端 Widget 也可引用同一 ToolDef::

        self.invoke(MyPlugin.http_get, GetArgs(url="..."))
    """

    def __init__(
        self,
        name: str,
        input_type: type[BaseModel],
        description: str = "",
        dangerous: bool = False,
    ) -> None:
        self.name = name
        self.input_type = input_type
        self.description = description
        self.dangerous = dangerous

    @property
    def input_schema(self) -> dict[str, Any]:
        """从 Pydantic 模型自动生成 JSON Schema"""
        return self.input_type.model_json_schema()

    def validate(self, arguments: dict[str, Any]) -> BaseModel:
        """将原始 dict 反序列化为类型化的参数对象

        过滤掉 None 值，让 Pydantic 的 Field(default=...) 生效。
        因为 FastMCP 对未传的可选参数填入 None，
        而 Pydantic 的 default 只在字段缺失时生效。
        """
        filtered = {k: v for k, v in arguments.items() if v is not None}
        return self.input_type.model_validate(filtered)

    def __repr__(self) -> str:
        return f"ToolDef({self.name!r}, {self.input_type.__name__})"
