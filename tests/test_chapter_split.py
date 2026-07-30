"""小说分章测试 —— novel 插件领域专用(「章」在此合法)。"""

from vega.plugins.novel import NovelPlugin
from vega.schemas import Segment


def _text() -> str:
    return (
        "第一章 灵豆化形\n黄豆豆睁眼。\n\n她饿了。\n\n"
        "第二章 初入宗门\n豆豆上山。\n\n遇见老儒。\n\n"
        "第三章 首战\n她拔剑。\n"
    )


def test_split_into_chapters():
    doc = NovelPlugin().split_chapters("d1", _text())
    assert [s.id for s in doc.segments] == [0, 1, 2]
    # 每章含章题 + 正文
    assert doc.segments[0].text.startswith("第一章")
    assert "黄豆豆睁眼" in doc.segments[0].text
    assert doc.segments[1].text.startswith("第二章")
    assert doc.segments[2].text.startswith("第三章")


def test_chapter_char_range_covers_full_text():
    text = _text()
    doc = NovelPlugin().split_chapters("d1", text)
    # 首段从 0 开始
    assert doc.segments[0].char_start == 0
    # 末段覆盖到文末
    assert doc.segments[-1].char_end == len(text)
    # 段不重叠、连续
    for i in range(len(doc.segments) - 1):
        assert doc.segments[i].char_end <= doc.segments[i + 1].char_start


def test_chapter_with_arabic_number():
    doc = NovelPlugin().split_chapters("d1", "第1章 甲\n内容甲\n\n第2章 乙\n内容乙\n")
    assert len(doc.segments) == 2
    assert doc.segments[0].text.startswith("第1章")
    assert doc.segments[1].text.startswith("第2章")


def test_chapter_zero_padded():
    doc = NovelPlugin().split_chapters("d1", "第001章 甲\n甲\n\n第042章 乙\n乙\n")
    assert len(doc.segments) == 2


def test_no_chapter_heading_falls_back_single_segment():
    """无章题识别 → 整篇作一个段(不丢)。"""
    doc = NovelPlugin().split_chapters("d1", "一段没有章题的文本。\n\n另一段。")
    assert len(doc.segments) == 1
    assert isinstance(doc.segments[0], Segment)


def test_chapter_heading_chinese_numerals():
    doc = NovelPlugin().split_chapters(
        "d1", "第一章 甲\n甲\n\n第十二章 乙\n乙\n\n第一百零三章 丙\n丙\n"
    )
    assert len(doc.segments) == 3
