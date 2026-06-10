# MCP Tool Hub — 开发计划

> 版本: 0.1.0 | 创建日期: 2026-06-10 | 状态: 开发中

---

## Phase 1 — 核心框架 + 数据层

| 序号 | 任务 | 产出文件 | 状态 | 完成日期 |
|------|------|----------|------|----------|
| 1.1 | 定义抽象接口 | `api/types.py`, `api/base_plugin.py`, `api/base_widget.py` | ✅ 已完成 | 2026-06-10 |
| 1.2 | 实现 Database | `server/database.py` | ✅ 已完成 | 2026-06-10 |
| 1.3 | 实现 PluginManager | `server/plugin_manager.py` | ✅ 已完成 | 2026-06-10 |
| 1.4 | 实现 ToolRegistry + ToolRouter | `server/registry.py`, `server/router.py` | ✅ 已完成 | 2026-06-10 |
| 1.5 | 实现 MCPServerApp | `server/app.py` | ✅ 已完成 | 2026-06-10 |
| 1.6 | 实现 ManagementAPI | `server/management_api.py` | ✅ 已完成 | 2026-06-10 |
| 1.7 | 创建插件模板 | `plugins/_template/` | ✅ 已完成 | 2026-06-10 |
| 1.8 | 编写入口 + 依赖 | `server.py`, `pyproject.toml` | ✅ 已完成 | 2026-06-10 |

**Phase 1 验收标准**：启动 `server.py` 后，MCP Server 通过 stdio 可响应 `tools/list` 和 `tools/call`，同时管理 API 在 `:9020` 可访问。

---

## Phase 2 — 管理界面

| 序号 | 任务 | 产出文件 | 状态 | 完成日期 |
|------|------|----------|------|----------|
| 2.1 | AsyncHttpClient(QObject) | `ui/http_client.py` | ✅ 已完成 | 2026-06-10 |
| 2.2 | MainWindow (MSFluentWindow) | `ui/main_window.py` | ✅ 已完成 | 2026-06-10 |
| 2.3 | OverviewPage | `ui/pages/overview_page.py` | ✅ 已完成 | 2026-06-10 |
| 2.4 | PluginListPage + PluginDetail | `ui/pages/plugin_list_page.py` | ✅ 已完成 | 2026-06-10 |
| 2.5 | LogPage | `ui/pages/log_page.py` | ✅ 已完成 | 2026-06-10 |
| 2.6 | SettingsPage | `ui/pages/settings_page.py` | ✅ 已完成 | 2026-06-10 |
| 2.7 | 主题 & InfoBar | `ui/theme.py` | ✅ 已完成 | 2026-06-10 |
| 2.8 | main_ui.py 入口 | `main_ui.py` | ✅ 已完成 | 2026-06-10 |

**Phase 2 验收标准**：启动 `main_ui.py` 后，Fluent Design 界面可通过 HTTP API 管理插件、查看日志、修改配置。

---

## Phase 3 — 完善与示例

| 序号 | 任务 | 产出文件 | 状态 | 完成日期 |
|------|------|----------|------|----------|
| 3.1 | 示例插件 | `plugins/http_tool/` | ✅ 已完成 | 2026-06-10 |
| 3.2 | 错误处理 & 日志完善 | — | ✅ 已完成 | 2026-06-10 |
| 3.3 | 打包脚本 | — | ⬜ 待开发 | |

---

## 状态图例

- ⬜ 待开发
- 🔄 开发中
- ✅ 已完成
- ❌ 阻塞

---

## 开发日志

### 2026-06-10
- 创建开发计划文档
- 完成 Phase 1 全部编码（1.1 ~ 1.8）
- 修复 registry.py `list_all_tools()` 逻辑 bug（`and` → 纯列表推导）
- 修复 app.py 移除访问 FastMCP 私有属性的 hack，改为纯动态注册
- 修复 server.py 移除 deprecated `asyncio.get_event_loop()` 和已废弃的信号处理
- 修复 pyproject.toml 移除不存在的入口点和 `ui` 包引用

### 2026-06-10 (Phase 2)
- 完成 Phase 2 全部编码（2.1 ~ 2.8）
- 实现 AsyncHttpClient：基于 httpx + 后台事件循环线程 + Qt Signal
- 实现 MainWindow：MSFluentWindow + 左侧导航栏 + 四个功能页
- 实现 OverviewPage：4 个统计卡片 + 刷新/重载操作
- 实现 PluginListPage：左列表右详情布局，支持加载/卸载/启用/禁用
- 实现 LogPage：日志文本区 + 插件筛选下拉 + 定时刷新
- 实现 SettingsPage：服务配置表单 + 关于信息
- 修复 FluentIcon 不存在的属性（DESKTOP→CLOUD, REFRESH→SYNC）
- UI 窗口验证通过，可正常创建并显示

### 2026-06-10 (Phase 3)
- 创建 http_tool 示例插件（提供 http_get / http_post 两个 MCP 工具）
- 端到端测试通过：插件发现→加载→注册→API 查询全流程正常
- 给 ManagementAPI 添加 CORS 中间件和全局异常处理
- 增强 app.py stop() 方法的健壮性（各步骤独立 try/catch）
- 增强 _register_single_tool 的异常捕获
- 修复 FluentIcon 不存在的属性（DESKTOP→CLOUD, REFRESH→SYNC）
