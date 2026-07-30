"""画像合成 —— 跨全文聚合一个实体的结构化 EntityProfile,带溯源 + CRAG 自检。

核心产物。每个属性字段挂 Mention(原文出处),无溯源不上画像。
合成后 CRAG 自检:校验属性有原文支撑,否则丢弃(防「灵豆化形」式幻觉)。
"""

from __future__ import annotations

from typing import Any

from ..schemas import Entity, EntityProfile, Relation


def aggregate_attributes(entity: Entity) -> dict[str, list[Any]]:
    """跨所有 mention 聚合属性增量,去矛盾(时序 latest-wins 或多数共识)。"""
    raise NotImplementedError


async def build_profile(
    entity: Entity,
    relations: list[Relation],
    *,
    crag_check: bool = True,
) -> EntityProfile:
    """合成实体画像。CRAG 自检开时,丢弃无溯源/无原文支撑的属性。"""
    raise NotImplementedError


__all__ = ["aggregate_attributes", "build_profile"]
