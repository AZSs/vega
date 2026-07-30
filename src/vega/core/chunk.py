"""子切块 —— 把段(章)切成 embedding 友好的小块(领域中立)。

整章直接 embed 会超 bge-m3 上下文长度,且粒度太粗。按段落合并到 ~max_chars,
长段硬切。通用,不沾领域词。
"""

from __future__ import annotations

import re

_PARA_SEP = re.compile(r"\n\s*\n")


def chunk_text(text: str, max_chars: int = 500) -> list[str]:
    """按段落切,合并短段到 ~max_chars,长段硬切。返非空块列表。"""
    paras = [p.strip() for p in _PARA_SEP.split(text) if p.strip()]
    chunks: list[str] = []
    buf = ""
    for p in paras:
        if len(p) > max_chars:
            if buf:
                chunks.append(buf)
                buf = ""
            for i in range(0, len(p), max_chars):
                chunks.append(p[i : i + max_chars])
        elif buf and len(buf) + len(p) + 2 > max_chars:
            chunks.append(buf)
            buf = p
        else:
            buf = f"{buf}\n\n{p}" if buf else p
    if buf:
        chunks.append(buf)
    return chunks or [text.strip()]


__all__ = ["chunk_text"]
