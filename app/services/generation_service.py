from __future__ import annotations

import threading
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from app.audio.assembler import AssemblyCancelled, ChapterAssembler
from app.domain.models import Chapter, ChapterStatus, Role
from app.storage.repository import ProjectRepository


@dataclass(slots=True)
class GenerationProgress:
    chapter_id: int
    completed_segments: int
    total_segments: int
    message: str


@dataclass(slots=True)
class GenerationResult:
    chapter_id: int
    status: ChapterStatus
    output_path: Path | None
    error: str | None


class GenerationService:
    def __init__(
        self,
        repository: ProjectRepository,
        assembler: ChapterAssembler,
    ) -> None:
        self.repository = repository
        self.assembler = assembler

    def generate(
        self,
        chapter_ids: Sequence[int],
        cancel_event: threading.Event,
        emit: Callable[[GenerationProgress], None],
    ) -> list[GenerationResult]:
        roles = {role.id: role for role in self.repository.load_roles()}
        all_chapters = self.repository.load_chapters()
        all_segments = self.repository.load_segments()
        by_id = {chapter.id: chapter for chapter in all_chapters}
        requested_ids = list(dict.fromkeys(chapter_ids))
        missing = [chapter_id for chapter_id in requested_ids if chapter_id not in by_id]
        if missing:
            raise ValueError(f"章节不存在: {', '.join(map(str, missing))}")
        selected = sorted(
            (by_id[chapter_id] for chapter_id in requested_ids),
            key=lambda chapter: chapter.index,
        )

        results: list[GenerationResult] = []
        for position, chapter in enumerate(selected):
            if cancel_event.is_set():
                results.extend(
                    self._pending_results(selected[position:])
                )
                break

            chapter.status = ChapterStatus.RUNNING
            chapter.error = None
            self.repository.save_chapters([chapter])
            total_segments = sum(
                1 for segment in all_segments if segment.chapter_id == chapter.id
            )
            emit(
                GenerationProgress(
                    chapter_id=chapter.id,
                    completed_segments=0,
                    total_segments=total_segments,
                    message=f"正在生成 {chapter.title}",
                )
            )
            try:
                paths = self.assembler.render(
                    [chapter],
                    all_segments,
                    roles,
                    self.repository.root / "exports",
                    cancel_event=cancel_event,
                    on_segment_completed=lambda completed, total, chapter=chapter: emit(
                        GenerationProgress(
                            chapter_id=chapter.id,
                            completed_segments=completed,
                            total_segments=total,
                            message=f"已完成 {completed}/{total} 个片段",
                        )
                    ),
                )
            except AssemblyCancelled:
                chapter.status = ChapterStatus.PENDING
                chapter.error = None
                self.repository.save_chapters([chapter])
                results.extend(self._pending_results(selected[position:]))
                break
            except Exception as error:
                message = f"{chapter.title}: {error}"
                chapter.status = ChapterStatus.FAILED
                chapter.error = message
                self.repository.save_chapters([chapter])
                results.append(
                    GenerationResult(
                        chapter_id=chapter.id,
                        status=ChapterStatus.FAILED,
                        output_path=None,
                        error=message,
                    )
                )
                emit(
                    GenerationProgress(
                        chapter_id=chapter.id,
                        completed_segments=0,
                        total_segments=total_segments,
                        message=message,
                    )
                )
                continue

            chapter.status = ChapterStatus.COMPLETED
            chapter.error = None
            chapter.output_path = str(paths[0])
            self.repository.save_chapters([chapter])
            results.append(
                GenerationResult(
                    chapter_id=chapter.id,
                    status=ChapterStatus.COMPLETED,
                    output_path=paths[0],
                    error=None,
                )
            )
        return results

    def retry(
        self,
        chapter_id: int,
        cancel_event: threading.Event,
        emit: Callable[[GenerationProgress], None],
    ) -> GenerationResult:
        chapter = next(
            (
                item
                for item in self.repository.load_chapters()
                if item.id == chapter_id
            ),
            None,
        )
        if chapter is None:
            raise ValueError(f"章节不存在: {chapter_id}")
        if chapter.status is not ChapterStatus.FAILED:
            raise ValueError("只能重试失败的章节")
        results = self.generate([chapter_id], cancel_event, emit)
        return results[0]

    @staticmethod
    def _pending_results(chapters: Sequence[Chapter]) -> list[GenerationResult]:
        return [
            GenerationResult(
                chapter_id=chapter.id,
                status=ChapterStatus.PENDING,
                output_path=None,
                error=None,
            )
            for chapter in chapters
        ]
