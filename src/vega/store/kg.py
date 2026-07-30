"""知识库存储 —— 文档级隔离的 SQLite(向量 + KG)。

一个 doc_id 一个 .sqlite 文件,落在 workdir/<doc_id>/store.sqlite。
向量用 sqlite-vec 扩展(可选,缺失则降级 numpy 内存)。
实体/关系/画像/段 落表,JSON 列存 pydantic 序列化产物。
"""

from __future__ import annotations

from pathlib import Path


class KnowledgeStore:
    """单文档知识库。文档级隔离边界。"""

    def __init__(self, workdir: str, doc_id: str) -> None:
        self.workdir = Path(workdir)
        self.doc_id = doc_id
        self.path = self.workdir / doc_id / "store.sqlite"
        # TODO: 建表(entities/relations/profiles/segments/vectors),按需 open

    def put_entity(self, entity: object) -> None:
        raise NotImplementedError

    def get_entity(self, entity_id: str) -> object | None:
        raise NotImplementedError

    def put_profile(self, profile: object) -> None:
        raise NotImplementedError

    def get_profile(self, entity_id: str) -> object | None:
        raise NotImplementedError


__all__ = ["KnowledgeStore"]
