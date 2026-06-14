"""MCP Tool Hub — 网络诊断插件

提供网络连通性和端口检测能力。

工具：
  - net_ping:        检测 IP 是否可达
  - net_port_scan:   扫描 IP 开放端口
  - net_port_check:  多 IP 检查某端口是否开放
  - net_ip_range:    扫描 IP 段存活主机
"""

from __future__ import annotations

import ipaddress
import socket
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from pydantic import Field

from api.base_plugin import BasePlugin
from api.tool import EmptyArgs, ToolDef
from api.types import MCPToolResult, PluginMeta


# ── 工具参数模型 ──


class PingArgs(EmptyArgs):
    """ping 检测参数"""

    ips: list[str] = Field(description="要检测的 IP 地址列表")


class PortScanArgs(EmptyArgs):
    """端口扫描参数"""

    ip: str = Field(description="目标 IP 地址")
    ports: list[int] = Field(description="要检测的端口列表，如 [22, 80, 443]")


class PortCheckArgs(EmptyArgs):
    """多 IP 端口检测参数"""

    ips: list[str] = Field(description="要检测的 IP 地址列表")
    port: int = Field(description="要检测的端口号")


class IpRangeArgs(EmptyArgs):
    """IP 段扫描参数"""

    start_ip: str = Field(description="起始 IP")
    end_ip: str = Field(description="结束 IP")
    ports: list[int] = Field(default=[], description="可选：检测这些端口是否开放")


# ── 插件实现 ──


class NetworkToolPlugin(BasePlugin):
    """网络诊断插件"""

    # ── 工具声明 ──
    net_ping = ToolDef("net_ping", PingArgs,
                       description="检测 IP 是否可达（使用 ping 命令）")
    net_port_scan = ToolDef("net_port_scan", PortScanArgs,
                            description="扫描 IP 开放端口")
    net_port_check = ToolDef("net_port_check", PortCheckArgs,
                             description="多 IP 检查某端口是���开放")
    net_ip_range = ToolDef("net_ip_range", IpRangeArgs,
                           description="扫描 IP 段存活主机")

    @property
    def meta(self) -> PluginMeta:
        return PluginMeta(
            name="network_tool",
            display_name="网络诊断",
            version="0.1.0",
            description="检测 IP 连通性、扫描端口、IP 段探测",
            author="MCP Tool Hub",
            icon="🌐",
        )

    # ── 辅助方法 ──

    def _ping(self, ip: str, timeout: int = 2) -> dict[str, Any]:
        """ping 一个 IP"""
        try:
            # Windows 用 -n，Linux 用 -c
            result = subprocess.run(
                ["ping", "-n", "1", "-w", str(timeout * 1000), ip]
                if socket.gethostname() != "Linux" else
                ["ping", "-c", "1", "-W", str(timeout), ip],
                capture_output=True,
                timeout=timeout + 1,
            )
            success = result.returncode == 0
            return {"ip": ip, "reachable": success, "error": None}
        except subprocess.TimeoutExpired:
            return {"ip": ip, "reachable": False, "error": "超时"}
        except Exception as e:
            return {"ip": ip, "reachable": False, "error": str(e)}

    def _check_port(self, ip: str, port: int, timeout: int = 2) -> dict[str, Any]:
        """检测端口是否开放"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        try:
            result = sock.connect_ex((ip, port))
            open_port = result == 0
            return {"ip": ip, "port": port, "open": open_port}
        except socket.timeout:
            return {"ip": ip, "port": port, "open": False, "error": "超时"}
        except Exception as e:
            return {"ip": ip, "port": port, "open": False, "error": str(e)}
        finally:
            sock.close()

    def _result(self, data: Any) -> MCPToolResult:
        import json
        text = json.dumps(data, ensure_ascii=False, indent=2)
        return MCPToolResult(content=[{"type": "text", "text": text}])

    # ── 工具实现 ──

    async def handle_net_ping(self, args: PingArgs) -> MCPToolResult:
        """ping 检测多个 IP"""
        results = []
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(self._ping, ip): ip for ip in args.ips}
            for future in as_completed(futures):
                results.append(future.result())
        return self._result({"results": results, "reachable": [r["ip"] for r in results if r["reachable"]]})

    async def handle_net_port_scan(self, args: PortScanArgs) -> MCPToolResult:
        """扫描端口"""
        results = []
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(
                self._check_port, args.ip, port): port for port in args.ports}
            for future in as_completed(futures):
                results.append(future.result())
        open_ports = [r["port"] for r in results if r.get("open")]
        return self._result({
            "ip": args.ip,
            "results": results,
            "open_ports": open_ports,
            "summary": f"{len(open_ports)}/{len(args.ports)} 端口开放"
        })

    async def handle_net_port_check(self, args: PortCheckArgs) -> MCPToolResult:
        """多 IP 检查某端口"""
        results = []
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(
                self._check_port, ip, args.port): ip for ip in args.ips}
            for future in as_completed(futures):
                results.append(future.result())
        open_ips = [r["ip"] for r in results if r.get("open")]
        return self._result({
            "port": args.port,
            "results": results,
            "open_ips": open_ips,
            "summary": f"{len(open_ips)}/{len(args.ips)} IP 的端口开放"
        })

    async def handle_net_ip_range(self, args: IpRangeArgs) -> MCPToolResult:
        """扫描 IP 段"""
        try:
            start = ipaddress.ip_address(args.start_ip)
            end = ipaddress.ip_address(args.end_ip)
        except ValueError as e:
            return self._result({"error": f"IP 地址无效: {e}"})

        # 生成 IP 列表（限制范围防止扫描过多）
        ip_list = []
        current = start
        while current <= end and len(ip_list) < 256:
            ip_list.append(str(current))
            current = ipaddress.ip_address(int(current) + 1)

        if args.ports:
            # 带端口检测：每个 IP 检测指定端口
            results = []
            with ThreadPoolExecutor(max_workers=20) as executor:
                tasks = []
                for ip in ip_list:
                    for port in args.ports:
                        tasks.append(
                            (ip, port, executor.submit(self._check_port, ip, port)))
                for ip, port, future in tasks:
                    r = future.result()
                    r["ip"] = ip
                    r["port"] = port
                    results.append(r)
            # 汇总：哪些 IP 至少有一个端口开放
            ip_ports = {}
            for r in results:
                if r.get("open"):
                    if r["ip"] not in ip_ports:
                        ip_ports[r["ip"]] = []
                    ip_ports[r["ip"]].append(r["port"])
            alive = [{"ip": ip, "open_ports": ports}
                     for ip, ports in ip_ports.items()]
            return self._result({"start": args.start_ip, "end": args.end_ip, "alive": alive, "count": len(alive)})
        else:
            # 只 ping 检测存活
            results = []
            with ThreadPoolExecutor(max_workers=20) as executor:
                futures = {executor.submit(
                    self._ping, ip): ip for ip in ip_list}
                for future in as_completed(futures):
                    results.append(future.result())
            alive = [r["ip"] for r in results if r["reachable"]]
            return self._result({"start": args.start_ip, "end": args.end_ip, "alive": alive, "count": len(alive)})
