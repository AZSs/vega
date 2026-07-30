"""hybrid 检索 + rerank —— 向量 + 关键词 + 图遍历三路融合,cross-encoder 精排。

查询改写(HyDE)→ 三路召回 → rerank(bge-reranker)→ 返回带溯源的片段。
"""

from __future__ import annotations

from ..schemas import Mention


async def retrieve(query: str, doc_id: str, *, top_k: int = 10) -> list[Mention]:
    """hybrid 检索:向量 + 关键词 + 图遍历,rerank 后返回 top_k 带出处片段。"""
    raise NotImplementedError


__all__ = ["retrieve"]
