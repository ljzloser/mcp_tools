"""MCP Tool Hub — 服务端启动入口

支持两种传输模式：
  python server.py              # stdio 模式（默认，由 AI 客户端启动）
  python server.py --sse        # SSE 模式（后台常驻服务，AI 客户端通过 URL 连接）
"""

from __future__ import annotations

import argparse
import asyncio

from loguru import logger

from server.app import MCPServerApp
from utils.logger import setup_logger


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="MCP Tool Hub 服务端")
    parser.add_argument(
        "--sse",
        action="store_true",
        help="使用 SSE 传输模式（后台常驻服务）",
    )
    parser.add_argument(
        "--sse-host",
        default="127.0.0.1",
        help="SSE 服务绑定地址（默认 127.0.0.1）",
    )
    parser.add_argument(
        "--sse-port",
        type=int,
        default=9021,
        help="SSE 服务端口（默认 9021）",
    )
    parser.add_argument(
        "--api-host",
        default="127.0.0.1",
        help="管理 API 绑定地址（默认 127.0.0.1）",
    )
    parser.add_argument(
        "--api-port",
        type=int,
        default=9020,
        help="管理 API 端口（默认 9020）",
    )
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    setup_logger("INFO")

    transport = "sse" if args.sse else "stdio"
    logger.info(f"MCP Tool Hub 启动中... (传输模式: {transport})")

    app = MCPServerApp(
        name="mcp-tool-hub",
        api_host=args.api_host,
        api_port=args.api_port,
        transport=transport,
        sse_host=args.sse_host,
        sse_port=args.sse_port,
    )

    # 优雅退出
    try:
        await app.start()
    except (KeyboardInterrupt, asyncio.CancelledError):
        logger.info("用户中断")
    finally:
        try:
            await app.stop()
        except (KeyboardInterrupt, asyncio.CancelledError):
            pass


if __name__ == "__main__":
    asyncio.run(main())
