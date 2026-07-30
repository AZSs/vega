"""RAPTOR 式层级摘要 —— 段→簇→更高层,多层检索。

借鉴 Stanford RAPTOR:叶子=段,上层=聚类摘要,支持细节与全局两级召回。
"""

from __future__ import annotations

from ..schemas import Segment


async def build_summary_tree(segments: list[Segment]) -> object:
    """聚类 + 逐层摘要,返回层级树。"""
    raise NotImplementedError


__all__ = ["build_summary_tree"]
