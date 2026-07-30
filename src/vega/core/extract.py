"""实体/关系抽取 —— 调领域插件的 extract_prompt,从段抽 Entity/Relation(带 Mention 溯源)。

经 DomainPlugin 接口注入领域 prompt,内核不感知具体领域。
抽取产物带 Mention(段号+字符区间),为画像溯源打基础。
"""

from __future__ import annotations

from ..plugins import DomainPlugin
from ..schemas import Entity, Relation, Segment


async def extract_segment(
    segment: Segment, plugin: DomainPlugin
) -> tuple[list[Entity], list[Relation]]:
    """对单段调 LLM 抽实体/关系。产物挂 Mention(segment.id + 字符区间)。"""
    raise NotImplementedError


__all__ = ["extract_segment"]
