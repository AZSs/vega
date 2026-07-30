"""实体画像 / 事件 —— 通用内核契约(领域中立)。

EntityProfile 是 vega 的核心产物:跨全文聚合一份实体的结构化档案,
每个字段带溯源。消费端(如 spica 写同人)读它 grounded,不再幻觉。
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from .entity import AttributeValue, Mention, Relation


class ProfileEvent(BaseModel):
    """涉及该实体的事件,按时序排列。带出处溯源。"""

    order: int = Field(ge=0, description="时序序(按段顺序)")
    segment_id: int
    desc: str
    mentions: list[Mention] = Field(default_factory=list)


class EntityProfile(BaseModel):
    """实体画像:跨全文聚合的结构化档案。

    - attributes: 带溯源的属性(如种族/身世/修为——key 由领域插件定义)
    - relations: 该实体参与的关系(带演化)
    - events: 时序事件线
    - 每个字段挂 Mention,可回查原文,防幻觉
    """

    entity_id: str
    summary: str = Field(default="", description="画像综述(LLM 合成,带溯源约束)")
    attributes: dict[str, AttributeValue] = Field(default_factory=dict)
    relations: list[Relation] = Field(default_factory=list)
    events: list[ProfileEvent] = Field(default_factory=list)
    provenance: list[Mention] = Field(default_factory=list, description="画像整体的原文出处")


__all__ = ["ProfileEvent", "EntityProfile"]
