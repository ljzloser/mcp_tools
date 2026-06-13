# Modbus 读写工具

基于 pymodbus 的 Modbus TCP 读写操作，支持线圈和寄存器的完整读写。

## 功能

### 读取操作

| 工具 | 功能码 | 说明 |
|------|--------|------|
| `modbus_read_coils` | FC1 | 读取线圈状态 |
| `modbus_read_discrete` | FC2 | 读取离散输入 |
| `modbus_read_holding` | FC3 | 读取保持寄存器 |
| `modbus_read_input` | FC4 | 读取输入寄存器 |

### 写入操作

| 工具 | 功能码 | 说明 |
|------|--------|------|
| `modbus_write_coil` | FC5 | 写入单个线圈 |
| `modbus_write_register` | FC6 | 写入单个寄存器 |
| `modbus_write_coils` | FC15 | 写入多个线圈 |
| `modbus_write_registers` | FC16 | 写入多个寄存器 |

## 通用参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `host` | string | 127.0.0.1 | Modbus TCP 主机地址 |
| `port` | integer | 502 | Modbus TCP 端口 |
| `device_id` | integer | 1 | 从站/设备地址 (0-247) |
