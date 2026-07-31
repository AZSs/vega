"""KG store + 名归一合并测试。"""

from vega.core.extract import ExtractedEntity
from vega.core.normalize import make_mention, merge_aliases, merge_entity
from vega.store import KnowledgeStore


def _ext(name: str, **kw) -> ExtractedEntity:
    return ExtractedEntity(name=name, type="character", **kw)


def test_kg_put_and_get_entity(tmp_path):
    store = KnowledgeStore(str(tmp_path), "d1")
    m = make_mention("d1", 0, 100)
    ent = merge_entity(None, _ext("黄豆豆", aliases=["豆豆"], attributes={"race": "人族"}), m)
    store.set_entity(ent)
    got = store.get_entity("黄豆豆")
    assert got is not None
    assert got["name"] == "黄豆豆"
    assert got["aliases"] == ["豆豆"]
    assert got["attributes"]["race"]["value"] == "人族"
    assert got["attributes"]["race"]["mentions"] == [m]
    store.close()


def test_kg_merge_across_segments(tmp_path):
    """两段都抽到黄豆豆,累积 mentions + attributes 带溯源。"""
    store = KnowledgeStore(str(tmp_path), "d1")
    m0 = make_mention("d1", 0, 100)
    m5 = make_mention("d1", 5, 200)
    e0 = merge_entity(None, _ext("黄豆豆", attributes={"race": "人族"}), m0)
    store.set_entity(e0)
    # 第二段:已有实体 + 新属性 age
    existing = store.get_entity("黄豆豆")
    e5 = merge_entity(existing, _ext("黄豆豆", attributes={"age": "16"}), m5)
    store.set_entity(e5)
    got = store.get_entity("黄豆豆")
    assert len(got["mentions"]) == 2  # 累积两段
    assert got["attributes"]["race"]["mentions"] == [m0]
    assert got["attributes"]["age"]["value"] == "16"
    assert got["attributes"]["age"]["mentions"] == [m5]
    store.close()


def test_kg_relations_dedup(tmp_path):
    store = KnowledgeStore(str(tmp_path), "d1")
    m = make_mention("d1", 0, 100)
    store.add_relation("黄豆豆", "陆阳", "好友", m)
    store.add_relation("黄豆豆", "陆阳", "好友", make_mention("d1", 3, 100))  # 同关系累积
    store.add_relation("黄豆豆", "陆阳", "师徒", m)  # 不同关系另建
    rels = store.get_relations("黄豆豆")
    assert len(rels) == 2  # 好友 + 师徒
    friend = [r for r in rels if r["type"] == "好友"][0]
    assert len(friend["mentions"]) == 2  # 累积两段
    store.close()


def test_kg_persistence_across_reopen(tmp_path):
    store = KnowledgeStore(str(tmp_path), "d1")
    store.set_entity(merge_entity(None, _ext("陆阳"), make_mention("d1", 0, 10)))
    store.close()
    store2 = KnowledgeStore(str(tmp_path), "d1")
    assert store2.count_entities() == 1
    assert store2.get_entity("陆阳") is not None
    store2.close()


def test_merge_aliases_combines_alias_overlap():
    """不朽仙子(aliases 含 黄豆豆)与 黄豆豆(aliases 含 不朽仙子)合并。"""
    a = {
        "name": "不朽仙子",
        "type": "character",
        "aliases": ["黄豆豆"],
        "attributes": {"race": {"value": "人族", "mentions": []}},
        "mentions": [{"segment_id": 1}],
    }
    b = {
        "name": "黄豆豆",
        "type": "character",
        "aliases": ["不朽仙子"],
        "attributes": {"age": {"value": "16", "mentions": []}},
        "mentions": [{"segment_id": 5}],
    }
    merged = merge_aliases([a, b])
    assert len(merged) == 1
    assert merged[0]["name"] == "不朽仙子"  # 保留首个
    assert "黄豆豆" in merged[0]["aliases"]
    assert "age" in merged[0]["attributes"]  # 属性合并
    assert len(merged[0]["mentions"]) == 2


def test_merge_aliases_no_overlap_keeps_separate():
    """灰豆豆(不同道果)与黄豆豆 不应被别名合并(灰豆豆不在黄豆豆 aliases)。"""
    a = {
        "name": "黄豆豆",
        "type": "character",
        "aliases": ["不朽仙子"],
        "attributes": {},
        "mentions": [],
    }
    b = {
        "name": "灰豆豆",
        "type": "character",
        "aliases": [],  # 灰豆豆是独立实体,不在黄豆豆别名里
        "attributes": {},
        "mentions": [],
    }
    merged = merge_aliases([a, b])
    assert len(merged) == 2  # 不合并
