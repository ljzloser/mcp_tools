# 文档格式转换工具

基于 [pypandoc](https://github.com/JessicaTegner/pypandoc) 的文档格式转换工具，支持 Markdown、Word DOCX 和 PDF 之间的互转。

## MCP 工具

| 工具名 | 描述 | 参数 |
|--------|------|------|
| `md_to_docx` | Markdown 转 Word DOCX | `input_path`, `output_path` |
| `docx_to_pdf` | Word DOCX 转 PDF | `input_path`, `output_path` |
| `md_to_pdf` | Markdown 转 PDF | `input_path`, `output_path` |

### 参数说明

| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| `input_path` | string | 是 | 输入文件路径 |
| `output_path` | string | 是 | 输出文件路径 |

## 依赖

### Python 包

- `pypandoc` — Pandoc 的 Python 封装

### 系统工具

- **pandoc** — 文档转换引擎（所有工具必需）
- **wkhtmltopdf** — PDF 渲染引擎（PDF 转换工具必需）

#### 安装 pandoc

```bash
# Windows
choco install pandoc
# 或从 https://pandoc.org/installing.html 下载安装包

# macOS
brew install pandoc

# Linux
sudo apt install pandoc
```

#### 安装 wkhtmltopdf

```bash
# Windows
# 从 https://wkhtmltopdf.org/downloads.html 下载安装包

# macOS
brew install wkhtmltopdf

# Linux
sudo apt install wkhtmltopdf
```

## 使用示例

### Markdown 转 DOCX

```json
{
  "tool": "md_to_docx",
  "arguments": {
    "input_path": "C:/Documents/report.md",
    "output_path": "C:/Documents/report.docx"
  }
}
```

### DOCX 转 PDF

```json
{
  "tool": "docx_to_pdf",
  "arguments": {
    "input_path": "C:/Documents/report.docx",
    "output_path": "C:/Documents/report.pdf"
  }
}
```

### Markdown 转 PDF

```json
{
  "tool": "md_to_pdf",
  "arguments": {
    "input_path": "C:/Documents/report.md",
    "output_path": "C:/Documents/report.pdf"
  }
}
```

## 错误处理

插件会在以下情况返回错误信息：

- 输入文件不存在
- pandoc 或 wkhtmltopdf 未安装
- 转换过程中发生异常（如格式不支持、文件损坏等）

错误信息中会包含安装指引，方便用户快速解决依赖问题。
