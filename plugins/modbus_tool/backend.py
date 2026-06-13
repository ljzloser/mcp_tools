"""MCP Tool Hub — Modbus 读写工具插件

基于 pymodbus，提供 Modbus TCP/RTU 的常用读写操作。

工具：
  - modbus_read_coils:          读线圈 (FC1)
  - modbus_read_discrete:       读离散输入 (FC2)
  - modbus_read_holding:        读保持寄存器 (FC3)
  - modbus_read_input:          读输入寄存器 (FC4)
  - modbus_write_coil:          写单个线圈 (FC5)
  - modbus_write_register:      写单个寄存器 (FC6)
  - modbus_write_coils:         写多个线圈 (FC15)
  - modbus_write_registers:     写多个寄存器 (FC16)
"""

from __future__ import annotations

from typing import Any

from loguru import logger
from pydantic import BaseModel, Field

from api.base_plugin import BasePlugin
from api.tool import ToolDef
from api.types import MCPToolResult, PluginMeta


# ── 通用参数 ──


class _ConnectionArgs(BaseModel):
    """连接参数（嵌入其他参数模型）"""

    host: str = Field(default="127.0.0.1", description="Modbus TCP 主机地址")
    port: int = Field(default=502, description="Modbus TCP 端口")
    device_id: int = Field(default=1, ge=0, le=247,
                           description="从站/设备地址 (0-247)")
    timeout: float = Field(default=10.0, ge=1, description="连接超时(秒)")


# ── 读参数 ──


class ReadCoilsArgs(_ConnectionArgs):
    """读线圈"""

    address: int = Field(ge=0, description="起始地址")
    count: int = Field(default=1, ge=1, le=2000, description="读取数量")


class ReadDiscreteArgs(_ConnectionArgs):
    """读离散输入"""

    address: int = Field(ge=0, description="起始地址")
    count: int = Field(default=1, ge=1, le=2000, description="读取数量")


class ReadHoldingArgs(_ConnectionArgs):
    """读保持寄存器"""

    address: int = Field(ge=0, description="起始地址")
    count: int = Field(default=1, ge=1, le=125, description="读取数量")


class ReadInputArgs(_ConnectionArgs):
    """读输入寄存器"""

    address: int = Field(ge=0, description="起始地址")
    count: int = Field(default=1, ge=1, le=125, description="读取数量")


# ── 写参数 ──


class WriteCoilArgs(_ConnectionArgs):
    """写单个线圈"""

    address: int = Field(ge=0, description="线圈地址")
    value: bool = Field(description="线圈值 (true/false)")


class WriteRegisterArgs(_ConnectionArgs):
    """写单个寄存器"""

    address: int = Field(ge=0, description="寄存器地址")
    value: int = Field(ge=0, le=65535, description="寄存器值 (0-65535)")


class WriteCoilsArgs(_ConnectionArgs):
    """写多个线圈"""

    address: int = Field(ge=0, description="起始地址")
    values: list[bool] = Field(description="线圈值列表")


class WriteRegistersArgs(_ConnectionArgs):
    """写多个寄存器"""

    address: int = Field(ge=0, description="起始地址")
    values: list[int] = Field(description="寄存器值列表 (每个 0-65535)")


# ── 读取结果的格式化 ──


def _format_bits(values: list[bool], address: int) -> str:
    """格式化线圈/离散输入结果"""
    lines = [f"地址  | 值", "-----|-----"]
    for i, v in enumerate(values):
        lines.append(f"{address + i:>4} | {'ON' if v else 'OFF'}")
    return "\n".join(lines)


def _format_registers(values: list[int], address: int) -> str:
    """格式化寄存器结果（十进制 + 十六进制）"""
    lines = [f"地址  | 十进制  | 十六进制", "-----|--------|--------"]
    for i, v in enumerate(values):
        lines.append(f"{address + i:>4} | {v:>7} | 0x{v:04X}")
    return "\n".join(lines)


# ── 连接辅助 ──


async def _read_with_client(host: str, port: int, device_id: int, timeout: float, read_func) -> Any:
    """建立 TCP 连接并执行读取操作"""
    from pymodbus.client import AsyncModbusTcpClient

    client = AsyncModbusTcpClient(host=host, port=port, timeout=timeout)
    try:
        await client.connect()
        if not client.connected:
            raise ConnectionError(f"无法连接到 {host}:{port}")
        result = await read_func(client)
        return result
    finally:
        client.close()


async def _write_with_client(host: str, port: int, device_id: int, timeout: float, write_func) -> Any:
    """建立 TCP 连接并执行写入操作"""
    from pymodbus.client import AsyncModbusTcpClient

    client = AsyncModbusTcpClient(host=host, port=port, timeout=timeout)
    try:
        await client.connect()
        if not client.connected:
            raise ConnectionError(f"无法连接到 {host}:{port}")
        result = await write_func(client)
        return result
    finally:
        client.close()


def _check_error(result) -> None:
    """检查 Modbus 响应是否有错误"""
    if result.isError():
        raise RuntimeError(f"Modbus 错误: {result}")


# ── 插件实现 ──


class ModbusToolPlugin(BasePlugin):
    """Modbus 读写工具插件"""

    # ── 工具声明 ──
    modbus_read_coils = ToolDef(
        "modbus_read_coils", ReadCoilsArgs, description="读取 Modbus 线圈 (FC1)")
    modbus_read_discrete = ToolDef(
        "modbus_read_discrete", ReadDiscreteArgs, description="读取 Modbus 离散输入 (FC2)")
    modbus_read_holding = ToolDef(
        "modbus_read_holding", ReadHoldingArgs, description="读取 Modbus 保持寄存器 (FC3)")
    modbus_read_input = ToolDef(
        "modbus_read_input", ReadInputArgs, description="读取 Modbus 输入寄存器 (FC4)")
    modbus_write_coil = ToolDef(
        "modbus_write_coil", WriteCoilArgs, description="写入 Modbus 单个线圈 (FC5)")
    modbus_write_register = ToolDef(
        "modbus_write_register", WriteRegisterArgs, description="写入 Modbus 单个寄存器 (FC6)")
    modbus_write_coils = ToolDef(
        "modbus_write_coils", WriteCoilsArgs, description="写入 Modbus 多个线圈 (FC15)")
    modbus_write_registers = ToolDef(
        "modbus_write_registers", WriteRegistersArgs, description="写入 Modbus 多个寄存器 (FC16)")

    @property
    def meta(self) -> PluginMeta:
        return PluginMeta(
            name="modbus_tool",
            display_name="Modbus 工具",
            version="0.1.0",
            description="Modbus TCP 读写操作，支持线圈和寄存器",
            author="MCP Tool Hub",
            icon="🔌",
        )

    # ── 读操作 ──

    async def handle_modbus_read_coils(self, args: ReadCoilsArgs) -> MCPToolResult:
        result = await _read_with_client(
            args.host, args.port, args.device_id, args.timeout,
            lambda c: c.read_coils(
                args.address, count=args.count, device_id=args.device_id),
        )
        _check_error(result)
        text = _format_bits(result.bits[: args.count], args.address)
        return MCPToolResult(content=[{"type": "text", "text": text}])

    async def handle_modbus_read_discrete(self, args: ReadDiscreteArgs) -> MCPToolResult:
        result = await _read_with_client(
            args.host, args.port, args.device_id, args.timeout,
            lambda c: c.read_discrete_inputs(
                args.address, count=args.count, device_id=args.device_id),
        )
        _check_error(result)
        text = _format_bits(result.bits[: args.count], args.address)
        return MCPToolResult(content=[{"type": "text", "text": text}])

    async def handle_modbus_read_holding(self, args: ReadHoldingArgs) -> MCPToolResult:
        result = await _read_with_client(
            args.host, args.port, args.device_id, args.timeout,
            lambda c: c.read_holding_registers(
                args.address, count=args.count, device_id=args.device_id),
        )
        _check_error(result)
        text = _format_registers(result.registers, args.address)
        return MCPToolResult(content=[{"type": "text", "text": text}])

    async def handle_modbus_read_input(self, args: ReadInputArgs) -> MCPToolResult:
        result = await _read_with_client(
            args.host, args.port, args.device_id, args.timeout,
            lambda c: c.read_input_registers(
                args.address, count=args.count, device_id=args.device_id),
        )
        _check_error(result)
        text = _format_registers(result.registers, args.address)
        return MCPToolResult(content=[{"type": "text", "text": text}])

    # ── 写操作 ──

    async def handle_modbus_write_coil(self, args: WriteCoilArgs) -> MCPToolResult:
        result = await _write_with_client(
            args.host, args.port, args.device_id, args.timeout,
            lambda c: c.write_coil(
                args.address, args.value, device_id=args.device_id),
        )
        _check_error(result)
        value_str = "ON" if args.value else "OFF"
        return MCPToolResult(content=[{"type": "text", "text": f"已写入线圈 {args.address}: {value_str}"}])

    async def handle_modbus_write_register(self, args: WriteRegisterArgs) -> MCPToolResult:
        result = await _write_with_client(
            args.host, args.port, args.device_id, args.timeout,
            lambda c: c.write_register(
                args.address, args.value, device_id=args.device_id),
        )
        _check_error(result)
        return MCPToolResult(content=[{"type": "text", "text": f"已写入寄存器 {args.address}: {args.value} (0x{args.value:04X})"}])

    async def handle_modbus_write_coils(self, args: WriteCoilsArgs) -> MCPToolResult:
        result = await _write_with_client(
            args.host, args.port, args.device_id, args.timeout,
            lambda c: c.write_coils(
                args.address, args.values, device_id=args.device_id),
        )
        _check_error(result)
        values_str = ", ".join("ON" if v else "OFF" for v in args.values)
        return MCPToolResult(content=[{"type": "text", "text": f"已写入线圈 {args.address}-{args.address + len(args.values) - 1}: [{values_str}]"}])

    async def handle_modbus_write_registers(self, args: WriteRegistersArgs) -> MCPToolResult:
        result = await _write_with_client(
            args.host, args.port, args.device_id, args.timeout,
            lambda c: c.write_registers(
                args.address, args.values, device_id=args.device_id),
        )
        _check_error(result)
        values_str = ", ".join(f"{v} (0x{v:04X})" for v in args.values)
        return MCPToolResult(content=[{"type": "text", "text": f"已写入寄存器 {args.address}-{args.address + len(args.values) - 1}: [{values_str}]"}])

    async def on_load(self) -> None:
        logger.info("ModbusToolPlugin 加载完成")

    async def on_unload(self) -> None:
        logger.info("ModbusToolPlugin 已卸载")
