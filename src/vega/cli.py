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
    p_ingest.add_argument("--limit", type=int, default=None, help="只 ingest 前 N 章(验证用)")
    p_ingest.add_argument(
        "--no-context", action="store_true", help="关闭 contextual 前缀(全文快速建库)"
    )

    p_profile = sub.add_parser("profile", help="合成实体画像(召回片段→LLM 结构化)")
    p_profile.add_argument("doc_id")
    p_profile.add_argument("--entity", required=True, help="实体主名(如 黄豆豆)")
    p_profile.add_argument("--aliases", default="", help="别名逗号分隔(如 不朽仙子,豆豆)")
    p_profile.add_argument("--workdir", default="./vega-workspace")
    p_profile.add_argument("--ollama-url", default="http://localhost:11434")
    p_profile.add_argument("--chat-model", default="qwen2.5:7b")

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
    if args.cmd == "profile":
        return asyncio.run(_profile(args))
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
        limit=args.limit,
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
    """合成实体画像:文本召回所有提到实体(主名+别名)的块 → 抽样 → LLM 结构化合成 → 打印。

    名归一:主名+别名并集召回(不朽仙子=黄豆豆)。溯源:每块带 segment_id。
    """
    import json
    import re
    import sqlite3
    from pathlib import Path

    from vega.core.llm import make_chat_from_env
    from vega.store import VectorHit, VectorStore

    db_path = Path(args.workdir) / args.doc_id / "vectors.sqlite"
    if not db_path.exists():
        print(f"[vega] 未找到 {args.doc_id} 的知识库(先 ingest)", file=sys.stderr)
        return 1
    con = sqlite3.connect(str(db_path))
    row = con.execute("SELECT sql FROM sqlite_master WHERE name='vec'").fetchone()
    con.close()
    if not row or "float[" not in row[0]:
        print("[vega] 向量表缺失", file=sys.stderr)
        return 1
    dim = int(row[0].split("float[")[1].split("]")[0])

    aliases = [a.strip() for a in args.aliases.split(",") if a.strip()]
    keywords = [args.entity] + aliases
    store = VectorStore(args.workdir, args.doc_id, dim=dim)

    # 召回所有提及实体(主名或别名)的块,去重
    seen: set[str] = set()
    mentions: list[VectorHit] = []
    for kw in keywords:
        for h in store.find_texts_containing(kw, limit=400):
            if h.text and h.text not in seen:
                seen.add(h.text)
                mentions.append(h)
    store.close()
    mentions.sort(key=lambda h: h.segment_id)
    print(f"[vega] 「{args.entity}」(含别名 {aliases})命中 {len(mentions)} 个块")

    if not mentions:
        print("[vega] 无命中,无法合成画像")
        return 0

    # 定向召回:含出身/成仙关键词的块优先(部落/道果/寂灭/成仙/岁...),否则均匀抽样会漏关键事实
    focus_kws = ["部落", "道果", "寂灭", "成仙", "十六岁", "岁", "族人", "灭族", "废"]
    focus_ids: set[int] = set()
    focus: list[VectorHit] = []
    for h in mentions:
        if any(k in h.text for k in focus_kws):
            focus.append(h)
            focus_ids.add(id(h))
    print(f"[vega] 定向命中(出身/成仙关键词){len(focus)} 块")

    # 样本:定向块优先,超量则均匀裁剪;不足则用其余块补齐到 n_target
    n_target = 80
    rest = [h for h in mentions if id(h) not in focus_ids]
    if len(focus) >= n_target:
        step = len(focus) / n_target
        sample = [focus[int(i * step)] for i in range(n_target)]
    else:
        n_fill = n_target - len(focus)
        if len(rest) > n_fill:
            rstep = len(rest) / n_fill
            fill = [rest[int(i * rstep)] for i in range(n_fill)]
        else:
            fill = rest
        sample = focus + fill
    sample.sort(key=lambda h: h.segment_id)
    print(f"[vega] 样本 {len(sample)} 块(定向 {len(focus)} 优先)")
    alias_note = f"(别名:{'、'.join(aliases)})" if aliases else ""
    chat_fn = make_chat_from_env()

    # 两遍合成(防一锅烩搞混主角):
    # pass1 逐片段只抽关于目标角色的事实(滤掉其他角色) → pass2 聚合成画像
    extract_sys = (
        "你从小说片段中提取【只关于指定角色】的事实。"
        "片段里会出现其他角色,只提取明确关于目标角色的事实,他人的忽略。"
        "重点关注:出身种族(人族/妖族等,区别于当前境界)、身世(部落/家族/遭遇,如部落被灭)、"
        "年龄、道果(道果名及状态,如 寂灭道果 被废)、修为境界、成仙相关(如何成仙/成仙前代价/复活)、"
        "化身或复活形态(如复活后使用某道果的另一个自我)、"
        "关系网(含所属群体如同辈仙人组合/上古四仙,及个体关系如师徒/恋人/好友)。"
        "无则 facts 空数组。只输出 JSON。"
    )
    all_facts: list[dict[str, object]] = []
    for h in sample:
        extract_user = (
            f"目标角色:{args.entity}{alias_note}\n片段:[段{h.segment_id}] {h.text}\n"
            '输出 {"facts":[{"field":"race|origin|age|dao_fruit|gender|appearance|'
            'personality|cultivation|technique|artifact|relation|immortalization|event",'
            '"value":"...","seg":N}]}'
        )
        try:
            raw = await chat_fn(extract_sys, extract_user)
            m = re.search(r"\{[\s\S]*\}", raw)
            if m:
                facts = json.loads(m.group(0)).get("facts", [])
                for f in facts:
                    all_facts.append(f)
        except Exception:
            continue
    print(f"[vega] pass1 抽取事实 {len(all_facts)} 条,pass2 聚合合成画像...")

    facts_block = json.dumps(all_facts, ensure_ascii=False, indent=1)[:8000]
    merge_sys = (
        "你是小说人物画像合成器。根据给定的事实列表(每条带来源段号 seg),"
        "为指定角色合成结构化人物画像。只依据事实,不确定填 null,不要编造。只输出 JSON。"
    )
    merge_user = (
        f"角色:{args.entity}{alias_note}\n\n事实列表:\n{facts_block}\n\n"
        "输出 JSON 格式:\n"
        '{"name":"...","race":"出身种族(人族/妖族等,非当前境界)",'
        '"origin":"身世出身(部落/家族/遭遇,如部落被灭)",'
        '"age":"年龄","dao_fruit":"道果及状态(如寂灭道果,成仙前被废)",'
        '"gender":"性别","appearance":"外貌","personality":"性格",'
        '"cultivation_stages":[{"stage":"境界","from_seg":N}],'
        '"techniques":["功法"],"artifacts":["法宝/持有物"],'
        '"relations":[{"target":"角色","type":"关系"}],'
        '"key_events":[{"seg":N,"desc":"事件"}],'
        '"immortalization_path":"成仙路径(如何成仙,代价是什么)"}'
    )
    raw = await chat_fn(merge_sys, merge_user)
    m = re.search(r"\{[\s\S]*\}", raw)
    if m:
        try:
            parsed = json.loads(m.group(0))
            print("\n=== 人物画像 ===")
            print(json.dumps(parsed, ensure_ascii=False, indent=2))
            print(
                f"\n(基于 {len(sample)} 个抽样片段 / pass1 {len(all_facts)} 条事实,"
                f"全文命中 {len(mentions)} 块)"
            )
            return 0
        except json.JSONDecodeError:
            pass
    print("\n=== 画像(原文输出) ===\n", raw)
    return 0


if __name__ == "__main__":
    sys.exit(main())
