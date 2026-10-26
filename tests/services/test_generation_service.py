import threading
from pathlib import Path

import pytest

from app.audio.assembler import ChapterAssembler
from app.domain.models import ChapterStatus
from app.services.generation_service import GenerationProgress, GenerationService
from app.services.project_service import ProjectService
from app.tts.cache import AudioCache
from app.tts.fake_engine import FakeTTSEngine

SOURCE = """第一章 开端
夜色很深。
林舟说道：“走吧。”
“等等。”沈月问道。

第二章 风雪
林舟说道：“出发。”

第三章 归途
林舟说道：“到了。”
"""


class CancellingFakeTTSEngine(FakeTTSEngine):
    def __init__(self, cancel_event: threading.Event | None = None) -> None:
        super().__init__()
        self.cancel_event = cancel_event
        self.calls = 0

    def synthesize(self, text: str, voice_id: str, speed: float):
        self.calls += 1
        clip = super().synthesize(text, voice_id, speed)
        if self.cancel_event is not None:
            self.cancel_event.set()
        return clip


def prepare_project(
    tmp_path: Path,
    *,
    cancel_event: threading.Event | None = None,
) -> tuple[ProjectService, GenerationService, CancellingFakeTTSEngine]:
    source_path = tmp_path / "source.txt"
    source_path.write_text(SOURCE, encoding="utf-8")
    project_service = ProjectService()
    project = project_service.create_from_txt(tmp_path / "project", "长夜", source_path)
    workspace = project_service.fetch_workspace()
    for index, role in enumerate(workspace.roles):
        project_service.assign_voice(role.id, f"voice-{index}", 1.0)

    engine = CancellingFakeTTSEngine(cancel_event)
    assembler = ChapterAssembler(
        engine,
        AudioCache(project.root / "cache" / "audio", "fake-v1"),
        pause_ms=50,
    )
    generation = GenerationService(project_service.repository, assembler)
    return project_service, generation, engine


def test_generate_multiple_chapters_emits_progress_and_saves_outputs(
    tmp_path: Path,
) -> None:
    project_service, generation, _ = prepare_project(tmp_path)
    chapters = project_service.fetch_workspace().chapters[:2]
    progress: list[GenerationProgress] = []

    results = generation.generate(
        [chapter.id for chapter in chapters],
        threading.Event(),
        progress.append,
    )

    assert [result.status for result in results] == [
        ChapterStatus.COMPLETED,
        ChapterStatus.COMPLETED,
    ]
    assert all(result.output_path and result.output_path.is_file() for result in results)
    assert progress[0].chapter_id == chapters[0].id
    assert progress[-1].completed_segments == progress[-1].total_segments
    saved = project_service.fetch_workspace().chapters[:2]
    assert all(chapter.status is ChapterStatus.COMPLETED for chapter in saved)
    project_service.close()


def test_failed_chapter_is_marked_and_generation_continues(tmp_path: Path) -> None:
    project_service, generation, _ = prepare_project(tmp_path)
    workspace = project_service.fetch_workspace()
    shen = next(role for role in workspace.roles if role.name == "沈月")
    project_service.assign_voice(shen.id, None, 1.0)

    results = generation.generate(
        [chapter.id for chapter in workspace.chapters[:2]],
        threading.Event(),
        lambda event: None,
    )

    assert results[0].status is ChapterStatus.FAILED
    assert "沈月" in (results[0].error or "")
    assert results[1].status is ChapterStatus.COMPLETED
    failed_chapter = project_service.fetch_workspace().chapters[0]
    assert failed_chapter.status is ChapterStatus.FAILED
    assert "沈月" in (failed_chapter.error or "")
    project_service.close()


def test_retry_only_accepts_failed_chapter_and_keeps_other_cache(
    tmp_path: Path,
) -> None:
    project_service, generation, engine = prepare_project(tmp_path)
    workspace = project_service.fetch_workspace()
    shen = next(role for role in workspace.roles if role.name == "沈月")
    project_service.assign_voice(shen.id, None, 1.0)
    first, second = workspace.chapters[:2]
    generation.generate([first.id, second.id], threading.Event(), lambda event: None)
    calls_before_retry = engine.calls

    project_service.assign_voice(shen.id, "voice-shen", 1.0)
    retried = generation.retry(first.id, threading.Event(), lambda event: None)

    assert retried.status is ChapterStatus.COMPLETED
    assert retried.output_path and retried.output_path.is_file()
    assert engine.calls > calls_before_retry
    with pytest.raises(ValueError, match="失败"):
        generation.retry(second.id, threading.Event(), lambda event: None)
    project_service.close()


def test_cancel_stops_between_segments_and_preserves_cached_audio(
    tmp_path: Path,
) -> None:
    cancel_event = threading.Event()
    project_service, generation, engine = prepare_project(
        tmp_path,
        cancel_event=cancel_event,
    )
    workspace = project_service.fetch_workspace()
    first, second = workspace.chapters[:2]

    results = generation.generate(
        [first.id, second.id],
        cancel_event,
        lambda event: None,
    )

    assert [result.status for result in results] == [
        ChapterStatus.PENDING,
        ChapterStatus.PENDING,
    ]
    assert engine.calls == 1
    cache_files = list((project_service.repository.root / "cache" / "audio").glob("*.wav"))
    assert len(cache_files) == 1

    engine.cancel_event = None
    resumed = generation.generate(
        [first.id, second.id],
        threading.Event(),
        lambda event: None,
    )
    assert [result.status for result in resumed] == [
        ChapterStatus.COMPLETED,
        ChapterStatus.COMPLETED,
    ]
    assert engine.calls > 1
    project_service.close()


def test_generate_rejects_unknown_chapter_id(tmp_path: Path) -> None:
    project_service, generation, _ = prepare_project(tmp_path)

    with pytest.raises(ValueError, match="章节不存在"):
        generation.generate([99999], threading.Event(), lambda event: None)

    project_service.close()
