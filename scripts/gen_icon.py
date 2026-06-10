"""用 icon_tool 插件的 Qt 渲染引擎重新生成高质量 ICO（无 Pillow 依赖）"""
import sys
import os

# 无头 Qt
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from pathlib import Path

# 直接导入插件的渲染函数
sys.path.insert(0, str(Path(__file__).parent.parent))
from plugins.icon_tool.backend import _ensure_qapp, _render_svg_to_png_bytes, _encode_ico
from PySide6.QtGui import QImage

_ensure_qapp()

svg_path = "assets/icon.svg"
sizes = [16, 32, 48, 64, 128, 256]

bgra_list = []
for size in sizes:
    png_data = _render_svg_to_png_bytes(svg_path, size)
    img = QImage()
    img.loadFromData(png_data)
    img = img.convertToFormat(QImage.Format.Format_RGBA8888)
    w, h = img.width(), img.height()
    bgra = bytes(img.constBits()[:w * h * 4])
    bgra_list.append((w, h, bgra))
    print(f"  渲染 {size}x{size} OK ({len(png_data)} bytes)")

# 从大到小排列
bgra_list.sort(key=lambda x: x[0], reverse=True)

# 编码 ICO
ico_data = _encode_ico(bgra_list)
Path("assets/icon.ico").write_bytes(ico_data)
ico_size = len(ico_data)
print(f"assets/icon.ico 生成成功 ({ico_size} bytes)")

# 也保存 256px PNG
png_256 = _render_svg_to_png_bytes(svg_path, 256)
Path("assets/icon_256.png").write_bytes(png_256)
print("assets/icon_256.png 生成成功")
