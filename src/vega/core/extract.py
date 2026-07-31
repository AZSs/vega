"""实体/关系抽取 —— 调领域插件的 extract_prompt,从段抽实体/关系(带段级 Mention 溯源)。

经 DomainPlugin 接口注入领域 prompt,内核不感知具体领域。
每段抽取的实体/关系挂 Mention(segment.id + 段级字符区间),为画像溯源打基础。
"""

from __future__ import annotations

import json
import re

from pydantic import BaseModel, Field

from ..plugins import DomainPlugin
from ..schemas import Segment
from .embed import ChatFn


class ExtractedRelation(BaseModel):
    """抽取的关系(subject/object 用角色名,后续名归一映射到 entity)。"""

    subject: str
    object: str
    type: str


class ExtractedEntity(BaseModel):
    """单段抽取的一个实体(尚未跨段归一)。attributes 为 str→原始值(合并时带溯源)。"""

    name: str
    type: str = "character"
    aliases: list[str] = Field(default_factory=list)
    attributes: dict[str, str] = Field(default_factory=dict)
    relations: list[ExtractedRelation] = Field(default_factory=list)


async def extract_segment(
    segment: Segment, plugin: DomainPlugin, *, chat: ChatFn, doc_id: str
) -> list[ExtractedEntity]:
    """对单段调 LLM 抽实体/关系。失败返空(降级,不阻断)。

    Mention 溯源在 KG 合并时按段附加(段级:char_start=0,char_end=len(text))。
    """
    try:
        raw = await chat("你只输出 JSON,不输出任何额外文字。", plugin.extract_prompt(segment.text))
    except Exception:
        return []
    m = re.search(r"\{[\s\S]*\}", raw)
    if not m:
        return []
    try:
        data = json.loads(m.group(0))
    except json.JSONDecodeError:
        return []
    out: list[ExtractedEntity] = []
    # relations 可能在顶层(data["relations"])或 entity 内(e["relations"]),两处都收
    top_rels: dict[str, list[ExtractedRelation]] = {}
    for r in data.get("relations", []):
        try:
            rel = ExtractedRelation(
                subject=str(r["subject"]), object=str(r["object"]), type=str(r["type"])
            )
            top_rels.setdefault(rel.subject, []).append(rel)
        except (KeyError, TypeError):
            continue
    for e in data.get("entities", []):
        try:
            name = str(e["name"])
            rels = [ExtractedRelation(**r) for r in e.get("relations", [])]
            rels.extend(top_rels.get(name, []))
            out.append(
                ExtractedEntity(
                    name=name,
                    type=str(e.get("type", "character")),
                    aliases=[str(a) for a in e.get("aliases", [])],
                    attributes={k: str(v) for k, v in e.get("attributes", {}).items()},
                    relations=rels,
                )
            )
        except (KeyError, TypeError):
            continue
    return out


async def extract_document(
    workdir: str,
    doc_id: str,
    plugin: DomainPlugin,
    *,
    chat: ChatFn | None = None,
    resume: bool = False,
    filter_keywords: list[str] | None = None,
    limit: int | None = None,
    concurrency: int = 5,
) -> None:
    """全量逐块抽取 → 落 KG(断点续跑)。

    遍历向量库所有块,逐块 extract_segment → merge_entity 累积进 KG(带段级 Mention 溯源)
    → 关系 add_relation。完成后 merge_aliases 名归一。kg_manifest.json 记 done rowid。
    filter_keywords: 只抽含任一关键词的块(验证用,缩小范围;None=全量)。
    """
    import json
    import sqlite3
    from pathlib import Path

    from ..store import KnowledgeStore, VectorStore
    from .llm import make_chat_from_env
    from .normalize import make_mention, merge_entity

    chat_fn = chat or make_chat_from_env()
    vdb_path = Path(workdir) / doc_id / "vectors.sqlite"
    con = sqlite3.connect(str(vdb_path))
    row = con.execute("SELECT sql FROM sqlite_master WHERE name='vec'").fetchone()
    con.close()
    if not row or "float[" not in row[0]:
        print(f"[vega] {doc_id} 无向量库(先 ingest)")
        return
    dim = int(row[0].split("float[")[1].split("]")[0])

    vstore = VectorStore(workdir, doc_id, dim=dim)
    chunks = vstore.all_texts()
    vstore.close()

    kg = KnowledgeStore(workdir, doc_id)
    manifest_path = Path(workdir) / doc_id / "kg_manifest.json"
    done: set[int] = set()
    if resume and manifest_path.exists():
        done = set(json.loads(manifest_path.read_text()).get("done", []))

    total = len(chunks)
    if filter_keywords:
        chunks = [(r, s, t) for (r, s, t) in chunks if any(k in t for k in filter_keywords)]
        print(f"[vega] {doc_id} filter={filter_keywords} 命中 {len(chunks)}/{total} 块")
    if limit is not None:
        # 均匀抽样 limit 块(跨全书,覆盖早/中/晚)
        if len(chunks) > limit:
            step = len(chunks) / limit
            chunks = [chunks[int(i * step)] for i in range(limit)]
        print(f"[vega] {doc_id} limit={limit} 抽样 {len(chunks)} 块")
    total = len(chunks)
    pending_chunks = [(r, s, t) for (r, s, t) in chunks if r not in done and t.strip()]

    import asyncio

    sem = asyncio.Semaphore(concurrency)
    batch_size = concurrency * 2

    async def extract_one(
        rowid: int, seg_id: int, text: str
    ) -> tuple[int, int, str, list[ExtractedEntity]]:
        async with sem:
            seg = Segment(id=seg_id, text=text)
            ents = await extract_segment(seg, plugin, chat=chat_fn, doc_id=doc_id)
            return (rowid, seg_id, text, ents)

    idx = 0
    for i in range(0, len(pending_chunks), batch_size):
        batch = pending_chunks[i : i + batch_size]
        results = await asyncio.gather(*(extract_one(r, s, t) for r, s, t in batch))
        # 串行落 KG(sqlite 单连接)
        for rowid, seg_id, text, entities in results:
            mention = make_mention(doc_id, seg_id, len(text))
            for e in entities:
                existing = kg.get_entity(e.name)
                kg.set_entity(merge_entity(existing, e, mention))
                for rel in e.relations:
                    kg.add_relation(e.name, rel.object, rel.type, mention)
            done.add(rowid)
            idx += 1
            if idx % 50 == 0 or idx == len(pending_chunks):
                n_ent = kg.count_entities()
                print(f"[vega] {doc_id} 抽取 {idx}/{len(pending_chunks)} 块,实体 {n_ent}")
                manifest_path.write_text(json.dumps({"done": sorted(done)}))

    # 名归一不在此自动做:LLM 抽的别名噪声大(如「不朽仙人」被标 alias 不朽仙子,实为另一人)。
    # 改由 build_profile_from_kg 按用户提供的别名集 + 权重(mentions 数)合并,正名取最高频。
    kg.close()
    manifest_path.write_text(json.dumps({"done": sorted(done)}))
    print(f"[vega] {doc_id} 抽取完成:{len(done)}/{total} 块,{kg.count_entities()} 实体")


__all__ = ["ExtractedEntity", "ExtractedRelation", "extract_segment"]
