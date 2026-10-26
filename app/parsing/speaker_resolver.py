from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import replace

from app.domain.models import SegmentKind
from app.parsing.dialogue_parser import ParsedSegment


_NAME = r"(?P<name>[\u4e00-\u9fff]{1,4}?)"
_VERB = (
    r"(?P<verb>(?:沉声|低声|冷声|轻声|大声|笑着|笑|冷笑)?"
    r"(?:说道|问道|答道|喊道|说|问|答|道))"
)
_PRE_CUE = re.compile(rf"(?:^|[，。！？；：、\s]){_NAME}{_VERB}\s*[:：]\s*$")
_POST_CUE = re.compile(rf"^\s*{_NAME}{_VERB}(?:[。！？!?，,；;：:]\s*)?")
_PRONOUNS = {
    "我",
    "你",
    "他",
    "她",
    "它",
    "我们",
    "你们",
    "他们",
    "她们",
    "它们",
    "大家",
}


def _cue_name(pattern: re.Pattern[str], text: str) -> tuple[str, str] | None:
    match = pattern.search(text)
    if match is None:
        return None
    name = match.group("name")
    if name in _PRONOUNS:
        return None
    return name, f"{name}{match.group('verb')}"


def resolve_explicit_speakers(
    segments: Sequence[ParsedSegment],
    aliases: Mapping[str, str] | None = None,
) -> list[ParsedSegment]:
    alias_map = aliases or {}
    resolved = list(segments)
    for index, segment in enumerate(resolved):
        if segment.kind is not SegmentKind.DIALOGUE:
            continue

        cue = None
        if index > 0 and resolved[index - 1].kind is SegmentKind.NARRATION:
            cue = _cue_name(_PRE_CUE, resolved[index - 1].text)
        if cue is None and index + 1 < len(resolved):
            if resolved[index + 1].kind is SegmentKind.NARRATION:
                cue = _cue_name(_POST_CUE, resolved[index + 1].text)
        if cue is None:
            continue

        name, evidence = cue
        resolved[index] = replace(
            segment,
            speaker_name=alias_map.get(name, name),
            confidence=0.95,
            evidence=evidence,
        )
    return resolved
