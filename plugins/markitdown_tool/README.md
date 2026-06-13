# MarkItDown 文档转换

基于 [markitdown](https://github.com/microsoft/markitdown) 的多格式文档转 Markdown 工具。

## 支持格式

| 格式 | 扩展名 |
|------|--------|
| PDF | `.pdf` |
| Word | `.docx`, `.doc` |
| PowerPoint | `.pptx`, `.ppt` |
| Excel | `.xlsx`, `.xls` |
| CSV | `.csv` |
| HTML | `.html`, `.htm` |
| EPUB | `.epub` |
| 图片 | `.png`, `.jpg`, `.jpeg`, `.gif`, `.bmp`, `.tiff` |
| 音频 | `.mp3`, `.wav`, `.ogg` |
| 文本 | `.txt`, `.md`, `.json`, `.xml` |
| Jupyter | `.ipynb` |

## MCP 工具

### markitdown_convert

将本地文档转换为 Markdown。

- `input_path`: 输入文件路径
- `output_path`: 输出路径（留空则同名 .md）

### markitdown_convert_url

将网页或远程文件 URL 转换为 Markdown。

- `url`: 网页/文件 URL
- `output_path`: 保存路径（留空则仅返回内容）
