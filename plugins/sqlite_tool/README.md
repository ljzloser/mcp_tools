# SQLite 数据库工具插件

提供 SQLite 数据库的查询、写入、结构查看、CSV 导入导出能力。无需 UI，纯后端工具。

## 工具列表

| 工具名 | 说明 |
|--------|------|
| `sqlite_query` | 执行 SELECT 查询，结果以 Markdown 表格返回 |
| `sqlite_execute` | 执行写操作（CREATE/INSERT/UPDATE/DELETE/DROP） |
| `sqlite_list_tables` | 列出所有表名及结构 |
| `sqlite_table_info` | 查看单表详情（列、索引、行数、样例数据） |
| `sqlite_import_csv` | 导入 CSV 为新表（自动推断列类型） |
| `sqlite_export_csv` | 导出查询结果为 CSV |

## 无额外依赖

仅使用 Python 标准库 `sqlite3` 和 `csv`。

## 示例

### 查询
```json
{"db_path": "data/test.db", "sql": "SELECT * FROM users WHERE age > 18", "limit": 50}
```

### 列出所有表
```json
{"db_path": "data/test.db"}
```

### 导入 CSV
```json
{"db_path": "data/test.db", "csv_path": "data/sales.csv", "table": "sales"}
```
