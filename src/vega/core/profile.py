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

    纯聚合(无 LLM):实体 attributes 已带 mentions 溯源,events 按 segment_id 时序,
    relations 带出处。比 synthesize_profile(抽样+LLM)更全更可信——每字段可回查原文。
    """
    from ..store import KnowledgeStore

    kg = KnowledgeStore(workdir, doc_id)
    ent = kg.get_entity(entity)
    if ent is None:
        # 别名查找
        for e in kg.list_entities():
            if entity in e.get("aliases", []) or any(a in e.get("aliases", []) for a in aliases):
                ent = e
                break
    if ent is None:
        kg.close()
        return None

    name = ent["name"]
    relations_raw = kg.get_relations(name)
    kg.close()

    events = sorted(ent.get("mentions", []), key=lambda m: m.get("segment_id", 0))
    relations = [
        {
            "target": r["object"] if r["subject"] == name else r["subject"],
            "type": r["type"],
            "mentions_count": len(r.get("mentions", [])),
        }
        for r in relations_raw
    ]
    return {
        "name": name,
        "aliases": ent.get("aliases", []),
        "type": ent.get("type"),
        "attributes": ent.get("attributes", {}),
        "relations": relations,
        "events": [{"seg": m.get("segment_id")} for m in events],
        "mention_count": len(ent.get("mentions", [])),
        "provenance": ent.get("mentions", []),
    }


__all__ = ["synthesize_profile", "build_profile_from_kg"]
