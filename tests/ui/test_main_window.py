from pathlib import Path

from PySide6.QtCore import QItemSelectionModel, Qt
from PySide6.QtWidgets import QAbstractItemView

from app.domain.models import ChapterStatus
from app.services.project_service import ProjectService
from app.tts.fake_engine import FakeTTSEngine
from app.ui.main_window import MainWindow

SOURCE = """第一章 开端
夜色很深。
林舟说道：“走吧。”
“等等。”沈月问道。
“我也去。”

第二章 风雪
林舟说道：“出发。”
"""

VOICES = {
    "voice-narrator": "沉稳旁白",
    "voice-lin": "低沉男声",
    "voice-shen": "清亮女声",
    "voice-extra": "青年男声",
}


def prepare_project(tmp_path: Path) -> tuple[Path, dict[str, int]]:
    source_path = tmp_path / "source.txt"
    source_path.write_text(SOURCE, encoding="utf-8")
    service = ProjectService()
    service.create_from_txt(tmp_path / "project", "长夜", source_path)
    workspace = service.fetch_workspace()
    role_ids = {role.name: role.id for role in workspace.roles}
    service.assign_voice(role_ids["旁白"], "voice-narrator", 1.0)
    service.assign_voice(role_ids["林舟"], "voice-lin", 1.0)
    service.assign_voice(role_ids["沈月"], "voice-shen", 1.0)
    unassigned = next(segment for segment in workspace.segments if segment.role_id is None)
    service.assign_speaker([unassigned.id], role_ids["林舟"])
    root = service.repository.root
    service.close()
    return root, role_ids


def make_window(qtbot, project_service: ProjectService | None = None) -> MainWindow:
    window = MainWindow(
        project_service=project_service or ProjectService(),
        engine=FakeTTSEngine(),
        voice_options=VOICES,
        model_version="fake-v1",
    )
    qtbot.addWidget(window)
    return window


def find_combo_index(combo, value: str) -> int:
    for index in range(combo.count()):
        if combo.itemData(index) == value:
            return index
    raise AssertionError(f"combo item not found: {value}")


def chapter_title_at(window: MainWindow, row: int) -> str:
    return window.chapter_list.item(row).text().split("  [", 1)[0]


def test_open_project_populates_three_pane_workspace(qtbot, tmp_path: Path) -> None:
    root, _ = prepare_project(tmp_path)
    window = make_window(qtbot)

    window.open_project(root)

    assert window.windowTitle().endswith("长夜")
    assert window.chapter_list.count() == 2
    assert [chapter_title_at(window, i) for i in range(2)] == [
        "第一章 开端",
        "第二章 风雪",
    ]
    assert "待生成" in window.chapter_list.item(0).text()
    assert window.segments_table.rowCount() == 6
    assert window.segments_table.columnCount() == 4
    assert window.roles_table.rowCount() == 3
    assert window.generate_button.isEnabled()


def test_batch_assign_speaker_and_change_role_voice(qtbot, tmp_path: Path) -> None:
    root, role_ids = prepare_project(tmp_path)
    window = make_window(qtbot)
    window.open_project(root)

    target_rows = [
        row
        for row in range(window.segments_table.rowCount())
        if window.segments_table.item(row, 2).text() in {"走吧。", "我也去。"}
    ]
    selection = window.segments_table.selectionModel()
    selection.clearSelection()
    for row in target_rows:
        selection.select(
            window.segments_table.model().index(row, 0),
            QItemSelectionModel.SelectionFlag.Select
            | QItemSelectionModel.SelectionFlag.Rows,
        )
    window.speaker_combo.setCurrentIndex(
        find_combo_index(window.speaker_combo, role_ids["沈月"])
    )
    window.apply_speaker_button.click()

    workspace = window.project_service.fetch_workspace()
    texts = {segment.text: segment for segment in workspace.segments}
    assert all(texts[text].role_id == role_ids["沈月"] for text in {"走吧。", "我也去。"})

    lin_row = next(
        row
        for row in range(window.roles_table.rowCount())
        if window.roles_table.item(row, 0).text() == "林舟"
    )
    window.roles_table.setCurrentCell(lin_row, 0)
    window.voice_combo.setCurrentIndex(find_combo_index(window.voice_combo, "voice-extra"))
    window.apply_voice_button.click()

    updated = window.project_service.fetch_workspace()
    lin = next(role for role in updated.roles if role.name == "林舟")
    assert lin.voice_id == "voice-extra"


def test_chapter_rename_split_and_merge_refresh_lists(qtbot, tmp_path: Path) -> None:
    root, _ = prepare_project(tmp_path)
    window = make_window(qtbot)
    window.open_project(root)
    window.chapter_list.setCurrentRow(1)

    window.rename_selected_chapter("风雪夜")
    assert chapter_title_at(window, 1) == "风雪夜"

    window.split_selected_chapter(offset=1, new_title="追兵")
    assert window.chapter_list.count() == 3
    assert [chapter_title_at(window, i) for i in range(3)] == [
        "第一章 开端",
        "风雪夜",
        "追兵",
    ]

    window.chapter_list.setSelectionMode(
        QAbstractItemView.SelectionMode.ExtendedSelection
    )
    window.chapter_list.clearSelection()
    window.chapter_list.item(1).setSelected(True)
    window.chapter_list.item(2).setSelected(True)
    window.merge_selected_chapters("风雪重逢")

    assert window.chapter_list.count() == 2
    assert chapter_title_at(window, 1) == "风雪重逢"


def test_role_alias_editor_merges_aliases(qtbot, tmp_path: Path) -> None:
    root, role_ids = prepare_project(tmp_path)
    window = make_window(qtbot)
    window.open_project(root)
    lin_row = next(
        row
        for row in range(window.roles_table.rowCount())
        if window.roles_table.item(row, 0).text() == "林舟"
    )
    window.roles_table.setCurrentCell(lin_row, 0)

    window.alias_input.setText("林师兄、阿舟")
    window.merge_aliases_button.click()

    workspace = window.project_service.fetch_workspace()
    lin = next(role for role in workspace.roles if role.id == role_ids["林舟"])
    assert lin.aliases == ["林师兄", "阿舟"]


def test_role_name_editor_renames_selected_role(qtbot, tmp_path: Path) -> None:
    root, role_ids = prepare_project(tmp_path)
    window = make_window(qtbot)
    window.open_project(root)
    lin_row = next(
        row
        for row in range(window.roles_table.rowCount())
        if window.roles_table.item(row, 0).text() == "林舟"
    )
    window.roles_table.setCurrentCell(lin_row, 0)

    window.role_name_input.setText("林舟舟")
    window.rename_role_button.click()

    workspace = window.project_service.fetch_workspace()
    renamed = next(role for role in workspace.roles if role.id == role_ids["林舟"])
    assert renamed.name == "林舟舟"
    assert any(
        window.roles_table.item(row, 0).text() == "林舟舟"
        for row in range(window.roles_table.rowCount())
    )


def test_generate_chapter_uses_background_worker(qtbot, tmp_path: Path) -> None:
    root, _ = prepare_project(tmp_path)
    window = make_window(qtbot)
    window.open_project(root)
    window.chapter_list.setCurrentRow(0)

    with qtbot.waitSignal(window.generation_worker.finished, timeout=10_000) as blocker:
        window.generate_button.click()

    results = blocker.args[0]
    assert results[0].status is ChapterStatus.COMPLETED
    assert results[0].output_path and results[0].output_path.is_file()
    assert window.progress_bar.value() == window.progress_bar.maximum()


def test_reopened_project_restores_chapter_and_filter(qtbot, tmp_path: Path) -> None:
    root, _ = prepare_project(tmp_path)
    first = make_window(qtbot)
    first.open_project(root)
    first.chapter_list.setCurrentRow(1)
    first.filter_input.setText("对白")
    first.close()

    second = make_window(qtbot)
    second.open_project(root)

    current = second.chapter_list.currentItem()
    assert current is not None
    assert current.text().startswith("第二章 风雪")
    assert second.filter_input.text() == "对白"
