# 系统监控工具

基于 psutil，提供系统资源监控能力。

## 工具列表

| 工具名 | 说明 | 参数 |
|--------|------|------|
| sys_info | 获取系统概览 | (无) |
| sys_cpu | 获取 CPU 详情 | `per_cpu`: 是否获取每核心 |
| sys_memory | 获取内存详情 | (无) |
| sys_disk | 获取磁盘详情 | `path`: 磁盘路径 |
| sys_network | 获取网络信息 | (无) |
| sys_processes | 获取进程 Top N | `sort_by`: cpu/memory, `top`: 数量 |

## 使用示例

```
sys_info: {}
sys_cpu: {"per_cpu": true}
sys_disk: {"path": "C:"}
sys_processes: {"sort_by": "memory", "top": 10}
```