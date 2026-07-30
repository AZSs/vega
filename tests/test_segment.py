"""切段纯逻辑测试 —— 通用(领域中立),不沾「章」等小说词。"""

from vega.core import segment_text


def test_segment_by_double_newline():
    doc = segment_text("d1", "第一段。\n\n第二段。\n\n第三段。")
    assert [s.id for s in doc.segments] == [0, 1, 2]
    assert doc.segments[0].text == "第一段。"
    assert doc.segments[1].char_start > 0


def test_segment_char_range_monotonic():
    text = "甲。\n\n乙。\n\n丙。"
    doc = segment_text("d1", text)
    starts = [s.char_start for s in doc.segments]
    ends = [s.char_end for s in doc.segments]
    assert starts == sorted(starts)
    assert all(s < e for s, e in zip(starts, ends, strict=True))
    assert doc.segments[0].char_start == 0


def test_segment_min_len_filters():
    doc = segment_text("d1", "长段内容足够。\n\n短\n\n另一长段内容。", min_len=5)
    # 「短」被过滤
    assert [s.text for s in doc.segments] == ["长段内容足够。", "另一长段内容。"]


def test_segment_tail():
    doc = segment_text("d1", "甲。\n\n乙。")
    assert doc.segments[-1].text == "乙。"
