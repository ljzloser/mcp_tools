"""MCP Tool Hub — {{ display_name }} Plugin"""

from .backend import {{plugin_class_name}}
# from .widget import {{ widget_class_name }}  # Uncomment if widget is needed

# Required: Backend plugin class
PLUGIN_CLASS = {{plugin_class_name}}

# Optional: Management UI class, set to None if no widget
WIDGET_CLASS = None  # or {{ widget_class_name }}
