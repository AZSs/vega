"""contextual embedding —— 给每段加 LLM 上下文前缀,再 embedding,落 sqlite-vec。

借鉴 Anthropic Contextual Retrieval:段脱离上下文会丢语义(谁说话/哪段),
加前缀后召回失准降 49%。embedding 走 Ollama bge-m3(可换),持久化走 store。
"""

from __future__ import annotations

from ..schemas import Segment


async def annotate_context_prefix(segment: Segment, doc_context: str) -> Segment:
    """调 LLM 给段生成上下文前缀,写入 segment.context_prefix。"""
    raise NotImplementedError


async def embed_segments(
    segments: list[Segment], *, base_url: str = "http://localhost:11434"
) -> list[list[float]]:
    """对 [context_prefix + text] 做 embedding,返回向量列表。"""
    raise NotImplementedError


__all__ = ["annotate_context_prefix", "embed_segments"]
