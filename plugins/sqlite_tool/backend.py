"""MCP Tool Hub — SQLite 数据库工具插件

提供 SQLite 数据库的查询、写入、结构查看、CSV 导入导出能力。

工具：
  - sqlite_query:       执行 SELECT 查询
  - sqlite_execute:     执行写操作（CREATE/INSERT/UPDATE/DROP 等）
  - sqlite_list_tables: 列出所有表及结构
  - sqlite_table_info:  查看单表详情（列、索引、行数、样例）
  - sqlite_import_csv:  导入 CSV 为新表
  - sqlite_export_csv:  导出查询结果为 CSV
"""

from __future__ import annotations

import csv
import io
import sqlite3
from pathlib import Path

from loguru import logger
from pydantic import BaseModel, Field

from api.base_plugin import BasePlugin
from api.tool import ToolDef
from api.types import MCPToolResult, PluginMeta


# ── 工具参数模型 ──


class QueryArgs(BaseModel):
    """SQL 查询参数"""

    db_path: str = Field(description="数据库文件路径（不存在则自动创建）")
    sql: str = Field(description="SQL 查询语句（仅支持 SELECT）")
    limit: int = Field(default=100, description="返回行数上限，0 表示不限")


class ExecuteArgs(BaseModel):
    """SQL 写操作参数"""

    db_path: str = Field(description="数据库文件路径")
    sql: str = Field(description="SQL 语句（INSERT/UPDATE/DELETE/CREATE/DROP 等）")
    params: list | None = Field(
        default=None, description="参数化查询参数，如 [1, \"test\"]")


class ListTablesArgs(BaseModel):
    """列出表参数"""

    db_path: str = Field(description="数据库文件路径")


class TableInfoArgs(BaseModel):
    """表详情参数"""

    db_path: str = Field(description="数据库文件路径")
    table: str = Field(description="表名")
    sample_rows: int = Field(default=5, description="样例数据行数，0 则不显示")


class ImportCsvArgs(BaseModel):
    """CSV 导入参数"""

    db_path: str = Field(description="数据库文件路径")
    csv_path: str = Field(description="CSV 文件路径")
    table: str = Field(default="", description="目标表名（留空则用文件名）")
    delimiter: str = Field(default=",", description="分隔符（制表符用 \\t）")
    has_header: bool = Field(default=True, description="CSV 是否有表头行")


class ExportCsvArgs(BaseModel):
    """CSV 导出参数"""

    db_path: str = Field(description="数据库文件路径")
    sql: str = Field(description="SQL 查询语句，结果将导出为 CSV")
    csv_path: str = Field(description="输出 CSV 文件路径")
    delimiter: str = Field(default=",", description="分隔符（制表符用 \\t）")


# ── 辅助函数 ──


def _format_as_table(columns: list[str], rows: list[tuple]) -> str:
    """将查询结果格式化为 Markdown 表格"""
    if not columns:
        return "(无结果)"

    # 计算每列最大宽度
    col_widths = [len(c) for c in columns]
    for row in rows:
        for i, val in enumerate(row):
            w = len(str(val))
            if i < len(col_widths):
                col_widths[i] = max(col_widths[i], w)

    # 构建表格
    header = "| " + \
        " | ".join(c.ljust(col_widths[i])
                   for i, c in enumerate(columns)) + " |"
    sep = "| " + " | ".join("-" * col_widths[i]
                            for i in range(len(columns))) + " |"
    lines = [header, sep]
    for row in rows:
        cells = []
        for i, val in enumerate(row):
            s = str(val) if val is not None else "NULL"
            cells.append(s.ljust(col_widths[i]) if i < len(col_widths) else s)
        lines.append("| " + " | ".join(cells) + " |")

    return "\n".join(lines)


def _infer_sqlite_type(values: list[str]) -> str:
    """根据列值推断 SQLite 类型"""
    if not values:
        return "TEXT"

    non_empty = [v for v in values if v.strip()]
    if not non_empty:
        return "TEXT"

    # 尝试整数
    all_int = True
    for v in non_empty:
        try:
            int(v)
        except ValueError:
            all_int = False
            break
    if all_int:
        return "INTEGER"

    # 尝试浮点
    all_float = True
    for v in non_empty:
        try:
            float(v)
        except ValueError:
            all_float = False
            break
    if all_float:
        return "REAL"

    return "TEXT"


# ── 插件实现 ──


class SqliteToolPlugin(BasePlugin):
    """SQLite 数据库工具插件"""

    sqlite_query = ToolDef("sqlite_query", QueryArgs,
                           description="执行 SQL SELECT 查询，结果以 Markdown 表格返回")
    sqlite_execute = ToolDef("sqlite_execute", ExecuteArgs,
                             description="执行 SQL 写操作（CREATE/INSERT/UPDATE/DELETE/DROP）")
    sqlite_list_tables = ToolDef("sqlite_list_tables", ListTablesArgs,
                                 description="列出数据库中所有表及其结构")
    sqlite_table_info = ToolDef("sqlite_table_info", TableInfoArgs,
                                description="查看单表详情：列定义、索引、行数、样例数据")
    sqlite_import_csv = ToolDef("sqlite_import_csv", ImportCsvArgs,
                                description="将 CSV 文件导入为数据库新表（自动推断列类型）")
    sqlite_export_csv = ToolDef("sqlite_export_csv", ExportCsvArgs,
                                description="将 SQL 查询结果导出为 CSV 文件")

    @property
    def meta(self) -> PluginMeta:
        return PluginMeta(
            name="sqlite_tool",
            display_name="SQLite工具",
            version="1.0.0",
            description="SQLite 数据库查询 / 写入 / 结构查看 / CSV 导入导出",
            author="MCP Tool Hub",
            icon="🗄️",
        )

    # ── sqlite_query ──

    async def handle_sqlite_query(self, args: QueryArgs) -> MCPToolResult:
        try:
            db = Path(args.db_path)
            db.parent.mkdir(parents=True, exist_ok=True)

            conn = sqlite3.connect(str(db))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            sql = args.sql.strip()
            if not sql.upper().startswith("SELECT"):
                conn.close()
                return MCPToolResult(
                    content=[
                        {"type": "text", "text": "sqlite_query 仅支持 SELECT 语句，写操作请用 sqlite_execute"}],
                    is_error=True,
                )

            if args.limit > 0:
                # 检查是否已有 LIMIT
                upper = sql.upper().rstrip(";").rstrip()
                if "LIMIT" not in upper.split("FROM")[-1].split("WHERE")[-1].split("GROUP")[-1].split("ORDER")[-1]:
                    sql = sql.rstrip(";") + f" LIMIT {args.limit}"

            cursor.execute(sql)
            rows = cursor.fetchall()
            columns = [desc[0]
                       for desc in cursor.description] if cursor.description else []
            conn.close()

            result = _format_as_table(columns, [tuple(r) for r in rows])
            count = f"\n\n共 {len(rows)} 行"
            if args.limit > 0 and len(rows) == args.limit:
                count += f"（已达 limit={args.limit} 上限，可能还有更多）"

            return MCPToolResult(content=[{"type": "text", "text": result + count}])
        except Exception as e:
            return MCPToolResult(
                content=[{"type": "text", "text": f"查询失败: {e}"}],
                is_error=True,
            )

    # ── sqlite_execute ──

    async def handle_sqlite_execute(self, args: ExecuteArgs) -> MCPToolResult:
        try:
            db = Path(args.db_path)
            db.parent.mkdir(parents=True, exist_ok=True)

            conn = sqlite3.connect(str(db))
            cursor = conn.cursor()

            params = args.params or ()
            cursor.execute(args.sql, params)
            affected = cursor.rowcount
            conn.commit()
            lastrowid = cursor.lastrowid
            conn.close()

            parts = [f"影响行数: {affected}"]
            if lastrowid:
                parts.append(f"最后插入 ID: {lastrowid}")
            return MCPToolResult(content=[{"type": "text", "text": "\n".join(parts)}])
        except Exception as e:
            return MCPToolResult(
                content=[{"type": "text", "text": f"执行失败: {e}"}],
                is_error=True,
            )

    # ── sqlite_list_tables ──

    async def handle_sqlite_list_tables(self, args: ListTablesArgs) -> MCPToolResult:
        try:
            db = Path(args.db_path)
            if not db.exists():
                return MCPToolResult(
                    content=[
                        {"type": "text", "text": f"数据库不存在: {args.db_path}"}],
                    is_error=True,
                )

            conn = sqlite3.connect(str(db))
            cursor = conn.cursor()

            # 获取所有用户表
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")
            tables = [row[0] for row in cursor.fetchall()]

            if not tables:
                conn.close()
                return MCPToolResult(content=[{"type": "text", "text": "数据库中没有用户表"}])

            # 获取每个表的结构
            lines = []
            for table in tables:
                cursor.execute(f'PRAGMA table_info("{table}")')
                cols = cursor.fetchall()
                col_lines = []
                for c in cols:
                    # cid, name, type, notnull, dflt_value, pk
                    pk = " 🔑" if c[5] else ""
                    nn = " NOT NULL" if c[3] else ""
                    col_lines.append(f"  {c[1]} {c[2] or 'ANY'}{nn}{pk}")

                cursor.execute(f'SELECT COUNT(*) FROM "{table}"')
                count = cursor.fetchone()[0]

                lines.append(f"## {table} ({count} 行)")
                lines.append("\n".join(col_lines))
                lines.append("")

            conn.close()
            return MCPToolResult(content=[{"type": "text", "text": "\n".join(lines)}])
        except Exception as e:
            return MCPToolResult(
                content=[{"type": "text", "text": f"操作失败: {e}"}],
                is_error=True,
            )

    # ── sqlite_table_info ──

    async def handle_sqlite_table_info(self, args: TableInfoArgs) -> MCPToolResult:
        try:
            db = Path(args.db_path)
            if not db.exists():
                return MCPToolResult(
                    content=[
                        {"type": "text", "text": f"数据库不存在: {args.db_path}"}],
                    is_error=True,
                )

            conn = sqlite3.connect(str(db))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # 列定义
            cursor.execute(f'PRAGMA table_info("{args.table}")')
            cols = cursor.fetchall()
            if not cols:
                conn.close()
                return MCPToolResult(
                    content=[{"type": "text", "text": f"表不存在: {args.table}"}],
                    is_error=True,
                )

            lines = [f"## {args.table} 列定义"]
            col_table_cols = ["列名", "类型", "非空", "默认值", "主键"]
            col_table_rows = []
            for c in cols:
                col_table_rows.append((c[1], c[2] or "ANY", "是" if c[3] else "否", str(
                    c[4]) if c[4] is not None else "-", "是" if c[5] else "否"))
            lines.append(_format_as_table(col_table_cols, col_table_rows))

            # 索引
            cursor.execute(f'PRAGMA index_list("{args.table}")')
            indexes = cursor.fetchall()
            if indexes:
                lines.append(f"\n## 索引")
                for idx in indexes:
                    cursor.execute(f'PRAGMA index_info("{idx[1]}")')
                    idx_cols = [ic[2] for ic in cursor.fetchall()]
                    unique = "UNIQUE" if idx[2] else ""
                    lines.append(
                        f"  {idx[1]} ({', '.join(idx_cols)}) {unique}")

            # 行数
            cursor.execute(f'SELECT COUNT(*) FROM "{args.table}"')
            count = cursor.fetchone()[0]
            lines.append(f"\n总行数: {count}")

            # 样例数据
            if args.sample_rows > 0 and count > 0:
                cursor.execute(
                    f'SELECT * FROM "{args.table}" LIMIT {args.sample_rows}')
                rows = cursor.fetchall()
                columns = [desc[0]
                           for desc in cursor.description] if cursor.description else []
                lines.append(
                    f"\n## 样例数据 (前 {min(args.sample_rows, len(rows))} 行)")
                lines.append(_format_as_table(
                    columns, [tuple(r) for r in rows]))

            conn.close()
            return MCPToolResult(content=[{"type": "text", "text": "\n".join(lines)}])
        except Exception as e:
            return MCPToolResult(
                content=[{"type": "text", "text": f"操作失败: {e}"}],
                is_error=True,
            )

    # ── sqlite_import_csv ──

    async def handle_sqlite_import_csv(self, args: ImportCsvArgs) -> MCPToolResult:
        try:
            csv_path = Path(args.csv_path)
            if not csv_path.exists():
                return MCPToolResult(
                    content=[
                        {"type": "text", "text": f"CSV 文件不存在: {args.csv_path}"}],
                    is_error=True,
                )

            table_name = args.table or csv_path.stem
            delimiter = args.delimiter.replace("\\t", "\t")

            # 读取 CSV
            with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
                reader = csv.reader(f, delimiter=delimiter)
                all_rows = list(reader)

            if not all_rows:
                return MCPToolResult(
                    content=[{"type": "text", "text": "CSV 文件为空"}],
                    is_error=True,
                )

            if args.has_header:
                headers = all_rows[0]
                data_rows = all_rows[1:]
            else:
                headers = [f"col_{i}" for i in range(len(all_rows[0]))]
                data_rows = all_rows

            # 推断列类型
            col_types = []
            for i in range(len(headers)):
                col_values = [row[i] if i < len(
                    row) else "" for row in data_rows]
                col_types.append(_infer_sqlite_type(col_values))

            # 建表并插入
            db = Path(args.db_path)
            db.parent.mkdir(parents=True, exist_ok=True)

            conn = sqlite3.connect(str(db))
            cursor = conn.cursor()

            # 建表
            col_defs = ", ".join(f'"{h}" {t}' for h,
                                 t in zip(headers, col_types))
            cursor.execute(f'DROP TABLE IF EXISTS "{table_name}"')
            cursor.execute(f'CREATE TABLE "{table_name}" ({col_defs})')

            # 批量插入
            placeholders = ", ".join("?" for _ in headers)
            inserted = 0
            for row in data_rows:
                # 补齐或截断列数
                padded = list(row) + [None] * (len(headers) - len(row))
                padded = padded[: len(headers)]
                cursor.execute(
                    f'INSERT INTO "{table_name}" VALUES ({placeholders})', padded)
                inserted += 1

            conn.commit()
            conn.close()

            return MCPToolResult(
                content=[{"type": "text", "text": f"导入完成: {csv_path.name} → {table_name}\n列: {', '.join(f'{h}({t})' for h, t in zip(
                    headers, col_types))}\n导入行数: {inserted}"}]
            )
        except Exception as e:
            return MCPToolResult(
                content=[{"type": "text", "text": f"导入失败: {e}"}],
                is_error=True,
            )

    # ── sqlite_export_csv ──

    async def handle_sqlite_export_csv(self, args: ExportCsvArgs) -> MCPToolResult:
        try:
            db = Path(args.db_path)
            if not db.exists():
                return MCPToolResult(
                    content=[
                        {"type": "text", "text": f"数据库不存在: {args.db_path}"}],
                    is_error=True,
                )

            delimiter = args.delimiter.replace("\\t", "\t")
            out = Path(args.csv_path)
            out.parent.mkdir(parents=True, exist_ok=True)

            conn = sqlite3.connect(str(db))
            cursor = conn.cursor()
            cursor.execute(args.sql)

            columns = [desc[0]
                       for desc in cursor.description] if cursor.description else []
            rows = cursor.fetchall()
            conn.close()

            with open(out, "w", encoding="utf-8-sig", newline="") as f:
                writer = csv.writer(f, delimiter=delimiter)
                writer.writerow(columns)
                writer.writerows(rows)

            return MCPToolResult(
                content=[
                    {"type": "text", "text": f"导出完成: {len(rows)} 行 → {out}"}]
            )
        except Exception as e:
            return MCPToolResult(
                content=[{"type": "text", "text": f"导出失败: {e}"}],
                is_error=True,
            )

    async def on_load(self) -> None:
        logger.info("SqliteToolPlugin 已加载")

    async def on_unload(self) -> None:
        logger.info("SqliteToolPlugin 已卸载")
