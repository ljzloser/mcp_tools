"""MCP Tool Hub — API 路由常量

前后端共享的路由路径定义，消除硬编码字符串。
"""


class Routes:
    """管理 API 路由常量"""

    # ── 健康检查 ──
    HEALTH = "/health"

    # ── 服务 ──
    SERVER_STATUS = "/server/status"
    SERVER_RELOAD = "/server/reload"

    # ── 插件（模板路径，含 {name} 占位）──
    PLUGINS = "/plugins"
    PLUGIN_DETAIL = "/plugins/{name}"
    PLUGIN_ENABLE = "/plugins/{name}/enable"
    PLUGIN_DISABLE = "/plugins/{name}/disable"
    PLUGIN_CONFIG = "/plugins/{name}/config"
    PLUGIN_INVOKE = "/plugins/{name}/invoke"
    PLUGIN_MCP = "/plugins/{name}/mcp"

    # ── 日志 ──
    LOGS = "/logs"
    LOGS_CONFIG = "/logs/config"
    LOGS_PRUNE = "/logs/prune"

    # ── 便捷方法：生成实际路径 ──

    @classmethod
    def plugin(cls, name: str) -> str:
        return cls.PLUGIN_DETAIL.format(name=name)

    @classmethod
    def plugin_enable(cls, name: str) -> str:
        return cls.PLUGIN_ENABLE.format(name=name)

    @classmethod
    def plugin_disable(cls, name: str) -> str:
        return cls.PLUGIN_DISABLE.format(name=name)

    @classmethod
    def plugin_config(cls, name: str) -> str:
        return cls.PLUGIN_CONFIG.format(name=name)

    @classmethod
    def plugin_mcp(cls, name: str) -> str:
        return cls.PLUGIN_MCP.format(name=name)

    @classmethod
    def plugin_invoke(cls, name: str) -> str:
        return cls.PLUGIN_INVOKE.format(name=name)
