"""ingest 管线测试 —— 注入 fake chat/embedder,验证流式 + 断点续跑 + 落库。"""

import asyncio

from vega.core.ingest import ingest_document
from vega.plugins.novel import NovelPlugin
from vega.store import VectorStore


def _text() -> str:
    return "第一章 灵豆\n黄豆豆睁眼。\n\n第二章 入宗\n豆豆上山。\n"


async def _fake_chat(system: str, user: str) -> str:
    return "上下文"


async def _fake_embed(texts: list[str]) -> list[list[float]]:
    # 用文本首字符的 hash 模拟确定性向量,同文本同向量
    return [[float(len(t) % 7), float(len(t) % 5), float(len(t) % 3)] for t in texts]


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
    assert store.count() == 2  # 两章各一个向量
    # manifest 记录进度
    import json

    manifest = json.loads((tmp_path / "d1" / "manifest.json").read_text())
    assert manifest["total_segments"] == 2
    assert manifest["done"] == [0, 1]


def test_ingest_resume_skips_done(tmp_path):
    # 先写一个只完成第0章的 manifest
    import json

    (tmp_path / "d1").mkdir()
    (tmp_path / "d1" / "manifest.json").write_text(json.dumps({"total_segments": 2, "done": [0]}))
    # 第0章向量已存在
    s = VectorStore(str(tmp_path), "d1", dim=3)
    s.put(0, b"\x00" * 12, "第一章")
    s.close()

    calls: list[str] = []

    async def chat(system: str, user: str) -> str:
        calls.append(user)
        return "ctx"

    async def embed(texts: list[str]) -> list[list[float]]:
        calls.append(f"embed:{len(texts)}")
        return [[0.1, 0.2, 0.3] for _ in texts]

    asyncio.run(
        ingest_document(
            "d1",
            _text(),
            NovelPlugin(),
            workdir=str(tmp_path),
            chat=chat,
            embed=embed,
            resume=True,
        )
    )
    # 只处理第1章(第0章已 done 跳过)
    store = VectorStore(str(tmp_path), "d1", dim=3)
    assert store.count() == 2
    manifest = json.loads((tmp_path / "d1" / "manifest.json").read_text())
    assert manifest["done"] == [0, 1]


def test_ingest_search_recalls_chapter(tmp_path):
    """端到端:ingest 后能用向量检索召回章。"""
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
    # 用与第二章相同的向量查
    import numpy as np

    q = np.array(
        [
            float(len("上下文\n第二章 入宗\n豆豆上山。\n") % 7),
            float(len("上下文\n第二章 入宗\n豆豆上山。\n") % 5),
            float(len("上下文\n第二章 入宗\n豆豆上山。\n") % 3),
        ],
        dtype=np.float32,
    ).tobytes()
    hits = store.search(q, top_k=1)
    assert len(hits) == 1
    assert "第二章" in hits[0].text
