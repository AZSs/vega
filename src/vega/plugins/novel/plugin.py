"""小说领域插件(vega 首个领域插件)。

定义小说专用概念:角色(character)/势力(faction)/法宝(item)、
修为境界/功法、师徒/盟友/仇敌关系、中文古风别名习惯。
内核不 import 本文件;消费端(如 spica)按需 import 取 CharacterProfile 等契约。

注意:此处出现「角色/修为/伏笔」是合理的——这些是领域词,只在 plugins/ 内合法。
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from ..base import DomainPlugin

# ---- 领域属性 schema(小说专用)----


class CultivationStage(BaseModel):
    """修为境界(随时间演化,带出处)。"""

    stage: str = Field(description="境界名(如 练气/筑基/金丹/元婴)")
    segment_id: int
    mentions: list[Any] = Field(default_factory=list)


class CharacterProfileAttributes(BaseModel):
    """小说角色画像的属性集(对应内核 EntityProfile.attributes 的 key 约定)。

    内核 EntityProfile.attributes 是通用 dict[str, AttributeValue];
    本类仅声明小说领域用哪些 key,供抽取/合成对齐,不强制内核感知。
    """

    race: str | None = Field(default=None, description="种族(人族/妖族/神族...)")
    origin: str | None = Field(default=None, description="身世出身")
    gender: str | None = Field(default=None)
    appearance: str | None = Field(default=None)
    personality: str | None = Field(default=None)
    cultivation_stages: list[CultivationStage] = Field(default_factory=list)
    techniques: list[str] = Field(default_factory=list, description="功法")
    artifacts: list[str] = Field(default_factory=list, description="法宝/持有物")


# ---- 实体/关系 type 词表 ----

ENTITY_TYPES = ["character", "faction", "item", "location", "concept"]
RELATION_TYPES = ["师徒", "同门", "盟友", "仇敌", "亲属", "恋人", "主仆"]


class NovelPlugin(DomainPlugin):
    """小说领域插件实现。"""

    @property
    def name(self) -> str:
        return "novel"

    @property
    def entity_types(self) -> list[str]:
        return ENTITY_TYPES

    @property
    def relation_types(self) -> list[str]:
        return RELATION_TYPES

    def attribute_schema(self, entity_type: str) -> dict[str, type]:
        if entity_type == "character":
            return {
                "race": str,
                "origin": str,
                "gender": str,
                "appearance": str,
                "personality": str,
                "cultivation_stages": list,
                "techniques": list,
                "artifacts": list,
            }
        return {}

    def extract_prompt(self, segment_text: str) -> str:
        return (
            "你是小说实体抽取器。从下面这段小说正文中抽取实体与关系,只输出 JSON:\n"
            '{"entities":[{"name":"...","type":"character|faction|item|location|concept",'
            '"aliases":[...],"attributes":{"race":"...","origin":"...",'
            '"cultivation_stages":[...],"techniques":[...],"artifacts":[...]}}],'
            '"relations":[{"subject":"...","object":"...",'
            '"type":"师徒|同门|盟友|仇敌|亲属|恋人|主仆"}]}\n'
            "要求:1) 别名含昵称/敬称/代词指代;2) 属性只填原文明确的,不确定不填;"
            "3) 每个事实标注段内依据。不编造。\n\n"
            f"正文:\n{segment_text}"
        )

    def normalize_aliases(self, name: str, aliases: list[str]) -> list[str]:
        """中文小说别名归一:去引号、合并单字昵称、剔通用代词(她/他/那女子 不算别名)。"""
        import re

        generic_pronouns = {
            "她",
            "他",
            "它",
            "那人",
            "那女子",
            "那男子",
            "少年",
            "少女",
            "此女",
            "此子",
        }
        quote_re = re.compile(r"^[\"\'“”‘’「」『』]+|[\"\'“”‘’「」『』]+$")
        cleaned: list[str] = []
        for a in aliases:
            a = quote_re.sub("", a.strip())
            if not a or a == name or a in generic_pronouns:
                continue
            if a not in cleaned:
                cleaned.append(a)
        return cleaned


__all__ = [
    "NovelPlugin",
    "CharacterProfileAttributes",
    "CultivationStage",
    "ENTITY_TYPES",
    "RELATION_TYPES",
]
