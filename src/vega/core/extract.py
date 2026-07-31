"""实体/关系抽取 —— 调领域插件的 extract_prompt,从段抽实体/关系(带段级 Mention 溯源)。

经 DomainPlugin 接口注入领域 prompt,内核不感知具体领域。
每段抽取的实体/关系挂 Mention(segment.id + 段级字符区间),为画像溯源打基础。
"""

from __future__ import annotations

import json
import re

from pydantic import BaseModel, Field

from ..plugins import DomainPlugin
from ..schemas import Segment
from .embed import ChatFn


class ExtractedRelation(BaseModel):
    """抽取的关系(subject/object 用角色名,后续名归一映射到 entity)。"""

    subject: str
    object: str
    type: str


class ExtractedEntity(BaseModel):
    """单段抽取的一个实体(尚未跨段归一)。attributes 为 str→原始值(合并时带溯源)。"""

    name: str
    type: str = "character"
    aliases: list[str] = Field(default_factory=list)
    attributes: dict[str, str] = Field(default_factory=dict)
    relations: list[ExtractedRelation] = Field(default_factory=list)


async def extract_segment(
    segment: Segment, plugin: DomainPlugin, *, chat: ChatFn, doc_id: str
) -> list[ExtractedEntity]:
    """对单段调 LLM 抽实体/关系。失败返空(降级,不阻断)。

    Mention 溯源在 KG 合并时按段附加(段级:char_start=0,char_end=len(text))。
    """
    try:
        raw = await chat("你只输出 JSON,不输出任何额外文字。", plugin.extract_prompt(segment.text))
    except Exception:
        return []
    m = re.search(r"\{[\s\S]*\}", raw)
    if not m:
        return []
    try:
        data = json.loads(m.group(0))
    except json.JSONDecodeError:
        return []
    out: list[ExtractedEntity] = []
    for e in data.get("entities", []):
        try:
            out.append(
                ExtractedEntity(
                    name=str(e["name"]),
                    type=str(e.get("type", "character")),
                    aliases=[str(a) for a in e.get("aliases", [])],
                    attributes={k: str(v) for k, v in e.get("attributes", {}).items()},
                    relations=[ExtractedRelation(**r) for r in e.get("relations", [])],
                )
            )
        except (KeyError, TypeError):
            continue
    return out


__all__ = ["ExtractedEntity", "ExtractedRelation", "extract_segment"]
