"""Vega CLI 入口。

用法:
  vega ingest <doc_id> --file <path> --plugin novel --workdir <dir>
  vega profile <doc_id> --entity <name> --workdir <dir>   # 未实现(后续)
  vega query <doc_id> "问题" --workdir <dir>              # 未实现(后续)
"""

from __future__ import annotations

import argparse
import asyncio
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="vega", description="把长文本织成知识图谱的通用引擎")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_ingest = sub.add_parser("ingest", help="ingest 一份长文本到知识库")
    p_ingest.add_argument("doc_id")
    p_ingest.add_argument("--file", required=True)
    p_ingest.add_argument("--plugin", default="novel")
    p_ingest.add_argument("--workdir", default="./vega-workspace")
    p_ingest.add_argument("--resume", action="store_true")
    p_ingest.add_argument("--ollama-url", default="http://localhost:11434")
    p_ingest.add_argument("--embed-model", default="bge-m3")
    p_ingest.add_argument("--chat-model", default="qwen2.5:7b")

    p_profile = sub.add_parser("profile", help="查实体画像(未实现)")
    p_profile.add_argument("doc_id")
    p_profile.add_argument("--entity", required=True)
    p_profile.add_argument("--workdir", default="./vega-workspace")

    p_query = sub.add_parser("query", help="语义检索:返回 top-k 相关片段")
    p_query.add_argument("doc_id")
    p_query.add_argument("question")
    p_query.add_argument("--workdir", default="./vega-workspace")
    p_query.add_argument("--ollama-url", default="http://localhost:11434")
    p_query.add_argument("--embed-model", default="bge-m3")

    args = parser.parse_args(argv)

    if args.cmd == "ingest":
        return asyncio.run(_ingest(args))
    if args.cmd == "query":
        return asyncio.run(_query(args))
    print(f"[vega] {args.cmd} —— 尚未实现", file=sys.stderr)
    return 0


async def _ingest(args: argparse.Namespace) -> int:
    from pathlib import Path

    from vega.core.ingest import ingest_document
    from vega.plugins.novel import NovelPlugin

    if args.plugin != "novel":
        print(f"[vega] 暂不支持插件:{args.plugin}(仅 novel)", file=sys.stderr)
        return 1
    text = Path(args.file).read_text(encoding="utf-8")
    await ingest_document(
        args.doc_id,
        text,
        NovelPlugin(),
        workdir=args.workdir,
        resume=args.resume,
        ollama_url=args.ollama_url,
        embed_model=args.embed_model,
        chat_model=args.chat_model,
    )
    return 0


async def _query(args: argparse.Namespace) -> int:
    """最小查询:embed 问题 → 搜向量库 → 打印 top-k 命中片段(带相似度)。"""
    import sqlite3
    from pathlib import Path

    import numpy as np

    from vega.core.embed import make_ollama_embedder
    from vega.store import VectorStore

    db_path = Path(args.workdir) / args.doc_id / "vectors.sqlite"
    if not db_path.exists():
        print(f"[vega] 未找到 {args.doc_id} 的知识库(先 ingest)", file=sys.stderr)
        return 1
    # 读 dim
    con = sqlite3.connect(str(db_path))
    row = con.execute("SELECT sql FROM sqlite_master WHERE name='vec'").fetchone()
    con.close()
    if not row or "float[" not in row[0]:
        print("[vega] 向量表缺失", file=sys.stderr)
        return 1
    dim = int(row[0].split("float[")[1].split("]")[0])

    embed_fn = make_ollama_embedder(base_url=args.ollama_url, model=args.embed_model)
    vecs = await embed_fn([args.question])
    q = np.array(vecs[0], dtype=np.float32).tobytes()

    store = VectorStore(args.workdir, args.doc_id, dim=dim)
    hits = store.search(q, top_k=5)
    store.close()
    if not hits:
        print("[vega] 无命中")
        return 0
    for h in hits:
        print(f"\n[seg {h.segment_id}] score={h.score:.3f}\n{h.text[:300]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
