"""MCP Tool Hub — JSON 处理工具插件

提供 JSON 格式化、校验、查询（JMESPath）、转换等能力。

工具：
  - json_format:     JSON 美化 / 压缩
  - json_validate:   JSON 校验
  - json_query:      JMESPath 查询
  - json_to_csv:     JSON → CSV
  - json_flatten:    JSON 扁平化
  - json_diff:       JSON 对比
"""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Mapping, Sequence

from loguru import logger
from pydantic import BaseModel, Field

from api.base_plugin import BasePlugin
from api.tool import ToolDef
from api.types import MCPToolResult, PluginMeta


# ── 工具参数模型 ──


class FormatArgs(BaseModel):
    """JSON 格式化参数"""

    json_str: str = Field(description="JSON 字符串")
    indent: int = Field(default=2, description="缩进空格数（0 则压缩为单行）")
    sort_keys: bool = Field(default=False, description="是否按键排序")
    ensure_ascii: bool = Field(default=False, description="是否转义非 ASCII 字符")


class ValidateArgs(BaseModel):
    """JSON 校验参数"""

    json_str: str = Field(description="要校验的 JSON 字符串")


class QueryArgs(BaseModel):
    """JMESPath 查询参数"""

    json_str: str = Field(description="JSON 字符串")
    expression: str = Field(
        description="JMESPath 表达式，如 people[?age > `20`].name")


class ToCsvArgs(BaseModel):
    """JSON 转 CSV 参数"""

    json_str: str = Field(
        description="JSON 数组字符串，如 [{\"name\":\"a\",\"age\":1},...]")
    delimiter: str = Field(default=",", description="分隔符（逗号用 , 制表符用 \\t）")
    include_header: bool = Field(default=True, description="是否包含表头")


class FlattenArgs(BaseModel):
    """JSON 扁平化参数"""

    json_str: str = Field(description="JSON 字符串")
    separator: str = Field(default=".", description="嵌套键的分隔符")


class DiffArgs(BaseModel):
    """JSON 对比参数"""

    json_str_a: str = Field(description="第一个 JSON 字符串")
    json_str_b: str = Field(description="第二个 JSON 字符串")


# ── 插件实现 ──


class JsonToolPlugin(BasePlugin):
    """JSON 处理工具插件"""

    json_format = ToolDef("json_format", FormatArgs,
                          description="JSON 格式化（美化/压缩/排序）")
    json_validate = ToolDef("json_validate", ValidateArgs,
                            description="校验 JSON 是否合法，返回错误位置和原因")
    json_query = ToolDef("json_query", QueryArgs,
                         description="使用 JMESPath 表达式查询 JSON 数据")
    json_to_csv = ToolDef("json_to_csv", ToCsvArgs,
                          description="将 JSON 数组转换为 CSV 表格")
    json_flatten = ToolDef("json_flatten", FlattenArgs,
                           description="将嵌套 JSON 扁平化为单层键值对")
    json_diff = ToolDef("json_diff", DiffArgs, description="对比两个 JSON 的差异")

    @property
    def meta(self) -> PluginMeta:
        return PluginMeta(
            name="json_tool",
            display_name="JSON工具",
            version="1.0.0",
            description="JSON 格式化 / 校验 / 查询(JMESPath) / 转CSV / 扁平化 / 对比",
            author="MCP Tool Hub",
            icon="📋",
        )

    # ── json_format ──

    async def handle_json_format(self, args: FormatArgs) -> MCPToolResult:
        try:
            data = json.loads(args.json_str)
            result = json.dumps(
                data,
                indent=args.indent if args.indent > 0 else None,
                sort_keys=args.sort_keys,
                ensure_ascii=args.ensure_ascii,
                separators=(",", ":") if args.indent == 0 else None,
            )
            return MCPToolResult(content=[{"type": "text", "text": result}])
        except json.JSONDecodeError as e:
            return MCPToolResult(
                content=[
                    {"type": "text", "text": f"JSON 解析失败: {e.msg} (行 {e.lineno}, 列 {e.colno})"}],
                is_error=True,
            )

    # ── json_validate ──

    async def handle_json_validate(self, args: ValidateArgs) -> MCPToolResult:
        try:
            json.loads(args.json_str)
            return MCPToolResult(content=[{"type": "text", "text": "✓ JSON 格式合法"}])
        except json.JSONDecodeError as e:
            # 尝试定位错误位置
            lines = args.json_str.splitlines()
            pointer = ""
            if 0 < e.lineno <= len(lines):
                line = lines[e.lineno - 1]
                pointer = f"\n  {line}\n  {' ' * max(0, e.colno - 1)}^"
            msg = f"✗ JSON 格式错误: {e.msg}\n  位置: 行 {e.lineno}, 列 {e.colno}{pointer}"
            return MCPToolResult(content=[{"type": "text", "text": msg}], is_error=True)

    # ── json_query ──

    async def handle_json_query(self, args: QueryArgs) -> MCPToolResult:
        try:
            data = json.loads(args.json_str)
        except json.JSONDecodeError as e:
            return MCPToolResult(
                content=[{"type": "text", "text": f"JSON 解析失败: {e.msg}"}],
                is_error=True,
            )
        try:
            import jmespath
            result = jmespath.search(args.expression, data)
            text = json.dumps(result, ensure_ascii=False,
                              indent=2) if result is not None else "null"
            return MCPToolResult(content=[{"type": "text", "text": text}])
        except Exception as e:
            return MCPToolResult(
                content=[{"type": "text", "text": f"JMESPath 查询失败: {e}"}],
                is_error=True,
            )

    # ── json_to_csv ──

    async def handle_json_to_csv(self, args: ToCsvArgs) -> MCPToolResult:
        try:
            data = json.loads(args.json_str)
        except json.JSONDecodeError as e:
            return MCPToolResult(
                content=[{"type": "text", "text": f"JSON 解析失败: {e.msg}"}],
                is_error=True,
            )

        if not isinstance(data, list):
            return MCPToolResult(
                content=[
                    {"type": "text", "text": "JSON 必须是数组格式，如 [{...}, {...}]"}],
                is_error=True,
            )
        if not data:
            return MCPToolResult(content=[{"type": "text", "text": ""}])

        # 收集所有键（保持顺序）
        keys: list[str] = []
        seen: set[str] = set()
        for item in data:
            if isinstance(item, Mapping):
                for k in item:
                    if k not in seen:
                        keys.append(k)
                        seen.add(k)

        delimiter = args.delimiter.replace("\\t", "\t")
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=keys,
                                delimiter=delimiter, extrasaction="ignore")

        if args.include_header:
            writer.writeheader()
        for item in data:
            if isinstance(item, Mapping):
                # 将非字符串值转为字符串
                row = {k: (str(v) if not isinstance(v, str) else v)
                       for k, v in item.items()}
                writer.writerow(row)

        return MCPToolResult(content=[{"type": "text", "text": output.getvalue()}])

    # ── json_flatten ──

    async def handle_json_flatten(self, args: FlattenArgs) -> MCPToolResult:
        try:
            data = json.loads(args.json_str)
        except json.JSONDecodeError as e:
            return MCPToolResult(
                content=[{"type": "text", "text": f"JSON 解析失败: {e.msg}"}],
                is_error=True,
            )

        def _flatten(obj, parent_key: str = "", sep: str = ".") -> dict:
            items: dict = {}
            if isinstance(obj, Mapping):
                for k, v in obj.items():
                    new_key = f"{parent_key}{sep}{k}" if parent_key else k
                    items.update(_flatten(v, new_key, sep))
            elif isinstance(obj, list):
                for i, v in enumerate(obj):
                    new_key = f"{parent_key}{sep}{i}" if parent_key else str(i)
                    items.update(_flatten(v, new_key, sep))
            else:
                items[parent_key] = obj
            return items

        flat = _flatten(data, sep=args.separator)
        return MCPToolResult(
            content=[{"type": "text", "text": json.dumps(
                flat, ensure_ascii=False, indent=2)}]
        )

    # ── json_diff ──

    async def handle_json_diff(self, args: DiffArgs) -> MCPToolResult:
        try:
            a = json.loads(args.json_str_a)
        except json.JSONDecodeError as e:
            return MCPToolResult(
                content=[{"type": "text", "text": f"第一个 JSON 解析失败: {e.msg}"}],
                is_error=True,
            )
        try:
            b = json.loads(args.json_str_b)
        except json.JSONDecodeError as e:
            return MCPToolResult(
                content=[{"type": "text", "text": f"第二个 JSON 解析失败: {e.msg}"}],
                is_error=True,
            )

        diffs = _compute_diff(a, b, prefix="")
        if not diffs:
            return MCPToolResult(content=[{"type": "text", "text": "两个 JSON 完全相同"}])

        lines = []
        for d in diffs:
            path = d["path"]
            if d["type"] == "added":
                lines.append(
                    f"+ {path}: {json.dumps(d['value'], ensure_ascii=False)}")
            elif d["type"] == "removed":
                lines.append(
                    f"- {path}: {json.dumps(d['value'], ensure_ascii=False)}")
            elif d["type"] == "changed":
                lines.append(
                    f"  {path}: {json.dumps(d['old'], ensure_ascii=False)} → {json.dumps(d['new'], ensure_ascii=False)}")

        return MCPToolResult(content=[{"type": "text", "text": "\n".join(lines)}])

    async def on_load(self) -> None:
        logger.info("JsonToolPlugin 已加载")

    async def on_unload(self) -> None:
        logger.info("JsonToolPlugin 已卸载")


# ── 辅助函数 ──


def _compute_diff(a, b, prefix: str = "") -> list[dict]:
    """递归对比两个 JSON 值的差异"""
    diffs: list[dict] = []

    if type(a) != type(b):
        diffs.append(
            {"type": "changed", "path": prefix or "(root)", "old": a, "new": b})
        return diffs

    if isinstance(a, Mapping):
        all_keys = set(a.keys()) | set(b.keys())
        for k in sorted(all_keys):
            path = f"{prefix}.{k}" if prefix else k
            if k not in a:
                diffs.append({"type": "added", "path": path, "value": b[k]})
            elif k not in b:
                diffs.append({"type": "removed", "path": path, "value": a[k]})
            else:
                diffs.extend(_compute_diff(a[k], b[k], path))
    elif isinstance(a, list):
        max_len = max(len(a), len(b))
        for i in range(max_len):
            path = f"{prefix}[{i}]"
            if i >= len(a):
                diffs.append({"type": "added", "path": path, "value": b[i]})
            elif i >= len(b):
                diffs.append({"type": "removed", "path": path, "value": a[i]})
            else:
                diffs.extend(_compute_diff(a[i], b[i], path))
    else:
        if a != b:
            diffs.append(
                {"type": "changed", "path": prefix or "(root)", "old": a, "new": b})

    return diffs
