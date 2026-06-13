# OCR 文字识别工具插件

基于 pytesseract + Pillow，提供图片文字识别能力。

## ⚠️ 重要：系统依赖

**本插件需要安装 Tesseract OCR 引擎（系统级），必须单独安装：**

### Windows 安装

1. 下载安装包：https://github.com/UB-Mannheim/tesseract/wiki
2. 安装时勾选 "Add to PATH"（添加环境变量）
3. 或手动添加到 PATH：`此电脑` → `属性` → `高级系统设置` → `环境变量` → 系统变量 `Path` → 添加 `C:\Program Files\Tesseract-OCR`
4. **或者**：在插件设置中指定 Tesseract 路径（如 `C:\Program Files\Tesseract-OCR\tesseract.exe`）

### ⚠️ 语言包说明

**安装时勾选语言包**：下载的安装包包含可选语言包，安装时勾选要用的语言（简体中文、繁体中文、日语等）。

如果没勾选，需要手动下载语言包放入 tessdata 目录：

1. 下载语言包：https://github.com/tesseract-ocr/tessdata
2. 放入 tessdata 目录：`C:\Program Files\Tesseract-OCR\tessdata\`

常用语言包：

| 语言 | 文件名 | 代码 |
|------|--------|------|
| 简体中文 | `chi_sim.traineddata` | chi_sim |
| 繁体中文 | `chi_tra.traineddata` | chi_tra |
| 日语 | `jpn.traineddata` | jpn |
| 韩语 | `kor.traineddata` | kor |
| 法语 | `fra.traineddata` | fra |
| 德语 | `deu.traineddata` | deu |

**组合示例**: `chi_sim+eng` 可识别中英混合内容。

### Linux 安装

```bash
# Debian/Ubuntu
sudo apt install tesseract-ocr

# RHEL/CentOS
sudo yum install tesseract-ocr
```

## 配置

在插件设置页面可配置：

| 配置项 | 说明 |
|--------|------|
| `tesseract_path` | Tesseract 可执行文件路径，留空则从 PATH 环境变量查找。Windows 示例: `C:\Program Files\Tesseract-OCR\tesseract.exe` |

## 工具列表

| 工具名 | 说明 |
|--------|------|
| `ocr_recognize` | 识别图片中的文字，支持多语言 |
| `ocr_languages` | 查看 Tesseract 支持的语言列表 |

## 示例

### 识别中文英文混合图片
```json
{"image_path": "screenshot.png", "language": "chi_sim+eng"}
```

### 识别英文
```json
{"image_path": "document.png", "language": "eng", "config": "--psm 6"}
```

### 查看支持的语言
```json
{}
```

## 常用语言代码

| 代码 | 语言 |
|------|------|
| `eng` | 英语 |
| `chi_sim` | 简体中文 |
| `chi_tra` | 繁体中文 |
| `jpn` | 日语 |
| `kor` | 韩语 |
| `fra` | 法语 |
| `deu` | 德语 |
| `spa` | 西班牙语 |

**组合使用**: `chi_sim+eng` 可识别中英混合内容。