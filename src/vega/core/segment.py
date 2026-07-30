"""切段 —— 通用(领域中立)。不叫「切章」(那是小说词)。

按分隔符切分长文本为 Segment 列表,记录字符区间。纯逻辑,零 IO。
contextual embedding 的 context_prefix 由 embed 模块后续填(调 LLM)。
"""

from __future__ import annotations

import re

from ..schemas import Document, Segment

# 默认段分隔:双换行(段落级)。文档级分隔(如小说分章)由调用方先拆再传入,或扩展 separator。
_DEFAULT_SEP = re.compile(r"\n\s*\n")


def segment_text(
    doc_id: str,
    text: str,
    *,
    separator: re.Pattern[str] | None = None,
    min_len: int = 1,
) -> Document:
    """把纯文本切成 Segment 列表,返回 Document。

    Args:
        doc_id: 文档 id(隔离 key)
        text: 原文
        separator: 段分隔正则,默认双换行
        min_len: 最短段长(字符),短于此并入相邻或丢弃(默认 1=不丢)
    """
    sep = separator or _DEFAULT_SEP
    segments: list[Segment] = []
    idx = 0
    pos = 0
    for m in sep.finditer(text):
        chunk = text[pos : m.start()]
        if len(chunk.strip()) >= min_len:
            segments.append(Segment(id=idx, text=chunk, char_start=pos, char_end=m.start()))
            idx += 1
        pos = m.end()
    # 尾段
    if pos < len(text):
        chunk = text[pos:]
        if len(chunk.strip()) >= min_len:
            segments.append(Segment(id=idx, text=chunk, char_start=pos, char_end=len(text)))
    return Document(id=doc_id, segments=segments)


__all__ = ["segment_text"]
