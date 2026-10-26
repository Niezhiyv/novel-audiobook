from app.parsing.chapter_parser import ParsedChapter, split_chapters


def test_split_chapters_recognizes_chinese_headings() -> None:
    text = """第一章 开端
夜色很深。

第二章 风雪
林舟继续赶路。

第十章 归途
天亮了。
"""

    assert split_chapters(text) == [
        ParsedChapter(index=1, title="第一章 开端", text="夜色很深。"),
        ParsedChapter(index=2, title="第二章 风雪", text="林舟继续赶路。"),
        ParsedChapter(index=3, title="第十章 归途", text="天亮了。"),
    ]


def test_split_chapters_recognizes_english_headings() -> None:
    text = "Chapter 1: Arrival\nA cold night.\n\nChapter 2 - Return\nMorning came."

    assert split_chapters(text) == [
        ParsedChapter(index=1, title="Chapter 1: Arrival", text="A cold night."),
        ParsedChapter(index=2, title="Chapter 2 - Return", text="Morning came."),
    ]


def test_split_chapters_wraps_text_without_headings() -> None:
    assert split_chapters("只有一段正文。\n第二段。") == [
        ParsedChapter(index=1, title="正文", text="只有一段正文。\n第二段。")
    ]


def test_split_chapters_returns_empty_list_for_empty_text() -> None:
    assert split_chapters(" \n\t ") == []

