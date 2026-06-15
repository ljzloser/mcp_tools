#!/usr/bin/env python3
"""New Plugin Scaffolding Script

Usage: python scripts/new_plugin.py <plugin_name> [options]

Options:
  --display-name TEXT    Human-readable name
  --tools TEXT          Comma-separated tool names
  --widget              Include PySide6 widget
  --config              Include configuration support
  --force               Overwrite existing plugin

Examples:
  python scripts/new_plugin.py weather --tools get_forecast,get_weather --widget
  python scripts/new_plugin.py calculator --config
"""

import argparse
import os
import sys
from pathlib import Path

# Project root
PROJECT_ROOT = Path(__file__).parent.parent
PLUGINS_DIR = PROJECT_ROOT / "plugins"


def create_plugin(name: str, display_name: str, tools: list, has_widget: bool, has_config: bool, force: bool):
    """Create a new plugin with scaffolding."""

    plugin_dir = PLUGINS_DIR / name

    if plugin_dir.exists() and not force:
        print(
            f"Error: Plugin '{name}' already exists. Use --force to overwrite.")
        sys.exit(1)

    plugin_dir.mkdir(parents=True, exist_ok=True)

    # Determine imports based on options
    if has_widget:
        widget_import = f"from .widget import {name.title().replace('_', '')}Widget"
        widget_class = f"{name.title().replace('_', '')}Widget"
    else:
        widget_import = "# from .widget import WidgetClass  # Uncomment if widget is needed"
        widget_class = "None"

    if has_config:
        config_import = "from api.config import ConfigModel, StringField"
        config_class = f"{name.title().replace('_', '')}Config"
        config_fields = f'''
    # Configuration fields
    api_key = StringField(default="", label="API Key", description="Your API key")'''
    else:
        config_import = "# from api.config import ConfigModel  # Uncomment if config is needed"
        config_class = "None"
        config_fields = ""

    # Generate tool definitions
    tool_defs = ""
    tool_handlers = ""
    tool_examples = ""

    for i, tool_name in enumerate(tools):
        camel_name = "".join(word.capitalize()
                             for word in tool_name.split("_"))
        args_model = f"{camel_name}Args"

        # ToolDef declaration
        tool_defs += f'''
    {tool_name} = ToolDef(
        name="{tool_name}",
        args_model={args_model},
        description="Tool description for {tool_name}"
    )'''

        # Handler method
        tool_handlers += f'''
    async def handle_{tool_name}(self, args: {args_model}) -> MCPToolResult:
        """Handle {tool_name} tool"""
        try:
            # TODO: Implement your tool logic here
            result = f"Result for: {{args}}"
            return MCPToolResult(content=[{{"type": "text", "text": result}}])
        except Exception as e:
            return MCPToolResult(
                content=[{{"type": "text", "text": f"Error: {{e}}"}}],
                is_error=True
            )
'''

        # README example
        tool_examples += f"""| {tool_name} | Tool description |
"""

    # Create __init__.py
    init_content = f'''"""MCP Tool Hub — {display_name} Plugin"""

from .backend import {name.title().replace('_', '')}Plugin
{widget_import}

# Required: Backend plugin class
PLUGIN_CLASS = {name.title().replace('_', '')}Plugin

# Optional: Management UI class, set to None if no widget
WIDGET_CLASS = {widget_class}
'''

    (plugin_dir / "__init__.py").write_text(init_content, encoding="utf-8")

    # Create backend.py
    backend_content = f'''"""{display_name} Plugin — Backend

{{docstring for the plugin}}
"""

from pydantic import BaseModel, Field

from api.base_plugin import BasePlugin
from api.config import ConfigModel, StringField
from api.tool import ToolDef
from api.types import MCPToolResult, PluginMeta


# ── Configuration ──
{config_import}


class {name.title().replace('_', '')}Config(ConfigModel):
    """{display_name} plugin configuration"""
{config_fields}


# ── Tool Arguments ──
'''

    # Add args models for each tool
    for tool_name in tools:
        camel_name = "".join(word.capitalize()
                             for word in tool_name.split("_"))
        backend_content += f'''
class {camel_name}Args(BaseModel):
    """{tool_name} tool arguments"""
    
    input_text: str = Field(description="Input text description")
'''

    # Add plugin class
    backend_content += f'''

# ── Plugin Implementation ──


class {name.title().replace('_', '')}Plugin(BasePlugin[{config_class}]):
    """{display_name} plugin for MCP Tool Hub"""

    # Configuration
    config_class = {config_class}

    # Tool declarations
'''

    backend_content += tool_defs

    backend_content += f'''
    @property
    def meta(self) -> PluginMeta:
        return PluginMeta(
            name="{name}",
            display_name="{display_name}",
            version="1.0.0",
            description="{display_name} plugin description",
            author="Your Name",
            icon="🔧"
        )

    # Tool handlers
'''

    backend_content += tool_handlers

    (plugin_dir / "backend.py").write_text(backend_content, encoding="utf-8")

    # Create widget.py if needed
    if has_widget:
        widget_content = f'''"""{display_name} Plugin — Management UI"""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFormLayout, QLabel, QLineEdit, QVBoxLayout, QWidget

from api.base_widget import BasePluginWidget
from api.types import MCPToolResult


class {name.title().replace('_', '')}Widget(BasePluginWidget):
    """Management interface for {display_name} plugin"""

    def get_name(self) -> str:
        return "{name}"

    def create_widget(self, parent: QWidget | None = None) -> QWidget:
        container = QWidget(parent)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(20, 20, 20, 20)

        # Title
        title = QLabel("{display_name}")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title)

        # Form
        form = QFormLayout()
        self.input_edit = QLineEdit()
        self.input_edit.setPlaceholderText("Enter input...")
        form.addRow("Input:", self.input_edit)
        layout.addLayout(form)

        # Execute button
        from qfluentwidgets import PrimaryPushButton
        self.execute_btn = PrimaryPushButton("Execute")
        self.execute_btn.clicked.connect(self._on_execute)
        layout.addWidget(self.execute_btn)

        # Result label
        self.result_label = QLabel("Result will appear here")
        self.result_label.setWordWrap(True)
        layout.addWidget(self.result_label)

        layout.addStretch()
        return container

    def _on_execute(self):
        input_text = self.input_edit.text()
        if not input_text:
            self.result_label.setText("Please enter input text")
            return

        # Use typed invoke instead of string
        from .backend import {name.title().replace('_', '')}Plugin, {name.title().replace('_', '')}Args
        self.invoke(
            {name.title().replace('_', '')}Plugin.{tools[0] if tools else 'example_tool'},
            {name.title().replace('_', '')}Args(input_text=input_text)
        )

    def on_result(self, result: MCPToolResult):
        if result.is_error:
            self.result_label.setText(f"Error: {{result.content[0]['text']}}")
        else:
            self.result_label.setText(result.content[0]["text"])
'''
        (plugin_dir / "widget.py").write_text(widget_content, encoding="utf-8")

    # Create README.md
    readme_content = f'''# {display_name}

Plugin description here.

## 工具列表

| 工具名 | 说明 |
|--------|------|
{tool_examples or "| tool_name | Tool description |\n"}

## 依赖

- List any external dependencies here

## 示例

```json
{{
  "tool_name": {{
    "input_text": "example"
  }}
}}
```
'''

    (plugin_dir / "README.md").write_text(readme_content, encoding="utf-8")

    # Summary
    print(f"\n✓ Created plugin '{name}' at {plugin_dir}")
    print(f"\nFiles created:")
    print(f"  - __init__.py")
    print(f"  - backend.py")
    if has_widget:
        print(f"  - widget.py")
    print(f"  - README.md")
    print(f"\nNext steps:")
    print(f"  1. Implement your tool logic in backend.py")
    if has_widget:
        print(f"  2. Build the UI in widget.py")
    print(f"  3. Run 'python server.py --sse' to test")
    print(f"  4. Add your plugin README content")


def main():
    parser = argparse.ArgumentParser(
        description="Create a new MCP Tool Hub plugin")
    parser.add_argument(
        "plugin_name", help="Plugin identifier (no _ or . prefix)")
    parser.add_argument(
        "--display-name", help="Human-readable name", default=None)
    parser.add_argument(
        "--tools", help="Comma-separated tool names", default="")
    parser.add_argument("--widget", action="store_true",
                        help="Include PySide6 widget")
    parser.add_argument("--config", action="store_true",
                        help="Include configuration support")
    parser.add_argument("--force", action="store_true",
                        help="Overwrite existing plugin")

    args = parser.parse_args()

    name = args.plugin_name
    display_name = args.display_name or name.replace("_", " ").title()
    tools = [t.strip() for t in args.tools.split(",") if t.strip()]

    # Validate name
    if name.startswith("_") or name.startswith("."):
        print("Error: Plugin name cannot start with '_' or '.'")
        sys.exit(1)

    create_plugin(name, display_name, tools,
                  args.widget, args.config, args.force)


if __name__ == "__main__":
    main()
