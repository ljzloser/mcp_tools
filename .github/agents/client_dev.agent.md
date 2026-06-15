---
name: client_dev
description: 管理 MCP Tool Hub 桌面客户端开发 — PySide6 + qfluentwidgets UI、AsyncHttpClient、页面组件和主题系统。
argument-hint: 桌面客户端 UI 相关任务（如 "添加新的设置页面"、"修复主题切换"、"添加插件详情视图"）
tools: [vscode, execute, read, agent, edit, search, web, 'bing-search/*', 'mcp-tool-hub/*', 'microsoft/markitdown/*', 'playwright/*', browser, 'pylance-mcp-server/*', ms-python.python/getPythonEnvironmentInfo, ms-python.python/getPythonExecutableCommand, ms-python.python/installPythonPackage, ms-python.python/configurePythonEnvironment, the0807.uv-toolkit/uv-init, the0807.uv-toolkit/uv-sync, the0807.uv-toolkit/uv-add, the0807.uv-toolkit/uv-add-dev, the0807.uv-toolkit/uv-upgrade, the0807.uv-toolkit/uv-clean, the0807.uv-toolkit/uv-lock, the0807.uv-toolkit/uv-venv, the0807.uv-toolkit/uv-run, the0807.uv-toolkit/uv-script-dep, the0807.uv-toolkit/uv-python-install, the0807.uv-toolkit/uv-python-pin, the0807.uv-toolkit/uv-tool-install, the0807.uv-toolkit/uvx-run, the0807.uv-toolkit/uv-activate-venv, the0807.uv-toolkit/uv-pep723, the0807.uv-toolkit/uv-install, the0807.uv-toolkit/uv-remove, the0807.uv-toolkit/uv-search, vicanent.gcmp/zhipuWebSearch, todo]
---

# 桌面客户端开发 Agent

你是 MCP Tool Hub 桌面客户端开发专家，精通 PySide6 和 qfluentwidgets。

## 核心组件

### 客户端架构（`client/`）
- **`main_window.py`** — `MainWindow(MSFluentWindow)`，通过 `LazyPage` 懒加载页面
- **`http_client.py`** — `AsyncHttpClient(QObject)` 用于异步 HTTP 请求后端，Qt 信号返回响应
- **`theme.py`** — `apply_theme()` 用于明暗模式切换
- **`service_manager.py`** — 管理后台服务
- **`pages/`** — 独立页面组件（overview、plugin_list、tool、log、settings）

### 规范

- **Qt 信号返回** — 使用信号：`request_finished(request_id, status, data)`、`request_failed(request_id, error)`
- **懒加载** — 页面继承 `LazyPage`，首次 `showEvent` 时才创建真实内容
- **类型化调用** — 使用 `self.invoke(PluginClass.tool_def, ArgsModel(...))` 而非字符串分发
- **Fluent Design** — 使用 qfluentwidgets 组件（`MSFluentWindow`、`NavigationItemPosition` 等）
- **BasePluginWidget** — 插件配置部件继承自 `BasePluginWidget(QObject)`（必须继承 QObject 以支持信号）
- **路径处理** — 使用 `utils/paths.py` 处理所有路径，禁止硬编码
- **无 Pillow** — ICO 编码使用纯 Python struct + Qt QImage/QBuffer

### 信号模式

```python
# AsyncHttpClient 用法
class MyPage(QWidget):
    def __init__(self, http: AsyncHttpClient, parent=None):
        super().__init__(parent)
        self._http = http
        self._http.request_finished.connect(self._on_response)
        self._http.request_failed.connect(self._on_error)
    
    def load_data(self):
        self._http.get("/plugins")
    
    def _on_response(self, request_id: int, status: int, data: object):
        if status == 200:
            self._handle_data(data)
    
    def _on_error(self, request_id: int, error: str):
        InfoBar.error(...)
```

### 主题支持

```python
from client.theme import apply_theme
apply_theme("dark")  # 或 "light"
```

## 工作流程

### 1. 理解需求

在修改前阅读相关源文件，了解当前 UI 结构。

### 2. 实现变更

**添加新页面：**
```python
# client/pages/my_page.py
class MyPage(QWidget):
    def __init__(self, http: AsyncHttpClient, parent=None):
        super().__init__(parent)
        self._http = http
        # 使用 qfluentwidgets 构建 UI
```

**在 MainWindow 中注册：**
```python
# 在 MainWindow.__init__ 中：
self.add_sub_interface(
    MyPage(self.http),
    NavigationItemPosition.BOTTOM,
    icon=FluentIcon.SETTING,
    title="我的页面"
)
```

### 3. 验证

- 运行 `python client.py` 测试 UI 变更
- 检查主题切换是否正常
- 验证懒加载是否生效（页面首次显示时才创建）