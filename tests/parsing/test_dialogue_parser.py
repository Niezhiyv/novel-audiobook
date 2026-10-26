from app.domain.models import SegmentKind
from app.parsing.dialogue_parser import ParsedSegment, split_segments


def test_split_segments_preserves_narration_and_chinese_dialogue_order() -> None:
    text = """夜色很冷。
林舟说道：“走吧。”
“等等。”她喊道。"""

    assert split_segments(text) == [
        ParsedSegment(
            kind=SegmentKind.NARRATION,
            text="夜色很冷。",
            speaker_name=None,
            confidence=0.0,
            evidence=None,
        ),
        ParsedSegment(
            kind=SegmentKind.NARRATION,
            text="林舟说道：",
            speaker_name=None,
            confidence=0.0,
            evidence=None,
        ),
        ParsedSegment(
            kind=SegmentKind.DIALOGUE,
            text="走吧。",
            speaker_name=None,
            confidence=0.0,
            evidence=None,
        ),
        ParsedSegment(
            kind=SegmentKind.DIALOGUE,
            text="等等。",
            speaker_name=None,
            confidence=0.0,
            evidence=None,
        ),
        ParsedSegment(
            kind=SegmentKind.NARRATION,
            text="她喊道。",
            speaker_name=None,
            confidence=0.0,
            evidence=None,
        ),
    ]


def test_split_segments_supports_corner_brackets_and_straight_quotes() -> None:
    text = "『第一句。』他说。\n「第二句。」\n\"第三句。\""

    assert [segment.kind for segment in split_segments(text)] == [
        SegmentKind.DIALOGUE,
        SegmentKind.NARRATION,
        SegmentKind.DIALOGUE,
        SegmentKind.DIALOGUE,
    ]
    assert [segment.text for segment in split_segments(text)] == [
        "第一句。",
        "他说。",
        "第二句。",
        "第三句。",
    ]


def test_split_segments_keeps_unclosed_quote_as_narration() -> None:
    assert split_segments("林舟说道：“没有结束") == [
        ParsedSegment(
            kind=SegmentKind.NARRATION,
            text="林舟说道：“没有结束",
            speaker_name=None,
            confidence=0.0,
            evidence=None,
        )
    ]

