"""plugins/ —— 领域插件(内核不 import 此目录,依赖倒置)。

内核 core 通过 DomainPlugin 接口注入领域知识;具体插件在此实现。
插件注册表:entry points + 配置覆盖 + 内置兜底(见 registry),可热重载。
首个内置插件:novel(小说)。切换领域 = 装包/改配置,内核不改。
"""

from .base import DomainPlugin
from .registry import (
    discover_plugins,
    load_plugin,
    load_plugin_config,
    reload_plugins,
    watch_plugins,
)

__all__ = [
    "DomainPlugin",
    "load_plugin",
    "discover_plugins",
    "load_plugin_config",
    "reload_plugins",
    "watch_plugins",
]
