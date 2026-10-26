import sqlite3
from pathlib import Path

import pytest

from app.domain.models import Chapter, Role, Segment, SegmentKind
from app.storage.repository import ProjectAlreadyExistsError, ProjectRepository


def test_create_project_writes_required_files_and_schema(tmp_path: Path) -> None:
    root = tmp_path / "长夜项目"
    repository = ProjectRepository()

    project = repository.create_project(root, "长夜", "第一章 开端\n夜色很深。")

    assert project.title == "长夜"
    assert project.root == root.resolve()
    assert (root / "source.txt").read_text(encoding="utf-8") == "第一章 开端\n夜色很深。"
    assert (root / "project.sqlite3").is_file()
    assert (root / "cache" / "audio").is_dir()
    assert (root / "exports").is_dir()
    assert (root / "logs").is_dir()

    with sqlite3.connect(root / "project.sqlite3") as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 1

    repository.close()


def test_project_round_trips_chapters_segments_and_roles(tmp_path: Path) -> None:
    root = tmp_path / "book"
    repository = ProjectRepository()
    repository.create_project(root, "测试小说", "第一章 开端\n林舟说道：“走吧。”")

    narrator = Role(name="旁白", is_narrator=True)
    lin = Role(name="林舟", aliases=["林师兄"])
    repository.save_role(narrator)
    repository.save_role(lin)

    chapter = Chapter(index=1, title="开端", text="林舟说道：“走吧。”")
    repository.save_chapters([chapter])
    segment = Segment(
        chapter_id=chapter.id,
        position=1,
        kind=SegmentKind.DIALOGUE,
        text="走吧。",
        role_id=lin.id,
        confidence=0.9,
        evidence="林舟说道",
    )
    repository.save_segment(segment)
    repository.close()

    reopened_repository = ProjectRepository()
    reopened = reopened_repository.open_project(root)

    assert reopened.id == 1
    assert reopened_repository.load_chapters() == [chapter]
    assert reopened_repository.load_segments() == [segment]
    assert reopened_repository.load_roles() == [narrator, lin]
    reopened_repository.close()


def test_reopening_project_preserves_existing_rows(tmp_path: Path) -> None:
    root = tmp_path / "book"
    first = ProjectRepository()
    first.create_project(root, "测试小说", "内容")
    first.save_role(Role(name="旁白", is_narrator=True))
    first.close()

    second = ProjectRepository()
    second.open_project(root)
    second.save_role(Role(name="林舟"))
    second.close()

    third = ProjectRepository()
    third.open_project(root)

    assert [role.name for role in third.load_roles()] == ["旁白", "林舟"]
    third.close()


def test_create_project_does_not_overwrite_non_project_directory(tmp_path: Path) -> None:
    root = tmp_path / "existing"
    root.mkdir()
    sentinel = root / "keep.txt"
    sentinel.write_text("不要删除", encoding="utf-8")

    with pytest.raises(ProjectAlreadyExistsError):
        ProjectRepository().create_project(root, "测试", "内容")

    assert sentinel.read_text(encoding="utf-8") == "不要删除"
