"""向量持久化测试 —— sqlite-vec,文档级隔离(每 doc 一个 sqlite)。"""

import numpy as np

from vega.store import VectorStore


def _vec(values: list[float]) -> bytes:
    return np.array(values, dtype=np.float32).tobytes()


def test_put_and_search_topk(tmp_path):
    store = VectorStore(str(tmp_path), "d1", dim=3)
    store.put(0, _vec([1.0, 0.0, 0.0]), "第一章")
    store.put(1, _vec([0.0, 1.0, 0.0]), "第二章")
    store.put(2, _vec([0.0, 0.0, 1.0]), "第三章")

    # 查询接近第一章
    hits = store.search(_vec([0.9, 0.1, 0.0]), top_k=2)
    assert len(hits) == 2
    assert hits[0].segment_id == 0  # 最相似
    assert "第一章" in hits[0].text


def test_search_returns_score_descending(tmp_path):
    store = VectorStore(str(tmp_path), "d1", dim=2)
    store.put(0, _vec([1.0, 0.0]), "a")
    store.put(1, _vec([0.7, 0.7]), "b")
    store.put(2, _vec([0.0, 1.0]), "c")
    hits = store.search(_vec([1.0, 0.0]), top_k=3)
    # 余弦相似度降序
    scores = [h.score for h in hits]
    assert scores == sorted(scores, reverse=True)
    assert hits[0].segment_id == 0


def test_persistence_across_reopen(tmp_path):
    store = VectorStore(str(tmp_path), "d1", dim=3)
    store.put(0, _vec([1.0, 0.0, 0.0]), "第一章")
    store.close()

    store2 = VectorStore(str(tmp_path), "d1", dim=3)
    hits = store2.search(_vec([1.0, 0.0, 0.0]), top_k=1)
    assert len(hits) == 1
    assert hits[0].segment_id == 0
    assert "第一章" in hits[0].text


def test_document_isolation(tmp_path):
    """两份文档各自独立 sqlite,互不污染。"""
    s1 = VectorStore(str(tmp_path), "d1", dim=2)
    s1.put(0, _vec([1.0, 0.0]), "d1-章0")
    s1.close()
    s2 = VectorStore(str(tmp_path), "d2", dim=2)
    s2.put(0, _vec([0.0, 1.0]), "d2-章0")
    hits = s2.search(_vec([1.0, 0.0]), top_k=1)
    # d2 库里只有 d2-章0,虽与查询方向不同但只能返它
    assert len(hits) == 1
    assert hits[0].text == "d2-章0"
