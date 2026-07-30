"""schemas/ —— 通用内核契约(领域中立,pydantic)。

最高纪律:本目录不得 import 任何领域插件。领域概念进 plugins/。
消费端(含 spica)与内核全消费同一份契约。
"""

from .document import Document, Segment
from .entity import AttributeValue, Entity, Mention, Relation
from .profile import EntityProfile, ProfileEvent

__all__ = [
    "Document",
    "Segment",
    "Mention",
    "AttributeValue",
    "Entity",
    "Relation",
    "EntityProfile",
    "ProfileEvent",
]
