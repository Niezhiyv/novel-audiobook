import numpy as np

from app.tts.fake_engine import FakeTTSEngine


def test_fake_engine_produces_deterministic_audio_clip() -> None:
    engine = FakeTTSEngine()

    first = engine.synthesize("你好，世界。", "voice-a", 1.0)
    second = engine.synthesize("你好，世界。", "voice-a", 1.0)

    assert first.sample_rate == 24_000
    assert first.samples.ndim == 1
    assert first.samples.size > 0
    np.testing.assert_array_equal(first.samples, second.samples)


def test_fake_engine_uses_different_waveforms_for_different_voices() -> None:
    engine = FakeTTSEngine()

    first = engine.synthesize("同一句话。", "voice-a", 1.0)
    second = engine.synthesize("同一句话。", "voice-b", 1.0)

    assert not np.array_equal(first.samples, second.samples)

