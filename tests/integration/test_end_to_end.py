import threading
from importlib.metadata import version
from pathlib import Path

import pytest
from mutagen.mp3 import MP3

from app.audio.assembler import ChapterAssembler
from app.domain.models import ChapterStatus
from app.services.generation_service import GenerationService
from app.services.project_service import ProjectService
from app.tts.cache import AudioCache
from app.tts.config import DEFAULT_VOICES, build_default_engine
from app.tts.fake_engine import FakeTTSEngine
from app.tts.kokoro_engine import (
    KokoroConfigurationError,
    KokoroTTSEngine,
    prepare_espeak_config,
)

SAMPLE_PATH = Path(__file__).parents[2] / "examples" / "sample-novel.txt"


def test_complete_fake_tts_workflow_persists_and_invalidates_only_affected_cache(
    tmp_path: Path,
) -> None:
    source_path = tmp_path / "sample-novel.txt"
    source_path.write_text(SAMPLE_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    project_service = ProjectService()
    project = project_service.create_from_txt(tmp_path / "project", "雾城夜行", source_path)
    workspace = project_service.fetch_workspace()

    roles_by_name = {role.name: role for role in workspace.roles}
    assert {"林舟", "沈月", "林师兄"}.issubset(roles_by_name)
    assert any(segment.role_id is None for segment in workspace.segments)

    project_service.create_or_merge_role("林舟", ["林师兄"])
    road_role = project_service.create_or_merge_role("路人", [])
    unassigned = next(
        segment for segment in workspace.segments if segment.role_id is None
    )
    project_service.assign_speaker([unassigned.id], road_role.id)
    for index, role in enumerate(project_service.fetch_workspace().roles):
        project_service.assign_voice(role.id, f"fake-voice-{index}", 1.0)

    engine = FakeTTSEngine()
    cache = AudioCache(project.root / "cache" / "audio", "fake-v1")
    assembler = ChapterAssembler(engine, cache, pause_ms=50)
    generation = GenerationService(project_service.repository, assembler)
    first = project_service.fetch_workspace().chapters[0]
    results = generation.generate([first.id], threading.Event(), lambda event: None)
    assert results[0].status is ChapterStatus.COMPLETED
    assert results[0].output_path and results[0].output_path.is_file()
    assert MP3(results[0].output_path).info.length > 0

    cache_before = set((project.root / "cache" / "audio").glob("*.wav"))
    lin = next(role for role in project_service.fetch_workspace().roles if role.name == "林舟")
    lin_segment_count = sum(
        1
        for segment in project_service.fetch_workspace().segments
        if segment.role_id == lin.id and segment.chapter_id == first.id
    )
    project_service.assign_voice(lin.id, "fake-voice-lin-changed", 1.0)
    generation.generate([first.id], threading.Event(), lambda event: None)
    cache_after = set((project.root / "cache" / "audio").glob("*.wav"))

    assert len(cache_after - cache_before) == lin_segment_count
    project_service.close()

    reopened = ProjectService()
    reopened.open_project(project.root)
    persisted = reopened.fetch_workspace()
    persisted_first = persisted.chapters[0]
    assert persisted_first.status is ChapterStatus.COMPLETED
    assert persisted_first.output_path
    assert Path(persisted_first.output_path).is_file()
    persisted_lin = next(role for role in persisted.roles if role.name == "林舟")
    assert persisted_lin.voice_id == "fake-voice-lin-changed"
    reopened.close()


def test_default_engine_is_lazy_kokoro_and_requires_local_model(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    missing_model = tmp_path / "missing.onnx"
    missing_voices = tmp_path / "missing.bin"
    monkeypatch.setenv("KOKORO_MODEL_PATH", str(missing_model))
    monkeypatch.setenv("KOKORO_VOICES_PATH", str(missing_voices))

    engine = build_default_engine()

    assert isinstance(engine, KokoroTTSEngine)
    assert len(DEFAULT_VOICES) >= 6
    with pytest.raises(KokoroConfigurationError, match="模型配置不完整"):
        engine.synthesize("你好。", next(iter(DEFAULT_VOICES)), 1.0)


def test_default_voice_ids_match_official_chinese_voice_pack() -> None:
    assert set(DEFAULT_VOICES) == {
        "zf_001",
        "zf_002",
        "zf_003",
        "zm_009",
        "zm_010",
        "zm_011",
    }


def test_default_model_path_uses_cpu_int8_variant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("KOKORO_MODEL_PATH", raising=False)

    engine = build_default_engine()

    assert engine.model_path.name == "kokoro-v1.1-zh.int8.onnx"


def test_kokoro_onnx_version_supports_float_speed_contract() -> None:
    installed = tuple(int(part) for part in version("kokoro-onnx").split(".")[:3])

    assert installed >= (0, 6, 0)


def test_prepare_espeak_config_copies_data_to_ascii_cache(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    source = tmp_path / "源数据"
    source.mkdir()
    (source / "phontab").write_text("data", encoding="utf-8")
    library = tmp_path / "espeak.dll"
    library.write_bytes(b"dll")
    cache = tmp_path / "espeak-cache"
    monkeypatch.setattr("espeakng_loader.get_data_path", lambda: str(source))
    monkeypatch.setattr("espeakng_loader.get_library_path", lambda: str(library))

    config = prepare_espeak_config(cache)

    assert Path(config.data_path).as_posix().isascii()
    assert (Path(config.data_path) / "phontab").is_file()
    assert config.lib_path == str(library)
