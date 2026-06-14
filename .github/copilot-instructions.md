# MCP Tool Hub — 项目指南

## 架构

集成式 MCP 工具平台：服务端作为纯转发层暴露 `tools/list` 和 `tools/call`，所有功能以插件形式内置。

- **后端**：`server/` — FastMCP (MCP 协议) + FastAPI (管理 API, 端口 9020) + aiosqlite
- **前端**：`client/` — PySide6 + qfluentwidgets (Fluent Design UI)，通过 HTTP 管理 API 与后端通信
- **Web 前端**：`web/` — Vue 3 SPA，构建到 `assets/web/`，由 FastAPI 在 `/web/` 路径提供静态服务
- **插件**：`plugins/` — 每个插件 = `BasePlugin`（后端）+ 可选 `BasePluginWidget`（UI Widget）
- **协议层**：`api/` — 前后端共享的 Pydantic 模型 (`protocol.py`)、路由常量 (`routes.py`)、工具定义 (`tool.py`)、配置系统 (`config.py`)

通信分层：MCP 层走 stdio/SSE（AI 客户端），管理操作走 HTTP REST（UI 客户端）。

详细设计见 [docs/DESIGN.md](../docs/DESIGN.md)，开发计划见 [docs/DEVPLAN.md](../docs/DEVPLAN.md)。

## 构建与运行

```bash
uv sync                    # 安装依赖
python server.py           # 启动服务 (stdio 模式)
python server.py --sse     # 启动服务 (SSE 模式, 端口 9021)
python client.py           # 启动管理 UI
pytest                     # 运行测试
cd web && npm run build    # 构建 Web 前端 → assets/web/
```

## 创建新插件

1. 在 `plugins/` 下创建目录（不能以 `_` 或 `.` 开头），含 `__init__.py`
2. `__init__.py` 导出 `PLUGIN_CLASS`（必须）和 `WIDGET_CLASS`（可选）
3. 后端继承 `BasePlugin[ConfigModel]`，声明 `ToolDef` 类属性，实现 `handle_{tool_name}`
4. 可选配置：声明 `config_class`，使用 `ConfigField` 子类定义字段
5. 可选 Widget：继承 `BasePluginWidget(QObject)`，实现 `get_name()` + `create_widget(parent)`
6. **必须添加 README.md**：每个插件目录下必须包含 README.md，描述工具列表和使用示例

参考模板：[plugins/_template/](../plugins/_template/)

## 关键约定

- **路径管理**：所有路径使用 `utils/paths.py` 的 `paths` 对象，禁止硬编码路径
- **工具声明**：用 `ToolDef` 类属性声明工具（非字符串/装饰器），`call_tool()` 自动分派到 `handle_{name}`
- **类型化 invoke**：Widget 使用 `invoke(PluginClass.tool_def, ArgsModel(...))` 而非字符串
- **API 路径**：使用 `api/routes.py` 的 `Routes` 常量，不硬编码 URL
- **响应解析**：前端用 `api/protocol.py` 的 Pydantic 模型解析 HTTP 响应
- **配置字段**：`ConfigField` descriptor 协议，`self.config.key` 直接读写，Pylance 可推断类型
- **数据库时间**：始终用 `datetime('now', 'localtime')`，不用 UTC
- **无 Pillow 依赖**：ICO 编码用纯 Python struct + Qt QImage/QBuffer
- **跨平台**：所有平台专用代码必须用 `if IS_WINDOWS:` / `if IS_LINUX:` 包裹，不直接调用平台 API
- **工具返回**：统一用 `MCPToolResult(content=[{"type": "text", "text": "..."}], is_error=False/True)`
- **插件元数据**：`meta` 属性返回 `PluginMeta(name, display_name, version, description, author, icon)`

## 陷阱

- **FastMCP 动态注册不能用 `**kwargs`**：必须根据 `input_schema` 动态创建 Pydantic ArgModel（见 `server/app.py` 的 `_register_single_tool`）
- **BasePluginWidget 必须继承 QObject**：否则跨线程信号无法排队到主线程，UI 更新被静默吞掉
- **Widget 实例需显式持有引用**：防止 GC 回收导致信号连接失效
- **MCP 开关 vs 插件加载**：关闭 MCP 只从 FastMCP 注销工具，插件仍加载，UI invoke 仍可用
- **启用 = 加载 + 持久化**，**禁用 = 卸载 + 持久化**（已合并，无单独 load/unload）
- **工具名全局唯一**：`ToolRegistry` 会检测冲突
- **`ToolDef.validate()` 过滤 None**：让 Pydantic 默认值生效
- **Management API 无 `/api` 前缀**：如 `/health` 而非 `/api/health`
- **ConfigField.create_widget() 懒加载 Qt**：后端不应调用此方法
- **FluentIcon 无 DESKTOP/REFRESH**：用 CLOUD/SYNC 替代
- **PySide6 用 `Signal`** 而非 `pyqtSignal`
- **`PluginConfigResponse.schema` 遮蔽 `BaseModel.schema()`**：已重命名为 `schema_info`
- **qfluentwidgets CheckBox 无 `checkedChanged`**：用 `toggled` 信号
- **`QImage.save(qbuf, "PNG")` Pylance 报错**：运行时正常，用 `# type: ignore[call-overload]` 抑制
- **`constBits()` 返回 `memoryview`**：用 `[:size]` 切片而非 `.asarray()`
- **ASGI 双重 `http.response.start`**：由 `ResponseGuardMiddleware` 中间件拦截
