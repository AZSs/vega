"""领域插件接口 —— 内核通过此接口注入领域知识(依赖倒置),内核不 import 任何具体插件。

领域插件负责定义:
- 实体 type 词表(如小说: character/faction/item)
- 属性 key 与 value schema(如小说: 种族/身世/修为)
- 关系 type 词表(如小说: 师徒/盟友/仇敌)
- 抽取 prompt 模板(喂给 LLM 抽实体/关系/属性)
- 名归一规则(别名/共指的领域习惯,如中文古风称呼)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class DomainPlugin(ABC):
    """领域插件抽象基类。内核 ingest 管线接收一个 DomainPlugin 实例。"""

    @property
    @abstractmethod
    def name(self) -> str:
        """领域名(如 'novel'),也作插件目录标识。"""

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
        """实体/关系/属性抽取的 LLM prompt 模板。"""

    @abstractmethod
    def normalize_aliases(self, name: str, aliases: list[str]) -> list[str]:
        """领域别名归一规则(如昵称/敬称/代词的处理)。返回归一后别名表。"""

    def profile_prompt(self, entity_name: str, aggregated: dict[str, Any]) -> str:
        """画像合成 prompt(可选覆盖,默认用内核通用模板)。"""
        return ""


__all__ = ["DomainPlugin"]
