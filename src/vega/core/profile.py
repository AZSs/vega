"""画像合成 —— 召回实体片段 → 两遍合成(逐片段抽取事实 → 聚合画像)。

CLI 与 HTTP API 共用本模块。所有领域知识(focus 关键词/抽取 prompt/画像 schema)
从 DomainPlugin 取,内核不感知领域。
"""

from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from typing import Any

from ..plugins import DomainPlugin
from ..store import VectorHit, VectorStore
from .embed import ChatFn
from .llm import make_chat_from_env


async def synthesize_profile(
    workdir: str,
    doc_id: str,
    entity: str,
    aliases: list[str],
    plugin: DomainPlugin,
    chat_fn: ChatFn | None = None,
) -> dict[str, Any] | None:
    """合成实体画像,返回画像 dict(失败返 None)。"""
    chat = chat_fn or make_chat_from_env()

    db_path = Path(workdir) / doc_id / "vectors.sqlite"
    con = sqlite3.connect(str(db_path))
    row = con.execute("SELECT sql FROM sqlite_master WHERE name='vec'").fetchone()
    con.close()
    if not row or "float[" not in row[0]:
        return None
    dim = int(row[0].split("float[")[1].split("]")[0])

    keywords = [entity] + aliases
    store = VectorStore(workdir, doc_id, dim=dim)
    seen: set[str] = set()
    mentions: list[VectorHit] = []
    for kw in keywords:
        for h in store.find_texts_containing(kw, limit=400):
            if h.text and h.text not in seen:
                seen.add(h.text)
                mentions.append(h)
    store.close()
    if not mentions:
        return None

    mentions.sort(key=lambda h: h.segment_id)
    focus_kws = plugin.focus_keywords()
    focus_ids: set[int] = set()
    focus: list[VectorHit] = []
    for h in mentions:
        if any(k in h.text for k in focus_kws):
            focus.append(h)
            focus_ids.add(id(h))

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

    alias_note = f"(别名:{'、'.join(aliases)})" if aliases else ""
    extract_sys = plugin.profile_extract_system()
    fields = plugin.profile_fields()
    all_facts: list[dict[str, object]] = []
    for h in sample:
        extract_user = (
            f"目标角色:{entity}{alias_note}\n片段:[段{h.segment_id}] {h.text}\n"
            f'输出 {{"facts":[{{"field":"{fields}","value":"...","seg":N}}]}}'
        )
        try:
            raw = await chat(extract_sys, extract_user)
            m = re.search(r"\{[\s\S]*\}", raw)
            if m:
                for f in json.loads(m.group(0)).get("facts", []):
                    all_facts.append(f)
        except Exception:
            continue

    facts_block = json.dumps(all_facts, ensure_ascii=False, indent=1)[:8000]
    merge_sys = (
        "你是实体画像合成器。根据给定的事实列表(每条带来源段号 seg),"
        "为指定实体合成结构化画像。只依据事实,不确定填 null,不要编造。只输出 JSON。"
    )
    merge_user = (
        f"实体:{entity}{alias_note}\n\n事实列表:\n{facts_block}\n\n"
        f"输出 JSON 格式(只依据事实,不确定填 null,不要编造):\n{plugin.profile_schema()}"
    )
    raw = await chat(merge_sys, merge_user)
    m = re.search(r"\{[\s\S]*\}", raw)
    if m:
        try:
            return dict[str, Any](json.loads(m.group(0)))
        except json.JSONDecodeError:
            pass
    return {"_raw": raw}


def build_profile_from_kg(
    workdir: str,
    doc_id: str,
    entity: str,
    aliases: list[str],
    plugin: DomainPlugin,
) -> dict[str, Any] | None:
    """从 KG 聚合实体画像(全量 mentions,无抽样,带溯源)。

    名归一(权重驱动):合并「用户提供的别名集」{entity}∪aliases 中各 name 的实体,
    正名取 mentions 最多的高频名(防低频噪声盖正名,如「不朽仙人」偶现不能盖「不朽仙子」)。
    不并 LLM 抽的噪声别名(如「不朽仙人」被标 alias 不朽仙子,实为另一人)。
    """
    from ..store import KnowledgeStore

    kg = KnowledgeStore(workdir, doc_id)
    name_set = {entity, *aliases}
    # 只按 name 精确匹配用户别名集(不认 LLM 抽的 aliases,防噪声错并)
    to_merge = [e for e in kg.list_entities() if e["name"] in name_set]
    if not to_merge:
        kg.close()
        return None

    # 权重:mentions 多的为正名(高频优先)
    to_merge.sort(key=lambda e: len(e.get("mentions", [])), reverse=True)
    canonical = to_merge[0]
    name = canonical["name"]

    # 聚合 attributes / mentions / aliases(带溯源,合并多实体)
    attributes: dict[str, Any] = {}
    all_mentions: list[dict[str, Any]] = []
    alias_union: set[str] = set()
    for e in to_merge:
        for k, entry in e.get("attributes", {}).items():
            if k not in attributes:
                attributes[k] = {
                    "value": entry.get("value"),
                    "mentions": list(entry.get("mentions", [])),
                }
            else:
                merged_entry = attributes[k]
                merged_entry["mentions"] = merged_entry["mentions"] + list(
                    entry.get("mentions", [])
                )
                if not merged_entry.get("value") and entry.get("value"):
                    merged_entry["value"] = entry["value"]
        all_mentions.extend(e.get("mentions", []))
        for a in e.get("aliases", []):
            if a not in name_set:
                alias_union.add(a)
    # relations:合并集里各实体的关系
    relations_raw: list[dict[str, Any]] = []
    for e in to_merge:
        relations_raw.extend(kg.get_relations(e["name"]))
    kg.close()

    # relations 去重(subject/object/type)
    seen_rel: set[tuple[str, str, str]] = set()
    relations: list[dict[str, Any]] = []
    for r in relations_raw:
        key = (r["subject"], r["object"], r["type"])
        if key in seen_rel:
            continue
        seen_rel.add(key)
        relations.append(
            {
                "target": r["object"] if r["subject"] in name_set else r["subject"],
                "type": r["type"],
                "mentions_count": len(r.get("mentions", [])),
            }
        )

    events = sorted(all_mentions, key=lambda m: m.get("segment_id", 0))
    return {
        "name": name,
        "canonical_weight": len(canonical.get("mentions", [])),
        "merged_names": [e["name"] for e in to_merge],
        "aliases": sorted(alias_union),
        "type": canonical.get("type"),
        "attributes": attributes,
        "relations": relations,
        "events": [{"seg": m.get("segment_id")} for m in events],
        "mention_count": len(all_mentions),
        "provenance_count": len(all_mentions),
    }


async def build_profile_from_lightrag(
    workdir: str,
    doc_id: str,
    entity: str,
    aliases: list[str],
    plugin: DomainPlugin,
    chat_fn: ChatFn | None = None,
    config: Any = None,
) -> dict[str, Any] | None:
    """从 LightRAG 底座聚合结构化画像(两层抽取)。

    第一层 LightRAG:自主发现实体 + source chunks(不靠用户种子)。
    第二层 vega:对 source chunks 跑结构化 extract_prompt(race/dao_fruit/origin),
    带 chunk_key 溯源 → 聚合成结构化画像。
    """
    from .config import load_config
    from .lightrag_engine import LightRAGEngine
    from .llm import make_chat_from_config

    cfg = config or load_config()
    chat = chat_fn or make_chat_from_config(cfg, "profile")
    engine = LightRAGEngine(workdir, doc_id, plugin, chat=chat, config=cfg)

    # 收集实体(含别名)的 source chunks(LightRAG 自主发现 + 溯源)
    all_chunks: dict[str, str] = {}  # chunk_key -> text(去重)
    merged_names: list[str] = []
    for name in [entity, *aliases]:
        result = await engine.get_entity_with_sources(name)
        if result:
            merged_names.append(name)
            for key, text in zip(
                result.get("source_chunk_keys", []), result.get("source_chunks", []), strict=False
            ):
                if key not in all_chunks and text.strip():
                    all_chunks[key] = text

    if not all_chunks:
        return None
    print(f"[vega-lightrag] {entity} 收集到 {len(all_chunks)} 个 source chunks(LightRAG 溯源)")

    # pass1:逐 chunk 抽目标实体结构化事实(race/dao_fruit/origin,带 chunk_key 溯源)
    extract_sys = plugin.profile_extract_system()
    fields = plugin.profile_fields()
    alias_note = f"(别名:{'、'.join(aliases)})" if aliases else ""
    all_facts: list[dict[str, object]] = []
    for chunk_key, text in all_chunks.items():
        extract_user = (
            f"目标角色:{entity}{alias_note}\n片段:[{chunk_key}] {text[:3000]}\n"
            f'输出 {{"facts":[{{"field":"{fields}","value":"...","seg":"{chunk_key}"}}]}}'
        )
        try:
            raw = await chat(extract_sys, extract_user)
            m = re.search(r"\{[\s\S]*\}", raw)
            if m:
                for f in json.loads(m.group(0)).get("facts", []):
                    all_facts.append(f)
        except Exception:
            continue

    print(f"[vega-lightrag] pass1 抽取 {len(all_facts)} 条事实,pass2 聚合...")

    # pass2:聚合事实 → 结构化画像
    facts_block = json.dumps(all_facts, ensure_ascii=False, indent=1)[:8000]
    merge_sys = (
        "你是实体画像合成器。根据给定的事实列表(每条带来源 chunk_key),"
        "为指定实体合成结构化画像。只依据事实,不确定填 null,不要编造。只输出 JSON。"
    )
    merge_user = (
        f"实体:{entity}{alias_note}\n\n事实列表:\n{facts_block}\n\n"
        f"输出 JSON 格式(只依据事实,不确定填 null,不要编造):\n{plugin.profile_schema()}"
    )
    raw = await chat(merge_sys, merge_user)
    m = re.search(r"\{[\s\S]*\}", raw)
    if m:
        try:
            result = dict[str, Any](json.loads(m.group(0)))
            result["_merged_names"] = merged_names
            result["_source_chunks"] = len(all_chunks)
            result["_facts"] = len(all_facts)
            return result
        except json.JSONDecodeError:
            pass
    return {"_raw": raw, "_merged_names": merged_names}


__all__ = ["synthesize_profile", "build_profile_from_kg", "build_profile_from_lightrag"]
