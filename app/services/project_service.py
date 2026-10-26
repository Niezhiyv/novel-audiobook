from __future__ import annotations

import json
import shutil
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from app.domain.models import Chapter, Project, Role, Segment, SegmentKind
from app.importers.text_importer import decode_txt
from app.parsing.chapter_parser import ParsedChapter, split_chapters
from app.parsing.dialogue_parser import ParsedSegment, split_segments
from app.parsing.speaker_resolver import resolve_explicit_speakers
from app.storage.repository import ProjectRepository


@dataclass(slots=True)
class ProjectWorkspace:
    project: Project
    chapters: list[Chapter]
    segments: list[Segment]
    roles: list[Role]


class ProjectService:
    def __init__(self, repository: ProjectRepository | None = None) -> None:
        self.repository = repository or ProjectRepository()

    def create_from_txt(self, root: Path, title: str, source_path: Path) -> Project:
        source_text = decode_txt(source_path)
        parsed_chapters = split_chapters(source_text)
        if not parsed_chapters:
            raise ValueError("文本中没有可导入的章节")

        project = self.repository.create_project(root, title, source_text)
        try:
            self._persist_parsed_chapters(parsed_chapters)
        except Exception:
            self.repository.close()
            shutil.rmtree(project.root, ignore_errors=True)
            raise
        return project

    def open_project(self, root: Path) -> Project:
        return self.repository.open_project(root)

    def fetch_workspace(self) -> ProjectWorkspace:
        return ProjectWorkspace(
            project=self.repository.project,
            chapters=self.repository.load_chapters(),
            segments=self.repository.load_segments(),
            roles=self.repository.load_roles(),
        )

    def assign_speaker(
        self,
        segment_ids: Sequence[int],
        role_id: int | None,
    ) -> None:
        if not segment_ids:
            return
        if role_id is not None and role_id not in {role.id for role in self.repository.load_roles()}:
            raise ValueError(f"角色不存在: {role_id}")
        placeholders = ",".join("?" for _ in segment_ids)
        with self.repository.connection:
            self.repository.connection.execute(
                f"UPDATE segments SET role_id = ? WHERE id IN ({placeholders})",
                (role_id, *segment_ids),
            )

    def create_or_merge_role(self, name: str, aliases: Sequence[str]) -> Role:
        canonical = name.strip()
        if not canonical:
            raise ValueError("角色名称不能为空")
        requested_aliases = [
            alias.strip()
            for alias in aliases
            if alias.strip() and alias.strip() != canonical
        ]
        roles = self.repository.load_roles()
        target = next((role for role in roles if role.name == canonical), None)
        matching = [
            role
            for role in roles
            if role.name != canonical and role.name in requested_aliases
        ]
        if target is None and matching:
            target = matching.pop(0)
            target.name = canonical
        target = target or Role(name=canonical)

        merged_aliases: list[str] = []
        for alias in [*target.aliases, *requested_aliases, *(role.name for role in matching)]:
            if alias and alias != target.name and alias not in merged_aliases:
                merged_aliases.append(alias)
        for role in matching:
            for alias in role.aliases:
                if alias and alias != target.name and alias not in merged_aliases:
                    merged_aliases.append(alias)
        target.aliases = merged_aliases
        source_ids = [role.id for role in matching if role.id != target.id]

        with self.repository.connection:
            if target.id == 0:
                cursor = self.repository.connection.execute(
                    """
                    INSERT INTO roles (name, aliases_json, voice_id, speed, is_narrator)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        target.name,
                        json.dumps(target.aliases, ensure_ascii=False),
                        target.voice_id,
                        target.speed,
                        int(target.is_narrator),
                    ),
                )
                target.id = int(cursor.lastrowid)
            else:
                self.repository.connection.execute(
                    """
                    UPDATE roles
                    SET name = ?, aliases_json = ?, voice_id = ?, speed = ?, is_narrator = ?
                    WHERE id = ?
                    """,
                    (
                        target.name,
                        json.dumps(target.aliases, ensure_ascii=False),
                        target.voice_id,
                        target.speed,
                        int(target.is_narrator),
                        target.id,
                    ),
                )
            if source_ids:
                placeholders = ",".join("?" for _ in source_ids)
                self.repository.connection.execute(
                    f"UPDATE segments SET role_id = ? WHERE role_id IN ({placeholders})",
                    (target.id, *source_ids),
                )
                self.repository.connection.execute(
                    f"DELETE FROM roles WHERE id IN ({placeholders})",
                    source_ids,
                )
        return target

    def assign_voice(self, role_id: int, voice_id: str | None, speed: float) -> None:
        if speed <= 0:
            raise ValueError("语速必须大于 0")
        roles = self.repository.load_roles()
        role = next((item for item in roles if item.id == role_id), None)
        if role is None:
            raise ValueError(f"角色不存在: {role_id}")
        role.voice_id = voice_id
        role.speed = speed
        self.repository.save_role(role)

    def rename_chapter(self, chapter_id: int, title: str) -> None:
        if not title.strip():
            raise ValueError("章节标题不能为空")
        chapters = self.repository.load_chapters()
        chapter = next((item for item in chapters if item.id == chapter_id), None)
        if chapter is None:
            raise ValueError(f"章节不存在: {chapter_id}")
        chapter.title = title.strip()
        self.repository.save_chapters([chapter])

    def split_chapter(
        self,
        chapter_id: int,
        offset: int,
        new_title: str,
    ) -> tuple[Chapter, Chapter]:
        if not new_title.strip():
            raise ValueError("新章节标题不能为空")
        workspace = self.fetch_workspace()
        chapter = next(
            (item for item in workspace.chapters if item.id == chapter_id),
            None,
        )
        if chapter is None:
            raise ValueError(f"章节不存在: {chapter_id}")
        chapter_segments = [
            segment for segment in workspace.segments if segment.chapter_id == chapter_id
        ]
        if offset <= 0 or offset >= len(chapter_segments):
            raise ValueError("拆分位置必须位于两个片段之间")

        first_segments = chapter_segments[:offset]
        second_segments = chapter_segments[offset:]
        split_at = next(
            index for index, item in enumerate(workspace.chapters) if item.id == chapter_id
        )
        second = Chapter(title=new_title.strip(), text="")
        ordered_chapters = [
            *workspace.chapters[: split_at + 1],
            second,
            *workspace.chapters[split_at + 1 :],
        ]
        chapter.text = _segments_text(first_segments)
        second.text = _segments_text(second_segments)

        grouped_segments: dict[int, list[Segment]] = {}
        for existing in workspace.chapters:
            grouped_segments[id(existing)] = [
                segment
                for segment in workspace.segments
                if segment.chapter_id == existing.id
            ]
        grouped_segments[id(chapter)] = first_segments
        grouped_segments[id(second)] = second_segments

        with self.repository.connection:
            self._rewrite_layout(ordered_chapters, grouped_segments)
        return chapter, second

    def merge_chapters(self, chapter_ids: Sequence[int], title: str) -> Chapter:
        if len(chapter_ids) < 2:
            raise ValueError("至少选择两个章节才能合并")
        if not title.strip():
            raise ValueError("合并后的章节标题不能为空")
        workspace = self.fetch_workspace()
        selected = [
            chapter for chapter in workspace.chapters if chapter.id in set(chapter_ids)
        ]
        if len(selected) != len(set(chapter_ids)):
            raise ValueError("存在无效的章节编号")
        positions = [workspace.chapters.index(chapter) for chapter in selected]
        if positions != list(range(min(positions), max(positions) + 1)):
            raise ValueError("只能合并连续章节")

        first = selected[0]
        first.title = title.strip()
        selected_segments = [
            segment
            for chapter in selected
            for segment in workspace.segments
            if segment.chapter_id == chapter.id
        ]
        first.text = _segments_text(selected_segments)
        ordered_chapters = [
            chapter for chapter in workspace.chapters if chapter not in selected[1:]
        ]
        grouped_segments: dict[int, list[Segment]] = {
            id(chapter): [
                segment
                for segment in workspace.segments
                if segment.chapter_id == chapter.id
            ]
            for chapter in ordered_chapters
        }
        grouped_segments[id(first)] = selected_segments

        with self.repository.connection:
            self._rewrite_layout(
                ordered_chapters,
                grouped_segments,
                delete_chapter_ids=[chapter.id for chapter in selected[1:]],
            )
        return first

    def close(self) -> None:
        self.repository.close()

    def _persist_parsed_chapters(
        self,
        parsed_chapters: Sequence[ParsedChapter],
    ) -> None:
        narrator = Role(name="旁白", is_narrator=True)
        discovered_roles: dict[str, Role] = {}
        chapters: list[Chapter] = []
        parsed_segments: dict[int, list[ParsedSegment]] = {}

        for index, parsed in enumerate(parsed_chapters, start=1):
            chapter = Chapter(
                index=index,
                title=parsed.title,
                text=parsed.text,
            )
            chapters.append(chapter)
            raw_segments = resolve_explicit_speakers(split_segments(parsed.text))
            parsed_segments[id(chapter)] = raw_segments
            for parsed_segment in raw_segments:
                if parsed_segment.speaker_name:
                    discovered_roles.setdefault(
                        parsed_segment.speaker_name,
                        Role(name=parsed_segment.speaker_name),
                    )

        self.repository.save_role(narrator)
        for role in discovered_roles.values():
            self.repository.save_role(role)
        self.repository.save_chapters(chapters)

        for chapter in chapters:
            for position, parsed_segment in enumerate(
                parsed_segments[id(chapter)],
                start=1,
            ):
                if parsed_segment.kind is SegmentKind.NARRATION:
                    role_id = narrator.id
                elif parsed_segment.speaker_name:
                    role_id = discovered_roles[parsed_segment.speaker_name].id
                else:
                    role_id = None
                self.repository.save_segment(
                    Segment(
                        chapter_id=chapter.id,
                        position=position,
                        kind=parsed_segment.kind,
                        text=parsed_segment.text,
                        role_id=role_id,
                        confidence=parsed_segment.confidence,
                        evidence=parsed_segment.evidence,
                    )
                )

    def _rewrite_layout(
        self,
        chapters: Sequence[Chapter],
        grouped_segments: Mapping[int, Sequence[Segment]],
        delete_chapter_ids: Sequence[int] = (),
    ) -> None:
        connection = self.repository.connection
        connection.execute("UPDATE chapters SET chapter_index = -id WHERE id > 0")
        connection.execute("UPDATE segments SET position = -id WHERE id > 0")

        for final_index, chapter in enumerate(chapters, start=1):
            chapter.index = final_index
            if chapter.id == 0:
                cursor = connection.execute(
                    """
                    INSERT INTO chapters
                        (chapter_index, title, text, status, output_path, error)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        -1_000_000 - final_index,
                        chapter.title,
                        chapter.text,
                        chapter.status.value,
                        chapter.output_path,
                        chapter.error,
                    ),
                )
                chapter.id = int(cursor.lastrowid)
            else:
                connection.execute(
                    """
                    UPDATE chapters
                    SET title = ?, text = ?, status = ?, output_path = ?, error = ?
                    WHERE id = ?
                    """,
                    (
                        chapter.title,
                        chapter.text,
                        chapter.status.value,
                        chapter.output_path,
                        chapter.error,
                        chapter.id,
                    ),
                )

        for chapter in chapters:
            for position, segment in enumerate(grouped_segments[id(chapter)], start=1):
                segment.chapter_id = chapter.id
                segment.position = position
                if segment.id == 0:
                    cursor = connection.execute(
                        """
                        INSERT INTO segments
                            (chapter_id, position, kind, text, role_id, confidence, evidence)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            segment.chapter_id,
                            segment.position,
                            segment.kind.value,
                            segment.text,
                            segment.role_id,
                            segment.confidence,
                            segment.evidence,
                        ),
                    )
                    segment.id = int(cursor.lastrowid)
                else:
                    connection.execute(
                        """
                        UPDATE segments
                        SET chapter_id = ?, position = ?, kind = ?, text = ?,
                            role_id = ?, confidence = ?, evidence = ?
                        WHERE id = ?
                        """,
                        (
                            segment.chapter_id,
                            segment.position,
                            segment.kind.value,
                            segment.text,
                            segment.role_id,
                            segment.confidence,
                            segment.evidence,
                            segment.id,
                        ),
                    )

        for chapter in chapters:
            connection.execute(
                "UPDATE chapters SET chapter_index = ? WHERE id = ?",
                (chapter.index, chapter.id),
            )
        if delete_chapter_ids:
            placeholders = ",".join("?" for _ in delete_chapter_ids)
            connection.execute(
                f"DELETE FROM chapters WHERE id IN ({placeholders})",
                tuple(delete_chapter_ids),
            )


def _segments_text(segments: Sequence[Segment]) -> str:
    pieces: list[str] = []
    for segment in segments:
        if segment.kind is SegmentKind.DIALOGUE:
            pieces.append(f"“{segment.text}”")
        else:
            pieces.append(segment.text)
    return "\n".join(pieces)
