"""向量持久化 —— sqlite-vec,文档级隔离。

每份文档一个独立 sqlite(<workdir>/<doc_id>/vectors.sqlite),互不污染。
向量表用 sqlite-vec 虚拟表(余弦 top-k);文本旁表存 segment_id→text 供回查。
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

import sqlite_vec


@dataclass
class VectorHit:
    segment_id: int
    score: float
    text: str


class VectorStore:
    """单文档向量库。文档级隔离边界。"""

    def __init__(self, workdir: str, doc_id: str, dim: int) -> None:
        self.workdir = Path(workdir)
        self.doc_id = doc_id
        self.dim = dim
        self.path = self.workdir / doc_id / "vectors.sqlite"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(self.path))
        self.db.enable_load_extension(True)
        sqlite_vec.load(self.db)
        self.db.enable_load_extension(False)
        self._init_schema()

    def _init_schema(self) -> None:
        self.db.execute(
            f"CREATE VIRTUAL TABLE IF NOT EXISTS vec USING vec0(embedding float[{self.dim}])"
        )
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS texts"
            " (rowid INTEGER PRIMARY KEY, segment_id INTEGER, text TEXT)"
        )
        self.db.commit()

    def put(self, segment_id: int, vector: bytes, text: str) -> None:
        """写入一个 segment 的向量 + 文本。rowid 复用自增。"""
        cur = self.db.execute("INSERT INTO vec(embedding) VALUES (?)", (vector,))
        rowid = cur.lastrowid
        self.db.execute(
            "INSERT INTO texts(rowid, segment_id, text) VALUES (?, ?, ?)",
            (rowid, segment_id, text),
        )
        self.db.commit()

    def search(self, query: bytes, top_k: int = 10) -> list[VectorHit]:
        """余弦相似度 top-k(sqlite-vec 的 distance 是 1-cosine,越小越相似)。"""
        rows = self.db.execute(
            "SELECT vec.rowid, vec.distance, texts.segment_id, texts.text "
            "FROM vec LEFT JOIN texts ON vec.rowid = texts.rowid "
            "WHERE vec.embedding MATCH ? AND k = ? "
            "ORDER BY vec.distance",
            (query, top_k),
        ).fetchall()
        hits: list[VectorHit] = []
        for _rowid, distance, seg_id, text in rows:
            score = 1.0 - float(distance)  # distance=1-cos → score=cos
            hits.append(VectorHit(segment_id=int(seg_id), score=score, text=text or ""))
        return hits

    def count(self) -> int:
        return int(self.db.execute("SELECT COUNT(*) FROM vec").fetchone()[0])

    def find_texts_containing(self, keyword: str, limit: int = 200) -> list[VectorHit]:
        """文本搜索:返回所有包含 keyword 的块(按 segment_id 升序)。用于画像召回。"""
        rows = self.db.execute(
            "SELECT segment_id, text FROM texts WHERE text LIKE ? ORDER BY segment_id LIMIT ?",
            (f"%{keyword}%", limit),
        ).fetchall()
        return [VectorHit(segment_id=int(s), score=1.0, text=t or "") for s, t in rows]

    def close(self) -> None:
        self.db.close()


__all__ = ["VectorStore", "VectorHit"]
