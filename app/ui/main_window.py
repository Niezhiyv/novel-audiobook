from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from pathlib import Path

from PySide6.QtCore import QUrl, Qt
from PySide6.QtGui import QFont
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QComboBox,
    QDoubleSpinBox,
)

from app.audio.assembler import ChapterAssembler
from app.services.generation_service import GenerationProgress, GenerationService
from app.services.project_service import ProjectService, ProjectWorkspace
from app.tts.base import TTSEngine
from app.tts.cache import AudioCache
from app.tts.config import KOKORO_MODEL_VERSION, VOICE_LABELS, build_default_engine
from app.ui.models import (
    SEGMENT_HEADERS,
    role_name,
    segment_kind_label,
    segment_matches_filter,
)
from app.ui.project_dialog import ProjectDialog
from app.workers.generation_worker import GenerationWorker

class MainWindow(QMainWindow):
    def __init__(
        self,
        *,
        project_service: ProjectService | None = None,
        engine: TTSEngine | None = None,
        voice_options: Mapping[str, str] | None = None,
        model_version: str = KOKORO_MODEL_VERSION,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.project_service = project_service or ProjectService()
        self.engine = engine or build_default_engine()
        self.voice_options = dict(voice_options or VOICE_LABELS)
        self.model_version = model_version
        self._workspace: ProjectWorkspace | None = None
        self._loading = False
        self._project_logger = logging.getLogger("app.project")
        self._media_player: QMediaPlayer | None = None
        self._audio_output: QAudioOutput | None = None
        self.generation_worker: GenerationWorker | None = None

        self.setWindowTitle("离线多人有声小说")
        self.setFont(QFont("Microsoft YaHei UI", 10))
        self.resize(1380, 820)
        self._build_ui()
        self._set_project_actions_enabled(False)

    def _build_ui(self) -> None:
        toolbar = self.addToolBar("项目")
        create_action = toolbar.addAction("创建项目")
        open_action = toolbar.addAction("打开项目")
        create_action.triggered.connect(self.create_project)
        open_action.triggered.connect(self.choose_and_open_project)

        self.chapter_list = QListWidget(self)
        self.chapter_list.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self.chapter_list.currentItemChanged.connect(self._on_chapter_changed)

        self.generate_button = QPushButton("生成当前章节", self)
        self.generate_all_button = QPushButton("生成整本", self)
        self.cancel_button = QPushButton("停止", self)
        self.retry_button = QPushButton("重试失败章节", self)
        self.rename_button = QPushButton("改名", self)
        self.split_button = QPushButton("拆分", self)
        self.merge_button = QPushButton("合并所选", self)

        left_layout = QVBoxLayout()
        left_layout.addWidget(QLabel("章节", self))
        left_layout.addWidget(self.chapter_list, 1)
        left_layout.addWidget(self.generate_button)
        left_layout.addWidget(self.generate_all_button)
        left_layout.addWidget(self.cancel_button)
        left_layout.addWidget(self.retry_button)
        left_layout.addWidget(self.rename_button)
        left_layout.addWidget(self.split_button)
        left_layout.addWidget(self.merge_button)
        left_panel = QWidget(self)
        left_panel.setLayout(left_layout)

        self.filter_input = QLineEdit(self)
        self.filter_input.setPlaceholderText("筛选类型、角色或正文")
        self.filter_input.textChanged.connect(self._on_filter_changed)
        self.segments_table = QTableWidget(0, len(SEGMENT_HEADERS), self)
        self.segments_table.setHorizontalHeaderLabels(SEGMENT_HEADERS)
        self.segments_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.segments_table.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self.segments_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        segment_header = self.segments_table.horizontalHeader()
        segment_header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        segment_header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        segment_header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        segment_header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.speaker_combo = QComboBox(self)
        self.apply_speaker_button = QPushButton("应用到所选片段", self)

        segment_controls = QHBoxLayout()
        segment_controls.addWidget(QLabel("说话人", self))
        segment_controls.addWidget(self.speaker_combo, 1)
        segment_controls.addWidget(self.apply_speaker_button)

        center_layout = QVBoxLayout()
        center_layout.addWidget(QLabel("文本片段", self))
        center_layout.addWidget(self.filter_input)
        center_layout.addWidget(self.segments_table, 1)
        center_layout.addLayout(segment_controls)
        center_panel = QWidget(self)
        center_panel.setLayout(center_layout)

        self.roles_table = QTableWidget(0, 3, self)
        self.roles_table.setHorizontalHeaderLabels(["角色", "音色", "语速"])
        self.roles_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.roles_table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.roles_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        role_header = self.roles_table.horizontalHeader()
        role_header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        role_header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        role_header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.roles_table.itemSelectionChanged.connect(self._sync_role_controls)
        self.voice_combo = QComboBox(self)
        self.alias_input = QLineEdit(self)
        self.alias_input.setPlaceholderText("别名，用顿号或逗号分隔")
        self.merge_aliases_button = QPushButton("合并别名", self)
        self.speed_input = QDoubleSpinBox(self)
        self.speed_input.setRange(0.5, 2.0)
        self.speed_input.setSingleStep(0.05)
        self.speed_input.setValue(1.0)
        self.apply_voice_button = QPushButton("应用音色", self)
        self.preview_button = QPushButton("短句试听", self)
        self.progress_label = QLabel("尚未生成", self)
        self.progress_label.setWordWrap(True)
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)

        right_layout = QVBoxLayout()
        right_layout.addWidget(QLabel("角色与音色", self))
        right_layout.addWidget(self.roles_table, 1)
        right_layout.addWidget(self.alias_input)
        right_layout.addWidget(self.merge_aliases_button)
        right_layout.addWidget(self.voice_combo)
        right_layout.addWidget(self.speed_input)
        right_layout.addWidget(self.apply_voice_button)
        right_layout.addWidget(self.preview_button)
        right_layout.addWidget(QLabel("当前章节进度", self))
        right_layout.addWidget(self.progress_bar)
        right_layout.addWidget(self.progress_label)
        right_panel = QWidget(self)
        right_panel.setLayout(right_layout)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        splitter.addWidget(left_panel)
        splitter.addWidget(center_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([260, 760, 360])
        self.setCentralWidget(splitter)

        self.generate_button.clicked.connect(self.start_selected_generation)
        self.generate_all_button.clicked.connect(self.start_full_generation)
        self.cancel_button.clicked.connect(self.cancel_generation)
        self.retry_button.clicked.connect(self.retry_failed_chapter)
        self.rename_button.clicked.connect(self.prompt_rename_chapter)
        self.split_button.clicked.connect(self.prompt_split_chapter)
        self.merge_button.clicked.connect(self.prompt_merge_chapters)
        self.apply_speaker_button.clicked.connect(self.apply_speaker_to_selection)
        self.merge_aliases_button.clicked.connect(self.merge_selected_role_aliases)
        self.apply_voice_button.clicked.connect(self.apply_selected_voice)
        self.preview_button.clicked.connect(self.preview_selected_role)

    def open_project(self, root: Path) -> None:
        try:
            project = self.project_service.open_project(root)
        except Exception as error:
            QMessageBox.critical(self, "无法打开项目", str(error))
            raise
        self._configure_project_logging(project.root)
        self._project_logger.info("打开项目: %s", project.root)
        self.setWindowTitle(f"离线多人有声小说 - {project.title}")
        self._set_project_actions_enabled(True)
        self._replace_generation_worker()
        self._loading = True
        try:
            self._workspace = self.project_service.fetch_workspace()
            self._populate_chapters()
            self._populate_roles()
            self.filter_input.setText(project.last_filter)
            target_row = self._chapter_row(project.last_chapter_id)
            self.chapter_list.setCurrentRow(target_row if target_row >= 0 else 0)
        finally:
            self._loading = False
        self._populate_segments()
        self._sync_role_controls()

    def create_project(self) -> None:
        dialog = ProjectDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        values = dialog.values()
        target = values.project_root / values.title
        try:
            project = self.project_service.create_from_txt(
                target,
                values.title,
                values.source_path,
            )
        except Exception as error:
            QMessageBox.critical(self, "无法创建项目", str(error))
            return
        self.open_project(project.root)

    def choose_and_open_project(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "选择小说项目目录")
        if path:
            self.open_project(Path(path))

    def current_chapter_ids(self) -> list[int]:
        selected = [
            int(item.data(Qt.ItemDataRole.UserRole))
            for item in self.chapter_list.selectedItems()
        ]
        if selected:
            return selected
        current = self.chapter_list.currentItem()
        if current is not None:
            return [int(current.data(Qt.ItemDataRole.UserRole))]
        return []

    def rename_selected_chapter(self, title: str) -> None:
        chapter_ids = self.current_chapter_ids()
        if not chapter_ids:
            return
        chapter_id = chapter_ids[0]
        self.project_service.rename_chapter(chapter_id, title)
        self._refresh_workspace(chapter_id)

    def split_selected_chapter(self, offset: int, new_title: str) -> None:
        chapter_ids = self.current_chapter_ids()
        if not chapter_ids:
            return
        first, second = self.project_service.split_chapter(
            chapter_ids[0],
            offset,
            new_title,
        )
        self._refresh_workspace(second.id)

    def merge_selected_chapters(self, title: str) -> None:
        selected_rows = sorted(
            self.chapter_list.row(item) for item in self.chapter_list.selectedItems()
        )
        chapter_ids = [
            int(self.chapter_list.item(row).data(Qt.ItemDataRole.UserRole))
            for row in selected_rows
        ]
        if len(chapter_ids) < 2:
            return
        merged = self.project_service.merge_chapters(chapter_ids, title)
        self._refresh_workspace(merged.id)

    def apply_speaker_to_selection(self) -> None:
        rows = sorted({index.row() for index in self.segments_table.selectedIndexes()})
        segment_ids = [
            int(self.segments_table.item(row, 0).data(Qt.ItemDataRole.UserRole))
            for row in rows
        ]
        role_id = self.speaker_combo.currentData()
        self.project_service.assign_speaker(segment_ids, role_id)
        self._refresh_workspace(self.current_chapter_id())

    def apply_selected_voice(self) -> None:
        role_id = self._selected_role_id()
        if role_id is None:
            return
        self.project_service.assign_voice(
            role_id,
            self.voice_combo.currentData(),
            self.speed_input.value(),
        )
        self._refresh_workspace(self.current_chapter_id(), preserve_role_id=role_id)

    def merge_selected_role_aliases(self) -> None:
        role_id = self._selected_role_id()
        if role_id is None or self._workspace is None:
            return
        role = next((item for item in self._workspace.roles if item.id == role_id), None)
        if role is None:
            return
        aliases = [
            item.strip()
            for item in self.alias_input.text().replace("，", "、").replace(",", "、").split("、")
            if item.strip()
        ]
        merged = self.project_service.create_or_merge_role(role.name, aliases)
        self._refresh_workspace(self.current_chapter_id(), preserve_role_id=merged.id)

    def preview_selected_role(self) -> None:
        role_id = self._selected_role_id()
        if role_id is None or self._workspace is None:
            return
        role = next((item for item in self._workspace.roles if item.id == role_id), None)
        if role is None or not role.voice_id:
            self.progress_label.setText("请先为角色分配音色")
            return
        segment = next(
            (
                item
                for item in self._workspace.segments
                if item.role_id == role_id and item.text.strip()
            ),
            None,
        )
        if segment is None:
            self.progress_label.setText("该角色还没有可试听片段")
            return
        cache = AudioCache(
            self.project_service.repository.root / "cache" / "audio",
            self.model_version,
        )
        path = cache.get_or_create(
            segment.text[:120],
            role.voice_id,
            role.speed,
            self.engine,
        )
        if self._media_player is None:
            self._audio_output = QAudioOutput(self)
            self._media_player = QMediaPlayer(self)
            self._media_player.setAudioOutput(self._audio_output)
        self._media_player.setSource(QUrl.fromLocalFile(str(path)))
        self._media_player.play()

    def start_selected_generation(self) -> None:
        self._start_generation(self.current_chapter_ids())

    def start_full_generation(self) -> None:
        if self._workspace is None:
            return
        self._start_generation([chapter.id for chapter in self._workspace.chapters])

    def cancel_generation(self) -> None:
        if self.generation_worker is not None:
            self.generation_worker.cancel()

    def retry_failed_chapter(self) -> None:
        if self._workspace is None:
            return
        failed = next(
            (
                chapter
                for chapter in self._workspace.chapters
                if chapter.status.value == "failed"
            ),
            None,
        )
        if failed is None:
            self.progress_label.setText("没有失败章节需要重试")
            return
        self._start_generation([failed.id])

    def prompt_rename_chapter(self) -> None:
        if self.chapter_list.currentItem() is None:
            return
        title, accepted = QInputDialog.getText(
            self,
            "章节改名",
            "新标题",
            text=self.chapter_list.currentItem().text(),
        )
        if accepted and title.strip():
            self.rename_selected_chapter(title)

    def prompt_split_chapter(self) -> None:
        offset, accepted = QInputDialog.getInt(
            self,
            "拆分章节",
            "在片段的第几个之后拆分",
            value=1,
            minValue=1,
        )
        if not accepted:
            return
        title, accepted = QInputDialog.getText(self, "拆分章节", "新章节标题")
        if accepted and title.strip():
            self.split_selected_chapter(offset, title)

    def prompt_merge_chapters(self) -> None:
        title, accepted = QInputDialog.getText(self, "合并章节", "合并后的标题")
        if accepted and title.strip():
            self.merge_selected_chapters(title)

    def closeEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        if self._workspace is not None:
            self.project_service.save_view_state(
                self.current_chapter_id(),
                self.filter_input.text(),
            )
        if self.generation_worker is not None:
            self.generation_worker.cancel()
            self.generation_worker.wait(5_000)
        self.project_service.close()
        super().closeEvent(event)

    def _start_generation(self, chapter_ids: Sequence[int]) -> None:
        if self.generation_worker is None or self.generation_worker.is_running():
            return
        if not chapter_ids:
            return
        self.progress_bar.setRange(0, 0)
        self.progress_label.setText("正在准备生成…")
        self.generation_worker.start_generation(chapter_ids)

    def _replace_generation_worker(self) -> None:
        if self.generation_worker is not None:
            self.generation_worker.cancel()
            self.generation_worker.wait(5_000)
        project_root = self.project_service.repository.root
        assembler = ChapterAssembler(
            self.engine,
            AudioCache(project_root / "cache" / "audio", self.model_version),
        )
        generation_service = GenerationService(
            self.project_service.repository,
            assembler,
        )
        self.generation_worker = GenerationWorker(generation_service)
        self.generation_worker.progress.connect(self._on_generation_progress)
        self.generation_worker.finished.connect(self._on_generation_finished)
        self.generation_worker.failed.connect(self._on_generation_failed)

    def _on_generation_progress(self, progress: GenerationProgress) -> None:
        self.progress_bar.setRange(0, max(1, progress.total_segments))
        self.progress_bar.setValue(progress.completed_segments)
        self.progress_label.setText(progress.message)

    def _on_generation_finished(self, results: list[object]) -> None:
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100)
        completed = sum(
            1 for result in results if getattr(result, "status", None).value == "completed"
        )
        failed = sum(
            1 for result in results if getattr(result, "status", None).value == "failed"
        )
        self.progress_label.setText(f"生成完成：成功 {completed}，失败 {failed}")
        self._refresh_workspace(self.current_chapter_id())

    def _on_generation_failed(self, message: str) -> None:
        self._project_logger.error("生成失败: %s", message)
        self.progress_bar.setRange(0, 100)
        self.progress_label.setText(message)

    def _on_chapter_changed(self, current: QListWidgetItem | None) -> None:
        if self._loading or current is None:
            return
        self._populate_segments()
        if self._workspace is not None:
            self.project_service.save_view_state(
                self.current_chapter_id(),
                self.filter_input.text(),
            )

    def _on_filter_changed(self, _text: str) -> None:
        if self._loading:
            return
        self._populate_segments()
        if self.project_service.repository._project is not None:
            self.project_service.save_view_state(
                self.current_chapter_id(),
                self.filter_input.text(),
            )

    def _refresh_workspace(
        self,
        chapter_id: int | None,
        *,
        preserve_role_id: int | None = None,
    ) -> None:
        selected_role = preserve_role_id or self._selected_role_id()
        self._workspace = self.project_service.fetch_workspace()
        self._loading = True
        try:
            self._populate_chapters()
            self._populate_roles(selected_role)
            target_row = self._chapter_row(chapter_id)
            self.chapter_list.setCurrentRow(target_row if target_row >= 0 else 0)
        finally:
            self._loading = False
        self._populate_segments()
        self._sync_role_controls()

    def _populate_chapters(self) -> None:
        if self._workspace is None:
            return
        self.chapter_list.blockSignals(True)
        self.chapter_list.clear()
        for chapter in self._workspace.chapters:
            item = QListWidgetItem(chapter.title, self.chapter_list)
            item.setData(Qt.ItemDataRole.UserRole, chapter.id)
            item.setToolTip(f"状态：{chapter.status.value}")
        self.chapter_list.blockSignals(False)

    def _populate_roles(self, selected_role_id: int | None = None) -> None:
        if self._workspace is None:
            return
        self.roles_table.blockSignals(True)
        self.roles_table.setRowCount(len(self._workspace.roles))
        selected_row = -1
        for row, role in enumerate(self._workspace.roles):
            role_item = QTableWidgetItem(role.name)
            role_item.setData(Qt.ItemDataRole.UserRole, role.id)
            voice_item = QTableWidgetItem(
                self.voice_options.get(role.voice_id or "", "未分配")
            )
            speed_item = QTableWidgetItem(f"{role.speed:.2f}")
            self.roles_table.setItem(row, 0, role_item)
            self.roles_table.setItem(row, 1, voice_item)
            self.roles_table.setItem(row, 2, speed_item)
            if role.id == selected_role_id:
                selected_row = row
        self.roles_table.blockSignals(False)
        if selected_row >= 0:
            self.roles_table.setCurrentCell(selected_row, 0)
        elif self._workspace.roles:
            self.roles_table.setCurrentCell(0, 0)
        self.speaker_combo.clear()
        self.speaker_combo.addItem("未分配", None)
        for role in self._workspace.roles:
            self.speaker_combo.addItem(role.name, role.id)

    def _populate_segments(self) -> None:
        if self._workspace is None:
            return
        chapter_id = self.current_chapter_id()
        roles_by_id = {role.id: role for role in self._workspace.roles}
        segments = [
            segment
            for segment in self._workspace.segments
            if segment.chapter_id == chapter_id
            and segment_matches_filter(segment, roles_by_id, self.filter_input.text())
        ]
        self.segments_table.setRowCount(len(segments))
        for row, segment in enumerate(segments):
            kind_item = QTableWidgetItem(segment_kind_label(segment.kind))
            kind_item.setData(Qt.ItemDataRole.UserRole, segment.id)
            self.segments_table.setItem(row, 0, kind_item)
            self.segments_table.setItem(
                row,
                1,
                QTableWidgetItem(role_name(segment, roles_by_id)),
            )
            self.segments_table.setItem(row, 2, QTableWidgetItem(segment.text))
            self.segments_table.setItem(
                row,
                3,
                QTableWidgetItem(f"{segment.confidence:.0%}"),
            )

    def _sync_role_controls(self) -> None:
        role_id = self._selected_role_id()
        if self._workspace is None or role_id is None:
            return
        role = next((item for item in self._workspace.roles if item.id == role_id), None)
        if role is None:
            return
        self.voice_combo.clear()
        self.voice_combo.addItem("未分配", None)
        for voice_id, label in self.voice_options.items():
            self.voice_combo.addItem(label, voice_id)
        target = self.voice_combo.findData(role.voice_id)
        self.voice_combo.setCurrentIndex(max(0, target))
        self.speed_input.setValue(role.speed)
        self.alias_input.setText("、".join(role.aliases))

    def _selected_role_id(self) -> int | None:
        row = self.roles_table.currentRow()
        item = self.roles_table.item(row, 0) if row >= 0 else None
        value = item.data(Qt.ItemDataRole.UserRole) if item else None
        return int(value) if value is not None else None

    def current_chapter_id(self) -> int | None:
        item = self.chapter_list.currentItem()
        if item is None:
            return None
        value = item.data(Qt.ItemDataRole.UserRole)
        return int(value) if value is not None else None

    def _chapter_row(self, chapter_id: int | None) -> int:
        if chapter_id is None:
            return -1
        for row in range(self.chapter_list.count()):
            item = self.chapter_list.item(row)
            if int(item.data(Qt.ItemDataRole.UserRole)) == chapter_id:
                return row
        return -1

    def _set_project_actions_enabled(self, enabled: bool) -> None:
        for widget in (
            self.chapter_list,
            self.generate_button,
            self.generate_all_button,
            self.cancel_button,
            self.retry_button,
            self.rename_button,
            self.split_button,
            self.merge_button,
            self.segments_table,
            self.speaker_combo,
            self.apply_speaker_button,
            self.roles_table,
            self.alias_input,
            self.merge_aliases_button,
            self.voice_combo,
            self.speed_input,
            self.apply_voice_button,
            self.preview_button,
            self.filter_input,
        ):
            widget.setEnabled(enabled)

    def _configure_project_logging(self, root: Path) -> None:
        self._project_logger.setLevel(logging.INFO)
        for handler in list(self._project_logger.handlers):
            if getattr(handler, "_audiobook_project_handler", False):
                self._project_logger.removeHandler(handler)
                handler.close()
        log_path = root / "logs" / "app.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        handler = logging.FileHandler(log_path, encoding="utf-8")
        handler._audiobook_project_handler = True  # type: ignore[attr-defined]
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
        )
        self._project_logger.addHandler(handler)
