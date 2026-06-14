# 网络诊断工具

提供网络连通性和端口检测能力。

## 工具列表

| 工具名 | 说明 | 参数 |
|--------|------|------|
| net_ping | 检测 IP 是否可达 | `ips`: IP 地址列表 |
| net_port_scan | 扫描 IP 开放端口 | `ip`: 目标IP, `ports`: 端口列表 |
| net_port_check | 多 IP 检查某端口是否开放 | `ips`: IP列表, `port`: 端口号 |
| net_ip_range | 扫描 IP 段存活主机 | `start_ip`: 起始IP, `end_ip`: 结束IP |

## 使用示例

```
net_ping: ["8.8.8.8", "1.1.1.1"]
net_port_scan: {"ip": "192.168.1.1", "ports": [22, 80, 443]}
net_port_check: {"ips": ["10.0.0.1", "10.0.0.2"], "port": 22}
net_ip_range: {"start_ip": "192.168.1.1", "end_ip": "192.168.1.254"}
```