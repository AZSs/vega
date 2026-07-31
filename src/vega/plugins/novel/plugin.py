"""小说领域插件(vega 首个领域插件)。

定义小说专用概念:角色(character)/势力(faction)/法宝(item)、
修为境界/功法、师徒/盟友/仇敌关系、中文古风别名习惯。
内核不 import 本文件;消费端(如 spica)按需 import 取 CharacterProfile 等契约。

注意:此处出现「角色/修为/伏笔」是合理的——这些是领域词,只在 plugins/ 内合法。
"""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field

from ...schemas import Document
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

# 章题正则:第一章/第1章/第001章/第十二章/第一百零三章...
_CHAPTER_RE = re.compile(r"第[零一二三四五六七八九十百千万0-9]+章")


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
            '"aliases":[...],"attributes":{"race":"出身种族(人族/妖族/神族,非当前境界)",'
            '"origin":"身世(部落/家族/遭遇,如部落被灭)","age":"年龄",'
            '"cultivation_stages":["修为境界(如练气/筑基/仙人)"],'
            '"techniques":["功法"],"artifacts":["法宝/持有物"],'
            '"dao_fruit":"道果名及状态"}}],'
            '"relations":[{"subject":"实体名","object":"另一实体名",'
            '"type":"师徒|同门|盟友|仇敌|亲属|恋人|主仆|同辈仙人"}]}\n'
            "要求:1) race 是【出身种族】不是当前境界(成仙后仍是人族,不填仙人);"
            "2) origin:原文提及部落/家族被灭/遭难/流离,务必提取(如'部落被灭'),不要填'未知';"
            "3) dao_fruit:化身/复活体(如灰豆豆)的道果(如寂灭道果)也要提取,与本体道果区分;"
            "4) 别名含昵称/敬称/指代;5) 属性只填原文明确的,不确定不填;6) 不编造。\n\n"
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

    def split_chapters(self, doc_id: str, text: str) -> Document:
        """按 第N章 章题切分,返回章级 Document(每章一段,含章题)。

        无章题时整篇作一段(不丢)。领域专用(「章」在此合法);内核 segment_text 是通用切段。
        """
        from ...schemas import Segment

        starts = [m.start() for m in _CHAPTER_RE.finditer(text)]
        if not starts:
            return Document(
                id=doc_id,
                segments=[Segment(id=0, text=text, char_start=0, char_end=len(text))],
            )
        # 去重保序(章题可能在一行内重复匹配?取首个)
        starts = sorted(set(starts))
        if starts[0] > 0:
            # 章题前有前言:并入首章
            starts[0] = 0
        segments: list[Segment] = []
        for i, s in enumerate(starts):
            e = starts[i + 1] if i + 1 < len(starts) else len(text)
            chunk = text[s:e]
            if chunk.strip():
                segments.append(Segment(id=len(segments), text=chunk, char_start=s, char_end=e))
        return Document(id=doc_id, segments=segments)

    # ---- 画像合成(小说领域定义;内核 profile 管线消费)----

    def split_sections(self, doc_id: str, text: str) -> Document:
        """文档分段 = 按第N章分章(领域实现)。"""
        return self.split_chapters(doc_id, text)

    def focus_keywords(self) -> list[str]:
        """画像召回优先关键词(修仙小说:出身/成仙/复活/道果相关)。"""
        return [
            "部落",
            "道果",
            "寂灭",
            "成仙",
            "十六岁",
            "岁",
            "族人",
            "灭族",
            "废",
            "薪火",
            "天庭",
            "复活",
            "念",
            "灰豆豆",
            "不朽道果",
        ]

    def profile_extract_system(self) -> str:
        return (
            "你从小说片段中提取【只关于指定角色】的事实。"
            "片段里会出现其他角色,只提取明确关于目标角色的事实,他人的忽略。"
            "特别注意区分:目标角色与其化身/复活体(如灰豆豆是另一个人,用不同道果)——"
            "若片段讲的是化身/复活体,标 field='incarnation' 并注明其名与道果,不要混入主角色道果。"
            "重点关注:出身种族(人族/妖族等,区别于当前境界)、身世(部落/家族/遭遇,如部落被灭)、"
            "年龄、道果(名称+当前状态:完好/失去/被谁使用,及出处)、"
            "成仙(如何成仙/成仙前代价)、复活(是否复活/谁复活/如何复活,如念名字/天庭)、"
            "关系网(含所属群体如上古四仙及成员,个体关系如师徒/恋人/生死之仇)、"
            "外貌(可多条,不同场景不同穿着,各带出处)。"
            "无则 facts 空数组。只输出 JSON。"
        )

    def profile_fields(self) -> str:
        return (
            "race|origin|age|dao_fruit|gender|appearance|personality|"
            "cultivation|technique|artifact|relation|immortalization|incarnation|revival|event"
        )

    def profile_schema(self) -> str:
        return (
            '{"name":"...","race":"出身种族(人族/妖族等,非当前境界)",'
            '"origin":"身世出身(部落/家族/遭遇,如部落被灭;含时代如薪火王朝)",'
            '"age":"年龄",'
            '"dao_fruit":{"name":"道果名","status":"完好/失去/被谁使用","seg":N},'
            '"gender":"性别",'
            '"appearance":[{"desc":"外貌/穿着","seg":N}](可多条,不同场景),'
            '"personality":"性格",'
            '"cultivation_stages":[{"stage":"境界","from_seg":N}],'
            '"techniques":["功法"],"artifacts":["法宝/持有物"],'
            '"relations":[{"target":"角色","type":"关系(含群体如上古四仙)"}],'
            '"revival":{"revived":true/false,"by":"谁复活","method":"如何复活(如念名字/天庭)","seg":N},'
            '"incarnations":[{"name":"化身/复活体名(如灰豆豆)","dao_fruit":"其道果","relation":"关系","seg":N}],'
            '"key_events":[{"seg":N,"desc":"事件"}],'
            '"immortalization_path":"成仙路径(如何成仙,代价;与复活体关系)"}'
        )


__all__ = [
    "NovelPlugin",
    "CharacterProfileAttributes",
    "CultivationStage",
    "ENTITY_TYPES",
    "RELATION_TYPES",
]
