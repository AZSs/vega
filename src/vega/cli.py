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
from pathlib import Path


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
    p_ingest.add_argument("--limit", type=int, default=None, help="只 ingest 前 N 章(验证用)")
    p_ingest.add_argument(
        "--no-context", action="store_true", help="关闭 contextual 前缀(全文快速建库)"
    )
    p_ingest.add_argument(
        "--backend",
        choices=["self", "lightrag"],
        default="self",
        help="底座:self=vega 自建(sqlite-vec+KG),lightrag=LightRAG 自主发现",
    )
    p_ingest.add_argument("--config", default=None, help="vega.toml 配置路径")
    p_ingest.add_argument(
        "--shards", type=int, default=1, help="并行分片数(>1 启用 MapReduce 并行)"
    )

    p_profile = sub.add_parser("profile", help="合成实体画像(召回片段→LLM 结构化)")
    p_profile.add_argument("doc_id")
    p_profile.add_argument("--entity", required=True, help="实体主名")
    p_profile.add_argument("--aliases", default="", help="别名逗号分隔")
    p_profile.add_argument("--plugin", default="novel", help="领域插件")
    p_profile.add_argument("--workdir", default="./vega-workspace")
    p_profile.add_argument("--ollama-url", default="http://localhost:11434")
    p_profile.add_argument("--chat-model", default="qwen2.5:7b")
    p_profile.add_argument(
        "--kg", action="store_true", help="从 KG 聚合画像(全量+溯源,需先 extract)"
    )
    p_profile.add_argument(
        "--backend",
        choices=["self", "lightrag"],
        default="self",
        help="底座:lightrag=LightRAG 自主发现+结构化画像",
    )
    p_profile.add_argument("--config", default=None, help="vega.toml 配置路径")

    p_query = sub.add_parser("query", help="语义检索:返回 top-k 相关片段")
    p_query.add_argument("doc_id")
    p_query.add_argument("question")
    p_query.add_argument("--workdir", default="./vega-workspace")
    p_query.add_argument("--ollama-url", default="http://localhost:11434")
    p_query.add_argument("--embed-model", default="bge-m3")

    p_plugins = sub.add_parser("plugins", help="列出可用领域插件")
    p_plugins.add_argument("--config", default=None, help="vega.toml 配置路径")

    p_extract = sub.add_parser("extract", help="全量逐块抽取实体/关系落 KG")
    p_extract.add_argument("doc_id")
    p_extract.add_argument("--plugin", default="novel")
    p_extract.add_argument("--workdir", default="./vega-workspace")
    p_extract.add_argument("--resume", action="store_true")
    p_extract.add_argument("--config", default=None, help="vega.toml 插件配置路径")
    p_extract.add_argument(
        "--filter", default="", help="只抽含这些关键词的块(逗号分隔,验证用缩小范围)"
    )
    p_extract.add_argument("--limit", type=int, default=None, help="抽样上限(均匀跨全书)")
    p_extract.add_argument("--concurrency", type=int, default=5, help="并发抽取数")

    p_serve = sub.add_parser("serve", help="启动 HTTP 服务(供消费端交互式查询)")
    p_serve.add_argument("--workdir", default="./vega-workspace")
    p_serve.add_argument("--host", default="127.0.0.1")
    p_serve.add_argument("--port", type=int, default=8765)
    p_serve.add_argument("--config", default=None, help="vega.toml 插件配置路径")

    args = parser.parse_args(argv)

    if args.cmd == "ingest":
        return asyncio.run(_ingest(args))
    if args.cmd == "query":
        return asyncio.run(_query(args))
    if args.cmd == "profile":
        return asyncio.run(_profile(args))
    if args.cmd == "extract":
        return asyncio.run(_extract(args))
    if args.cmd == "plugins":
        return _plugins(args)
    if args.cmd == "serve":
        return _serve(args)
    print(f"[vega] {args.cmd} —— 尚未实现", file=sys.stderr)
    return 0


async def _ingest(args: argparse.Namespace) -> int:
    from pathlib import Path

    from vega.plugins import load_plugin

    try:
        plugin = load_plugin(args.plugin)
    except ValueError as e:
        print(f"[vega] {e}", file=sys.stderr)
        return 1
    text = Path(args.file).read_text(encoding="utf-8")
    if args.limit:
        # 限章:只取前 N 章(切章后截断)
        document = plugin.split_sections(args.doc_id, text)
        text = "\n\n".join(s.text for s in document.segments[: args.limit])

    if args.backend == "lightrag":
        from vega.core.config import load_config
        from vega.core.lightrag_engine import LightRAGEngine

        config = load_config(getattr(args, "config", None))
        engine = LightRAGEngine(args.workdir, args.doc_id, plugin, config=config)
        if args.shards > 1:
            await engine.ingest_parallel(text, shards=args.shards)
        else:
            await engine.ingest(text)
        entities = await engine.discover_entities()
        print(f"\n[vega-lightrag] 自主发现 {len(entities)} 实体(前 20):")
        for ent in entities[:20]:
            print(f"  {ent['name']} ({ent['type']}) degree={ent['degree']}")
        return 0

    from vega.core.ingest import ingest_document

    await ingest_document(
        args.doc_id,
        text,
        plugin,
        workdir=args.workdir,
        resume=args.resume,
        ollama_url=args.ollama_url,
        embed_model=args.embed_model,
        chat_model=args.chat_model,
        context_prefix=not args.no_context,
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


async def _profile(args: argparse.Namespace) -> int:
    """合成实体画像。--backend lightrag:LightRAG 自主发现+结构化画像;--kg:自建 KG 聚合。"""
    import json

    from vega.plugins import load_plugin

    aliases = [a.strip() for a in args.aliases.split(",") if a.strip()]
    plugin = load_plugin(args.plugin, getattr(args, "config", None))

    if args.backend == "lightrag":
        from vega.core.config import load_config
        from vega.core.profile import build_profile_from_lightrag

        config = load_config(getattr(args, "config", None))
        result = await build_profile_from_lightrag(
            args.workdir, args.doc_id, args.entity, aliases, plugin, config=config
        )
        if result is None:
            print(f"[vega] LightRAG 中未找到 {args.entity}(先 vega ingest --backend lightrag?)")
            return 1
        print("\n=== 人物画像(LightRAG 自主发现 + 结构化溯源) ===")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    if args.kg:
        from vega.core.profile import build_profile_from_kg

        result = build_profile_from_kg(args.workdir, args.doc_id, args.entity, aliases, plugin)
        if result is None:
            print(f"[vega] KG 中未找到 {args.entity}(先 vega extract?)")
            return 1
        print("\n=== 人物画像(KG 聚合,全量+溯源) ===")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    db_path = Path(args.workdir) / args.doc_id / "vectors.sqlite"
    if not db_path.exists():
        print(f"[vega] 未找到 {args.doc_id} 的知识库(先 ingest)", file=sys.stderr)
        return 1
    from vega.core.profile import synthesize_profile

    result = await synthesize_profile(args.workdir, args.doc_id, args.entity, aliases, plugin)
    if result is None:
        print("[vega] 无命中或向量表缺失,无法合成画像")
        return 1
    print("\n=== 人物画像 ===")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


async def _extract(args: argparse.Namespace) -> int:
    """全量逐块抽取实体/关系 → 落 KG(断点续跑)。"""
    from vega.core.extract import extract_document
    from vega.plugins import load_plugin

    try:
        plugin = load_plugin(args.plugin, getattr(args, "config", None))
    except ValueError as e:
        print(f"[vega] {e}", file=sys.stderr)
        return 1
    fks = [k.strip() for k in args.filter.split(",") if k.strip()] or None
    await extract_document(
        args.workdir,
        args.doc_id,
        plugin,
        resume=args.resume,
        filter_keywords=fks,
        limit=args.limit,
        concurrency=args.concurrency,
    )
    return 0


def _plugins(args: argparse.Namespace) -> int:
    """列出可用领域插件(注册表:entry points + 配置 + 内置)。"""
    from vega.plugins import discover_plugins

    plugins = discover_plugins(args.config)
    print("可用插件:")
    for name, spec in sorted(plugins.items()):
        print(f"  {name} -> {spec}")
    return 0


def _serve(args: argparse.Namespace) -> int:
    """启动 HTTP 服务(FastAPI),供消费端(如 spica)交互式查询。"""
    import uvicorn

    from vega.api import create_app

    app = create_app(workdir=args.workdir, config_path=args.config)
    uvicorn.run(app, host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    sys.exit(main())
