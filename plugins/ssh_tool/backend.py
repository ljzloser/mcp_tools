"""MCP Tool Hub — SSH 远程连接插件

基于 paramiko，提供 SSH 连接和命令执行能力。

工具：
  - ssh_add_config:     添加 SSH 连接配置
  - ssh_delete_config:  删除 SSH 连接配置
  - ssh_list_configs:   列出所有 SSH 配置（密码掩码）
  - ssh_update_cipher:  修改加密密钥（先用旧 key 解密，再用新 key 加密）
  - ssh_exec:           执行远程命令
  - ssh_sftp_put:       SFTP 上传文件
  - ssh_sftp_get:       SFTP 下载文件
"""

from __future__ import annotations

import base64
import hashlib
import json
from typing import Any

from cryptography.fernet import Fernet
from loguru import logger
from pydantic import BaseModel, Field

from api.base_plugin import BasePlugin
from api.config import ConfigModel, StringField
from api.tool import EmptyArgs, ToolDef
from api.types import MCPToolResult, PluginMeta


# ── 工具参数模型 ──


class AddConfigArgs(EmptyArgs):
    """添加 SSH 配置参数"""

    name: str = Field(description="配置名称（唯一标识）")
    host: str = Field(description="主机地址")
    port: int = Field(default=22, description="SSH 端口")
    username: str = Field(description="用户名")
    password: str = Field(description="密码")


class DeleteConfigArgs(EmptyArgs):
    """删除 SSH 配置参数"""

    name: str = Field(description="要删除的配置名称")


class UpdateCipherArgs(EmptyArgs):
    """修改加密密钥参数"""

    new_key: str = Field(description="新的加密密钥（任意字符串）")


class ExecArgs(EmptyArgs):
    """执行命令参数"""

    name: str = Field(description="配置名称")
    command: str = Field(description="要执行的命令")
    timeout: int = Field(default=30, description="超时时间（秒）")


class SftpPutArgs(EmptyArgs):
    """SFTP 上传参数"""

    name: str = Field(description="配置名称")
    local_path: str = Field(description="本地文件路径")
    remote_path: str = Field(description="远程目标路径")


class SftpGetArgs(EmptyArgs):
    """SFTP 下载参数"""

    name: str = Field(description="配置名称")
    remote_path: str = Field(description="远程文件路径")
    local_path: str = Field(description="本地保存路径")


# ── 插件配置模型 ──


class SSHConfig(ConfigModel):
    """SSH 插件配置"""

    cipher_key = StringField(
        default="",
        label="加密密钥",
        description="用于加密保存的密码。需要手动设置，设置后可用于保存 SSH 配置。"
    )
    connections = StringField(
        default="[]",
        label="SSH 配置列表",
        description="JSON 格式的连接配置列表（密码已加密）"
    )


# ── 插件实现 ──


class SSHPlugin(BasePlugin[SSHConfig]):
    """SSH 远程连接插件"""

    config_class = SSHConfig

    # 用于跟踪 key 变更
    _last_cipher_key: str = ""

    # ── 工具声明 ──
    ssh_save_config = ToolDef("ssh_save_config", AddConfigArgs,
                              description="保存 SSH 连接配置（名称不存在则添加，存在则更新）")
    ssh_delete_config = ToolDef("ssh_delete_config", DeleteConfigArgs,
                                description="删除 SSH 连接配置")
    ssh_list_configs = ToolDef("ssh_list_configs", EmptyArgs,
                               description="列出所有 SSH 配置（密码已掩码）")
    ssh_update_cipher = ToolDef("ssh_update_cipher", UpdateCipherArgs,
                                description="修改加密密钥（先用旧 key 解密，再用新 key 重新加密）")
    ssh_exec = ToolDef("ssh_exec", ExecArgs,
                       description="在远程主机执行命令",
                       dangerous=True)
    ssh_sftp_put = ToolDef("ssh_sftp_put", SftpPutArgs,
                           description="SFTP 上传文件到远程主机",
                           dangerous=True)
    ssh_sftp_get = ToolDef("ssh_sftp_get", SftpGetArgs,
                           description="从远程主机下载文件",
                           dangerous=True)

    @property
    def meta(self) -> PluginMeta:
        return PluginMeta(
            name="ssh_tool",
            display_name="SSH 远程连接",
            version="0.1.0",
            description="SSH 连接、远程命令执行、SFTP 文件传输",
            author="MCP Tool Hub",
            icon="🔐",
        )

    # ── 加密/解密辅助 ──

    def _derive_key(self, password: str) -> bytes:
        """把任意字符串转成 Fernet 需要的 32 字节 key"""
        return base64.urlsafe_b64encode(hashlib.sha256(password.encode()).digest())

    def _get_cipher(self) -> Fernet | None:
        """获取 Fernet 加密器，无 key 返回 None"""
        key = self.config.cipher_key if self.config else ""
        if not key:
            return None
        try:
            derived = self._derive_key(key)
            return Fernet(derived)
        except Exception:
            return None

    def _encrypt(self, plain: str) -> str:
        """加密明文，无 key 则失败"""
        cipher = self._get_cipher()
        if not cipher:
            raise ValueError("请先设置加密密钥")
        return base64.b64encode(cipher.encrypt(plain.encode())).decode()

    def _decrypt(self, encrypted: str) -> str:
        """解密密文，无 key 则失败"""
        cipher = self._get_cipher()
        if not cipher:
            raise ValueError("请先设置加密密钥")
        return cipher.decrypt(base64.b64decode(encrypted.encode())).decode()

    def _get_connections(self) -> list[dict[str, Any]]:
        """获取连接列表"""
        data = self.config.connections if self.config else "[]"
        try:
            return json.loads(data or "[]")
        except json.JSONDecodeError:
            return []

    def _save_connections(self, conns: list[dict[str, Any]]) -> None:
        """保存连接列表（修改配置后调用 save_config 保存）"""
        if self.config:
            self.config.connections = json.dumps(conns, ensure_ascii=False)

    def _result(self, data: Any) -> MCPToolResult:
        """构建文本结果"""
        text = json.dumps(data, ensure_ascii=False, indent=2)
        return MCPToolResult(content=[{"type": "text", "text": text}])

    def on_config_changed(self, config: SSHConfig) -> None:
        """配置变更回调：检测 key 变化并重新加密"""
        new_key = config.cipher_key if config else ""
        if new_key and new_key != self._last_cipher_key and self._last_cipher_key:
            # key 变更了，需要重新加密所有密码
            conns = self._get_connections()
            try:
                old_cipher = Fernet(self._derive_key(self._last_cipher_key))
                new_cipher = Fernet(self._derive_key(new_key))
                for c in conns:
                    if "password" in c and c["password"]:
                        decrypted = old_cipher.decrypt(
                            base64.b64decode(c["password"]))
                        c["password"] = base64.b64encode(
                            new_cipher.encrypt(decrypted)).decode()
                # 保存重新加密后的配置
                if self._save_config_callback:
                    import asyncio
                    asyncio.create_task(self._save_config_callback({
                        "cipher_key": new_key,
                        "connections": json.dumps(conns, ensure_ascii=False)
                    }))
            except Exception:
                # 忽略错误，保留原状
                pass
        self._last_cipher_key = new_key

    # ── 工具实现 ──

    async def handle_ssh_save_config(self, args: AddConfigArgs) -> MCPToolResult:
        """保存 SSH 配置（添加或更新）"""
        if not self.config or not self.config.cipher_key:
            return MCPToolResult(
                content=[{"type": "text", "text": "错误：请先设置加密密钥"}],
                is_error=True
            )

        conns = self._get_connections()
        encrypted_password = self._encrypt(args.password)

        # 检查名称是否存在，存在则更新，不存在则添加
        found = False
        for i, c in enumerate(conns):
            if c.get("name") == args.name:
                conns[i] = {
                    "name": args.name,
                    "host": args.host,
                    "port": args.port,
                    "username": args.username,
                    "password": encrypted_password,
                }
                found = True
                break

        if not found:
            conns.append({
                "name": args.name,
                "host": args.host,
                "port": args.port,
                "username": args.username,
                "password": encrypted_password,
            })

        self._save_connections(conns)
        await self.save_config()
        action = "已更新" if found else "已添加"
        return self._result({"status": "ok", "message": f"配置 '{args.name}' {action}"})

    async def handle_ssh_delete_config(self, args: DeleteConfigArgs) -> MCPToolResult:
        """删除 SSH 配置"""
        conns = self._get_connections()
        new_conns = [c for c in conns if c.get("name") != args.name]
        if len(new_conns) == len(conns):
            return MCPToolResult(
                content=[{"type": "text", "text": f"错误：配置 '{args.name}' 不存在"}],
                is_error=True
            )
        self._save_connections(new_conns)
        await self.save_config()
        return self._result({"status": "ok", "message": f"配置 '{args.name}' 已删除"})

    async def handle_ssh_list_configs(self, args: EmptyArgs) -> MCPToolResult:
        """列出所有 SSH 配置"""
        if not self.config or not self.config.cipher_key:
            return MCPToolResult(
                content=[{"type": "text", "text": "请先设置加密密钥"}],
                is_error=False
            )

        conns = self._get_connections()
        # 密码掩码
        safe_conns = []
        for c in conns:
            safe_conns.append({
                "name": c.get("name"),
                "host": c.get("host"),
                "port": c.get("port", 22),
                "username": c.get("username"),
                "password": "******",
            })
        return self._result({"configs": safe_conns, "count": len(safe_conns)})

    async def handle_ssh_update_cipher(self, args: UpdateCipherArgs) -> MCPToolResult:
        """修改加密密钥（只更新配置，保存时统一处理）"""
        if not self.config:
            return MCPToolResult(
                content=[{"type": "text", "text": "错误：配置未加载"}],
                is_error=True
            )

        # 验证新 key 是否有效
        try:
            Fernet(self._derive_key(args.new_key))
        except Exception:
            return MCPToolResult(
                content=[{"type": "text", "text": "错误：无效的密钥"}],
                is_error=True
            )

        # 更新配置，save_config 会触发 on_config_changed
        self.config.cipher_key = args.new_key
        await self.save_config()
        return self._result({"status": "ok", "message": "密钥已更新"})

    def _find_config(self, name: str) -> dict[str, Any] | None:
        """根据名称查找配置"""
        for c in self._get_connections():
            if c.get("name") == name:
                return c
        return None

    async def handle_ssh_exec(self, args: ExecArgs) -> MCPToolResult:
        """执行远程命令"""
        cfg = self._find_config(args.name)
        if not cfg:
            return MCPToolResult(
                content=[{"type": "text", "text": f"错误：配置 '{args.name}' 不存在"}],
                is_error=True
            )

        try:
            password = self._decrypt(cfg["password"])
        except Exception:
            return MCPToolResult(
                content=[{"type": "text", "text": "错误：密码解密失败，请检查密钥"}],
                is_error=True
            )

        import paramiko
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        try:
            client.connect(
                hostname=cfg["host"],
                port=cfg.get("port", 22),
                username=cfg["username"],
                password=password,
                timeout=10,
            )
            stdin, stdout, stderr = client.exec_command(
                args.command, timeout=args.timeout)
            out = stdout.read().decode("utf-8", errors="replace")
            err = stderr.read().decode("utf-8", errors="replace")
            client.close()

            result = {"stdout": out, "stderr": err,
                      "exit_code": stdout.channel.recv_exit_status()}
            return self._result(result)
        except Exception as e:
            return MCPToolResult(
                content=[{"type": "text", "text": f"连接或执行失败：{str(e)}"}],
                is_error=True
            )

    async def handle_ssh_sftp_put(self, args: SftpPutArgs) -> MCPToolResult:
        """SFTP 上传文件"""
        cfg = self._find_config(args.name)
        if not cfg:
            return MCPToolResult(
                content=[{"type": "text", "text": f"错误：配置 '{args.name}' 不存在"}],
                is_error=True
            )

        try:
            password = self._decrypt(cfg["password"])
        except Exception:
            return MCPToolResult(
                content=[{"type": "text", "text": "错误：密码解密失败，请检查密钥"}],
                is_error=True
            )

        import paramiko
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        try:
            client.connect(
                hostname=cfg["host"],
                port=cfg.get("port", 22),
                username=cfg["username"],
                password=password,
                timeout=10,
            )
            sftp = client.open_sftp()
            sftp.put(args.local_path, args.remote_path)
            sftp.close()
            client.close()
            return self._result({"status": "ok", "message": f"已上传到 {args.remote_path}"})
        except Exception as e:
            return MCPToolResult(
                content=[{"type": "text", "text": f"上传失败：{str(e)}"}],
                is_error=True
            )

    async def handle_ssh_sftp_get(self, args: SftpGetArgs) -> MCPToolResult:
        """SFTP 下载文件"""
        cfg = self._find_config(args.name)
        if not cfg:
            return MCPToolResult(
                content=[{"type": "text", "text": f"错误：配置 '{args.name}' 不存在"}],
                is_error=True
            )

        try:
            password = self._decrypt(cfg["password"])
        except Exception:
            return MCPToolResult(
                content=[{"type": "text", "text": "错误：密码解密失败，请检查密钥"}],
                is_error=True
            )

        import paramiko
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        try:
            client.connect(
                hostname=cfg["host"],
                port=cfg.get("port", 22),
                username=cfg["username"],
                password=password,
                timeout=10,
            )
            sftp = client.open_sftp()
            sftp.get(args.remote_path, args.local_path)
            sftp.close()
            client.close()
            return self._result({"status": "ok", "message": f"已下载到 {args.local_path}"})
        except Exception as e:
            return MCPToolResult(
                content=[{"type": "text", "text": f"下载失败：{str(e)}"}],
                is_error=True
            )
