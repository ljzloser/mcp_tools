# MCP Tool Hub — 技术开发文档

> 版本: 0.1.0 | 日期: 2026-06-10 | 状态: 设计阶段

---

## 1. 项目概述

### 1.1 目标

构建一个集成式 MCP 工具平台（MCP Tool Hub），将多个 MCP 工具封装为一个统一服务。服务端本身是一个 MCP Server，所有功能以**插件**形式内置。服务端作为**纯转发层**，负责向外部暴露 `tools/list` 和 `tools/call`，实际业务逻辑由内部插件实现。

每个插件由两个核心组件构成：

| 组件 | 基类 | 职责 |
|------|------|------|
| 后端插件 | `BasePlugin` | 定义工具列表、执行工具调用 |
| 管理界面 | `BasePluginWidget` | 提供 PySide6 可视化配置面板 |

### 1.2 核心原则

- **面向接口编程**：所有对外接口通过抽象基类定义，不允许硬编码函数或字典结构
- **插件即工具**：每个插件自描述（元数据 + 工具定义），服务端自动聚合暴露
- **零耦合**：UI 与后端通过统一 API 通信，互不直接依赖
- **可迁移**：整个服务打包为一个进程，一键部署

---

## 2. 技术栈

| 层级 | 技术 | 版本要求 | 用途 |
|------|------|----------|------|
| 语言 | Python | >= 3.12 | — |
| MCP 框架 | `mcp` (官方 SDK) | >= 1.0.0 | MCP Server / 协议通信 |
| 桌面 UI 框架 | PySide6 | >= 6.6.0 | 管理界面 |
| UI 组件库 | **PySide6-Fluent-Widgets** | >= 1.6.0 | Fluent Design 现代风格组件 |
| Web 框架 | `fastapi` + `uvicorn` | >= 0.110.0 | HTTP 管理 API（异步） |
| 类型校验 | Pydantic | >= 2.0.0 | 请求/响应模型、配置校验 |
| 日志 | loguru | >= 0.7.0 | 日志记录 |
| 异步数据库 | `aiosqlite` | >= 0.20.0 | SQLite 异步访问 |
| HTTP 客户端 | `httpx` | >= 0.27.0 | UI 侧异步 HTTP 请求 |
| 图标 | QFluentWidgets 内置图标 | — | Fluent 风格系统图标 |
| 包管理 | uv | — | 依赖与虚拟环境 |

> **全异步栈**：FastAPI（ASGI）、aiosqlite、httpx.AsyncClient、MCP SDK 均为 async-first

### 2.1 通信分层

```
┌──────────────────────────────────────────────────────┐
│                   外部世界                             │
│  ┌──────────────┐        ┌───────────────────────┐   │
│  │ MCP Client   │        │  PySide6 Management UI │   │
│  │ (Claude 等)  │        │  (本项目的桌面界面)      │   │
│  └──────┬───────┘        └───────────┬───────────┘   │
│         │ stdio                      │ HTTP (REST)    │
│         │ (MCP 协议)                 │ (管理 API)     │
└─────────┼────────────────────────────┼───────────────┘
          │                            │
┌─────────┴────────────────────────────┴───────────────┐
│                  MCP Tool Hub Server                  │
│  ┌────────────────┐   ┌──────────────────────────┐   │
│  │  MCP Server    │   │  Management API           │   │
│  │  (FastMCP)     │   │  (Starlette HTTP Server)  │   │
│  │                │   │  · GET  /status           │   │
│  │ tools/list ────┤   │  · GET  /plugins          │   │
│  │ tools/call ────┤   │  · POST /plugins/{id}/... │   │
│  └───────┬────────┘   │  · POST /server/start     │   │
│          │            │  · POST /server/stop      │   │
│          │            └──────────────┬─────────────┘   │
│          │         共享核心          │                  │
│  ┌───────┴──────────────────────────┴─────────────┐   │
│  │        PluginManager / ToolRegistry / DB        │   │
│  └────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────┘
```

- **MCP 层**（图左）：走 stdio 传输，与外部 AI 客户端通信，传递 MCP 标准协议
- **管理 API 层**（图右）：走 HTTP，提供 `/plugins`、`/server` 等 REST 端点，供 PySide6 UI 调用
- **核心层**（底部）：PluginManager、ToolRegistry、SQLite 数据库为两层共享

---

## 3. 架构总览

### 3.1 整体分层

```
┌──────────────────────────────────────────────────────────────┐
│  外部 MCP Client (Claude Desktop / Cursor)                    │
└─────────────────────────┬────────────────────────────────────┘
                          │ stdio (MCP 协议)
┌─────────────────────────┴────────────────────────────────────┐
│                  MCP Tool Hub Server                          │
│                                                              │
│  ┌─────────────────────────┐  ┌──────────────────────────┐  │
│  │   MCP Server (FastMCP)  │  │  Management HTTP API     │  │
│  │   tools/list → 聚合     │  │  (FastAPI + uvicorn)     │  │
│  │   tools/call → 路由     │  │  Port: 9020              │  │
│  └───────────┬─────────────┘  └────────────┬─────────────┘  │
│              │         共享核心层            │                │
│  ┌───────────┴──────────────────────────────┴─────────────┐  │
│  │  PluginManager ←→ ToolRegistry ←→ SQLite DB            │  │
│  └───────────────────────────┬────────────────────────────┘  │
│                              │                                │
│  ┌───────────────────────────┴────────────────────────────┐  │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐              │  │
│  │  │ Plugin A │  │ Plugin B │  │ Plugin C │              │  │
│  │  │ Backend  │  │ Backend  │  │ Backend  │              │  │
│  │  └──────────┘  └──────────┘  └──────────┘              │  │
│  └────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
                          │ HTTP (管理 API)
                          ▼
┌──────────────────────────────────────────────────────────────┐
│           PySide6 Management UI                               │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  MainWindow                                            │  │
│  │  ┌───────────────┐ ┌────────────────────────────────┐  │  │
│  │  │ PluginList    │ │ PluginDetail (StackedWidget)   │  │  │
│  │  │               │ │  ← MyToolWidget.create_widget()│  │  │
│  │  └───────────────┘ └────────────────────────────────┘  │  │
│  ├────────────────────────────────────────────────────────┤  │
│  │  LogPanel                                              │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
│  所有 HTTP 请求通过 AsyncHttpClient(QObject) 发出             │
│  响应通过 Qt Signal 回到主线程更新 UI                          │
└──────────────────────────────────────────────────────────────┘
```

### 3.2 两条数据流

**流 1 — MCP 工具调用（stdio）**

```
外部 MCP Client → stdio → FastMCP handler → ToolRouter
    → PluginManager → 目标 Plugin.call_tool()
    → 返回 MCPToolResult → stdio → 外部 Client
```

**流 2 — UI 管理操作（HTTP）**

```
PySide6 UI 点击 "启动服务"
    → AsyncHttpClient.post("/server/start")
    → httpx 异步请求 → Starlette 路由处理
    → 返回 JSON → httpx 响应回调
    → QObject Signal 发射 → 主线程 UI 更新
```

---

## 4. 目录结构

```
mcp_tools/
│
├── api/                            # 【抽象接口层】
│   ├── __init__.py                 #   导出所有公共类型
│   ├── base_plugin.py              #   BasePlugin 抽象基类
│   ├── base_widget.py              #   BasePluginWidget 抽象基类
│   └── types.py                    #   通用数据类型定义
│
├── server/                         # 【服务端核心】
│   ├── __init__.py
│   ├── app.py                      #   MCPServerApp — FastMCP 封装
│   ├── plugin_manager.py           #   PluginManager — 插件生命周期
│   ├── registry.py                 #   ToolRegistry — 工具名→插件映射
│   ├── router.py                   #   ToolRouter — 聚合与路由
│   ├── management_api.py           #   Starlette HTTP 管理 API
│   └── database.py                 #   SQLite 数据库管理（建表/CRUD）
│
├── plugins/                        # 【插件仓库】
│   ├── __init__.py
│   ├── _template/                  #   【插件模板】
│   │   ├── __init__.py
│   │   ├── backend.py              #    继承 BasePlugin
│   │   └── widget.py               #    继承 BasePluginWidget
│   └── ...                         #   后续新增的插件
│
├── ui/                             # 【管理界面】
│   ├── __init__.py
│   ├── app.py                      #   QApplication 启动入口
│   ├── main_window.py             #   主窗口
│   ├── plugin_list.py             #   左侧插件列表
│   ├── plugin_detail.py           #   右侧详情容器 (QStackedWidget)
│   ├── log_panel.py               #   底部日志面板
│   ├── http_client.py             #   AsyncHttpClient(QObject) — httpx + 信号槽
│   └── theme.py                   #   样式主题
│
├── utils/                          # 【工具模块】
│   ├── __init__.py
│   └── logger.py                   #   loguru 日志配置
│
├── docs/                           # 【文档】
│   └── DESIGN.md                   #   本文件
│
├── data/                           # 【运行时数据（自动创建）】
│   └── mcp_tools.db                #   SQLite 数据库文件
│
├── server.py                       # 服务端启动脚本（MCP + 管理 API）
├── main_ui.py                      # 管理界面启动脚本
├── pyproject.toml                  # 项目配置与依赖
└── README.md
```

---

## 5. 核心接口设计

### 5.1 通用类型 (`api/types.py`)

```python
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class PluginStatus(Enum):
    """插件运行状态"""
    UNLOADED  = "unloaded"
    LOADING   = "loading"
    LOADED    = "loaded"
    ERROR     = "error"


@dataclass
class PluginMeta:
    """插件元数据（自描述）"""
    name: str                    # 唯一标识，如 "http_tool"
    display_name: str            # 显示名称，如 "HTTP 请求工具"
    version: str                 # 语义化版本
    description: str             # 功能简述
    author: str = ""
    icon: str = ""               # 图标路径或 emoji


@dataclass
class MCPToolDef:
    """MCP 工具定义"""
    name: str                    # 工具名（全局唯一）
    description: str             # 工具描述
    input_schema: dict[str, Any] # JSON Schema 格式的参数定义


@dataclass
class MCPToolResult:
    """MCP 工具调用结果"""
    content: list[dict[str, Any]]  # [{"type": "text", "text": "..."}]
    is_error: bool = False
```

### 5.2 后端插件基类 (`api/base_plugin.py`)

```python
from abc import ABC, abstractmethod
from .types import PluginMeta, MCPToolDef, MCPToolResult


class BasePlugin(ABC):
    """
    后端插件抽象基类

    每个插件实例化后：
    1. 调用 on_load()  进行初始化
    2. 通过 get_tools() 获取工具列表，注册到转发层
    3. 通过 call_tool() 响应外部工具调用
    4. 调用 on_unload() 进行清理
    """

    # ── 必须实现 ──

    @property
    @abstractmethod
    def meta(self) -> PluginMeta:
        """返回插件元数据"""
        ...

    @abstractmethod
    def get_tools(self) -> list[MCPToolDef]:
        """返回本插件提供的所有 MCP 工具定义"""
        ...

    @abstractmethod
    async def call_tool(self, tool_name: str, arguments: dict) -> MCPToolResult:
        """执行指定的工具调用"""
        ...

    # ── 生命周期钩子（可选覆写）──

    async def on_load(self) -> None:
        """插件加载时调用（同步初始化放这里）"""
        pass

    async def on_unload(self) -> None:
        """插件卸载时调用（清理资源）"""
        pass

    async def health_check(self) -> bool:
        """健康检查，返回 True 表示正常"""
        return True
```

### 5.3 管理界面基类 (`api/base_widget.py`)

```python
from abc import ABC, abstractmethod
from PySide6.QtWidgets import QWidget
from .types import PluginMeta


class BasePluginWidget(ABC):
    """
    插件管理界面抽象基类

    每个插件提供一个 QWidget，嵌入到主界面的详情区域。
    Widget 可以包含：状态显示、配置表单、手动触发、日志查看等。
    """

    # ── 必须实现 ──

    @abstractmethod
    def get_name(self) -> str:
        """返回关联的插件名（对应 PluginMeta.name）"""
        ...

    @abstractmethod
    def create_widget(self, parent: QWidget | None = None) -> QWidget:
        """创建并返回管理界面 QWidget"""
        ...

    # ── 可选覆写 ──

    def on_status_changed(self, status: str) -> None:
        """插件状态变更时的回调"""
        pass

    def get_config_schema(self) -> dict:
        """返回可配置项的 JSON Schema"""
        return {}

    def apply_config(self, config: dict) -> None:
        """应用配置变更"""
        pass
```

### 5.4 工具注册表 (`server/registry.py`)

```python
from api.types import MCPToolDef, MCPToolResult
from api.base_plugin import BasePlugin


class ToolRegistry:
    """
    工具名 → 插件 的映射表

    职责：
    - 注册/注销插件提供的所有工具
    - 提供 tool_name → plugin 的快速查找
    - 对外提供聚合的 tools/list
    """

    def register_plugin(self, plugin: BasePlugin) -> None:
        """注册一个插件的所有工具"""
        ...

    def unregister_plugin(self, plugin_name: str) -> None:
        """注销一个插件的所有工具"""
        ...

    def find_plugin(self, tool_name: str) -> BasePlugin | None:
        """根据工具名查找所属插件"""
        ...

    def list_all_tools(self) -> list[MCPToolDef]:
        """返回所有已注册工具的聚合列表"""
        ...

    def clear(self) -> None:
        """清空所有注册"""
        ...
```

### 5.5 插件管理器 (`server/plugin_manager.py`)

```python
from pathlib import Path
from api.base_plugin import BasePlugin
from api.base_widget import BasePluginWidget
from api.types import PluginMeta, PluginStatus


class PluginManager:
    """
    插件管理器

    职责：
    - 扫描 plugins/ 目录，发现可用插件
    - 加载/卸载插件（实例化 + 生命周期管理）
    - 管理插件状态
    - 提供插件实例和 Widget 实例的查询
    """

    def __init__(self, plugins_dir: Path): ...

    def discover(self) -> list[str]:
        """扫描目录，返回发现的插件名列表（不加载）"""
        ...

    def load(self, name: str) -> BasePlugin:
        """加载指定插件，返回后端实例"""
        ...

    def unload(self, name: str) -> None:
        """卸载指定插件"""
        ...

    def get_plugin(self, name: str) -> BasePlugin | None:
        """获取已加载的后端插件实例"""
        ...

    def get_widget(self, name: str) -> BasePluginWidget | None:
        """获取已加载的管理界面实例"""
        ...

    def get_status(self, name: str) -> PluginStatus:
        """获取插件状态"""
        ...

    def list_plugins(self) -> list[PluginMeta]:
        """列出所有插件元数据"""
        ...

    def load_all(self) -> None:
        """加载所有发现的插件"""
        ...

    def unload_all(self) -> None:
        """卸载所有已加载的插件"""
        ...
```

### 5.6 工具路由器 (`server/router.py`)

```python
from api.types import MCPToolDef, MCPToolResult


class ToolRouter:
    """
    工具路由器（供 MCP Server 使用）

    职责：
    - 封装 tools/list → 从 ToolRegistry 聚合
    - 封装 tools/call → 查找插件 → 调用 PluginManager.dispatch
    """

    def __init__(self, registry: "ToolRegistry", plugin_manager: "PluginManager"): ...

    def list_tools(self) -> list[MCPToolDef]:
        """聚合所有已注册工具（对应 MCP tools/list）"""
        ...

    async def call_tool(self, tool_name: str, arguments: dict) -> MCPToolResult:
        """路由到对应插件执行（对应 MCP tools/call）"""
        ...
```

### 5.7 MCP 服务端应用 (`server/app.py`)

```python
from pathlib import Path
from mcp.server.fastmcp import FastMCP
from .plugin_manager import PluginManager
from .registry import ToolRegistry
from .router import ToolRouter


class MCPServerApp:
    """
    MCP Server 应用主类

    职责：
    - 持有 FastMCP 实例
    - 持有 PluginManager / ToolRegistry / ToolRouter
    - 注册 tools/list 和 tools/call 处理器到 FastMCP
    - 控制服务启停
    """

    def __init__(self, name: str = "mcp-tool-hub", plugins_dir: Path | None = None):
        self.name = name
        self.mcp = FastMCP(name)
        self.plugins_dir = plugins_dir or Path("plugins")
        self.registry = ToolRegistry()
        self.plugin_manager = PluginManager(self.plugins_dir)
        self.router = ToolRouter(self.registry, self.plugin_manager)

        self._register_handlers()

    def _register_handlers(self) -> None:
        """向 self.mcp 注册 tools/list 和 tools/call 处理器"""
        ...

    async def start(self) -> None:
        """发现并加载所有插件，启动 MCP Server"""
        ...

    async def stop(self) -> None:
        """卸载所有插件，停止服务"""
        ...
```

### 5.8 数据库管理 (`server/database.py`)

```python
import aiosqlite
import json
from pathlib import Path
from typing import Any


class Database:
    """
    SQLite 异步数据库管理（基于 aiosqlite）

    所有方法均为 async，与 FastAPI 的异步路由天然匹配。
    """

    def __init__(self, db_path: str | Path = "data/mcp_tools.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: aiosqlite.Connection | None = None

    # ── 生命周期 ──
    async def connect(self) -> None: ...
    async def close(self) -> None: ...
    async def init_tables(self) -> None: ...

    # ── 服务端配置 ──
    async def get_config(self, key: str, default: str = "") -> str: ...
    async def set_config(self, key: str, value: str) -> None: ...
    async def get_all_config(self) -> dict[str, str]: ...

    # ── 插件管理 ──
    async def register_plugin(self, name: str, display_name: str, version: str) -> None: ...
    async def set_plugin_enabled(self, name: str, enabled: bool) -> None: ...
    async def update_plugin_status(self, name: str, status: str) -> None: ...
    async def get_plugin_config(self, name: str) -> dict: ...
    async def set_plugin_config(self, name: str, config: dict) -> None: ...
    async def list_plugins(self) -> list[dict]: ...

    # ── 日志 ──
    async def add_log(self, plugin_name: str, level: str, message: str) -> None: ...
    async def get_logs(self, plugin_name: str | None = None, limit: int = 200) -> list[dict]: ...
```

### 5.9 管理 API (`server/management_api.py`)

```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from .plugin_manager import PluginManager
from .database import Database


# ── Pydantic 请求/响应模型 ──

class PluginConfigUpdate(BaseModel):
    config: dict

class ServerStatus(BaseModel):
    running: bool
    plugins_loaded: int
    plugins_total: int

class PluginSummary(BaseModel):
    name: str
    display_name: str
    version: str
    status: str
    enabled: bool

class PluginDetail(PluginSummary):
    tools: list[dict]
    config: dict


class ManagementAPI:
    """
    FastAPI HTTP 管理 API 服务

    与 MCP Server 共享 PluginManager 和 Database 实例。
    所有端点均为 async，框架自动处理并发。

    FastAPI 自动生成：
    - Swagger UI:  http://127.0.0.1:9020/docs
    - ReDoc:       http://127.0.0.1:9020/redoc
    - OpenAPI JSON: http://127.0.0.1:9020/openapi.json
    """

    def __init__(
        self,
        plugin_manager: PluginManager,
        database: Database,
        host: str = "127.0.0.1",
        port: int = 9020,
    ):
        self.plugin_manager = plugin_manager
        self.database = database
        self.host = host
        self.port = port
        self.app = FastAPI(title="MCP Tool Hub API", version="0.1.0")
        self._register_routes()

    def _register_routes(self) -> None:
        """注册所有路由和 Pydantic 模型"""
        app = self.app

        @app.get("/health")
        async def health():
            return {"status": "ok"}

        @app.get("/server/status", response_model=ServerStatus)
        async def server_status(): ...

        @app.post("/server/reload")
        async def server_reload(): ...

        @app.get("/plugins", response_model=dict)
        async def list_plugins(): ...

        @app.get("/plugins/{name}", response_model=PluginDetail)
        async def get_plugin(name: str): ...

        @app.post("/plugins/{name}/load")
        async def load_plugin(name: str): ...

        @app.post("/plugins/{name}/unload")
        async def unload_plugin(name: str): ...

        @app.put("/plugins/{name}/enable")
        async def enable_plugin(name: str): ...

        @app.put("/plugins/{name}/disable")
        async def disable_plugin(name: str): ...

        @app.put("/plugins/{name}/config")
        async def update_plugin_config(name: str, body: PluginConfigUpdate): ...

        @app.get("/logs")
        async def get_logs(plugin: str | None = None, limit: int = 200): ...

    async def start(self) -> None:
        """启动 uvicorn 服务（后台任务）"""
        import uvicorn
        self._config = uvicorn.Config(
            self.app, host=self.host, port=self.port, log_level="info"
        )
        self._server = uvicorn.Server(self._config)
        self._task = asyncio.create_task(self._server.serve())

    async def stop(self) -> None:
        """停止 HTTP 服务"""
        if self._server:
            self._server.should_exit = True
            await self._task
```

### 5.10 MCPServerApp (`server/app.py`)

```python
class MCPServerApp:
    """
    全异步调度中心

    持有：
    - FastMCP（MCP 协议层，stdio 传输）
    - FastAPI ManagementAPI（HTTP 管理接口）
    - Database（aiosqlite）
    - PluginManager / ToolRegistry / ToolRouter
    """

    def __init__(self, ...):
        self.database = Database("data/mcp_tools.db")
        self.plugin_manager = PluginManager(...)
        self.registry = ToolRegistry()
        self.router = ToolRouter(self.registry, self.plugin_manager)
        self.management_api = ManagementAPI(self.plugin_manager, self.database)
        self.mcp = FastMCP("mcp-tool-hub")

    async def start(self) -> None:
        await self.database.connect()
        await self.database.init_tables()

        # 从 DB 读取禁用插件列表，传给 PluginManager
        disabled = await self._load_disabled_plugins()
        await self.plugin_manager.discover()
        await self.plugin_manager.load_all(skip=disabled)

        await self.management_api.start()        # FastAPI 在 :9020 启动
        await self.mcp.run_stdio_async()         # MCP stdio（阻塞）

    async def stop(self) -> None:
        await self.management_api.stop()
        await self.plugin_manager.unload_all()
        await self.database.close()

    async def _load_disabled_plugins(self) -> list[str]:
        rows = await self.database.list_plugins()
        return [r["name"] for r in rows if not r["enabled"]]
```

---

## 6. 插件开发规范

### 6.1 插件包结构

每个插件是 `plugins/` 下的一个 Python 包，约定如下结构：

```
plugins/my_tool/
├── __init__.py      # 导出 PLUGIN_CLASS 和 WIDGET_CLASS
├── backend.py       # class MyToolPlugin(BasePlugin): ...
└── widget.py        # class MyToolWidget(BasePluginWidget): ...
```

### 6.2 `__init__.py` 约定

```python
# plugins/my_tool/__init__.py
from .backend import MyToolPlugin
from .widget import MyToolWidget

PLUGIN_CLASS = MyToolPlugin    # 必需：后端插件类
WIDGET_CLASS = MyToolWidget    # 可选：管理界面类，无界面则设为 None
```

插件管理器通过 `importlib.import_module` 加载 `__init__.py`，然后读取 `PLUGIN_CLASS` 和 `WIDGET_CLASS` 属性。

### 6.3 后端示例

```python
# plugins/my_tool/backend.py
from api.base_plugin import BasePlugin
from api.types import PluginMeta, MCPToolDef, MCPToolResult


class MyToolPlugin(BasePlugin):

    @property
    def meta(self) -> PluginMeta:
        return PluginMeta(
            name="my_tool",
            display_name="我的工具",
            version="1.0.0",
            description="这是一个示例工具",
            author="Your Name",
        )

    def get_tools(self) -> list[MCPToolDef]:
        return [
            MCPToolDef(
                name="my_action",
                description="执行某个操作",
                input_schema={
                    "type": "object",
                    "properties": {
                        "input": {"type": "string", "description": "输入参数"}
                    },
                    "required": ["input"],
                },
            )
        ]

    async def call_tool(self, tool_name: str, arguments: dict) -> MCPToolResult:
        if tool_name == "my_action":
            result = f"处理结果: {arguments.get('input')}"
            return MCPToolResult(
                content=[{"type": "text", "text": result}]
            )
        return MCPToolResult(
            content=[{"type": "text", "text": f"未知工具: {tool_name}"}],
            is_error=True,
        )

    async def on_load(self) -> None:
        print("MyToolPlugin 加载完成")

    async def on_unload(self) -> None:
        print("MyToolPlugin 已卸载")
```

### 6.4 Widget 示例

```python
# plugins/my_tool/widget.py
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton
from api.base_widget import BasePluginWidget


class MyToolWidget(BasePluginWidget):

    def get_name(self) -> str:
        return "my_tool"

    def create_widget(self, parent: QWidget | None = None) -> QWidget:
        container = QWidget(parent)
        layout = QVBoxLayout(container)

        layout.addWidget(QLabel("状态：运行中"))
        btn = QPushButton("刷新")
        layout.addWidget(btn)
        layout.addStretch()

        return container
```

---

## 7. 服务端启动流程

```
server.py 启动 (async)
    │
    ▼
MCPServerApp.__init__()
    ├─ Database("data/mcp_tools.db")       → aiosqlite 连接
    ├─ PluginManager(plugins_dir)           → 插件目录
    ├─ ToolRegistry + ToolRouter           → 映射 + 路由
    ├─ ManagementAPI(plugin_manager, db)    → FastAPI app
    └─ 注册 MCP list_tools / call_tool handler
    │
    ▼
await app.start()
    ├─ await database.connect()             → aiosqlite 异步连接
    ├─ await database.init_tables()         → 建表
    ├─ await plugin_manager.discover()      → 扫描 plugins/
    ├─ await plugin_manager.load_all()      → 逐个 async 加载
    │    └─ 每个插件：实例化 → await on_load() → get_tools() → registry.register_plugin()
    ├─ await management_api.start()         → FastAPI 在 127.0.0.1:9020 启动
    └─ await mcp.run_stdio_async()          → MCP stdio 阻塞等待
    │
    ▼
服务就绪：
  · stdio ── 外部 AI Client 调用 MCP 工具
  · HTTP  :9020 ── PySide6 UI 管理界面
  · Swagger ── http://127.0.0.1:9020/docs
```

---

## 8. 管理界面设计

### 8.1 界面风格

采用 **PySide6-Fluent-Widgets**（QFluentWidgets）组件库，实现微软 Fluent Design 现代风格。

核心组件使用：

| 原生 PySide6 | FluentWidgets 替代 | 说明 |
|-------------|-------------------|------|
| `QMainWindow` | `FluentWindow` / `MSFluentWindow` | 带导航侧栏的主窗口 |
| `QPushButton` | `PrimaryPushButton` / `FilledPushButton` | Fluent 风格按钮 |
| `QListWidget` | `ListWidget` / `TreeWidget` | 带 hover 效果 |
| `QLabel` | `BodyLabel` / `StrongBodyLabel` / `TitleLabel` | 排版层级 |
| `QLineEdit` | `LineEdit` | 圆角输入框 |
| `QTextEdit` | `TextEdit` | 圆角文本区 |
| `QStackedWidget` | `StackedWidget` | 页面切换 |
| `QStatusBar` | `StateToolTip` / `InfoBar` | 状态提示 |
| `QToolBar` | `CommandBar` | 命令栏 |
| 图标 | `FluentIcon` 系列 | 内置 600+ 图标 |
| 卡片 | `CardWidget` / `SimpleCardWidget` | 卡片容器 |
| 开关 | `SwitchButton` | Fluent 风格开关 |
| 对话框 | `MessageBox` / `Dialog` | Fluent 风格对话框 |

### 8.2 主窗口布局 (FluentWindow)

```
┌────────────────────────────────────────────────────────────┐
│  MCP Tool Hub                                    [_][□][×] │
├──────────┬─────────────────────────────────────────────────┤
│          │                                                 │
│  🔌 概览  │   ┌─────────────────────────────────────────┐  │
│          │   │                                         │  │
│  📦 插件  │   │        当前页面内容 (StackedWidget)       │  │
│  ├ HTTP   │   │                                         │  │
│  ├ 文件   │   │     · 概览页 → 服务状态卡片               │  │
│  └ 数据库 │   │     · 插件页 → 插件列表 + 详情            │  │
│          │   │     · 日志页 → 日志面板                    │  │
│  📋 日志  │   │     · 设置页 → 全局配置                   │  │
│          │   │                                         │  │
│  ⚙ 设置  │   │                                         │  │
│          │   └─────────────────────────────────────────┘  │
├──────────┴─────────────────────────────────────────────────┤
│  ● 服务运行中  │  MCP Tool Hub v0.1.0  │  已加载: 2/3     │
└────────────────────────────────────────────────────────────┘
```

使用 `MSFluentWindow` 的导航接口 `NavigationInterface` 实现左侧导航栏。

### 8.3 页面结构

| 导航项 | 页面组件 | 说明 |
|--------|---------|------|
| 概览 | `OverviewPage` | 服务状态卡片、插件数量统计、快捷操作按钮 |
| 插件 | `PluginListPage` + `PluginDetailWidget` | 左列表右详情的插件管理（复用原方案） |
| 日志 | `LogPage` | 实时日志查看、筛选、清空、导出 |
| 设置 | `SettingsPage` | 全局配置表单（管理端口、日志级别等） |

### 8.4 主窗口代码骨架

```python
# ui/main_window.py
from qfluentwidgets import (
    MSFluentWindow, NavigationInterface, NavigationItemPosition,
    FluentIcon, SubtitleLabel, BodyLabel, CardWidget,
    PrimaryPushButton, InfoBar, InfoBarPosition,
)
from PySide6.QtCore import Qt

from .plugin_list import PluginListPage
from .plugin_detail import PluginDetailPage
from .log_panel import LogPage
from .http_client import AsyncHttpClient


class MainWindow(MSFluentWindow):
    """主窗口"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("MCP Tool Hub")
        self.resize(1100, 720)

        # HTTP 客户端
        self.http = AsyncHttpClient()
        self.http.request_finished.connect(self._on_response)
        self.http.request_failed.connect(self._on_error)

        # 初始化导航
        self._init_navigation()
        self._init_pages()

    def _init_navigation(self):
        """左侧导航栏"""
        nav = self.navigationInterface
        nav.addItem(
            routeKey="overview",
            icon=FluentIcon.HOME,
            text="概览",
            onClick=lambda: self.switchTo(self.overview_page),
            position=NavigationItemPosition.TOP,
        )
        nav.addItem(
            routeKey="plugins",
            icon=FluentIcon.APPLICATION,
            text="插件管理",
            onClick=lambda: self.switchTo(self.plugin_page),
            position=NavigationItemPosition.TOP,
        )
        nav.addItem(
            routeKey="logs",
            icon=FluentIcon.DOCUMENT,
            text="日志",
            onClick=lambda: self.switchTo(self.log_page),
            position=NavigationItemPosition.TOP,
        )
        nav.addItem(
            routeKey="settings",
            icon=FluentIcon.SETTING,
            text="设置",
            onClick=lambda: self.switchTo(self.settings_page),
            position=NavigationItemPosition.BOTTOM,
        )

    def _init_pages(self):
        """页面初始化"""
        self.overview_page = OverviewPage(self.http)
        self.plugin_page = PluginListPage(self.http)
        self.log_page = LogPage(self.http)
        self.settings_page = SettingsPage(self.http)
        # 注册到 QStackedWidget（FluentWindow 内置）

    def show_success_message(self, text: str):
        InfoBar.success(
            title="成功",
            content=text,
            parent=self,
            position=InfoBarPosition.TOP_RIGHT,
            duration=2000,
        )

    def show_error_message(self, text: str):
        InfoBar.error(
            title="错误",
            content=text,
            parent=self,
            position=InfoBarPosition.TOP_RIGHT,
            duration=3000,
        )
```

### 8.5 概览页示例

```python
# ui/pages/overview_page.py
from qfluentwidgets import (
    CardWidget, SubtitleLabel, BodyLabel, StrongBodyLabel,
    PrimaryPushButton, FluentIcon, InfoBar, InfoBarPosition,
    FlowLayout,
)
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout


class OverviewPage(QWidget):
    def __init__(self, http_client, parent=None):
        super().__init__(parent)
        self.http = http_client
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 36, 36, 36)

        # 标题
        title = SubtitleLabel("服务概览")
        layout.addWidget(title)

        # 状态卡片
        self.status_card = CardWidget()
        card_layout = QVBoxLayout(self.status_card)
        self.status_label = StrongBodyLabel("● 服务状态：检查中...")
        card_layout.addWidget(self.status_label)
        layout.addWidget(self.status_card)

        # 操作按钮
        btn_layout = QHBoxLayout()
        self.btn_start = PrimaryPushButton(FluentIcon.PLAY, "启动服务")
        self.btn_stop = PrimaryPushButton(FluentIcon.PAUSE, "停止服务")
        btn_layout.addWidget(self.btn_start)
        btn_layout.addWidget(self.btn_stop)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        layout.addStretch()
```

### 8.6 插件管理页（嵌入 Widget）

```python
# PluginListPage 中动态嵌入插件自定义 Widget：
def _on_plugin_selected(self, plugin_name: str):
    widget_class = self.plugin_manager.get_widget_class(plugin_name)
    if widget_class:
        instance = widget_class()
        custom_widget = instance.create_widget()
        self.detail_container.addWidget(custom_widget)
```
注意：插件 Widget 内部也可以使用 QFluentWidgets 组件（`CardWidget`、`BodyLabel`、`SwitchButton` 等），让插件管理面板风格统一。

### 8.7 前后端通信 — AsyncHttpClient(QObject)

UI 端所有与服务端的通信统一通过 `AsyncHttpClient` 完成。

#### 设计思路

```
PySide6 UI 组件
    │
    │  调用 AsyncHttpClient.get/post/put/delete()
    │  (传入 endpoint + params/body)
    ▼
AsyncHttpClient (QObject)
    ├── 内部使用 httpx.AsyncClient 发送异步请求
    ├── 请求完成后，通过 Qt Signal 发射结果
    │
    ├── Signal: request_finished(int request_id, int status_code, dict data)
    ├── Signal: request_failed(int request_id, str error_message)
    ├── Signal: server_status_changed(bool is_running)
    │
    └── 所有信号在主线程被接收，安全更新 UI
```

#### 接口定义 (`ui/http_client.py`)

```python
import httpx
from PySide6.QtCore import QObject, Signal, QThread
from dataclasses import dataclass
from typing import Any, Callable

@dataclass
class APIResponse:
    """HTTP 响应封装"""
    status_code: int
    data: dict[str, Any]
    ok: bool

class AsyncHttpClient(QObject):
    """
    基于 httpx + QObject 的异步 HTTP 客户端

    使用方式：
        client = AsyncHttpClient("http://127.0.0.1:9020")
        client.request_finished.connect(self._on_response)   # 连接信号
        client.request_failed.connect(self._on_error)
        client.get("/plugins")                                # 发起请求

    特点：
    - 内部维护 httpx.AsyncClient 实例
    - 请求在后台线程执行，不阻塞 UI
    - 响应通过 Qt Signal 返回主线程
    - 支持请求 ID 追踪，区分并发请求
    """

    # ── 信号定义 ──
    request_finished = Signal(int, int, object)
    #                     request_id, status_code, response_data(dict)

    request_failed = Signal(int, str)
    #                     request_id, error_message

    server_status_changed = Signal(bool)
    #                         is_running

    # ── 构造 ──
    def __init__(self, base_url: str = "http://127.0.0.1:9020", parent=None):
        super().__init__(parent)
        self._base_url = base_url.rstrip("/")
        self._client: httpx.AsyncClient | None = None
        self._request_counter = 0
        self._pending: dict[int, str] = {}  # request_id → endpoint

    async def _ensure_client(self) -> None:
        """延迟创建 httpx 客户端"""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=httpx.Timeout(10.0))

    # ── 公开方法（非阻塞，信号驱动）──

    def get(self, endpoint: str, params: dict = None) -> int:
        """发起 GET 请求，返回 request_id"""
        ...

    def post(self, endpoint: str, body: dict = None) -> int:
        """发起 POST 请求，返回 request_id"""
        ...

    def put(self, endpoint: str, body: dict = None) -> int:
        """发起 PUT 请求，返回 request_id"""
        ...

    def delete(self, endpoint: str) -> int:
        """发起 DELETE 请求，返回 request_id"""
        ...

    # ── 内部实现 ──

    async def _execute(self, method: str, endpoint: str, body: dict = None) -> None:
        """在后台线程执行 HTTP 请求，完成后发射信号"""
        ...

    async def close(self) -> None:
        """关闭 httpx 客户端"""
        ...

    # ── 便捷方法 ──

    async def check_server_status(self) -> bool:
        """快速检查服务是否在运行"""
        ...
```

#### 使用示例

```python
# MainWindow 中的使用
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.http = AsyncHttpClient("http://127.0.0.1:9020")

        # 连接信号
        self.http.request_finished.connect(self._on_response)
        self.http.request_failed.connect(self._on_error)

    def refresh_plugins(self):
        """刷新插件列表"""
        self.http.get("/plugins")

    def _on_response(self, request_id: int, status_code: int, data: dict):
        """响应到达（主线程）"""
        if status_code == 200:
            # 直接更新 UI 控件
            self._update_plugin_list(data["plugins"])

    def _on_error(self, request_id: int, error: str):
        QMessageBox.warning(self, "网络错误", error)

    def closeEvent(self, event):
        asyncio.ensure_future(self.http.close())
        super().closeEvent(event)
```

### 8.8 UI 信号流

```
用户点击 "启动服务"
    → QPushButton.clicked
    → MainWindow.on_start_server()
    → self.http.post("/server/reload")
    → AsyncHttpClient 后台执行请求
    → request_finished Signal 发射
    → MainWindow._on_response() 更新 UI

用户选中左侧插件
    → PluginListWidget.currentItemChanged
    → 从缓存的 PluginMeta 中获取插件名
    → PluginDetail.set_plugin(name)
    → plugin_manager.get_widget(name).create_widget()
    → QStackedWidget 切换显示

用户修改插件配置
    → PluginWidget 中的表单变更确认
    → self.http.put(f"/plugins/{name}/config", body=config_dict)
    → request_finished Signal → 刷新界面
```

---

## 9. SQLite 数据存储设计

### 9.1 数据库文件

- 路径：`data/mcp_tools.db`（自动创建）
- 引擎：Python 内置 `sqlite3`，无需额外依赖

### 9.2 表结构

```sql
-- ============================================================
-- 1. server_config: 服务端全局配置（key-value）
-- ============================================================
CREATE TABLE IF NOT EXISTS server_config (
    key         TEXT PRIMARY KEY,
    value       TEXT NOT NULL,
    updated_at  TEXT DEFAULT (datetime('now'))
);

-- 预设行：
-- ('server_name', 'mcp-tool-hub')
-- ('mcp_transport', 'stdio')
-- ('mcp_host', '0.0.0.0')
-- ('mcp_port', '8080')
-- ('management_host', '127.0.0.1')
-- ('management_port', '9020')
-- ('log_level', 'INFO')


-- ============================================================
-- 2. plugins: 插件注册表
-- ============================================================
CREATE TABLE IF NOT EXISTS plugins (
    name          TEXT PRIMARY KEY,        -- 插件唯一标识
    display_name  TEXT NOT NULL,           -- 显示名称
    version       TEXT NOT NULL,           -- 版本号
    enabled       INTEGER DEFAULT 1,       -- 是否启用 (0/1)
    config_json   TEXT DEFAULT '{}',       -- 插件私有配置 (JSON 字符串)
    status        TEXT DEFAULT 'unloaded', -- 当前状态: unloaded/loaded/error
    created_at    TEXT DEFAULT (datetime('now')),
    updated_at    TEXT DEFAULT (datetime('now'))
);


-- ============================================================
-- 3. plugin_logs: 运行日志（持久化，方便 UI 查询历史）
-- ============================================================
CREATE TABLE IF NOT EXISTS plugin_logs (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    plugin_name  TEXT NOT NULL,
    level        TEXT NOT NULL,            -- DEBUG/INFO/WARNING/ERROR
    message      TEXT NOT NULL,
    created_at   TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_logs_plugin ON plugin_logs(plugin_name, created_at);
CREATE INDEX IF NOT EXISTS idx_logs_time ON plugin_logs(created_at);
```

### 9.3 Database 类的典型用法

```python
# server/database.py — 关键方法实现示意（全异步）

import aiosqlite
import json
from pathlib import Path

class Database:
    def __init__(self, db_path="data/mcp_tools.db"):
        self.db_path = Path(db_path)
        self._conn: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = await aiosqlite.connect(
            str(self.db_path),
            # aiosqlite 默认 check_same_thread=False
        )
        self._conn.row_factory = aiosqlite.Row
        await self._conn.execute("PRAGMA journal_mode=WAL")
        await self._conn.execute("PRAGMA foreign_keys=ON")

    async def close(self) -> None:
        if self._conn:
            await self._conn.close()
            self._conn = None

    # ── 服务端配置 ──
    async def get_config(self, key: str, default: str = "") -> str:
        cursor = await self._conn.execute(
            "SELECT value FROM server_config WHERE key = ?", (key,)
        )
        row = await cursor.fetchone()
        return row["value"] if row else default

    async def set_config(self, key: str, value: str) -> None:
        await self._conn.execute(
            """INSERT INTO server_config (key, value, updated_at)
               VALUES (?, ?, datetime('now'))
               ON CONFLICT(key) DO UPDATE SET value=excluded.value,
               updated_at=excluded.updated_at""",
            (key, value),
        )
        await self._conn.commit()

    # ── 插件管理 ──
    async def register_plugin(self, name: str, display_name: str, version: str) -> None:
        await self._conn.execute(
            """INSERT OR IGNORE INTO plugins (name, display_name, version)
               VALUES (?, ?, ?)""",
            (name, display_name, version),
        )
        await self._conn.commit()

    async def update_plugin_status(self, name: str, status: str) -> None:
        await self._conn.execute(
            "UPDATE plugins SET status=?, updated_at=datetime('now') WHERE name=?",
            (status, name),
        )
        await self._conn.commit()

    async def set_plugin_config(self, name: str, config: dict) -> None:
        await self._conn.execute(
            """UPDATE plugins SET config_json=?, updated_at=datetime('now')
               WHERE name=?""",
            (json.dumps(config), name),
        )
        await self._conn.commit()

    async def get_plugin_config(self, name: str) -> dict:
        cursor = await self._conn.execute(
            "SELECT config_json FROM plugins WHERE name=?", (name,)
        )
        row = await cursor.fetchone()
        return json.loads(row["config_json"]) if row else {}

    async def list_plugins(self) -> list[dict]:
        cursor = await self._conn.execute("SELECT * FROM plugins")
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    # ── 日志 ──
    async def add_log(self, plugin_name: str, level: str, message: str) -> None:
        await self._conn.execute(
            "INSERT INTO plugin_logs (plugin_name, level, message) VALUES (?, ?, ?)",
            (plugin_name, level, message),
        )
        await self._conn.commit()

    async def get_logs(self, plugin_name: str | None = None, limit: int = 200) -> list[dict]:
        if plugin_name:
            cursor = await self._conn.execute(
                "SELECT * FROM plugin_logs WHERE plugin_name=? "
                "ORDER BY created_at DESC LIMIT ?",
                (plugin_name, limit),
            )
        else:
            cursor = await self._conn.execute(
                "SELECT * FROM plugin_logs ORDER BY created_at DESC LIMIT ?",
                (limit,),
            )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
```

---

## 10. 管理 API 端点完整定义

### 10.1 路由表

| Method | Path | 说明 | 响应 |
|--------|------|------|------|
| `GET` | `/server/status` | 服务运行状态 | `{"running": true, "plugins_loaded": 3}` |
| `POST` | `/server/reload` | 重新加载全部插件 | `{"ok": true, "loaded": [...], "failed": [...]}` |
| `GET` | `/plugins` | 所有插件列表 | `{"plugins": [{"name":"...", "status":"...",...}]}` |
| `GET` | `/plugins/{name}` | 单个插件详情 | `{"name":"...", "tools": [...], "config": {...}}` |
| `POST` | `/plugins/{name}/load` | 加载指定插件 | `{"ok": true}` |
| `POST` | `/plugins/{name}/unload` | 卸载指定插件 | `{"ok": true}` |
| `PUT` | `/plugins/{name}/enable` | 启用插件 | `{"ok": true}` |
| `PUT` | `/plugins/{name}/disable` | 禁用插件 | `{"ok": true}` |
| `PUT` | `/plugins/{name}/config` | 更新插件配置 | `{"ok": true}` |
| `GET` | `/logs` | 查询日志 | `{"logs": [{"level":"...","message":"..."}]}` |
| `GET` | `/health` | 健康检查 | `{"status": "ok"}` |

### 10.2 请求/响应示例

```
# 刷新插件列表
GET /plugins
→ 200 {"plugins": [
    {"name": "http_tool", "display_name": "HTTP 工具", "status": "loaded", "enabled": true},
    {"name": "file_tool", "display_name": "文件工具", "status": "error", "enabled": true}
]}

# 加载插件
POST /plugins/http_tool/load
→ 200 {"ok": true}

# 更新配置
PUT /plugins/http_tool/config
Body: {"timeout": 30, "retries": 3}
→ 200 {"ok": true}

# 查询日志
GET /logs?plugin=http_tool&limit=50
→ 200 {"logs": [{"level":"INFO","message":"...","created_at":"..."}]}
```

---

## 11. 依赖清单 (`pyproject.toml`)

```toml
[project]
name = "mcp-tool-hub"
version = "0.1.0"
description = "集成式 MCP 工具平台"
requires-python = ">=3.12"
dependencies = [
    "mcp>=1.0.0",                # MCP 协议（async stdio）
    "pyside6>=6.6.0",            # 桌面 UI 框架
    "PySide6-Fluent-Widgets>=1.6.0", # Fluent Design 组件库
    "fastapi>=0.110.0",          # HTTP 管理 API 框架（async）
    "uvicorn[standard]>=0.30.0", # ASGI 服务器
    "pydantic>=2.0.0",           # 数据校验
    "loguru>=0.7.0",             # 日志
    "httpx>=0.27.0",             # UI 侧异步 HTTP 客户端
    "aiosqlite>=0.20.0",         # SQLite 异步访问
]

[project.scripts]
mcp-tool-hub = "server:main"
mcp-tool-ui = "main_ui:main"

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "ruff>=0.3.0",
]
```

---

## 12. 开发计划

### Phase 1 — 核心框架 + 数据层

| 序号 | 任务 | 产出 | 预估 |
|------|------|------|------|
| 1.1 | 定义抽象接口 | `api/` 全部模块 (`types.py`, `base_plugin.py`, `base_widget.py`) | ★ |
| 1.2 | 实现 Database | `server/database.py` — SQLite 建表/CRUD | ★ |
| 1.3 | 实现 PluginManager | `server/plugin_manager.py` — 发现/加载/卸载 | ★ |
| 1.4 | 实现 ToolRegistry + ToolRouter | `server/registry.py`, `server/router.py` | ★ |
| 1.5 | 实现 MCPServerApp | `server/app.py` — 聚合，注册 MCP handler | ★ |
| 1.6 | 实现 ManagementAPI | `server/management_api.py` — Starlette 路由 | ★ |
| 1.7 | 创建插件模板 | `plugins/_template/` | ★ |
| 1.8 | 编写 `server.py` 入口 | 可启动的 MCP Server + 管理 API | ★ |

### Phase 2 — 管理界面

| 序号 | 任务 | 产出 | 预估 |
|------|------|------|------|
| 2.1 | 实现 AsyncHttpClient(QObject) | `ui/http_client.py` — httpx + 信号槽 | ★★ |
| 2.2 | MainWindow (FluentWindow) | `ui/main_window.py` — 导航栏 + 页面路由 | ★★ |
| 2.3 | OverviewPage | `ui/pages/overview_page.py` — 服务状态卡片 | ★ |
| 2.4 | PluginListPage + PluginDetail | `ui/pages/` — 插件列表 + Widget 嵌入 | ★★ |
| 2.5 | LogPage | `ui/pages/log_page.py` — 日志查看/筛选 | ★ |
| 2.6 | SettingsPage | `ui/pages/settings_page.py` — 全局配置表单 | ★ |
| 2.7 | 全局主题 & InfoBar | 暗色/亮色主题切换、消息通知 | ★ |
| 2.8 | `main_ui.py` 入口 | 可启动的管理界面 | ★ |

### Phase 3 — 完善

| 序号 | 任务 | 产出 | 预估 |
|------|------|------|------|
| 3.1 | 示例插件 | HTTP 请求工具等 | ★★ |
| 3.2 | 错误处理 & 日志完善 | — | ★ |
| 3.3 | 打包脚本 | — | ★ |

---

## 13. 关键约束

1. **工具名全局唯一**：所有插件的 `MCPToolDef.name` 不能重复，加载时检测并报错
2. **异步优先**：`call_tool`、`on_load`、`on_unload` 均为 async，不阻塞事件循环
3. **UI 线程安全**：Widget 操作始终在主线程。HTTP 请求在 AsyncHttpClient 内部通过后台协程执行，响应通过 Qt Signal 回到主线程更新 UI
4. **优雅降级**：某个插件加载失败不影响其他插件和服务整体运行
5. **无硬编码**：所有工具定义、接口、配置均通过类抽象，不使用裸字典或硬编码字符串路由
6. **管理 API 仅本地绑定**：管理 API 默认绑定 `127.0.0.1:9020`，不对外暴露
7. **SQLite WAL 模式**：启用 WAL 模式支持读写并发，`check_same_thread=False` 允许多线程访问
