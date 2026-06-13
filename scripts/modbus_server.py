#!/usr/bin/env python
"""Modbus TCP 从站模拟器

启动一个本地 Modbus TCP 服务器，用于测试 MCP Modbus 工具。
运行后AI可以通过 modbus_read_*/modbus_write_* 工具访问。

用法:
    python modbus_server.py              # 默认端口 5020 (避免占用 502)
    python modbus_server.py 5021         # 自定义端口

注意: 需要先启动此服务器，再让 AI 调用 Modbus MCP 工具
"""

from pymodbus.server import StartAsyncTcpServer
from pymodbus import ModbusDeviceIdentification
from pymodbus.datastore import (
    ModbusDeviceContext,
    ModbusSequentialDataBlock,
    ModbusServerContext,
)
from loguru import logger
import sys
import asyncio
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)


def create_datastore():
    """创建 Modbus 数据存储 (pymodbus 3.x 地址从 1 开始)"""
    coils = ModbusSequentialDataBlock(1, [False] * 100)
    discrete = ModbusSequentialDataBlock(1, [i % 2 == 0 for i in range(100)])
    holding = ModbusSequentialDataBlock(1, list(range(100)))
    input_regs = ModbusSequentialDataBlock(1, [100 - i for i in range(100)])

    return ModbusDeviceContext(
        co=coils,
        di=discrete,
        hr=holding,
        ir=input_regs,
    )


def create_identity() -> ModbusDeviceIdentification:
    """创建设备标识"""
    info = {
        0x00: "MCP Tool Hub",   # VendorName
        0x01: "MCT",            # ProductCode
        0x02: "https://github.com/mcp-tool-hub",  # VendorUrl
        0x03: "Modbus Simulator",  # ProductName
        0x04: "Simulator v1.0",    # ModelName
        0x05: "1.0.0",            # MajorMinorRevision
        0x06: "1",                # Revision
    }
    return ModbusDeviceIdentification(info=info)


async def run_server(port: int):
    """启动 Modbus TCP 服务器"""
    store = create_datastore()
    context = ModbusServerContext(devices=store)

    print(f"{'=' * 50}")
    print(f"  Modbus TCP 从站模拟器")
    print(f"{'=' * 50}")
    print(f"  主机: 127.0.0.1")
    print(f"  端口: {port}")
    print(f"  从站ID: 1")
    print(f"{'=' * 50}")
    print()
    print("按 Ctrl+C 停止服务器")
    print()

    await StartAsyncTcpServer(
        context=context,
        identity=create_identity(),
        address=("127.0.0.1", port),
    )


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5020
    logger.info(f"启动 Modbus TCP 服务器 (端口 {port})...")
    try:
        asyncio.run(run_server(port))
    except KeyboardInterrupt:
        print("\n服务器已停止")


if __name__ == "__main__":
    main()
