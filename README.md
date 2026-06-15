# MCP Tool Hub

MCP Tool Hub 是一个集成式 MCP 工具平台，将多种实用工具以插件形式统一暴露为 MCP 协议，供 AI 客户端发现和调用，同时提供桌面客户端和 Web UI 进行管理。

## 概述

`MCP Tool Hub` 是一个跨平台的 Python 应用，包含：

- 基于 FastMCP + FastAPI 的后端服务 (`server/`)，同时提供 MCP 协议桥接和 HTTP 管理 API
- 基于 PySide6 Fluent UI 的桌面客户端 (`client/`)
- 基于 Vue 3 的 Web 管理前端 (`web/`)
- 插件系统，支持后端工具与可选前端 Widget (`plugins/`)

内置插件覆盖计算、文档转换、图片处理、JSON 操作、Markdown 转换、Modbus 通信、网络工具、OCR 识别、二维码/条码、SQLite 查询、SSH 远程执行、系统监控等场景。

## 仓库结构

- `server/` — 后端服务、插件管理、HTTP 管理 API、数据库层
- `client/` — PySide6 GUI 客户端、本地服务管理器
- `web/` — Vue 3 Web 管理前端，构建后输出到 `assets/web/`
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
uv run server.py
```

3. 启动桌面客户端：

```bash
uv run client.py
```

4. 可选：以 SSE 模式启动服务：

```bash
uv run server.py --sse
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

## AI 辅助开发

MCP Tool Hub 配备了完整的 AI 智能体与技能体系，深度集成 GitHub Copilot，显著提升开发效率、降低上手门槛。

### 智能体（Agents）

项目内置 7 个专业智能体，各司其职、协同工作，覆盖从开发到测试到发布的全流程：

| 智能体           | 职责                                         | 典型用法                                              |
| ---------------- | -------------------------------------------- | ----------------------------------------------------- |
| `project_lead`   | 全栈协调，将任务委派给专业智能体             | "添加带 Web UI 的新插件"、"修复服务端-客户端通信问题" |
| `server_dev`     | 后端开发：FastMCP、FastAPI、数据库、插件加载 | "添加新的 API 端点"、"修复插件加载问题"               |
| `client_dev`     | 桌面 UI：PySide6 + qfluentwidgets            | "添加新的设置页面"、"修复主题切换"                    |
| `web_dev`        | Web 前端：Vue 3 SPA                          | "添加新的仪表盘页面"、"修复响应式布局"                |
| `plugin_creator` | 插件脚手架：自动生成目录结构和代码模板       | "一个 PDF 转换插件，支持合并和拆分工具"               |
| `mcp_tester`     | MCP 工具测试：直接调用工具验证功能           | "测试 md_to_pdf"、"测试所有工具"                      |
| `git_ops`        | Git 操作：提交、分支、标签、推送             | "提交所有变更"、"创建并推送 v0.2.0 标签"              |

**如何提高开发效率：**

- **零门槛创建插件**：只需用自然语言描述需求，`plugin_creator` 自动生成完整的插件骨架（目录结构、`__init__.py`、`backend.py`、`README.md`），无需手动搭建
- **跨层任务自动协调**：`project_lead` 智能分析任务涉及的组件层，自动按依赖顺序委派给对应智能体，避免手动协调前后端开发节奏
- **一键测试验证**：`mcp_tester` 直接通过 MCP 协议调用工具，无需手动启动服务端或编写测试脚本
- **规范化 Git 操作**：`git_ops` 自动生成 Conventional Commits 格式的提交信息，管理版本标签和发布流程

### 技能（Skills）

| 技能         | 触发方式                     | 说明                                                   |
| ------------ | ---------------------------- | ------------------------------------------------------ |
| `new-plugin` | "创建新插件"、"add a plugin" | 自动化插件脚手架生成，支持工具列表、Widget、配置等选项 |

### 指令（Instructions）

| 指令                      | 适用范围     | 说明                                                   |
| ------------------------- | ------------ | ------------------------------------------------------ |
| `plugins.instructions.md` | `plugins/**` | 插件开发规范，确保所有插件遵循统一的代码风格和架构约定 |

### 协作示例

```
用户: "添加一个 SSH 文件传输插件，带桌面 UI"

→ project_lead 分析任务，按序委派:
  1. plugin_creator → 生成 ssh_tool 插件骨架（backend.py + widget.py）
  2. server_dev → 验证插件加载和工具注册
  3. client_dev → 集成 Widget 到桌面 UI
  4. mcp_tester → 测试所有 SSH 工具
  5. git_ops → 提交并推送变更
```

这种智能体协作模式让开发者只需描述**做什么**，而无需关心**怎么做**——从代码生成、集成验证到版本发布，全流程自动化。

## 开发计划

### 🔄 进行中

- **Web 管理前端** — 基于 Vue 3 的 Web UI 已搭建基础框架，通过管理 API 实现浏览器端插件管理、日志查看、配置编辑
- **Linux 打包支持** — 提供 `.deb` / `.AppImage` 打包脚本，替代 Windows 专属的 `build.ps1` + Inno Setup 流程

### 📋 计划中

- **多语言支持 (i18n)** — 界面国际化，支持中/英等多语言切换

## 许可证

[MIT License](LICENSE)
