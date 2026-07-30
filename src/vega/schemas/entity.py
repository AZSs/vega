"""实体 / 关系 / 属性 / 出处 —— 通用内核契约(领域中立)。

最高纪律:本文件不得出现任何领域词(角色/伏笔/修为/功法/章节...)。
内核只认:实体(Entity)、关系(Relation)、属性(Attribute)、出处(Mention)。
领域概念(如小说的「修为境界」)由 plugins 定义实体 type 与属性 key。
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class Mention(BaseModel):
    """原文出处:定位到文档内某段的字符区间。溯源防幻觉的基石——
    画像每个属性都挂 Mention,无出处不上画像。"""

    doc_id: str
    segment_id: int
    char_start: int = Field(ge=0)
    char_end: int = Field(ge=0)
    text: str = Field(default="", description="原文片段(可截断,仅备查)")

    model_config = {"frozen": True}


class AttributeValue(BaseModel):
    """实体的某个属性值,带出处溯源 + 置信度。
    value 类型由领域插件约定(内核用 Any,不绑领域)。"""

    value: Any
    mentions: list[Mention] = Field(default_factory=list, description="该值的原文出处")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class Entity(BaseModel):
    """实体:跨全文归一后的一个对象(人/物/组织/概念,由 type 区分,type 由领域插件定义)。"""

    id: str = Field(description="稳定唯一 id(归一后不变)")
    name: str = Field(description="规范名(归一后的主名)")
    aliases: list[str] = Field(default_factory=list, description="别名/指代(名归一产物)")
    type: str = Field(description="实体类型,由领域插件定义(如 character/faction/concept)")
    attributes: dict[str, AttributeValue] = Field(default_factory=dict)
    mentions: list[Mention] = Field(default_factory=list, description="所有出现位置")


class Relation(BaseModel):
    """实体间的关系。type 由领域插件定义(如 师徒/盟友/仇敌)。带出处溯源。"""

    id: str
    subject: str = Field(description="主体 entity id")
    object: str = Field(description="客体 entity id")
    type: str
    attributes: dict[str, AttributeValue] = Field(default_factory=dict)
    mentions: list[Mention] = Field(default_factory=list)


__all__ = ["Mention", "AttributeValue", "Entity", "Relation"]
