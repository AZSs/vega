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
from ..plugins.novel import NovelPlugin
from ..store import VectorStore
from .embed import ChatFn, EmbedFn, annotate_context_prefix, embed_segments


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
) -> None:
    """流式 ingest:切章 → 每章 contextual 前缀 → embedding → 落 sqlite-vec。

    断点续跑:manifest.json 记 done 段号;resume=True 时跳过已 done。
    chat/embed 省略则用 Ollama 真实实现(ollama_url/embed_model/chat_model 配置)。
    """
    from .embed import make_ollama_chat, make_ollama_embedder

    doc_dir = Path(workdir) / doc_id
    doc_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = doc_dir / "manifest.json"

    # 切段(novel 插件用 split_chapters;通用插件回退 segment_text)
    if isinstance(plugin, NovelPlugin):
        document = plugin.split_chapters(doc_id, text)
    else:
        from .segment import segment_text

        document = segment_text(doc_id, text)
    segments = document.segments
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
        print(f"[vega] {doc_id} 段 {seg.id}/{total - 1} contextual+embed...")
        annotated = await annotate_context_prefix(seg, doc_context, chat=chat_fn)
        try:
            vecs = await embed_segments([annotated], embed=embed_fn)
        except Exception as e:
            # embed 失败(Ollama 未启/超时):停止本轮,保留已完成进度,可 resume 续跑
            print(f"[vega] {doc_id} 段 {seg.id} embedding 失败,中断(可 --resume 续跑):{e}")
            break
        vec = vecs[0] if vecs and vecs[0] else [0.0] * (dim or 1024)
        # lazy 开库:首段确定 dim
        if store is None:
            store = VectorStore(workdir, doc_id, dim=len(vec))
        store.put(seg.id, np.array(vec, dtype=np.float32).tobytes(), annotated.text)
        done.add(seg.id)
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
