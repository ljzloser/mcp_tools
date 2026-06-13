# 图片互转工具

全格式图片互转 + ICO 编解码，基于 Qt 图像引擎。

## 功能

### image_convert — 图片格式互转

支持缩放、质量调整，兼容 Qt 可读写的所有格式。

- 输入：PNG / JPEG / BMP / WEBP / TIFF / ICO / GIF / SVG 等
- 输出：PNG / JPEG / BMP / WEBP / TIFF / ICO / GIF / PBM / PGM / PPM 等

### image_to_ico — 多图合并 ICO

将多张图片合并为多尺寸 ICO 图标文件。

- 单图模式：自动缩放到 16/32/48/64/128/256 等尺寸
- 多图模式：按原尺寸合并

### ico_to_images — ICO 提取

从 ICO 文件提取各帧为独立图片。

- 支持输出 PNG / BMP / WEBP / JPEG 格式

## 参数说明

| 参数 | 类型 | 说明 |
|------|------|------|
| `input_path` | string | 输入文件路径 |
| `output_path` | string | 输出文件路径 |
| `output_format` | string | 输出格式（留空自动推断） |
| `width` | integer | 输出宽度（留空保持比例） |
| `height` | integer | 输出高度（留空保持比例） |
| `quality` | integer | 输出质量 0-100（-1 为默认） |
