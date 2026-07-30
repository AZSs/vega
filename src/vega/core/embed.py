"""contextual embedding —— 给每段加 LLM 上下文前缀,再 embedding,落向量库。

借鉴 Anthropic Contextual Retrieval:段脱离上下文会丢语义(谁说话/哪段),
加前缀后召回失准降 49%。embedding 走 Ollama bge-m3(可换),经 embed 参数注入便于测试。
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from ..schemas import Segment

# 注入类型:chat(system, user) -> text; embed(texts) -> vectors
ChatFn = Callable[[str, str], Awaitable[str]]
EmbedFn = Callable[[list[str]], Awaitable[list[list[float]]]]


async def annotate_context_prefix(segment: Segment, doc_context: str, *, chat: ChatFn) -> Segment:
    """调 LLM 给段生成上下文前缀,返回带 context_prefix 的新 Segment。

    doc_context: 文档级背景(书名/简介),帮 LLM 理解段所处位置。
    chat 可注入测试。LLM 失败 → context_prefix 空(降级,不阻断)。
    """
    system = (
        "你给小说段落生成简短上下文前缀(20-40 字),说明该段在全书中的位置/在场角色/情境,"
        "用于提升向量检索召回。只输出前缀文本,不要解释。"
    )
    user = f"文档背景:{doc_context}\n\n段落:\n{segment.text[:1000]}"
    try:
        prefix = (await chat(system, user)).strip()
    except Exception:
        prefix = ""
    return segment.model_copy(update={"context_prefix": prefix})


async def embed_segments(segments: list[Segment], *, embed: EmbedFn) -> list[list[float]]:
    """对 [context_prefix + text] 做 embedding,返回向量列表(顺序与 segments 一致)。

    无 context_prefix 的段直接用 text。embed 可注入测试(真实走 Ollama bge-m3)。
    """
    texts = [f"{s.context_prefix}\n{s.text}" if s.context_prefix else s.text for s in segments]
    return await embed(texts)


# ---- Ollama bge-m3 真实实现(可注入)----


def make_ollama_embedder(
    base_url: str = "http://localhost:11434", model: str = "bge-m3"
) -> EmbedFn:
    """构造 Ollama embedding 函数(批量:一次请求 embed 多个文本)。失败抛错,调用方降级。"""
    import httpx

    async def embed(texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(f"{base_url}/api/embed", json={"model": model, "input": texts})
            resp.raise_for_status()
            data = resp.json()
            return [[float(x) for x in v] for v in data["embeddings"]]

    return embed


def make_ollama_chat(base_url: str = "http://localhost:11434", model: str = "qwen2.5:7b") -> ChatFn:
    """构造 Ollama chat 函数(用于 contextual prefix,本地小模型即可)。"""
    import httpx

    async def chat(system: str, user: str) -> str:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{base_url}/api/chat",
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "stream": False,
                },
            )
            resp.raise_for_status()
            return str(resp.json()["message"]["content"])

    return chat


__all__ = [
    "annotate_context_prefix",
    "embed_segments",
    "make_ollama_embedder",
    "make_ollama_chat",
    "ChatFn",
    "EmbedFn",
]
