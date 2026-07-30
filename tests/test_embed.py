"""contextual embedding 测试 —— 注入 fake chat/embedder,不依赖 Ollama。"""

from vega.core.embed import annotate_context_prefix, embed_segments
from vega.schemas import Segment


def test_annotate_context_prefix_calls_chat_and_sets_prefix():
    seg = Segment(id=0, text="她拔剑冲向敌人。")

    async def fake_chat(system: str, user: str) -> str:
        assert "上下文" in system or "context" in system.lower()
        return "本章为开篇战斗"

    import asyncio

    out = asyncio.run(annotate_context_prefix(seg, doc_context="书名:成仙记", chat=fake_chat))
    assert out.context_prefix == "本章为开篇战斗"
    assert out.text == "她拔剑冲向敌人。"  # 原文不变


def test_embed_segments_concatenates_prefix_and_text():
    seg = Segment(id=0, text="正文内容", context_prefix="上下文")

    async def fake_embed(texts: list[str]) -> list[list[float]]:
        # 验证拼接了 prefix + text
        assert texts == ["上下文\n正文内容"]
        return [[0.1, 0.2, 0.3]]

    import asyncio

    vecs = asyncio.run(embed_segments([seg], embed=fake_embed))
    assert vecs == [[0.1, 0.2, 0.3]]


def test_embed_segments_without_prefix_uses_text_only():
    seg = Segment(id=0, text="正文")

    async def fake_embed(texts: list[str]) -> list[list[float]]:
        assert texts == ["正文"]
        return [[0.0]]

    import asyncio

    asyncio.run(embed_segments([seg], embed=fake_embed))


def test_annotate_failure_returns_empty_prefix():
    """LLM 失败 → context_prefix 空(降级,不阻断)。"""
    seg = Segment(id=0, text="正文")

    async def fake_chat(system: str, user: str) -> str:
        raise RuntimeError("LLM 挂了")

    import asyncio

    out = asyncio.run(annotate_context_prefix(seg, doc_context="", chat=fake_chat))
    assert out.context_prefix == ""
