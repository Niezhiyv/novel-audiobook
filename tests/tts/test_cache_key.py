from pathlib import Path

from app.tts.cache import AudioCache, chunk_text
from app.tts.fake_engine import FakeTTSEngine


class CountingFakeTTSEngine(FakeTTSEngine):
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, float]] = []

    def synthesize(self, text: str, voice_id: str, speed: float):
        self.calls.append((text, voice_id, speed))
        return super().synthesize(text, voice_id, speed)


def test_audio_cache_writes_wav_and_reuses_existing_clip(tmp_path: Path) -> None:
    engine = CountingFakeTTSEngine()
    cache = AudioCache(tmp_path / "cache", model_version="fake-v1")

    first = cache.get_or_create("  第一句话。 ", "voice-a", 1.0, engine)
    second = cache.get_or_create("第一句话。", "voice-a", 1.0, engine)

    assert first == second
    assert first.is_file()
    assert len(engine.calls) == 1


def test_cache_key_changes_when_any_synthesis_input_changes(tmp_path: Path) -> None:
    cache = AudioCache(tmp_path / "cache", model_version="fake-v1")

    baseline = cache.key("文本", "voice-a", 1.0)

    assert cache.key("另一段文本", "voice-a", 1.0) != baseline
    assert cache.key("文本", "voice-b", 1.0) != baseline
    assert cache.key("文本", "voice-a", 1.1) != baseline
    assert AudioCache(tmp_path / "cache", "fake-v2").key("文本", "voice-a", 1.0) != baseline


def test_chunk_text_prefers_chinese_punctuation_without_losing_text() -> None:
    text = "第一段内容很长但还没有结束。" * 5 + "最后一段。"

    chunks = chunk_text(text, max_chars=32)

    assert chunks
    assert all(len(chunk) <= 32 for chunk in chunks)
    assert "".join(chunks) == text
    assert all(chunk.endswith(("。", "！", "？", "；", "，")) for chunk in chunks[:-1])


def test_chunk_text_hard_splits_when_no_punctuation_exists() -> None:
    text = "无标点文本" * 20

    chunks = chunk_text(text, max_chars=15)

    assert all(len(chunk) <= 15 for chunk in chunks)
    assert "".join(chunks) == text
