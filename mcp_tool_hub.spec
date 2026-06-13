# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec — 双入口单目录打包
输出: dist/mcp-tool-hub/
├── mcp-server.exe    (控制台模式, MCP 服务端)
├── mcp-client.exe    (窗口模式, 管理 UI)
└── _internal/        (共享依赖 + 资源)
    ├── plugins/
    └── assets/
"""

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules, collect_data_files


# ── 扫描插件依赖 ──
def scan_plugin_imports():
    """扫描所有插件的第三方依赖"""
    imports = set()
    for plugin_dir in Path("plugins").iterdir():
        if not plugin_dir.is_dir() or plugin_dir.name.startswith(("_", ".")):
            continue
        for py_file in plugin_dir.rglob("*.py"):
            try:
                content = py_file.read_text(encoding="utf-8")
                import ast
                tree = ast.parse(content)
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for a in node.names:
                            imports.add(a.name.split(".")[0])
                    elif isinstance(node, ast.ImportFrom) and node.module:
                        imports.add(node.module.split(".")[0])
            except:
                pass
    # 过滤标准库和已手动包含的
    stdlib = {
        "loguru", "pydantic", "PySide6", "qfluentwidgets",
        "api", "server", "client", "utils",
        # 标准库
        "os", "sys", "re", "typing", "pathlib", "io", "struct",
        "collections", "platform", "ast", "datetime", "json",
        "csv", "sqlite3", "base64", "subprocess", "threading",
        "concurrent", "asyncio", "abc", "functools", "itertools",
        "copy", "pickle", "shutil", "tempfile", "warnings",
        "contextlib", "dataclasses", "enum", "gc", "inspect",
        "__future__",
    }
    return sorted(imports - stdlib - {""})

plugin_deps = scan_plugin_imports()
print("插件依赖:", plugin_deps)


# ── 插件模块收集 ──
# 插件通过 importlib.import_module 动态加载，PyInstaller 无法自动发现
plugin_hiddenimports = []
for item in sorted(Path("plugins").iterdir()):
    if item.is_dir() and not item.name.startswith("_") and not item.name.startswith("."):
        if (item / "__init__.py").exists():
            plugin_hiddenimports.append(f"plugins.{item.name}")
            # 同时收集子模块
            for py_file in sorted(item.glob("*.py")):
                if py_file.stem != "__init__":
                    plugin_hiddenimports.append(f"plugins.{item.name}.{py_file.stem}")

# ── 通用 hidden imports ──
common_hiddenimports = [
    # 数据库
    "aiosqlite",
    # ASGI 服务器
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
    # MCP
    "mcp",
    "mcp.server.fastmcp",
    "mcp.server.fastmcp.tools",
    "mcp.server.fastmcp.utilities",
    # Pydantic (动态 create_model)
    "pydantic",
    "pydantic.deprecated",
    # 日志
    "loguru",
    # Qt
    "PySide6.QtWinExtras",
]
common_hiddenimports.extend(plugin_hiddenimports)
common_hiddenimports.extend(plugin_deps)

# ── 通用排除 ──
common_excludes = [
    "tkinter",
    "matplotlib",
    "numpy",
    "scipy",
    "pandas",
    "PIL",
    "cv2",
    "torch",
    "tensorflow",
    "jedi",
    "IPython",
    "jupyter",
    "notebook",
]

# ── 通用 datas ──
common_datas = [
    ("plugins", "plugins"),
    ("assets", "assets"),
]

# ================================================================
# Analysis: server
# ================================================================
a_server = Analysis(
    ["server.py"],
    pathex=[],
    binaries=[],
    datas=common_datas,
    hiddenimports=common_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=common_excludes,
    noarchive=False,
)

# ================================================================
# Analysis: client
# ================================================================
a_client = Analysis(
    ["client.py"],
    pathex=[],
    binaries=[],
    datas=common_datas,
    hiddenimports=common_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=common_excludes,
    noarchive=False,
)

# ================================================================
# 合并 PYZ (共享)
# ================================================================
pyz = PYZ(a_server.pure + a_client.pure)

# ================================================================
# EXE: mcp-server (控制台模式)
# ================================================================
exe_server = EXE(
    pyz,
    a_server.scripts,
    [],
    exclude_binaries=True,
    name="mcp-server",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,           # MCP 服务端需要控制台（stdio 模式）
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="assets/icon.ico",
)

# ================================================================
# EXE: mcp-client (窗口模式, GUI)
# ================================================================
exe_client = EXE(
    pyz,
    a_client.scripts,
    [],
    exclude_binaries=True,
    name="mcp-client",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,          # GUI 应用，无控制台窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="assets/icon.ico",
)

# ================================================================
# COLLECT: 合并到单一目录 (共享 _internal)
# ================================================================
coll = COLLECT(
    exe_server,
    exe_client,
    a_server.binaries,
    a_client.binaries,
    a_server.datas,
    a_client.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="mcp-tool-hub",
)