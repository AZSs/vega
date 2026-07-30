"""名归一 —— 跨段把同一实体的不同称呼(别名/指代)合并成一个 Entity。

500 万字里「黄豆豆/豆豆/不朽仙子/那丫头」指向同一人,归一错了画像就把两人的事迹混到一起。
名归一是画像的命门。领域别名习惯(中文古风称呼)经 plugin.normalize_aliases 注入。
"""

from __future__ import annotations

from ..plugins import DomainPlugin
from ..schemas import Entity


def merge_aliases(entities: list[Entity], plugin: DomainPlugin) -> list[Entity]:
    """跨段实体别名归并:同实体(主名或别名相交)合并 mentions/aliases,保留一个 Entity。"""
    raise NotImplementedError


def resolve_coreference(name: str, context: str, candidates: list[Entity]) -> str | None:
    """共指消解:代词(她/他)指代哪个已知实体。返回 entity id 或 None。"""
    raise NotImplementedError


__all__ = ["merge_aliases", "resolve_coreference"]
