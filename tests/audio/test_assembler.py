from pathlib import Path

import pytest
from mutagen.mp3 import MP3

from app.audio.assembler import ChapterAssembler, MissingVoiceError
from app.domain.models import Chapter, ChapterStatus, Role, Segment, SegmentKind
from app.tts.cache import AudioCache
from app.tts.fake_engine import FakeTTSEngine


class CountingFakeTTSEngine(FakeTTSEngine):
    def __init__(self) -> None:
        self.calls = 0

    def synthesize(self, text: str, voice_id: str, speed: float):
        self.calls += 1
        return super().synthesize(text, voice_id, speed)


def test_render_creates_playable_mp3_and_reuses_cached_segments(
    tmp_path: Path,
) -> None:
    chapter = Chapter(id=1, index=1, title="开端", text="夜色很深。林舟说道：“走吧。”")
    narrator = Role(id=1, name="旁白", voice_id="voice-narrator", is_narrator=True)
    lin = Role(id=2, name="林舟", voice_id="voice-lin")
    segments = [
        Segment(
            id=1,
            chapter_id=1,
            position=1,
            kind=SegmentKind.NARRATION,
            text="夜色很深。",
            role_id=1,
        ),
        Segment(
            id=2,
            chapter_id=1,
            position=2,
            kind=SegmentKind.DIALOGUE,
            text="走吧。",
            role_id=2,
        ),
        Segment(
            id=3,
            chapter_id=1,
            position=3,
            kind=SegmentKind.NARRATION,
            text="他转身离开。",
            role_id=1,
        ),
    ]
    engine = CountingFakeTTSEngine()
    cache = AudioCache(tmp_path / "cache", model_version="fake-v1")
    assembler = ChapterAssembler(engine, cache, pause_ms=250)
    output_dir = tmp_path / "exports"

    paths = assembler.render([chapter], segments, {1: narrator, 2: lin}, output_dir)

    assert paths == [output_dir / "001 - 开端.mp3"]
    assert paths[0].is_file()
    assert chapter.status is ChapterStatus.COMPLETED
    assert chapter.output_path == str(paths[0])
    assert MP3(paths[0]).info.length > 0.6
    calls_after_first_render = engine.calls
    assert calls_after_first_render >= 3

    assembler.render([chapter], segments, {1: narrator, 2: lin}, output_dir)
    assert engine.calls == calls_after_first_render


def test_render_rejects_role_without_voice(tmp_path: Path) -> None:
    chapter = Chapter(id=1, index=1, title="开端", text="林舟说道：“走吧。”")
    lin = Role(id=1, name="林舟", voice_id=None)
    segment = Segment(
        id=1,
        chapter_id=1,
        position=1,
        kind=SegmentKind.DIALOGUE,
        text="走吧。",
        role_id=1,
    )
    assembler = ChapterAssembler(
        FakeTTSEngine(),
        AudioCache(tmp_path / "cache", model_version="fake-v1"),
    )

    with pytest.raises(MissingVoiceError, match="林舟"):
        assembler.render([chapter], [segment], {1: lin}, tmp_path / "exports")


def test_output_filename_sanitizes_windows_invalid_characters(tmp_path: Path) -> None:
    chapter = Chapter(id=1, index=2, title='风雪:归途?', text="正文。")
    narrator = Role(id=1, name="旁白", voice_id="voice-narrator", is_narrator=True)
    segment = Segment(
        id=1,
        chapter_id=1,
        position=1,
        kind=SegmentKind.NARRATION,
        text="正文。",
        role_id=1,
    )
    assembler = ChapterAssembler(
        FakeTTSEngine(),
        AudioCache(tmp_path / "cache", model_version="fake-v1"),
    )

    paths = assembler.render([chapter], [segment], {1: narrator}, tmp_path / "exports")

    assert paths[0].name == "002 - 风雪_归途_.mp3"
