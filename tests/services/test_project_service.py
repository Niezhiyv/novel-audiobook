from pathlib import Path

import pytest

from app.domain.models import SegmentKind
from app.services.project_service import ProjectService

SOURCE = """第一章 开端
夜色很深。
林舟说道：“走吧。”
“等等。”沈月问道。
“我也去。”

第二章 风雪
林师兄沉声道：“站住。”
"""


def create_service(tmp_path: Path) -> tuple[ProjectService, Path]:
    source_path = tmp_path / "source.txt"
    source_path.write_text(SOURCE, encoding="utf-8")
    service = ProjectService()
    service.create_from_txt(tmp_path / "project", "长夜", source_path)
    return service, tmp_path / "project"


def test_create_from_txt_builds_chapters_segments_and_roles(tmp_path: Path) -> None:
    service, _ = create_service(tmp_path)
    workspace = service.fetch_workspace()

    assert [chapter.title for chapter in workspace.chapters] == ["第一章 开端", "第二章 风雪"]
    assert len(workspace.segments) == 8

    narrator = next(role for role in workspace.roles if role.is_narrator)
    roles_by_name = {role.name: role for role in workspace.roles}
    segments_by_text = {segment.text: segment for segment in workspace.segments}

    assert all(
        segment.role_id == narrator.id
        for segment in workspace.segments
        if segment.kind is SegmentKind.NARRATION
    )
    assert segments_by_text["走吧。"].role_id == roles_by_name["林舟"].id
    assert segments_by_text["等等。"].role_id == roles_by_name["沈月"].id
    assert segments_by_text["站住。"].role_id == roles_by_name["林师兄"].id
    assert segments_by_text["我也去。"].role_id is None
    assert all(role.voice_id is None for role in workspace.roles)

    service.close()


def test_assign_speaker_updates_multiple_segments_and_can_clear(tmp_path: Path) -> None:
    service, _ = create_service(tmp_path)
    workspace = service.fetch_workspace()
    lin = next(role for role in workspace.roles if role.name == "林舟")
    targets = [
        segment.id
        for segment in workspace.segments
        if segment.text in {"我也去。", "等等。"}
    ]

    service.assign_speaker(targets, lin.id)
    updated = {segment.id: segment for segment in service.fetch_workspace().segments}
    assert all(updated[segment_id].role_id == lin.id for segment_id in targets)

    service.assign_speaker([targets[0]], None)
    cleared = {segment.id: segment for segment in service.fetch_workspace().segments}
    assert cleared[targets[0]].role_id is None
    assert cleared[targets[1]].role_id == lin.id
    service.close()


def test_create_or_merge_role_combines_aliases_and_reassigns_segments(
    tmp_path: Path,
) -> None:
    service, _ = create_service(tmp_path)
    original = service.fetch_workspace()
    lin = next(role for role in original.roles if role.name == "林舟")
    alias_role = next(role for role in original.roles if role.name == "林师兄")

    merged = service.create_or_merge_role("林舟", ["林师兄", "阿舟"])
    workspace = service.fetch_workspace()

    assert merged.id == lin.id
    assert merged.aliases == ["林师兄", "阿舟"]
    assert {role.name for role in workspace.roles} == {"旁白", "林舟", "沈月"}
    assert alias_role.id not in {role.id for role in workspace.roles}
    assert next(segment for segment in workspace.segments if segment.text == "站住。").role_id == lin.id
    service.close()


def test_assign_voice_does_not_touch_unassigned_roles(tmp_path: Path) -> None:
    service, _ = create_service(tmp_path)
    workspace = service.fetch_workspace()
    lin = next(role for role in workspace.roles if role.name == "林舟")

    service.assign_voice(lin.id, "voice.lin", 1.1)
    updated = service.fetch_workspace()

    updated_lin = next(role for role in updated.roles if role.id == lin.id)
    assert updated_lin.voice_id == "voice.lin"
    assert updated_lin.speed == 1.1
    assert next(role for role in updated.roles if role.name == "沈月").voice_id is None
    assert all(
        segment.role_id is not None or segment.kind is SegmentKind.DIALOGUE
        for segment in updated.segments
    )
    service.close()


def test_chapter_rename_split_and_merge_preserve_segments(tmp_path: Path) -> None:
    service, _ = create_service(tmp_path)
    workspace = service.fetch_workspace()
    second = workspace.chapters[1]

    service.rename_chapter(second.id, "风雪夜")
    first_half, second_half = service.split_chapter(second.id, offset=1, new_title="追兵")

    split_workspace = service.fetch_workspace()
    assert [chapter.title for chapter in split_workspace.chapters] == [
        "第一章 开端",
        "风雪夜",
        "追兵",
    ]
    assert [chapter.index for chapter in split_workspace.chapters] == [1, 2, 3]
    assert len(
        [s for s in split_workspace.segments if s.chapter_id == first_half.id]
    ) == 1
    assert len(
        [s for s in split_workspace.segments if s.chapter_id == second_half.id]
    ) == 1

    merged = service.merge_chapters([first_half.id, second_half.id], "风雪重逢")
    merged_workspace = service.fetch_workspace()

    assert merged.title == "风雪重逢"
    assert [chapter.title for chapter in merged_workspace.chapters] == [
        "第一章 开端",
        "风雪重逢",
    ]
    assert [chapter.index for chapter in merged_workspace.chapters] == [1, 2]
    assert len([s for s in merged_workspace.segments if s.chapter_id == merged.id]) == 2
    service.close()


def test_reopened_service_retains_manual_role_and_voice_changes(tmp_path: Path) -> None:
    service, root = create_service(tmp_path)
    workspace = service.fetch_workspace()
    lin = next(role for role in workspace.roles if role.name == "林舟")
    unassigned = next(segment for segment in workspace.segments if segment.role_id is None)

    service.assign_speaker([unassigned.id], lin.id)
    service.assign_voice(lin.id, "voice.lin", 1.2)
    service.close()

    reopened = ProjectService()
    reopened.open_project(root)
    updated = reopened.fetch_workspace()

    assert next(segment for segment in updated.segments if segment.id == unassigned.id).role_id == lin.id
    updated_lin = next(role for role in updated.roles if role.id == lin.id)
    assert (updated_lin.voice_id, updated_lin.speed) == ("voice.lin", 1.2)
    reopened.close()


def test_assign_speaker_rejects_unknown_role(tmp_path: Path) -> None:
    service, _ = create_service(tmp_path)
    segment_id = service.fetch_workspace().segments[0].id

    with pytest.raises(ValueError, match="角色不存在"):
        service.assign_speaker([segment_id], 99999)

    service.close()
