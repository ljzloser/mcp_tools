"""MCP Tool Hub — 系统监控插件

基于 psutil，提供系统资源监控能力。

工具：
  - sys_info:      获取系统概览（CPU/内存/磁盘/网络/开机时间）
  - sys_cpu:       获取 CPU 详细信息
  - sys_memory:    获取内存详细信息
  - sys_disk:      获取磁盘详细信息
  - sys_network:   获取网络信息
  - sys_processes: 获取进程 Top N
"""

from __future__ import annotations

import datetime
from typing import Any

from loguru import logger
from pydantic import BaseModel, Field

from api.base_plugin import BasePlugin
from api.tool import ToolDef
from api.types import MCPToolResult, PluginMeta


# ── 工具参数模型 ──


class SysInfoArgs(BaseModel):
    """系统概览参数（无必填参数）"""


class CpuArgs(BaseModel):
    """CPU 信息参数"""

    per_cpu: bool = Field(default=False, description="是否获取每颗核心的使用率")


class MemoryArgs(BaseModel):
    """内存信息参数（无必填参数）"""


class DiskArgs(BaseModel):
    """磁盘信息参数"""

    path: str = Field(default="", description="磁盘路径（留空则列出所有分区）")


class NetworkArgs(BaseModel):
    """网络信息参数（无必填参数）"""


class ProcessArgs(BaseModel):
    """进程列表参数"""

    sort_by: str = Field(default="memory", description="排序方式：memory(内存) 或 cpu")
    top: int = Field(default=10, description="返回前 N 个进程", ge=1, le=50)


# ── 插件实现 ──


class SystemMonitorPlugin(BasePlugin):
    """系统监控插件：提供 CPU/内存/磁盘/网络/进程等系统信息"""

    # ── 工具声明 ──
    sys_info = ToolDef("sys_info", SysInfoArgs,
                       description="获取系统概览（CPU/内存/磁盘/开机时间）")
    sys_cpu = ToolDef("sys_cpu", CpuArgs,
                      description="获取 CPU 详细信息（使用率/频率/核心数）")
    sys_memory = ToolDef("sys_memory", MemoryArgs,
                         description="获取内存详细信息（物理内存/交换内存）")
    sys_disk = ToolDef("sys_disk", DiskArgs, description="获取磁盘详细信息（使用率/IO）")
    sys_network = ToolDef("sys_network", NetworkArgs,
                          description="获取网络信息（IO流量/网卡列表）")
    sys_processes = ToolDef("sys_processes", ProcessArgs,
                            description="获取进程 Top N（按CPU或内存排序）")

    @property
    def meta(self) -> PluginMeta:
        return PluginMeta(
            name="system_monitor",
            display_name="系统监控",
            version="0.1.0",
            description="监控 CPU、内存、磁盘、网络、进程等系统资源",
            author="MCP Tool Hub",
            icon="📊",
        )

    # ── 辅助方法 ──

    @staticmethod
    def _fmt_bytes(size: int) -> str:
        """字节数格式化"""
        for unit in ("B", "KB", "MB", "GB", "TB"):
            if abs(size) < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024  # type: ignore[assignment]
        return f"{size:.1f} PB"

    def _result(self, data: dict[str, Any]) -> MCPToolResult:
        """构建文本结果"""
        import json
        text = json.dumps(data, ensure_ascii=False, indent=2)
        return MCPToolResult(content=[{"type": "text", "text": text}])

    # ── 工具实现 ──

    async def handle_sys_info(self, args: SysInfoArgs) -> MCPToolResult:
        """系统概览"""
        import psutil

        cpu = psutil.cpu_percent(interval=1)
        mem = psutil.virtual_memory()
        boot = datetime.datetime.fromtimestamp(
            psutil.boot_time()).strftime("%Y-%m-%d %H:%M:%S")
        uptime = datetime.datetime.now() - datetime.datetime.fromtimestamp(psutil.boot_time())
        uptime_str = f"{uptime.days}天 {uptime.seconds // 3600}小时 {(uptime.seconds % 3600) // 60}分钟"

        # 所有分区概览
        partitions = []
        for p in psutil.disk_partitions():
            try:
                u = psutil.disk_usage(p.mountpoint)
                partitions.append({
                    "挂载点": p.mountpoint,
                    "使用率": f"{u.percent}%",
                    "已用/总量": f"{self._fmt_bytes(u.used)} / {self._fmt_bytes(u.total)}",
                })
            except (PermissionError, OSError):
                continue

        return self._result({
            "CPU 使用率": f"{cpu}%",
            "内存使用率": f"{mem.percent}%",
            "内存": f"{self._fmt_bytes(mem.used)} / {self._fmt_bytes(mem.total)}",
            "磁盘分区": partitions,
            "开机时间": boot,
            "运行时长": uptime_str,
        })

    async def handle_sys_cpu(self, args: CpuArgs) -> MCPToolResult:
        """CPU 详细信息"""
        import psutil

        freq = psutil.cpu_freq()
        data: dict[str, Any] = {
            "物理核心数": psutil.cpu_count(logical=False),
            "逻辑核心数": psutil.cpu_count(logical=True),
            "总使用率": f"{psutil.cpu_percent(interval=1)}%",
        }
        if freq:
            data["当前频率"] = f"{freq.current:.0f} MHz"
            data["最小频率"] = f"{freq.min:.0f} MHz" if freq.min else None
            data["最大频率"] = f"{freq.max:.0f} MHz" if freq.max else None
        if args.per_cpu:
            per = psutil.cpu_percent(interval=1, percpu=True)
            data["每核使用率"] = {f"核心{i}": f"{v}%" for i, v in enumerate(per)}
        return self._result(data)

    async def handle_sys_memory(self, args: MemoryArgs) -> MCPToolResult:
        """内存详细信息"""
        import psutil

        mem = psutil.virtual_memory()
        swap = psutil.swap_memory()
        return self._result({
            "物理内存": {
                "总量": self._fmt_bytes(mem.total),
                "可用": self._fmt_bytes(mem.available),
                "已用": self._fmt_bytes(mem.used),
                "使用率": f"{mem.percent}%",
            },
            "交换内存": {
                "总量": self._fmt_bytes(swap.total),
                "已用": self._fmt_bytes(swap.used),
                "可用": self._fmt_bytes(swap.free),
                "使用率": f"{swap.percent}%",
            },
        })

    async def handle_sys_disk(self, args: DiskArgs) -> MCPToolResult:
        """磁盘详细信息"""
        import psutil

        path = args.path
        # 空路径：列出所有分区详情
        if not path:
            partitions = []
            for p in psutil.disk_partitions():
                try:
                    u = psutil.disk_usage(p.mountpoint)
                    partitions.append({
                        "挂载点": p.mountpoint,
                        "设备": p.device,
                        "文件系统": p.fstype,
                        "总量": self._fmt_bytes(u.total),
                        "已用": self._fmt_bytes(u.used),
                        "可用": self._fmt_bytes(u.free),
                        "使用率": f"{u.percent}%",
                    })
                except (PermissionError, OSError):
                    continue
            # 总磁盘IO（全局）
            io = psutil.disk_io_counters()
            data: dict[str, Any] = {"所有分区": partitions}
            if io:
                data["磁盘IO(总计)"] = {
                    "读取": self._fmt_bytes(io.read_bytes),
                    "写入": self._fmt_bytes(io.write_bytes),
                }
            return self._result(data)

        # 指定路径：查询单个分区详情
        try:
            usage = psutil.disk_usage(path)
        except FileNotFoundError:
            return MCPToolResult(
                content=[{"type": "text", "text": f"错误：路径 '{path}' 不存在"}],
                is_error=True,
            )

        io = psutil.disk_io_counters()
        data = {
            "路径": path,
            "总量": self._fmt_bytes(usage.total),
            "已用": self._fmt_bytes(usage.used),
            "可用": self._fmt_bytes(usage.free),
            "使用率": f"{usage.percent}%",
        }
        if io:
            data["磁盘IO(总计)"] = {
                "读取": self._fmt_bytes(io.read_bytes),
                "写入": self._fmt_bytes(io.write_bytes),
            }
        return self._result(data)

    async def handle_sys_network(self, args: NetworkArgs) -> MCPToolResult:
        """网络信息"""
        import psutil

        io = psutil.net_io_counters()
        addrs = psutil.net_if_addrs()
        data: dict[str, Any] = {
            "总流量": {
                "发送": self._fmt_bytes(io.bytes_sent),
                "接收": self._fmt_bytes(io.bytes_recv),
                "发送包数": io.packets_sent,
                "接收包数": io.packets_recv,
            },
            "网卡信息": {},
        }
        for iface, addr_list in addrs.items():
            ips = [
                a.address for a in addr_list
                if a.family.name in ("AF_INET", "AF_INET6") and not a.address.startswith("fe80")
            ]
            if ips:
                data["网卡信息"][iface] = ips
        return self._result(data)

    async def handle_sys_processes(self, args: ProcessArgs) -> MCPToolResult:
        """进程 Top N"""
        import psutil

        sort_key = "memory_percent" if args.sort_by == "memory" else "cpu_percent"
        procs = []
        for p in psutil.process_iter(["pid", "name", sort_key]):
            try:
                info = p.info
                procs.append({
                    "PID": info["pid"],
                    "名称": info["name"],
                    "内存%" if args.sort_by == "memory" else "CPU%": f"{info[sort_key]:.1f}%",
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        procs.sort(key=lambda x: float(
            x[list(x.keys())[-1]].rstrip("%")), reverse=True)
        return self._result({
            "排序": "按内存" if args.sort_by == "memory" else "按CPU",
            f"Top {args.top}": procs[: args.top],
        })
