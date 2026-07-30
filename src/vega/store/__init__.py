"""store/ —— 持久化(文档级隔离)。

每个 doc_id 一个独立 SQLite(向量 + KG),互不污染。
向量用 sqlite-vec;KG(实体/关系/画像)落 SQLite 表。
"""

from .kg import KnowledgeStore
from .vector_store import VectorHit, VectorStore

__all__ = ["KnowledgeStore", "VectorStore", "VectorHit"]
