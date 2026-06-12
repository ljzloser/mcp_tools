"""MCP Tool Hub — SQLite 异步数据库管理"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import aiosqlite

from utils.paths import paths


class Database:
    """
    SQLite 异步数据库管理（基于 aiosqlite）

    所有方法均为 async，与 FastAPI 的异步路由天然匹配。
    """

    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = Path(db_path) if db_path else paths.db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: aiosqlite.Connection | None = None

    # ── 生命周期 ──

    async def connect(self) -> None:
        """建立数据库连接"""
        self._conn = await aiosqlite.connect(str(self.db_path))
        self._conn.row_factory = aiosqlite.Row
        await self._conn.execute("PRAGMA journal_mode=WAL")
        await self._conn.execute("PRAGMA foreign_keys=ON")

    async def close(self) -> None:
        """关闭数据库连接"""
        if self._conn:
            await self._conn.close()
            self._conn = None

    async def init_tables(self) -> None:
        """创建所有数据表"""
        assert self._conn is not None, "数据库未连接，请先调用 connect()"

        await self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS server_config (
                key         TEXT PRIMARY KEY,
                value       TEXT NOT NULL,
                updated_at  TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS plugins (
                name          TEXT PRIMARY KEY,
                display_name  TEXT NOT NULL,
                version       TEXT NOT NULL,
                enabled       INTEGER DEFAULT 1,
                mcp_enabled   INTEGER DEFAULT 1,
                config_json   TEXT DEFAULT '{}',
                status        TEXT DEFAULT 'unloaded',
                created_at    TEXT DEFAULT (datetime('now')),
                updated_at    TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS plugin_logs (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                plugin_name  TEXT NOT NULL,
                level        TEXT NOT NULL,
                message      TEXT NOT NULL,
                created_at   TEXT DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_logs_plugin
                ON plugin_logs(plugin_name, created_at);

            CREATE INDEX IF NOT EXISTS idx_logs_time
                ON plugin_logs(created_at);
            """
        )
        await self._conn.commit()

        # 迁移：为旧表添加 mcp_enabled 列
        try:
            await self._conn.execute(
                "ALTER TABLE plugins ADD COLUMN mcp_enabled INTEGER DEFAULT 1"
            )
            await self._conn.commit()
        except Exception:
            pass  # 列已存在，忽略

    # ── 服务端配置 ──

    async def get_config(self, key: str, default: str = "") -> str:
        """获取配置值"""
        assert self._conn is not None
        cursor = await self._conn.execute(
            "SELECT value FROM server_config WHERE key = ?", (key,)
        )
        row = await cursor.fetchone()
        return row["value"] if row else default

    async def set_config(self, key: str, value: str) -> None:
        """设置配置值（upsert）"""
        assert self._conn is not None
        await self._conn.execute(
            """INSERT INTO server_config (key, value, updated_at)
               VALUES (?, ?, datetime('now'))
               ON CONFLICT(key) DO UPDATE SET value=excluded.value,
               updated_at=excluded.updated_at""",
            (key, value),
        )
        await self._conn.commit()

        # 迁移：为旧表添加 mcp_enabled 列
        try:
            await self._conn.execute(
                "ALTER TABLE plugins ADD COLUMN mcp_enabled INTEGER DEFAULT 1"
            )
            await self._conn.commit()
        except Exception:
            pass  # 列已存在，忽略

    async def get_all_config(self) -> dict[str, str]:
        """获取所有配置"""
        assert self._conn is not None
        cursor = await self._conn.execute("SELECT key, value FROM server_config")
        rows = await cursor.fetchall()
        return {row["key"]: row["value"] for row in rows}

    # ── 插件管理 ──

    async def register_plugin(
        self, name: str, display_name: str, version: str
    ) -> None:
        """注册插件（如已存在则忽略）"""
        assert self._conn is not None
        await self._conn.execute(
            """INSERT OR IGNORE INTO plugins (name, display_name, version)
               VALUES (?, ?, ?)""",
            (name, display_name, version),
        )
        await self._conn.commit()

        # 迁移：为旧表添加 mcp_enabled 列
        try:
            await self._conn.execute(
                "ALTER TABLE plugins ADD COLUMN mcp_enabled INTEGER DEFAULT 1"
            )
            await self._conn.commit()
        except Exception:
            pass  # 列已存在，忽略

    async def set_plugin_enabled(self, name: str, enabled: bool) -> None:
        """设置插件启用/禁用"""
        assert self._conn is not None
        await self._conn.execute(
            "UPDATE plugins SET enabled=?, updated_at=datetime('now') WHERE name=?",
            (int(enabled), name),
        )
        await self._conn.commit()

        # 迁移：为旧表添加 mcp_enabled 列
        try:
            await self._conn.execute(
                "ALTER TABLE plugins ADD COLUMN mcp_enabled INTEGER DEFAULT 1"
            )
            await self._conn.commit()
        except Exception:
            pass  # 列已存在，忽略

    async def update_plugin_status(self, name: str, status: str) -> None:
        """更新插件状态"""
        assert self._conn is not None
        await self._conn.execute(
            "UPDATE plugins SET status=?, updated_at=datetime('now') WHERE name=?",
            (status, name),
        )
        await self._conn.commit()

        # 迁移：为旧表添加 mcp_enabled 列
        try:
            await self._conn.execute(
                "ALTER TABLE plugins ADD COLUMN mcp_enabled INTEGER DEFAULT 1"
            )
            await self._conn.commit()
        except Exception:
            pass  # 列已存在，忽略

    async def get_plugin_config(self, name: str) -> dict[str, Any]:
        """获取插件配置"""
        assert self._conn is not None
        cursor = await self._conn.execute(
            "SELECT config_json FROM plugins WHERE name=?", (name,)
        )
        row = await cursor.fetchone()
        return json.loads(row["config_json"]) if row else {}

    async def set_plugin_config(self, name: str, config: dict[str, Any]) -> None:
        """设置插件配置"""
        assert self._conn is not None
        await self._conn.execute(
            """UPDATE plugins SET config_json=?, updated_at=datetime('now')
               WHERE name=?""",
            (json.dumps(config, ensure_ascii=False), name),
        )
        await self._conn.commit()

        # 迁移：为旧表添加 mcp_enabled 列
        try:
            await self._conn.execute(
                "ALTER TABLE plugins ADD COLUMN mcp_enabled INTEGER DEFAULT 1"
            )
            await self._conn.commit()
        except Exception:
            pass  # 列已存在，忽略

    async def list_plugins(self) -> list[dict[str, Any]]:
        """列出所有插件"""
        assert self._conn is not None
        cursor = await self._conn.execute("SELECT * FROM plugins")
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def get_plugin(self, name: str) -> dict[str, Any] | None:
        """获取单个插件信息"""
        assert self._conn is not None
        cursor = await self._conn.execute(
            "SELECT * FROM plugins WHERE name=?", (name,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def is_plugin_enabled(self, name: str) -> bool:
        """检查插件是否启用"""
        assert self._conn is not None
        cursor = await self._conn.execute(
            "SELECT enabled FROM plugins WHERE name=?", (name,)
        )
        row = await cursor.fetchone()
        return bool(row["enabled"]) if row else True

    async def set_plugin_mcp_enabled(self, name: str, enabled: bool) -> None:
        """设置插件 MCP 开关"""
        assert self._conn is not None
        await self._conn.execute(
            "UPDATE plugins SET mcp_enabled=?, updated_at=datetime('now') WHERE name=?",
            (int(enabled), name),
        )
        await self._conn.commit()

        # 迁移：为旧表添加 mcp_enabled 列
        try:
            await self._conn.execute(
                "ALTER TABLE plugins ADD COLUMN mcp_enabled INTEGER DEFAULT 1"
            )
            await self._conn.commit()
        except Exception:
            pass  # 列已存在，忽略

    async def is_plugin_mcp_enabled(self, name: str) -> bool:
        """检查插件 MCP 是否启用"""
        assert self._conn is not None
        cursor = await self._conn.execute(
            "SELECT mcp_enabled FROM plugins WHERE name=?", (name,)
        )
        row = await cursor.fetchone()
        return bool(row["mcp_enabled"]) if row else True

    # ── 日志 ──

    async def get_log_count(self, plugin_name: str | None = None) -> int:
        """获取日志总条数"""
        assert self._conn is not None
        if plugin_name:
            cursor = await self._conn.execute(
                "SELECT COUNT(*) FROM plugin_logs WHERE plugin_name=?", (plugin_name,)
            )
        else:
            cursor = await self._conn.execute("SELECT COUNT(*) FROM plugin_logs")
        row = await cursor.fetchone()
        return row[0] if row else 0

    async def add_log(
        self, plugin_name: str, level: str, message: str
    ) -> None:
        """添加日志记录（存储 UTC 时间，查询时转为本地时间）"""
        assert self._conn is not None
        await self._conn.execute(
            "INSERT INTO plugin_logs (plugin_name, level, message, created_at) "
            "VALUES (?, ?, ?, datetime('now'))",
            (plugin_name, level, message),
        )
        await self._conn.commit()

        # 迁移：为旧表添加 mcp_enabled 列
        try:
            await self._conn.execute(
                "ALTER TABLE plugins ADD COLUMN mcp_enabled INTEGER DEFAULT 1"
            )
            await self._conn.commit()
        except Exception:
            pass  # 列已存在，忽略

    async def get_logs(
        self,
        plugin_name: str | None = None,
        limit: int = 200,
        start_at: str | None = None,
        end_at: str | None = None,
    ) -> list[dict[str, Any]]:
        """查询日志（created_at 统一转为本地时间显示）"""
        assert self._conn is not None
        # 存储统一为 UTC，查询返回本地时间
        sql = (
            "SELECT id, plugin_name, level, message, "
            "strftime('%Y-%m-%d %H:%M:%S', created_at, 'localtime') AS created_at "
            "FROM plugin_logs"
        )
        conditions: list[str] = []
        params: list[Any] = []

        if plugin_name:
            conditions.append("plugin_name=?")
            params.append(plugin_name)

        if start_at:
            conditions.append(
                "strftime('%Y-%m-%d %H:%M:%S', created_at, 'localtime') >= ?"
            )
            params.append(start_at)

        if end_at:
            conditions.append(
                "strftime('%Y-%m-%d %H:%M:%S', created_at, 'localtime') <= ?"
            )
            params.append(end_at)

        if conditions:
            sql += " WHERE " + " AND ".join(conditions)

        sql += " ORDER BY id DESC LIMIT ?"
        params.append(limit)

        cursor = await self._conn.execute(sql, tuple(params))
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def clear_logs(self, plugin_name: str | None = None) -> int:
        """清除日志，返回删除行数"""
        assert self._conn is not None
        if plugin_name:
            cursor = await self._conn.execute(
                "DELETE FROM plugin_logs WHERE plugin_name=?", (plugin_name,)
            )
        else:
            cursor = await self._conn.execute("DELETE FROM plugin_logs")
        await self._conn.commit()

        # 迁移：为旧表添加 mcp_enabled 列
        try:
            await self._conn.execute(
                "ALTER TABLE plugins ADD COLUMN mcp_enabled INTEGER DEFAULT 1"
            )
            await self._conn.commit()
        except Exception:
            pass  # 列已存在，忽略
        return cursor.rowcount

    async def prune_logs(
        self,
        retention_days: int | None = None,
        max_records: int | None = None,
    ) -> int:
        """清理过期日志，返回删除行数

        - retention_days: 保留最近 N 天的日志，更早的删除
        - max_records: 保留最新 N 条日志，超出部分按时间倒序删除
        两个条件独立生效，取并集删除。
        """
        assert self._conn is not None
        total_deleted = 0

        if retention_days and retention_days > 0:
            cursor = await self._conn.execute(
                "DELETE FROM plugin_logs WHERE created_at < datetime('now', ?)",
                (f"-{retention_days} days",),
            )
            total_deleted += cursor.rowcount

        if max_records and max_records > 0:
            cursor = await self._conn.execute(
                "DELETE FROM plugin_logs WHERE id NOT IN ("
                "  SELECT id FROM plugin_logs ORDER BY created_at DESC LIMIT ?"
                ")",
                (max_records,),
            )
            total_deleted += cursor.rowcount

        if total_deleted > 0:
            await self._conn.commit()

        # 迁移：为旧表添加 mcp_enabled 列
        try:
            await self._conn.execute(
                "ALTER TABLE plugins ADD COLUMN mcp_enabled INTEGER DEFAULT 1"
            )
            await self._conn.commit()
        except Exception:
            pass  # 列已存在，忽略
        return total_deleted
