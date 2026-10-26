from __future__ import annotations

import logging
import threading
from collections.abc import Sequence

from PySide6.QtCore import QObject, QThread, Signal, Slot

from app.services.generation_service import GenerationService
from app.storage.repository import ProjectRepository


class GenerationWorker(QObject):
    progress = Signal(object)
    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, generation_service: GenerationService) -> None:
        super().__init__()
        self.generation_service = generation_service
        self._thread = QThread()
        self._chapter_ids: list[int] = []
        self._cancel_event = threading.Event()
        self._running = False
        self._thread.started.connect(self._run)
        self.moveToThread(self._thread)

    def start_generation(self, chapter_ids: Sequence[int]) -> None:
        if self._thread.isRunning():
            raise RuntimeError("已有生成任务正在运行")
        self._chapter_ids = list(chapter_ids)
        self._cancel_event = threading.Event()
        self._running = True
        self._thread.start()

    def cancel(self) -> None:
        self._cancel_event.set()

    def is_running(self) -> bool:
        return self._running or self._thread.isRunning()

    def wait(self, timeout_ms: int = 5_000) -> bool:
        return self._thread.wait(timeout_ms)

    @Slot()
    def _run(self) -> None:
        worker_repository: ProjectRepository | None = None
        try:
            project_root = self.generation_service.repository.root
            worker_repository = ProjectRepository()
            worker_repository.open_project(project_root)
            worker_service = GenerationService(
                worker_repository,
                self.generation_service.assembler,
            )
            results = worker_service.generate(
                self._chapter_ids,
                self._cancel_event,
                self.progress.emit,
            )
        except Exception as error:
            logging.getLogger("app.project").exception("章节生成任务失败")
            self.failed.emit(str(error))
        else:
            self.finished.emit(results)
        finally:
            if worker_repository is not None:
                worker_repository.close()
            self._running = False
            self._thread.quit()
