"""MCP Tool Hub — 基于 httpx + QObject 的异步 HTTP 客户端

UI 侧所有与后端管理 API 的通信统一通过此类完成。
请求在后台事件循环中执行，响应通过 Qt Signal 返回主线程。
"""

from __future__ import annotations

import asyncio
import threading
from typing import Any

import httpx
from loguru import logger
from PySide6.QtCore import QObject, Signal


class AsyncHttpClient(QObject):
    """
    基于 httpx + QObject 的异步 HTTP 客户端

    使用方式：
        client = AsyncHttpClient("http://127.0.0.1:9020")
        client.request_finished.connect(on_response)
        client.request_failed.connect(on_error)
        client.get("/plugins")

    特点：
    - 内部维护独立事件循环线程
    - 请求在后台线程执行，不阻塞 UI
    - 响应通过 Qt Signal 返回主线程
    - 支持请求 ID 追踪，区分并发请求
    """

    # ── 信号定义 ──
    request_finished = Signal(int, int, object)
    #                     request_id, status_code, response_data(dict)

    request_failed = Signal(int, str)
    #                     request_id, error_message

    # ── 构造 ──
    def __init__(self, base_url: str = "http://127.0.0.1:9020", parent=None):
        super().__init__(parent)
        self._base_url = base_url.rstrip("/")
        self._request_counter = 0
        self._pending: dict[int, str] = {}  # request_id → endpoint

        # 后台线程 + 事件循环
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._client: httpx.AsyncClient | None = None
        self._started = threading.Event()

        self._start_background_loop()

    def _start_background_loop(self) -> None:
        """启动后台事件循环线程"""
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        self._started.wait(timeout=5.0)

    def _run_loop(self) -> None:
        """后台线程运行的事件循环"""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

        # 同步初始化 HTTP 客户端（AsyncClient.__init__ 不依赖事件循环）
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=httpx.Timeout(10.0),
        )
        self._started.set()

        try:
            self._loop.run_forever()
        except Exception:
            logger.exception("AsyncHttpClient 后台事件循环异常退出")
        finally:
            self._cleanup_loop()

    def _cleanup_loop(self) -> None:
        """清理事件循环资源"""
        # 取消所有待处理任务
        pending = asyncio.all_tasks(self._loop)
        for task in pending:
            task.cancel()
        if pending:
            self._loop.run_until_complete(
                asyncio.gather(*pending, return_exceptions=True)
            )
        # 关闭 HTTP 客户端
        if self._client:
            self._loop.run_until_complete(self._client.aclose())
            self._client = None
        self._loop.close()

    # ── 公开方法（非阻塞，信号驱动）──

    def get(self, endpoint: str, params: dict | None = None) -> int:
        """发起 GET 请求，返回 request_id"""
        return self._enqueue("GET", endpoint, params=params)

    def post(self, endpoint: str, body: dict | None = None) -> int:
        """发起 POST 请求，返回 request_id"""
        return self._enqueue("POST", endpoint, body=body)

    def put(self, endpoint: str, body: dict | None = None) -> int:
        """发起 PUT 请求，返回 request_id"""
        return self._enqueue("PUT", endpoint, body=body)

    def delete(self, endpoint: str, params: dict | None = None) -> int:
        """发起 DELETE 请求，返回 request_id"""
        return self._enqueue("DELETE", endpoint, params=params)

    # ── 内部实现 ──

    def _enqueue(
        self,
        method: str,
        endpoint: str,
        params: dict | None = None,
        body: dict | None = None,
    ) -> int:
        """将请求加入后台事件循环"""
        self._request_counter += 1
        request_id = self._request_counter
        self._pending[request_id] = endpoint

        if self._loop is None or self._loop.is_closed():
            self.request_failed.emit(request_id, "后台事件循环未就绪")
            return request_id

        asyncio.run_coroutine_threadsafe(
            self._execute(request_id, method, endpoint, params, body),
            self._loop,
        )
        return request_id

    async def _execute(
        self,
        request_id: int,
        method: str,
        endpoint: str,
        params: dict | None,
        body: dict | None,
    ) -> None:
        """在后台线程执行 HTTP 请求，完成后发射信号"""
        if self._client is None:
            self.request_failed.emit(request_id, "HTTP 客户端未初始化")
            return

        try:
            response = await self._client.request(
                method=method,
                url=endpoint,
                params=params,
                json=body,
            )

            data: Any = None
            try:
                data = response.json()
            except Exception:
                data = {"raw": response.text}

            if response.status_code >= 400:
                logger.warning(f"[HTTP] #{request_id} {method} {endpoint} → {response.status_code}: {data}")
            else:
                logger.debug(f"[HTTP] #{request_id} {method} {endpoint} → {response.status_code}")

            self.request_finished.emit(request_id, response.status_code, data)

        except httpx.ConnectError:
            msg = f"无法连接到服务器 {self._base_url}"
            logger.error(f"[HTTP] 请求失败 #{request_id} {endpoint}: {msg}")
            self.request_failed.emit(request_id, msg)
        except httpx.TimeoutException:
            msg = "请求超时"
            logger.error(f"[HTTP] 请求失败 #{request_id} {endpoint}: {msg}")
            self.request_failed.emit(request_id, msg)
        except Exception as e:
            msg = str(e)
            logger.error(f"[HTTP] 请求失败 #{request_id} {endpoint}: {msg}")
            self.request_failed.emit(request_id, msg)
        finally:
            self._pending.pop(request_id, None)

    def close(self) -> None:
        """关闭客户端"""
        if self._loop and not self._loop.is_closed() and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)

    def is_pending(self, request_id: int) -> bool:
        """检查请求是否仍在进行中"""
        return request_id in self._pending

    @property
    def base_url(self) -> str:
        return self._base_url
