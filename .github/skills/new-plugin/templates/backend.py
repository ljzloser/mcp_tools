"""{{ display_name }} Plugin — Backend

{{ plugin_description }}
"""

from pydantic import BaseModel, Field

from api.base_plugin import BasePlugin
# from api.config import ConfigModel, StringField  # Uncomment if config is needed
from api.tool import ToolDef
from api.types import MCPToolResult, PluginMeta


# ── Configuration (optional) ──
# class {{ config_class_name }}(ConfigModel):
#     """{{ display_name }} plugin configuration"""
#     api_key = StringField(default="", label="API Key", description="Your API key")


# ── Tool Arguments ──

{% for tool in tools % }


class {{tool.args_model_name}}(BaseModel):
    """{{ tool.name }} tool arguments"""

    input_text: str = Field(description="Input text description")

{% endfor % }


# ── Plugin Implementation ──


class {{plugin_class_name}}(BasePlugin[None]):
    """{{ display_name }} plugin for MCP Tool Hub"""

    # Configuration (uncomment if config is needed)
    # config_class = {{ config_class_name }}

    # Tool declarations
{% for tool in tools % }
{{tool.name}} = ToolDef(
    name="{{ tool.name }}",
    args_model={{tool.args_model_name}},
    description="{{ tool.description }}"
    )
{% endfor % }


@property
def meta(self) -> PluginMeta:
    return PluginMeta(
        name="{{ plugin_name }}",
        display_name="{{ display_name }}",
        version="1.0.0",
        description="{{ plugin_description }}",
        author="{{ author }}",
        icon="🔧"
        )

    # Tool handlers
{% for tool in tools % }
 async def handle_{{tool.name}}(self, args: {{tool.args_model_name}}) -> MCPToolResult:
      """Handle {{ tool.name }} tool"""
       try:
            # TODO: Implement your tool logic here
            result = f"Result for: {args.input_text}"
            return MCPToolResult(content=[{"type": "text", "text": result}])
        except Exception as e:
            return MCPToolResult(
                content=[{"type": "text", "text": f"Error: {e}"}],
                is_error=True
            )

{% endfor % }