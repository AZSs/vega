"""ingest 管线测试 —— 注入 fake chat/embedder,验证流式 + 切块 + 断点续跑 + 落库。"""

import asyncio

from vega.core.ingest import ingest_document
from vega.plugins.novel import NovelPlugin
from vega.store import VectorStore


def _text() -> str:
    return "第一章 灵豆\n黄豆豆睁眼。\n\n第二章 入宗\n豆豆上山。\n"


async def _fake_chat(system: str, user: str) -> str:
    return "上下文"


async def _fake_embed(texts: list[str]) -> list[list[float]]:
    # 内容确定性:含"第二章"的块 → [1,0,0],否则 [0,0,0]
    return [[1.0, 0.0, 0.0] if "第二章" in t else [0.0, 0.0, 0.0] for t in texts]


def test_ingest_writes_vectors_and_manifest(tmp_path):
    asyncio.run(
        ingest_document(
            "d1",
            _text(),
            NovelPlugin(),
            workdir=str(tmp_path),
            chat=_fake_chat,
            embed=_fake_embed,
        )
    )
    store = VectorStore(str(tmp_path), "d1", dim=3)
    assert store.count() >= 2  # 至少每章一块
    import json

    manifest = json.loads((tmp_path / "d1" / "manifest.json").read_text())
    assert manifest["total_segments"] == 2
    assert manifest["done"] == [0, 1]


def test_ingest_resume_skips_done(tmp_path):
    import json

    (tmp_path / "d1").mkdir()
    (tmp_path / "d1" / "manifest.json").write_text(json.dumps({"total_segments": 2, "done": [0]}))
    s = VectorStore(str(tmp_path), "d1", dim=3)
    s.put(0, b"\x00" * 12, "第一章")
    s.close()

    asyncio.run(
        ingest_document(
            "d1",
            _text(),
            NovelPlugin(),
            workdir=str(tmp_path),
            chat=_fake_chat,
            embed=_fake_embed,
            resume=True,
        )
    )
    store = VectorStore(str(tmp_path), "d1", dim=3)
    assert store.count() >= 2
    manifest = json.loads((tmp_path / "d1" / "manifest.json").read_text())
    assert manifest["done"] == [0, 1]


def test_ingest_no_context_prefix(tmp_path):
    """context_prefix=False 时不调 chat,直接 embed 原文块。"""
    chat_calls: list[str] = []

    async def chat(system: str, user: str) -> str:
        chat_calls.append(user)
        return "ctx"

    asyncio.run(
        ingest_document(
            "d1",
            _text(),
            NovelPlugin(),
            workdir=str(tmp_path),
            chat=chat,
            embed=_fake_embed,
            context_prefix=False,
        )
    )
    assert chat_calls == []  # 未调 chat
    store = VectorStore(str(tmp_path), "d1", dim=3)
    assert store.count() >= 2


def test_ingest_search_recalls_chapter(tmp_path):
    """端到端:ingest 后能用向量检索召回含'第二章'的块。"""
    asyncio.run(
        ingest_document(
            "d1",
            _text(),
            NovelPlugin(),
            workdir=str(tmp_path),
            chat=_fake_chat,
            embed=_fake_embed,
        )
    )
    store = VectorStore(str(tmp_path), "d1", dim=3)
    import numpy as np

    # 查询向量 = [1,0,0](对应含"第二章"的块)
    q = np.array([1.0, 0.0, 0.0], dtype=np.float32).tobytes()
    hits = store.search(q, top_k=1)
    assert len(hits) == 1
    assert "第二章" in hits[0].text
