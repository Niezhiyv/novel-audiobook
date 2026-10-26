from __future__ import annotations

import re
from dataclasses import dataclass

from app.importers.text_importer import normalize_text


@dataclass(slots=True)
class ParsedChapter:
    index: int
    title: str
    text: str


_CHINESE_ORDINAL = "0-9零〇一二三四五六七八九十百千万两"
_CHINESE_HEADING = re.compile(
    rf"^\s*第[{_CHINESE_ORDINAL}]+章(?:\s+|[:：、.．-]+)?[^\n]{{0,48}}$"
)
_ENGLISH_HEADING = re.compile(
    r"^\s*Chapter\s+\d+(?:\s*[:：.、-]\s*|\s+).{0,48}$",
    re.IGNORECASE,
)
_SPECIAL_HEADING = re.compile(r"^\s*(?:序章|楔子|引子|前言|后记|尾声)\s*$")


def _is_heading(line: str) -> bool:
    candidate = line.strip()
    if not candidate or len(candidate) > 64:
        return False
    return bool(
        _CHINESE_HEADING.match(candidate)
        or _ENGLISH_HEADING.match(candidate)
        or _SPECIAL_HEADING.match(candidate)
    )


def split_chapters(text: str) -> list[ParsedChapter]:
    normalized = normalize_text(text)
    if not normalized:
        return []

    lines = normalized.split("\n")
    heading_indexes = [index for index, line in enumerate(lines) if _is_heading(line)]
    if not heading_indexes:
        return [ParsedChapter(index=1, title="正文", text=normalized)]

    chapters: list[ParsedChapter] = []
    first_heading = heading_indexes[0]
    preface = "\n".join(lines[:first_heading]).strip()
    if preface:
        chapters.append(ParsedChapter(index=1, title="序言", text=preface))

    for position, line_index in enumerate(heading_indexes):
        next_heading = (
            heading_indexes[position + 1]
            if position + 1 < len(heading_indexes)
            else len(lines)
        )
        body = "\n".join(lines[line_index + 1 : next_heading]).strip()
        chapters.append(
            ParsedChapter(
                index=len(chapters) + 1,
                title=lines[line_index].strip(),
                text=body,
            )
        )
    return chapters

