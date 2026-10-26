from app.domain.models import SegmentKind
from app.parsing.dialogue_parser import ParsedSegment
from app.parsing.speaker_resolver import resolve_explicit_speakers


def dialogue(text: str) -> ParsedSegment:
    return ParsedSegment(SegmentKind.DIALOGUE, text, None, 0.0, None)


def narration(text: str) -> ParsedSegment:
    return ParsedSegment(SegmentKind.NARRATION, text, None, 0.0, None)


def test_resolve_explicit_speaker_before_dialogue() -> None:
    segments = [narration("林舟说道："), dialogue("走吧。")]

    result = resolve_explicit_speakers(segments)

    assert result[1].speaker_name == "林舟"
    assert result[1].confidence >= 0.9
    assert result[1].evidence == "林舟说道"


def test_resolve_explicit_speaker_after_dialogue() -> None:
    segments = [dialogue("等等。"), narration("沈月问道。")]

    result = resolve_explicit_speakers(segments)

    assert result[0].speaker_name == "沈月"
    assert result[0].evidence == "沈月问道"


def test_resolve_leaves_pronoun_speaker_unassigned() -> None:
    segments = [narration("她笑道："), dialogue("别走。")]

    result = resolve_explicit_speakers(segments)

    assert result[1].speaker_name is None
    assert result[1].confidence == 0.0


def test_resolve_only_applies_aliases_after_explicit_mapping() -> None:
    segments = [narration("林师兄沉声道："), dialogue("站住。")]

    unassigned = resolve_explicit_speakers(segments)
    mapped = resolve_explicit_speakers(segments, aliases={"林师兄": "林舟"})

    assert unassigned[1].speaker_name == "林师兄"
    assert mapped[1].speaker_name == "林舟"
    assert mapped[1].confidence >= 0.9


def test_resolve_does_not_assign_narration_segments() -> None:
    segments = [narration("林舟说道："), dialogue("走吧。"), narration("他转身离开。")]

    result = resolve_explicit_speakers(segments)

    assert result[0].speaker_name is None
    assert result[2].speaker_name is None
