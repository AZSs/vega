"""插件注册表 —— entry points + 配置覆盖 + 内置兜底,可热重载。

优先级(后者覆盖前者):内置 < entry_points < 配置文件。
- entry points:任何 pip 包装的插件声明 [project.entry-points."vega.plugins"],自动发现,无需改 vega。
- 配置:vega.toml [plugins] name = "module:Class",本地重定义/开发期即用。
- 热重载:reload_plugins() 清缓存;watch_plugins() 监听文件变更回调(serve 用)。

切换/重定义领域插件 = 装包或改配置,内核不改。
"""

from __future__ import annotations

import importlib
import tomllib
from importlib.metadata import entry_points
from pathlib import Path

from .base import DomainPlugin

# 内置兜底(entry points 未注册时用)
_BUILTIN: dict[str, str] = {"novel": "vega.plugins.novel:NovelPlugin"}

# 实例缓存(name -> DomainPlugin);reload 清空
_cache: dict[str, DomainPlugin] = {}


def load_plugin_config(path: str | None = None) -> dict[str, str]:
    """读 vega.toml [plugins] 段:name -> "module:Class"。文件不存在返空。"""
    p = Path(path or "vega.toml")
    if not p.exists():
        return {}
    data = tomllib.loads(p.read_text(encoding="utf-8"))
    return dict(data.get("plugins", {}))


def discover_plugins(config_path: str | None = None) -> dict[str, str]:
    """合并:内置 < entry_points < 配置(后者覆盖同名)。返 name -> "module:Class"。"""
    result: dict[str, str] = dict(_BUILTIN)
    try:
        for ep in entry_points(group="vega.plugins"):
            result[ep.name] = ep.value
    except TypeError:  # 老 API 兼容
        for ep in entry_points().get("vega.plugins", []):
            result[ep.name] = ep.value
    result.update(load_plugin_config(config_path))
    return result


def load_plugin(name: str, config_path: str | None = None) -> DomainPlugin:
    """按优先级加载插件实例(缓存)。未知插件抛 ValueError。"""
    key = f"{name}@{config_path or ''}"
    if key in _cache:
        return _cache[key]
    plugins = discover_plugins(config_path)
    if name not in plugins:
        raise ValueError(f"未知插件: {name}(可用: {', '.join(sorted(plugins))})")
    spec = plugins[name]
    module_name, _, attr = spec.partition(":")
    cls = getattr(importlib.import_module(module_name), attr or "Plugin")
    instance: DomainPlugin = cls()
    _cache[key] = instance
    return instance


def reload_plugins() -> None:
    """清插件缓存(配置/entry point 变更后,下次 load 重新发现)。"""
    _cache.clear()


def watch_plugins(plugin_dirs: list[str], on_change: object) -> None:
    """监听插件目录变更,变更时调 on_change(无参回调)+ reload。

    需 watchfiles(watch extra)。serve 进程用:插件文件改 → reload → 下个请求拿新插件。
    """
    from watchfiles import watch

    for _changes in watch(*plugin_dirs):
        reload_plugins()
        on_change()  # type: ignore[operator]


__all__ = [
    "load_plugin",
    "discover_plugins",
    "load_plugin_config",
    "reload_plugins",
    "watch_plugins",
]
