"""MCP Tool Hub — 网络诊断插件测试"""

import asyncio

from plugins.network_tool import PLUGIN_CLASS


def test_net_ping():
    """测试 ping 功能"""
    plugin = PLUGIN_CLASS()
    args = plugin.net_ping.input_type(ips=["127.0.0.1", "localhost"])
    result = asyncio.run(plugin.handle_net_ping(args))
    print("=== net_ping ===")
    print(result.content[0]["text"])
    return result


def test_net_port_scan():
    """测试端口扫描"""
    plugin = PLUGIN_CLASS()
    args = plugin.net_port_scan.input_type(
        ip="127.0.0.1", ports=[22, 80, 443, 3306])
    result = asyncio.run(plugin.handle_net_port_scan(args))
    print("=== net_port_scan ===")
    print(result.content[0]["text"])
    return result


def test_net_port_check():
    """测试多 IP 端口检查"""
    plugin = PLUGIN_CLASS()
    args = plugin.net_port_check.input_type(
        ips=["127.0.0.1", "192.168.1.1"], port=80)
    result = asyncio.run(plugin.handle_net_port_check(args))
    print("=== net_port_check ===")
    print(result.content[0]["text"])
    return result


def test_net_ip_range():
    """测试 IP 段扫描"""
    plugin = PLUGIN_CLASS()
    args = plugin.net_ip_range.input_type(
        start_ip="127.0.0.1", end_ip="127.0.0.3")
    result = asyncio.run(plugin.handle_net_ip_range(args))
    print("=== net_ip_range ===")
    print(result.content[0]["text"])
    return result


def test_net_ip_range_with_ports():
    """测试 IP 段扫描（带端口）"""
    plugin = PLUGIN_CLASS()
    args = plugin.net_ip_range.input_type(
        start_ip="127.0.0.1", end_ip="127.0.0.2", ports=[80])
    result = asyncio.run(plugin.handle_net_ip_range(args))
    print("=== net_ip_range with ports ===")
    print(result.content[0]["text"])
    return result


if __name__ == "__main__":
    test_net_ping()
    test_net_port_scan()
    test_net_port_check()
    test_net_ip_range()
    test_net_ip_range_with_ports()
    print("\n=== All tests passed! ===")
