"""内核 schema 契约测试 —— 领域中立,任何领域产物都能套。"""

from vega.schemas import (
    AttributeValue,
    Document,
    Entity,
    EntityProfile,
    Mention,
    ProfileEvent,
    Relation,
    Segment,
)


def test_mention_frozen():
    m = Mention(doc_id="d1", segment_id=0, char_start=0, char_end=10, text="片段")
    assert m.doc_id == "d1"
    try:
        m.text = "改"  # frozen
        raise AssertionError("Mention 应不可变")
    except Exception:
        pass


def test_entity_with_attributes_and_mentions():
    e = Entity(
        id="e1",
        name="黄豆豆",
        aliases=["豆豆", "仙子"],
        type="character",
        attributes={
            "race": AttributeValue(
                value="人族",
                mentions=[Mention(doc_id="d1", segment_id=2, char_start=0, char_end=5)],
            )
        },
        mentions=[Mention(doc_id="d1", segment_id=0, char_start=0, char_end=3)],
    )
    assert e.attributes["race"].value == "人族"
    assert len(e.attributes["race"].mentions) == 1
    assert e.aliases == ["豆豆", "仙子"]


def test_relation():
    r = Relation(
        id="r1",
        subject="e1",
        object="e2",
        type="师徒",
        mentions=[Mention(doc_id="d1", segment_id=1, char_start=0, char_end=4)],
    )
    assert r.subject == "e1" and r.object == "e2" and r.type == "师徒"


def test_entity_profile_provenance():
    p = EntityProfile(
        entity_id="e1",
        summary="...",
        attributes={"race": AttributeValue(value="人族")},
        events=[ProfileEvent(order=0, segment_id=0, desc="登场")],
        provenance=[Mention(doc_id="d1", segment_id=0, char_start=0, char_end=3)],
    )
    assert p.events[0].order == 0
    assert len(p.provenance) == 1


def test_document_segment_lookup():
    d = Document(id="d1", segments=[Segment(id=0, text="a"), Segment(id=1, text="b")])
    assert d.segment_by_id(1) is not None and d.segment_by_id(1).text == "b"
    assert d.segment_by_id(99) is None
