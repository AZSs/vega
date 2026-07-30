"""plugins/ —— 领域插件(内核不 import 此目录,依赖倒置)。

内核 core 通过 DomainPlugin 接口注入领域知识;具体插件在此实现。
首个插件:novel(小说)。
"""

from .base import DomainPlugin

__all__ = ["DomainPlugin"]
