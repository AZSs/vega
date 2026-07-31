"""名归一 + 实体合并 —— 纯逻辑(零 LLM,零 IO)。

- merge_entity:把单段抽取的 ExtractedEntity 合并进累积实体(累积 mentions/aliases/
  attributes 带溯源),跨段同实体事实聚合。
- merge_aliases:别名相交的实体合并成一个(名归一)。
"""

from __future__ import annotations

from typing import Any

from .extract import ExtractedEntity


def make_mention(doc_id: str, segment_id: int, char_end: int) -> dict[str, Any]:
    """段级 Mention(整段为溯源单位)。"""
    return {"doc_id": doc_id, "segment_id": segment_id, "char_start": 0, "char_end": char_end}


def merge_entity(
    existing: dict[str, Any] | None,
    extracted: ExtractedEntity,
    mention: dict[str, Any],
) -> dict[str, Any]:
    """把单段抽取的实体合并进 existing(无则新建)。返回合并后实体 dict。

    - aliases: 并集
    - mentions: 追加 mention
    - attributes: 同 key 追加 mention(保留首个非空 value;跨段多值用 mentions 溯源)
    """
    if existing is None:
        attributes: dict[str, Any] = {}
        for k, v in extracted.attributes.items():
            attributes[k] = {"value": v, "mentions": [mention]}
        return {
            "name": extracted.name,
            "type": extracted.type,
            "aliases": list(extracted.aliases),
            "attributes": attributes,
            "mentions": [mention],
        }

    # aliases 并集
    aliases = list(existing.get("aliases", []))
    for a in extracted.aliases:
        if a not in aliases and a != existing["name"]:
            aliases.append(a)

    # attributes 合并
    attributes = dict(existing.get("attributes", {}))
    for k, v in extracted.attributes.items():
        if k not in attributes:
            attributes[k] = {"value": v, "mentions": [mention]}
        else:
            entry = dict(attributes[k])
            mentions = list(entry.get("mentions", []))
            mentions.append(mention)
            # 保留首个非空 value
            if not entry.get("value") and v:
                entry["value"] = v
            entry["mentions"] = mentions
            attributes[k] = entry

    mentions = list(existing.get("mentions", [])) + [mention]
    return {
        "name": existing["name"],
        "type": existing["type"],
        "aliases": aliases,
        "attributes": attributes,
        "mentions": mentions,
    }


def merge_aliases(entities: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """别名相交的实体合并成一个(名归一)。

    若 A 的 name 在 B 的 aliases 里(或反之),把 B 并入 A(累积 mentions/attributes/aliases)。
    返回去重后的实体列表。
    """
    result: list[dict[str, Any]] = []
    for ent in entities:
        target = _find_alias_match(ent, result)
        if target is None:
            result.append(dict(ent))
        else:
            merged = _merge_two(target, ent)
            result[result.index(target)] = merged
    return result


def _find_alias_match(ent: dict[str, Any], pool: list[dict[str, Any]]) -> dict[str, Any] | None:
    names = {ent["name"], *ent.get("aliases", [])}
    for p in pool:
        p_names = {p["name"], *p.get("aliases", [])}
        if names & p_names:
            return p
    return None


def _merge_two(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    """合并两个同实体(别名相交)的累积实体。"""
    aliases = list(a.get("aliases", []))
    for x in [b["name"], *b.get("aliases", [])]:
        if x not in aliases and x != a["name"]:
            aliases.append(x)
    attributes = dict(a.get("attributes", {}))
    for k, entry in b.get("attributes", {}).items():
        if k not in attributes:
            attributes[k] = entry
        else:
            merged_entry = dict(attributes[k])
            merged_entry["mentions"] = list(merged_entry.get("mentions", [])) + list(
                entry.get("mentions", [])
            )
            if not merged_entry.get("value") and entry.get("value"):
                merged_entry["value"] = entry["value"]
            attributes[k] = merged_entry
    return {
        "name": a["name"],
        "type": a.get("type") or b.get("type"),
        "aliases": aliases,
        "attributes": attributes,
        "mentions": list(a.get("mentions", [])) + list(b.get("mentions", [])),
    }


__all__ = ["merge_entity", "merge_aliases", "make_mention"]
