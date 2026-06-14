---
name: new-plugin
description: Use when user wants to create a new MCP Tool Hub plugin — automates scaffolding with directory structure, __init__.py, backend.py, and README.md from templates
user-invocable: true
---

# New Plugin Workflow

This skill automates creating a new MCP Tool Hub plugin with proper scaffolding.

## When to Use

User asks to:
- "create a new plugin"
- "add a plugin"
- "make a new tool"
- Any variant expressing intent to create a new MCP plugin

## Input Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| `plugin_name` | Yes | Unique plugin identifier (no `_` or `.` prefix) |
| `display_name` | No | Human-readable name (defaults to plugin_name) |
| `tools` | No | Comma-separated list of tool names |
| `has_widget` | No | Whether to include a PySide6 widget (default: false) |
| `has_config` | No | Whether to include configuration support (default: false) |

## Workflow

### Step 1: Validate Input

- Check `plugin_name` doesn't start with `_` or `.`
- Check `plugin_name` doesn't already exist in `plugins/`

### Step 2: Create Directory

Create `plugins/{plugin_name}/` directory.

### Step 3: Generate Files

Generate the following files from templates:

**`__init__.py`**:
```python
from .backend import PluginClass

PLUGIN_CLASS = PluginClass
WIDGET_CLASS = None  # or WidgetClass if has_widget=true
```

**`backend.py`**:
- Plugin class with `ToolDef` declarations for each tool
- Handler methods `handle_{tool_name}`
- PluginMeta property

**`widget.py`** (if `has_widget=true`):
- `BasePluginWidget` subclass with UI components

**`README.md`**:
- Plugin description
- Tools table
- Dependencies list
- Usage examples

### Step 4: Register in Project

No manual registration needed — PluginManager auto-discovers.

## Output

- Plugin directory at `plugins/{plugin_name}/`
- All required files generated
- Summary of created files and next steps

## Example

User: `/new-plugin plugin_name=weather,tools=get_forecast;get_weather,has_widget=true`

Output: Creates `plugins/weather/` with backend.py, widget.py, __init__.py, README.md