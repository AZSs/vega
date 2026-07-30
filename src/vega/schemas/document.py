"""文档 / 段 —— 通用内核契约(领域中立)。

「段(Segment)」是通用切分单元,不叫「章」(那是小说词)。
contextual retrieval:每段带 LLM 生成的上下文前缀,再 embedding,降召回失准。
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class Segment(BaseModel):
    """文档的一个切段。id 在文档内唯一。"""

    id: int = Field(ge=0)
    text: str
    char_start: int = Field(default=0, ge=0, description="在原文中的起始字符")
    char_end: int = Field(default=0, ge=0)
    context_prefix: str = Field(
        default="",
        description="contextual retrieval:LLM 生成的段上下文前缀,embedding 时拼在 text 前",
    )


class Document(BaseModel):
    """一份长文本(一本书 / 一份文书 / 一篇文档)。文档级隔离的边界。"""

    id: str = Field(description="文档唯一 id,也是知识库隔离 key")
    title: str = ""
    segments: list[Segment] = Field(default_factory=list)

    def segment_by_id(self, segment_id: int) -> Segment | None:
        for seg in self.segments:
            if seg.id == segment_id:
                return seg
        return None


__all__ = ["Segment", "Document"]
