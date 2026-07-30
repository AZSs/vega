"""ingest 管线 —— 流式:切段 → contextual embed → 抽取 → 名归一 → 画像 → 落库。

长文本(百万字级)必须可断点续跑:每段处理完 checkpoint,中断后从断点续。
文档级隔离:每个 doc_id 一个库。
"""

from __future__ import annotations

from ..plugins import DomainPlugin


async def ingest_document(
    doc_id: str,
    text: str,
    plugin: DomainPlugin,
    *,
    workdir: str,
    resume: bool = False,
) -> None:
    """流式 ingest 一份长文本到 workdir 的知识库。断点续跑。"""
    raise NotImplementedError


__all__ = ["ingest_document"]
