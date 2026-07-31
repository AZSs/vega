"""领域插件接口 —— 内核通过此接口注入领域知识(依赖倒置),内核不 import 任何具体插件。

领域插件负责定义(全部领域专属,内核不感知):
- 实体 type 词表 / 属性 schema / 关系 type 词表
- 抽取 prompt(KG 实体关系抽取)
- 名归一规则(别名/共指的领域习惯)
- 文档分段(split_sections:小说分章/法律分条/技术分节)
- 画像抽取:关注关键词 + 逐片段抽取prompt + 字段表 + 画像输出schema

切换领域 = 实现一个新 DomainPlugin;内核 ingest/embed/store/recall/合成管线不改。
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..schemas import Document


class DomainPlugin(ABC):
    """领域插件抽象基类。内核 ingest/profile 管线接收一个 DomainPlugin 实例。"""

    @property
    @abstractmethod
    def name(self) -> str:
        """领域名(如 'novel'),也作插件目录标识。"""

    # ---- KG 实体关系抽取(领域定义)----

    @property
    @abstractmethod
    def entity_types(self) -> list[str]:
        """该领域支持的实体 type 词表。"""

    @property
    @abstractmethod
    def relation_types(self) -> list[str]:
        """该领域支持的关系 type 词表。"""

    @abstractmethod
    def attribute_schema(self, entity_type: str) -> dict[str, type]:
        """某实体 type 的属性 key → value 类型(用于校验抽取产物)。"""

    @abstractmethod
    def extract_prompt(self, segment_text: str) -> str:
        """KG 实体/关系抽取的 LLM prompt(领域定义实体/关系词表与属性)。"""

    @abstractmethod
    def normalize_aliases(self, name: str, aliases: list[str]) -> list[str]:
        """领域别名归一规则(如昵称/敬称/代词的处理)。返回归一后别名表。"""

    @abstractmethod
    def split_sections(self, doc_id: str, text: str) -> Document:
        """文档分段(领域定义:小说分章/法律分条/技术分节)。返回章级 Document。"""

    # ---- 画像合成(领域定义;内核 profile 管线消费)----

    def focus_keywords(self) -> list[str]:
        """画像召回优先关键词(领域定义,如小说:部落/道果/成仙)。默认空。"""
        return []

    def profile_extract_system(self) -> str:
        """画像 pass1 逐片段抽取的 system prompt(领域定义:该抽哪些维度)。"""
        return (
            "你从片段中提取【只关于指定角色】的事实。片段里会出现其他角色,"
            "只提取明确关于目标角色的事实,他人的忽略。无则 facts 空数组。只输出 JSON。"
        )

    def profile_fields(self) -> str:
        """画像抽取的字段枚举(领域定义,如 race|origin|age|...)。"""
        return "field|value|seg"

    def profile_schema(self) -> str:
        """画像输出 JSON schema 字符串(领域定义画像结构)。"""
        return '{"name":"..."}'


__all__ = ["DomainPlugin"]
