"""ingest 管线 —— 流式:切章 → contextual embed → 落 sqlite-vec,断点续跑。

长文本(百万字级)逐段处理,每段落盘后写 manifest.json,中断后 resume 跳过已 done。
文档级隔离:每个 doc_id 一个库。
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import numpy as np

from ..plugins import DomainPlugin
from ..store import VectorStore
from .embed import ChatFn, EmbedFn, annotate_context_prefix


async def ingest_document(
    doc_id: str,
    text: str,
    plugin: DomainPlugin,
    *,
    workdir: str,
    chat: ChatFn | None = None,
    embed: EmbedFn | None = None,
    resume: bool = False,
    ollama_url: str = "http://localhost:11434",
    embed_model: str = "bge-m3",
    chat_model: str = "qwen2.5:7b",
    limit: int | None = None,
    context_prefix: bool = True,
) -> None:
    """流式 ingest:切章 → 子切块 → (可选)contextual 前缀 → 批量 embedding → 落 sqlite-vec。

    断点续跑:manifest.json 记 done 段号;resume=True 时跳过已 done。
    context_prefix=False 关闭 LLM 上下文前缀(全文快速建库用,只 embed 原文)。
    chat/embed 省略则用 Ollama 真实实现(ollama_url/embed_model/chat_model 配置)。
    """
    from .embed import make_ollama_chat, make_ollama_embedder

    doc_dir = Path(workdir) / doc_id
    doc_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = doc_dir / "manifest.json"

    # 切段:领域插件定义分段策略(小说分章/法律分条),内核不感知
    document = plugin.split_sections(doc_id, text)
    segments = document.segments
    if limit is not None:
        segments = segments[:limit]
    total = len(segments)
    if total == 0:
        print(f"[vega] {doc_id} 无段,跳过")
        return

    done: set[int] = set()
    if resume and manifest_path.exists():
        done = set(json.loads(manifest_path.read_text()).get("done", []))

    chat_fn = chat or make_ollama_chat(base_url=ollama_url, model=chat_model)
    embed_fn = embed or make_ollama_embedder(base_url=ollama_url, model=embed_model)
    doc_context = f"文档:{doc_id},共 {total} 段"

    # 维度:优先读已有库;否则探测首段
    dim = _read_existing_dim(workdir, doc_id)
    store: VectorStore | None = None
    if dim is not None:
        store = VectorStore(workdir, doc_id, dim=dim)

    pending = [s for s in segments if s.id not in done]
    for seg in pending:
        # 子切块(整章 embed 会超 bge-m3 上下文长度,且粒度太粗)
        from .chunk import chunk_text

        chunks = chunk_text(seg.text, max_chars=500)
        prefix = ""
        if context_prefix:
            annotated = await annotate_context_prefix(seg, doc_context, chat=chat_fn)
            prefix = annotated.context_prefix
        embed_inputs = [f"{prefix}\n{c}" if prefix else c for c in chunks]
        try:
            vecs = await embed_fn(embed_inputs)
        except Exception as e:
            print(f"[vega] {doc_id} 段 {seg.id} embedding 失败,中断(可 --resume 续跑):{e}")
            break
        if store is None:
            dim = len(vecs[0]) if vecs and vecs[0] else 1024
            store = VectorStore(workdir, doc_id, dim=dim)
        for c, v in zip(chunks, vecs, strict=True):
            if v:
                store.put(seg.id, np.array(v, dtype=np.float32).tobytes(), c)
        done.add(seg.id)
        if seg.id % 50 == 0 or seg.id == total - 1:
            print(f"[vega] {doc_id} 段 {seg.id}/{total - 1} 完成")
        _write_manifest(manifest_path, total, sorted(done))

    if store is not None:
        store.close()
    print(f"[vega] {doc_id} ingest 完成:{len(done)}/{total} 段")


def _read_existing_dim(workdir: str, doc_id: str) -> int | None:
    """从已有 vectors.sqlite 读向量维度(用于 resume / 续写)。"""
    db_path = Path(workdir) / doc_id / "vectors.sqlite"
    if not db_path.exists():
        return None
    con = sqlite3.connect(str(db_path))
    row = con.execute("SELECT sql FROM sqlite_master WHERE name='vec'").fetchone()
    con.close()
    if row and "float[" in row[0]:
        return int(row[0].split("float[")[1].split("]")[0])
    return None


def _write_manifest(path: Path, total: int, done: list[int]) -> None:
    path.write_text(json.dumps({"total_segments": total, "done": done}, ensure_ascii=False))


__all__ = ["ingest_document"]
