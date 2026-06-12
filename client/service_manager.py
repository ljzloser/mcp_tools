"""MCP Tool Hub — 服务管理器

前端通过 NSSM 管理 Windows 服务；Linux 使用 systemd user service。
所有操作在子线程中执行，通过 Signal 返回主线程。
"""

from __future__ import annotations

import sys
import os
import shlex
import shutil
import subprocess
from pathlib import Path
from typing import Optional

from loguru import logger
from PySide6.QtCore import QObject, Signal, QThread

IS_WINDOWS = sys.platform == "win32"


# ── 服务状态 ──

SERVICE_STOPPED = "stopped"
SERVICE_RUNNING = "running"
SERVICE_NOT_INSTALLED = "not_installed"
SERVICE_UNKNOWN = "unknown"


if IS_WINDOWS:
    import ctypes
    from ctypes import wintypes

    # ── Win32 常量 ──
    SC_MANAGER_CONNECT = 0x0001
    SERVICE_QUERY_STATUS = 0x0004
    SC_STATUS_PROCESS_INFO = 0
    ERROR_SERVICE_DOES_NOT_EXIST = 1060
    SERVICE_STOPPED_STATE = 1
    SERVICE_START_PENDING = 2
    SERVICE_STOP_PENDING = 3
    SERVICE_RUNNING_STATE = 4
    SERVICE_CONTINUE_PENDING = 5
    SERVICE_PAUSE_PENDING = 6
    SERVICE_PAUSED_STATE = 7

    class SERVICE_STATUS_PROCESS(ctypes.Structure):
        _fields_ = [
            ("dwServiceType", wintypes.DWORD),
            ("dwCurrentState", wintypes.DWORD),
            ("dwControlsAccepted", wintypes.DWORD),
            ("dwWin32ExitCode", wintypes.DWORD),
            ("dwServiceSpecificExitCode", wintypes.DWORD),
            ("dwCheckPoint", wintypes.DWORD),
            ("dwWaitHint", wintypes.DWORD),
            ("dwProcessId", wintypes.DWORD),
            ("dwServiceFlags", wintypes.DWORD),
        ]

    def _query_windows_service_status(service_name: str) -> str:
        """通过 Windows SCM 查询服务状态"""
        advapi32 = ctypes.WinDLL("Advapi32", use_last_error=True)
        OpenSCManager = advapi32.OpenSCManagerW
        OpenSCManager.argtypes = [wintypes.LPCWSTR,
                                  wintypes.LPCWSTR, wintypes.DWORD]
        OpenSCManager.restype = wintypes.SC_HANDLE

        OpenService = advapi32.OpenServiceW
        OpenService.argtypes = [wintypes.SC_HANDLE,
                                wintypes.LPCWSTR, wintypes.DWORD]
        OpenService.restype = wintypes.SC_HANDLE

        QueryServiceStatusEx = advapi32.QueryServiceStatusEx
        QueryServiceStatusEx.argtypes = [
            wintypes.SC_HANDLE,
            wintypes.DWORD,
            ctypes.POINTER(SERVICE_STATUS_PROCESS),
            wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),
        ]
        QueryServiceStatusEx.restype = wintypes.BOOL

        CloseServiceHandle = advapi32.CloseServiceHandle
        CloseServiceHandle.argtypes = [wintypes.SC_HANDLE]
        CloseServiceHandle.restype = wintypes.BOOL

        scm_handle = OpenSCManager(None, None, SC_MANAGER_CONNECT)
        if not scm_handle:
            return SERVICE_UNKNOWN

        try:
            service_handle = OpenService(
                scm_handle, service_name, SERVICE_QUERY_STATUS)
            if not service_handle:
                error = ctypes.get_last_error()
                if error == ERROR_SERVICE_DOES_NOT_EXIST:
                    return SERVICE_NOT_INSTALLED
                return SERVICE_UNKNOWN

            try:
                status_process = SERVICE_STATUS_PROCESS()
                bytes_needed = wintypes.DWORD(0)
                success = QueryServiceStatusEx(
                    service_handle,
                    SC_STATUS_PROCESS_INFO,
                    ctypes.byref(status_process),
                    ctypes.sizeof(status_process),
                    ctypes.byref(bytes_needed),
                )
                if not success:
                    return SERVICE_UNKNOWN

                state = status_process.dwCurrentState
                if state == SERVICE_RUNNING_STATE:
                    return SERVICE_RUNNING
                if state == SERVICE_STOPPED_STATE:
                    return SERVICE_STOPPED
                return SERVICE_UNKNOWN
            finally:
                CloseServiceHandle(service_handle)
        finally:
            CloseServiceHandle(scm_handle)


class _ServiceWorker(QThread):
    """在子线程中执行 NSSM 命令"""

    finished = Signal(str, object)  # action, result

    def __init__(self, action: str, nssm_path: str, service_name: str, server_path: str = ""):
        super().__init__()
        self.action = action
        self.nssm_path = nssm_path
        self.service_name = service_name
        self.server_path = server_path

    def run(self) -> None:
        try:
            if self.action == "status":
                result = self._query_status()
            elif self.action == "install":
                result = self._install()
            elif self.action == "uninstall":
                result = self._uninstall()
            elif self.action == "start":
                result = self._start()
            elif self.action == "stop":
                result = self._stop()
            else:
                result = (False, f"未知操作: {self.action}")
            self.finished.emit(self.action, result)
        except Exception as e:
            logger.error(f"服务管理异常 [{self.action}]: {e}")
            self.finished.emit(self.action, (False, str(e)))

    def _run_nssm(self, *args: str, admin: bool = False) -> tuple[bool, str]:
        """执行 NSSM 命令

        admin=True 时通过 runas 提权（仅安装/卸载/启动/停止需要管理员权限）。
        """
        if not IS_WINDOWS:
            return (False, "仅 Windows 平台支持服务管理")

        cmd = [self.nssm_path, *args]
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=15,
                creationflags=creationflags,
            )
            output = (result.stdout or "").strip()
            error = (result.stderr or "").strip()

            if result.returncode != 0:
                # nssm 返回非零不一定代表失败（如服务不存在时 status）
                return (False, error or output or f"退出码 {result.returncode}")
            return (True, output)
        except FileNotFoundError:
            return (False, f"找不到 NSSM: {self.nssm_path}")
        except subprocess.TimeoutExpired:
            return (False, "操作超时")
        except Exception as e:
            return (False, str(e))

    def _run_command(self, cmd: list[str], cwd: str | None = None) -> tuple[bool, str]:
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=15,
                cwd=cwd,
            )
            output = (result.stdout or "").strip()
            error = (result.stderr or "").strip()

            if result.returncode != 0:
                return (False, error or output or f"退出码 {result.returncode}")
            return (True, output)
        except subprocess.TimeoutExpired:
            return (False, "操作超时")
        except FileNotFoundError:
            return (False, f"命令不存在: {cmd[0]}")
        except Exception as e:
            return (False, str(e))

    def _run_systemctl(self, *args: str) -> tuple[bool, str]:
        if shutil.which("systemctl") is None:
            return (False, "找不到 systemctl")
        return self._run_command(["systemctl", "--user", *args])

    def _service_unit_name(self) -> str:
        return f"{self.service_name}.service"

    def _service_unit_path(self) -> Path:
        return Path.home() / ".config" / "systemd" / "user" / self._service_unit_name()

    def _render_systemd_service_unit(self) -> str:
        server_path = Path(self.server_path)
        if server_path.suffix == ".py":
            exec_start = f"{shlex.quote(sys.executable)} {shlex.quote(str(server_path))} --sse"
        else:
            exec_start = f"{shlex.quote(str(server_path))} --sse"
        working_dir = shlex.quote(str(server_path.parent))
        return "\n".join([
            "[Unit]",
            "Description=MCP Tool Hub Service",
            "After=network.target",
            "",
            "[Service]",
            "Type=simple",
            f"WorkingDirectory={working_dir}",
            f"ExecStart={exec_start}",
            "Restart=on-failure",
            "RestartSec=5",
            "StandardOutput=journal",
            "StandardError=journal",
            "",
            "[Install]",
            "WantedBy=default.target",
            "",
        ])

    def _run_elevated(self, *args: str) -> tuple[bool, str]:
        """通过 ShellExecute runas 以管理员权限执行 NSSM 命令

        返回 (True, "") 表示已发起请求（无法获取实际结果）。
        """
        if not IS_WINDOWS:
            return (False, "仅 Windows 平台支持服务管理")

        import ctypes

        params = " ".join(args)
        try:
            # 构建 nssm 命令行
            cmd_line = f'"{self.nssm_path}" {params}'
            ret = ctypes.windll.shell32.ShellExecuteW(
                None, "runas", self.nssm_path, params, None, 0
            )
            if ret <= 32:
                return (False, f"提权失败 (ShellExecute 返回 {ret})，可能被用户取消")
            return (True, "")
        except Exception as e:
            return (False, str(e))

    def _query_status(self) -> tuple[bool, str]:
        """查询服务状态"""
        if not IS_WINDOWS:
            ok, output = self._run_systemctl(
                "is-active", self._service_unit_name())
            if not ok:
                normalized = output.lower()
                if ("could not be found" in normalized or "not-found" in normalized
                        or "not found" in normalized or "no such file" in normalized):
                    return (True, SERVICE_NOT_INSTALLED)
                return (True, SERVICE_UNKNOWN)

            active = output.strip().lower()
            if active == "active":
                return (True, SERVICE_RUNNING)
            if active == "inactive":
                return (True, SERVICE_STOPPED)
            return (True, SERVICE_UNKNOWN)

        status = _query_windows_service_status(self.service_name)
        if status == SERVICE_NOT_INSTALLED:
            return (True, SERVICE_NOT_INSTALLED)
        if status in (SERVICE_RUNNING, SERVICE_STOPPED):
            return (True, status)

        # 如果 Windows SCM 读取失败，再回退到 NSSM
        ok, output = self._run_nssm("status", self.service_name)
        if not ok:
            normalized = output.lower()
            if "not exist" in normalized or "service does not exist" in normalized or "找不到" in normalized:
                return (True, SERVICE_NOT_INSTALLED)
            return (True, SERVICE_UNKNOWN)

        status = output.strip().lower()
        if "service_running" in status or "running" in status:
            return (True, SERVICE_RUNNING)
        if "service_stopped" in status or "stopped" in status:
            return (True, SERVICE_STOPPED)
        return (True, SERVICE_UNKNOWN)

    def _install(self) -> tuple[bool, str]:
        """安装服务"""
        if not self.server_path:
            return (False, "未指定服务端路径")

        if not IS_WINDOWS:
            try:
                unit_path = self._service_unit_path()
                unit_path.parent.mkdir(parents=True, exist_ok=True)
                unit_path.write_text(
                    self._render_systemd_service_unit(), encoding="utf-8")
            except Exception as e:
                return (False, f"写入 systemd 单元失败: {e}")

            ok, msg = self._run_systemctl("daemon-reload")
            if not ok:
                return (False, f"重载 systemd 失败: {msg}")
            ok, msg = self._run_systemctl(
                "enable", "--now", self._service_unit_name())
            if not ok:
                return (False, f"启动服务失败: {msg}")
            return (True, "服务安装并启动请求已发送")

        # 依次执行安装 + 配置
        ok, msg = self._run_elevated(
            "install", self.service_name, f'"{self.server_path}"', "--sse")
        if not ok:
            return (False, f"安装服务失败: {msg}")

        # 配置 AppDirectory
        app_dir = os.path.dirname(self.server_path)
        self._run_elevated("set", self.service_name,
                           "AppDirectory", f'"{app_dir}"')

        # 配置 DisplayName
        self._run_elevated("set", self.service_name,
                           "DisplayName", '"MCP Tool Hub Service"')

        # 配置自动启动
        self._run_elevated("set", self.service_name,
                           "Start", "SERVICE_AUTO_START")

        return (True, "服务安装请求已发送")

    def _uninstall(self) -> tuple[bool, str]:
        """卸载服务（先停止再删除）"""
        if not IS_WINDOWS:
            self._run_systemctl("stop", self._service_unit_name())
            self._run_systemctl("disable", self._service_unit_name())
            try:
                self._service_unit_path().unlink(missing_ok=True)
            except Exception as e:
                return (False, f"删除 systemd 单元失败: {e}")
            self._run_systemctl("daemon-reload")
            return (True, "服务卸载请求已发送")

        # 先尝试停止
        self._run_elevated("stop", self.service_name)
        import time
        time.sleep(1)
        ok, msg = self._run_elevated("remove", self.service_name, "confirm")
        if not ok:
            return (False, f"卸载服务失败: {msg}")
        return (True, "服务卸载请求已发送")

    def _start(self) -> tuple[bool, str]:
        """启动服务"""
        if not IS_WINDOWS:
            ok, msg = self._run_systemctl("start", self._service_unit_name())
            if not ok:
                return (False, f"启动服务失败: {msg}")
            return (True, "服务启动请求已发送")

        ok, msg = self._run_elevated("start", self.service_name)
        if not ok:
            return (False, f"启动服务失败: {msg}")
        return (True, "服务启动请求已发送")

    def _stop(self) -> tuple[bool, str]:
        """停止服务"""
        if not IS_WINDOWS:
            ok, msg = self._run_systemctl("stop", self._service_unit_name())
            if not ok:
                return (False, f"停止服务失败: {msg}")
            return (True, "服务停止请求已发送")

        ok, msg = self._run_elevated("stop", self.service_name)
        if not ok:
            return (False, f"停止服务失败: {msg}")
        return (True, "服务停止请求已发送")


class ServiceManager(QObject):
    """服务管理器（前端使用）

    Windows 通过 NSSM 管理服务，Linux 使用 systemd user unit。
    所有操作在子线程执行，结果通过 Signal 返回。
    """

    # ── 信号 ──
    # 当前状态: running / stopped / not_installed / unknown
    status_changed = Signal(str)
    action_finished = Signal(str, bool, str)  # action, success, message

    SERVICE_NAME = "MCPToolHub"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker: Optional[_ServiceWorker] = None
        self._current_status: str = SERVICE_UNKNOWN
        self._nssm_path: str = ""
        self._server_path: str = ""

    @property
    def is_supported(self) -> bool:
        return IS_WINDOWS or shutil.which("systemctl") is not None

    @property
    def is_systemd(self) -> bool:
        return not IS_WINDOWS and shutil.which("systemctl") is not None

    def setup_paths(self, nssm_path: str, server_path: str) -> None:
        """设置 NSSM 和服务端路径（由主窗口初始化时调用）"""
        self._nssm_path = nssm_path
        self._server_path = server_path

    @property
    def current_status(self) -> str:
        return self._current_status

    def _ensure_worker_finished(self) -> None:
        """等待上一个 worker 完成"""
        if self._worker and self._worker.isRunning():
            self._worker.wait(5000)

    def _run(self, action: str) -> None:
        """启动 worker 执行操作"""
        self._ensure_worker_finished()
        self._worker = _ServiceWorker(
            action=action,
            nssm_path=self._nssm_path,
            service_name=self.SERVICE_NAME,
            server_path=self._server_path,
        )
        self._worker.finished.connect(self._on_worker_finished)
        self._worker.start()

    def _on_worker_finished(self, action: str, result: tuple) -> None:
        """Worker 完成，更新状态"""
        success, message = result

        if action == "status":
            if success:
                self._current_status = message
                self.status_changed.emit(message)
            else:
                self._current_status = SERVICE_UNKNOWN
                self.status_changed.emit(SERVICE_UNKNOWN)
        else:
            self.action_finished.emit(action, success, message)
            # 操作完成后刷新状态（延迟一下让服务状态更新）
            from PySide6.QtCore import QTimer
            QTimer.singleShot(2000, self.refresh_status)

    def refresh_status(self) -> None:
        """刷新服务状态"""
        if not self.is_supported:
            self._current_status = SERVICE_UNKNOWN
            self.status_changed.emit(SERVICE_UNKNOWN)
            return
        self._run("status")

    def install(self) -> None:
        """安装服务"""
        if not self.is_supported:
            self.action_finished.emit("install", False, "当前平台不支持服务管理")
            return
        self._run("install")

    def uninstall(self) -> None:
        """卸载服务"""
        if not self.is_supported:
            self.action_finished.emit("uninstall", False, "当前平台不支持服务管理")
            return
        self._run("uninstall")

    def start(self) -> None:
        """启动服务"""
        if not self.is_supported:
            self.action_finished.emit("start", False, "当前平台不支持服务管理")
            return
        self._run("start")

    def stop(self) -> None:
        """停止服务"""
        if not self.is_supported:
            self.action_finished.emit("stop", False, "当前平台不支持服务管理")
            return
        self._run("stop")
