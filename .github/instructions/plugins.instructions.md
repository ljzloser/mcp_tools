---
name: plugin-development
description: Use when developing or modifying MCP Tool Hub plugins in plugins/ directory
applyTo: "plugins/**"
---

# MCP Tool Hub 插件开发指南

## 插件结构

每个插件目录包含：
- `__init__.py` — 导出 `PLUGIN_CLASS` 和 `WIDGET_CLASS`（可选）
- `backend.py` — 插件后端逻辑
- `widget.py` — 可选的 PySide6 UI 组件
- `README.md` — 插件文档（必须）

目录名不能以 `_` 或 `.` 开头。

## 后端模式

### 基本结构

```python
from api.base_plugin import BasePlugin
from api.tool import ToolDef, MCPToolResult
from api.config import ConfigModel, StringField
from pydantic import BaseModel, Field

# 可选：配置模型
class MyPluginConfig(ConfigModel):
    api_key = StringField(default="", label="API 密钥", description="...")

# 工具参数模型
class MyToolArgs(BaseModel):
    input_text: str = Field(description="输入文本")

# 插件类
class MyPlugin(BasePlugin[MyPluginConfig]):
    config_class = MyPluginConfig
    
    # 工具声明 — 使用类属性 ToolDef
    my_tool = ToolDef(
        name="my_tool",
        args_model=MyToolArgs,
        description="工具描述"
    )
    
    @property
    def meta(self) -> PluginMeta:
        return PluginMeta(
            name="my_plugin",
            display_name="我的插件",
            version="1.0.0",
            description="插件功能描述",
            author="MCP Tool Hub",
            icon="🔧"
        )
    
    async def handle_my_tool(self, args: MyToolArgs) -> MCPToolResult:
        try:
            result = f"处理: {args.input_text}"
            return MCPToolResult(content=[{"type": "text", "text": result}])
        except Exception as e:
            return MCPToolResult(
                content=[{"type": "text", "text": f"错误: {e}"}],
                is_error=True
            )
```

### 工具声明规范

- 使用 `ToolDef` 类属性（非装饰器）
- `name`: 工具唯一名称，全局唯一
- `args_model`: Pydantic BaseModel，用于参数验证和 JSON Schema 生成
- `description`: 工具功能描述，供 AI 客户端使用

### 返回格式

统一使用 `MCPToolResult`:
```python
# 成功
MCPToolResult(content=[{"type": "text", "text": "结果"}])

# 错误
MCPToolResult(content=[{"type": "text", "text": "错误信息"}], is_error=True)
```

### 访问配置

```python
class MyPlugin(BasePlugin[MyPluginConfig]):
    async def handle_my_tool(self, args):
        # 直接通过 self.config 访问配置字段
        api_key = self.config.api_key
```

## Widget 模式（可选）

### 基本结构

```python
from api.base_widget import BasePluginWidget
from qfluentwidgets import (
    QWidget, QVBoxLayout, LineEdit, PushButton, InfoBar
)
from PySide6.QtCore import Signal

class MyPluginWidget(BasePluginWidget):
    # 必须继承 QObject（Signal 需要）
    
    def get_name(self) -> str:
        return "我的插件"
    
    def create_widget(self, parent: QWidget | None = None) -> QWidget:
        widget = QWidget(parent)
        layout = QVBoxLayout(widget)
        
        # 输入控件
        self.input = LineEdit()
        self.input.setPlaceholderText("输入...")
        
        # 按钮
        self.btn = PushButton("执行")
        self.btn.clicked.connect(self._on_execute)
        
        layout.addWidget(self.input)
        layout.addWidget(self.btn)
        
        return widget
    
    def _on_execute(self):
        text = self.input.text()
        if not text:
            InfoBar.warning("提示", "请输入内容", parent=self._widget)
            return
        
        # 使用类型化 invoke
        self.invoke(
            MyPlugin.my_tool,
            MyToolArgs(input_text=text)
        )
    
    def on_result(self, result: MCPToolResult):
        if result.is_error:
            InfoBar.error("错误", result.content[0]["text"], parent=self._widget)
        else:
            InfoBar.success("成功", result.content[0]["text"], parent=self._widget)
```

### Widget 约定

- 必须继承 `BasePluginWidget(QObject)`，否则跨线程信号无法排队
- 实例需显式持有引用防止 GC：`self._widget_instance = widget`
- 使用 `self.invoke(PluginClass.tool_def, ArgsModel(...))` 而非字符串
- 在 `on_result(self, result: MCPToolResult)` 中处理结果
- UI 框架使用 **qfluentwidgets**（Fluent Design）

## 配置系统

### 可用字段类��

```python
from api.config import (
    StringField, IntField, FloatField, BoolField,
    PathField, ChoiceField, TextField
)

class MyConfig(ConfigModel):
    # 字符串
    api_key = StringField(default="", label="API Key", description="...")
    
    # 整数/浮点数
    timeout = IntField(default=30, label="超时", description="...")
    
    # 布尔
    debug = BoolField(default=False, label="调试模式")
    
    # 路径
    output_dir = PathField(default="", label="输出目录")
    
    # 选择
    mode = ChoiceField(default="auto", choices=["auto", "manual"], label="模式")
    
    # 多行文本
    notes = TextField(default="", label="备注")
```

### 配置对话框约定

- 对话框需 `load_dict()` 后 `config_form.set_values(model._data)` 回填数据
- `get_values()` 需 `to_storage()` 序列化

## README 模板

```markdown
# 插件名称

一句话功能描述。

## 工具列表

| 工具名 | 说明 |
|--------|------|
| tool_name | 工具功能 |

## 依赖

- 列出外部依赖库

## 示例

```json
{
  "tool_name": {
    "input_text": "hello"
  }
}
```

参考现有插件：[plugins/calculator_tool/](../../plugins/calculator_tool/)、[plugins/json_tool/](../../plugins/json_tool/)

## 常见陷阱

1. **ToolDef 用 `**kwargs`** — FastMCP 无法解析，必须用 Pydantic 模型
2. **Widget 不继承 QObject** — 信号无法跨线程排队，UI 更新被静默吞掉
3. **Widget 实例被 GC** — 需显式持有引用
4. **工具名重复** — ToolRegistry 会检测冲突
5. **ConfigField.create_widget()** — 懒加载 Qt，后端不应调用