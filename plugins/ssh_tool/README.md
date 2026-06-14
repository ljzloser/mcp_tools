# SSH 远程连接工具

基于 paramiko，提供 SSH 连接和命令执行能力。

## 工具列表

| 工具名 | 说明 | 参数 |
|--------|------|------|
| ssh_save_config | 保存 SSH 配置 | `name`, `host`, `port`, `username`, `password` |
| ssh_delete_config | 删除 SSH 配置 | `name` |
| ssh_list_configs | 列出所有配置 | (无) |
| ssh_update_cipher | 修改加密密钥 | `old_key`, `new_key` |
| ssh_exec | 执行远程命令 | `name`, `command` |
| ssh_sftp_put | SFTP 上传文件 | `name`, `local_path`, `remote_path` |
| ssh_sftp_get | SFTP 下载文件 | `name`, `remote_path`, `local_path` |

## 使用示例

```
ssh_save_config: {"name": "my-server", "host": "192.168.1.100", "port": 22, "username": "root", "password": "xxx"}
ssh_exec: {"name": "my-server", "command": "ls -la"}
ssh_sftp_put: {"name": "my-server", "local_path": "data.txt", "remote_path": "/tmp/data.txt"}
```

> 注意：密码会以加密形式存储在本地数据库中。