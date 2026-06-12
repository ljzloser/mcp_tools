# MCP Tool Hub

MCP Tool Hub 是一个基于 MCP 的桌面管理平台，主要用于插件管理、日志查询、服务控制与打包部署。

## 概述

`MCP Tool Hub` 是一个跨平台的 Python 应用，包含：

- 基于 FastAPI 的管理后端 (`server/`)
- 基于 PySide6 Fluent UI 的桌面客户端 (`client/`)
- 插件系统，支持后端工具与可选前端 Widget (`plugins/`)
- MCP 协议桥接，供 AI 客户端发现并调用插件工具

功能包括：

- 插件发现、加载/卸载、配置管理
- 日志查询、筛选、时间范围过滤
- 服务安装与控制（Windows 通过 NSSM，Linux 通过 systemd）
- PyInstaller 打包与 Inno Setup 安装程序生成（Windows）

## 仓库结构

- `server/` — 后端服务、插件管理、HTTP 管理 API、数据库层
- `client/` — PySide6 GUI 客户端、本地服务管理器
- `plugins/` — 插件目录，每个插件为单独包，支持后端与可选 UI
- `api/` — 共享协议模型、路由常量、工具定义
- `assets/` — 应用静态资源与图标
- `docs/` — 设计与开发文档
- `build.ps1` — Windows 打包脚本
- `mcp_tool_hub.spec` — PyInstaller 打包配置
- `setup.iss` — Inno Setup 安装脚本

## 需求

- Python 3.12+
- `uv` 包管理器
- Windows 10/11 或 Linux（systemd）

## 快速启动

1. 安装依赖：

```bash
uv sync
```

2. 启动后台服务：

```bash
python server.py
```

3. 启动桌面客户端：

```bash
python client.py
```

4. 可选：以 SSE 模式启动服务：

```bash
python server.py --sse
```

## 开发指南

### 插件开发

每个插件目录位于 `plugins/<plugin_name>/`，至少需要导出：

- `PLUGIN_CLASS` — 继承自 `api.base_plugin.BasePlugin` 的后端插件类
- 可选 `WIDGET_CLASS` — 继承自 `api.base_widget.BasePluginWidget` 的前端 Widget 类

后端插件通过 `ToolDef` 定义工具，并实现对应的 `handle_<tool_name>` 方法。

### 共享接口

- `api/protocol.py` 存放 Pydantic 请求/响应模型，供客户端和服务端共享使用。
- `api/routes.py` 定义所有管理 API 的路由常量。

### 本地服务管理

- **Windows**: `client/service_manager.py` 使用 NSSM 管理 Windows 服务的安装、卸载、启动和停止。
- **Linux**: 使用 `systemctl --user` 管理 systemd 用户服务，自动生成 `.service` 单元文件。
- `build.ps1` 会在打包前检查依赖并下载 `nssm.exe`（如果缺失，仅 Windows）。

### 跨平台约定

所有平台专用代码必须使用平台判断包裹：

```python
import sys
IS_WINDOWS = sys.platform == "win32"

if IS_WINDOWS:
    # Windows 专用代码
else:
    # Linux/macOS 代码
```

- Windows 专用模块（`ctypes`、`wintypes`）在 `if IS_WINDOWS:` 下导入
- 子进程标志使用 `getattr(subprocess, "CREATE_NO_WINDOW", 0)` 安全获取
- UI 层通过 `ServiceManager.is_supported` 判断是否启用服务管理功能

## 打包流程

生成可执行程序（Windows）：

```powershell
.\build.ps1
```

生成 Inno 安装程序（Windows）：

```powershell
.\build.ps1 -Inno
```

## 说明

- 服务管理支持 Windows（NSSM）和 Linux（systemd user unit）。
- 日志存储在 SQLite 中，支持插件级、级别、关键词和时间范围筛选。
- 插件架构已支持通过管理 API 调用后端工具。

## 开发计划

### 🔄 进行中

- **Linux 打包支持** — 提供 `.deb` / `.AppImage` 打包脚本，替代 Windows 专属的 `build.ps1` + Inno Setup 流程

### 📋 计划中

- **Web 管理前端** — 基于 Vue / React 的 Web UI，通过管理 API 实现浏览器端插件管理、日志查看、配置编辑，无需安装桌面客户端
- **多语言支持 (i18n)** — 界面国际化，支持中/英等多语言切换

## 许可证

[MIT License](LICENSE)
