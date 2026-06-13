# QR 码 / 条码 生成 + 解码

基于 qrcode、python-barcode、pyzbar 等实现。

## 工具

### qrbarcode_generate_qr — 生成 QR 码

- `content`: 内容（文本/URL）
- `size`: 图片尺寸（默认 256px）
- `output_path`: 保存路径（留空返回 base64）
- `fill_color` / `back_color`: 前景/背景色

### qrbarcode_generate_barcode — 生成条码

- `content`: 条码内容
- `barcode_type`: 类型
- `output_path`: 保存路径（留空返回 base64）

### qrbarcode_decode — 识别解码

- `image_path`: 图片路径
- 支持 QR 码 + 所有条码类型

## 支持的条码类型

| 类型 | 说明 |
|------|------|
| Code128 | 通用 ASCII 条码 |
| Code39 | 字母数字条码 |
| EAN13 | 商品条码（13 位） |
| EAN8 | 商品条码（8 位） |
| UPC-A | 美国商品条码 |
| ITF | 交叉二五码 |
| CODABAR | 图书/血库条码 |
