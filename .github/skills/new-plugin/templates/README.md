# {{ display_name }}

{{ plugin_description }}

## 工具列表

| 工具名 | 说明 |
|--------|------|
{% for tool in tools %}
| {{ tool.name }} | {{ tool.description }} |
{% endfor %}

## 依赖

- List any external dependencies here (e.g., `pip install package`)

## 系统依赖

- If there are any system-level dependencies (e.g., Tesseract, Node.js), list them here

## 配置

If the plugin has configuration, describe the config fields here.

## 示例

```json
{
  "{{ tools[0].name }}": {
    "input_text": "example"
  }
}
```