"""plugins/ —— 领域插件(内核不 import 此目录,依赖倒置)。

内核 core 通过 DomainPlugin 接口注入领域知识;具体插件在此实现。
首个插件:novel(小说)。切换领域 = 实现新插件 + load_plugin 注册。
"""

from .base import DomainPlugin


def load_plugin(name: str) -> DomainPlugin:
    """按名加载领域插件(内核/CLI 通过此入口,不直接 import 具体插件)。"""
    if name == "novel":
        from .novel import NovelPlugin

        return NovelPlugin()
    raise ValueError(f"未知插件: {name}(已注册: novel)")


__all__ = ["DomainPlugin", "load_plugin"]
