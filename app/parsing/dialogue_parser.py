from __future__ import annotations

from dataclasses import dataclass

from app.domain.models import SegmentKind


@dataclass(slots=True)
class ParsedSegment:
    kind: SegmentKind
    text: str
    speaker_name: str | None = None
    confidence: float = 0.0
    evidence: str | None = None


_QUOTE_PAIRS = {
    "“": "”",
    "「": "」",
    "『": "』",
    '"': '"',
}


def _append_narration(result: list[ParsedSegment], text: str) -> None:
    stripped = text.strip()
    if stripped:
        result.append(ParsedSegment(kind=SegmentKind.NARRATION, text=stripped))


def _split_paragraph(paragraph: str) -> list[ParsedSegment]:
    result: list[ParsedSegment] = []
    cursor = 0
    while cursor < len(paragraph):
        opening_index = next(
            (index for index in range(cursor, len(paragraph)) if paragraph[index] in _QUOTE_PAIRS),
            None,
        )
        if opening_index is None:
            _append_narration(result, paragraph[cursor:])
            break

        opening = paragraph[opening_index]
        closing = _QUOTE_PAIRS[opening]
        closing_index = paragraph.find(closing, opening_index + 1)
        if closing_index == -1:
            _append_narration(result, paragraph[cursor:])
            break

        _append_narration(result, paragraph[cursor:opening_index])
        dialogue = paragraph[opening_index + 1 : closing_index].strip()
        if dialogue:
            result.append(ParsedSegment(kind=SegmentKind.DIALOGUE, text=dialogue))
        cursor = closing_index + 1

    return result


def split_segments(text: str) -> list[ParsedSegment]:
    result: list[ParsedSegment] = []
    for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if line.strip():
            result.extend(_split_paragraph(line))
    return result
