from __future__ import annotations

import json
import os
import shutil
import sqlite3
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from app.domain.models import Chapter, ChapterStatus, Project, Role, Segment, SegmentKind
from app.storage.database import (
    SchemaVersionError,
    initialize_database,
    open_and_migrate_database,
)


class InvalidProjectError(RuntimeError):
    pass


class ProjectAlreadyExistsError(RuntimeError):
    pass


class ProjectNotOpenError(RuntimeError):
    pass


class ProjectRepository:
    def __init__(self) -> None:
        self._root: Path | None = None
        self._connection: sqlite3.Connection | None = None
        self._project: Project | None = None

    @property
    def root(self) -> Path:
        if self._root is None:
            raise ProjectNotOpenError("尚未创建或打开项目")
        return self._root

    @property
    def project(self) -> Project:
        if self._project is None:
            raise ProjectNotOpenError("尚未创建或打开项目")
        return self._project

    @property
    def connection(self) -> sqlite3.Connection:
        if self._connection is None:
            raise ProjectNotOpenError("尚未创建或打开项目")
        return self._connection

    def create_project(
        self,
        root: Path,
        title: str,
        source_text: str,
    ) -> Project:
        target = Path(root).expanduser().resolve()
        if target.exists():
            raise ProjectAlreadyExistsError(f"项目目录已存在: {target}")
        if not title.strip():
            raise ValueError("项目名称不能为空")

        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.parent / f".{target.name}.{uuid.uuid4().hex}.tmp"
        try:
            temporary.mkdir()
            (temporary / "source.txt").write_text(source_text, encoding="utf-8")
            (temporary / "cache" / "audio").mkdir(parents=True)
            (temporary / "exports").mkdir()
            (temporary / "logs").mkdir()
            initialize_database(temporary / "project.sqlite3")

            now = datetime.now(UTC).isoformat()
            connection = open_and_migrate_database(temporary / "project.sqlite3")
            try:
                with connection:
                    connection.execute(
                        """
                        INSERT INTO projects (id, title, created_at, updated_at)
                        VALUES (1, ?, ?, ?)
                        """,
                        (title.strip(), now, now),
                    )
            finally:
                connection.close()

            os.replace(temporary, target)
        except Exception:
            shutil.rmtree(temporary, ignore_errors=True)
            raise

        return self.open_project(target)

    def open_project(self, root: Path) -> Project:
        target = Path(root).expanduser().resolve()
        database_path = target / "project.sqlite3"
        source_path = target / "source.txt"
        if not database_path.is_file() or not source_path.is_file():
            raise InvalidProjectError(f"不是有效项目目录: {target}")

        self.close()
        try:
            connection = open_and_migrate_database(database_path)
        except (sqlite3.DatabaseError, SchemaVersionError) as error:
            raise InvalidProjectError(f"无法打开项目数据库: {error}") from error

        row = connection.execute(
            """
            SELECT id, title, created_at, updated_at, last_chapter_id, last_filter
            FROM projects WHERE id = 1
            """
        ).fetchone()
        if row is None:
            connection.close()
            raise InvalidProjectError("项目数据库缺少 project 记录")

        self._root = target
        self._connection = connection
        self._project = Project(
            id=int(row["id"]),
            title=str(row["title"]),
            root=target,
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
            last_chapter_id=row["last_chapter_id"],
            last_filter=str(row["last_filter"]),
        )
        return self._project

    def save_chapters(self, chapters: Sequence[Chapter]) -> None:
        with self.connection:
            for chapter in chapters:
                if chapter.id == 0:
                    cursor = self.connection.execute(
                        """
                        INSERT INTO chapters
                            (chapter_index, title, text, status, output_path, error)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            chapter.index,
                            chapter.title,
                            chapter.text,
                            chapter.status.value,
                            chapter.output_path,
                            chapter.error,
                        ),
                    )
                    chapter.id = int(cursor.lastrowid)
                else:
                    self.connection.execute(
                        """
                        UPDATE chapters
                        SET chapter_index = ?, title = ?, text = ?, status = ?,
                            output_path = ?, error = ?
                        WHERE id = ?
                        """,
                        (
                            chapter.index,
                            chapter.title,
                            chapter.text,
                            chapter.status.value,
                            chapter.output_path,
                            chapter.error,
                            chapter.id,
                        ),
                    )

    def load_chapters(self) -> list[Chapter]:
        rows = self.connection.execute(
            """
            SELECT id, chapter_index, title, text, status, output_path, error
            FROM chapters ORDER BY chapter_index
            """
        ).fetchall()
        return [
            Chapter(
                id=int(row["id"]),
                index=int(row["chapter_index"]),
                title=str(row["title"]),
                text=str(row["text"]),
                status=ChapterStatus(str(row["status"])),
                output_path=row["output_path"],
                error=row["error"],
            )
            for row in rows
        ]

    def save_segment(self, segment: Segment) -> None:
        with self.connection:
            if segment.id == 0:
                cursor = self.connection.execute(
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
                self.connection.execute(
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

    def load_segments(self) -> list[Segment]:
        rows = self.connection.execute(
            """
            SELECT id, chapter_id, position, kind, text, role_id, confidence, evidence
            FROM segments ORDER BY chapter_id, position
            """
        ).fetchall()
        return [
            Segment(
                id=int(row["id"]),
                chapter_id=int(row["chapter_id"]),
                position=int(row["position"]),
                kind=SegmentKind(str(row["kind"])),
                text=str(row["text"]),
                role_id=row["role_id"],
                confidence=float(row["confidence"]),
                evidence=row["evidence"],
            )
            for row in rows
        ]

    def save_role(self, role: Role) -> None:
        aliases = json.dumps(role.aliases, ensure_ascii=False)
        with self.connection:
            if role.id == 0:
                row = self.connection.execute(
                    """
                    INSERT INTO roles (name, aliases_json, voice_id, speed, is_narrator)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(name) DO UPDATE SET
                        aliases_json = excluded.aliases_json,
                        voice_id = excluded.voice_id,
                        speed = excluded.speed,
                        is_narrator = excluded.is_narrator
                    RETURNING id
                    """,
                    (
                        role.name,
                        aliases,
                        role.voice_id,
                        role.speed,
                        int(role.is_narrator),
                    ),
                ).fetchone()
                role.id = int(row["id"])
            else:
                self.connection.execute(
                    """
                    UPDATE roles
                    SET name = ?, aliases_json = ?, voice_id = ?, speed = ?, is_narrator = ?
                    WHERE id = ?
                    """,
                    (
                        role.name,
                        aliases,
                        role.voice_id,
                        role.speed,
                        int(role.is_narrator),
                        role.id,
                    ),
                )

    def load_roles(self) -> list[Role]:
        rows = self.connection.execute(
            """
            SELECT id, name, aliases_json, voice_id, speed, is_narrator
            FROM roles ORDER BY id
            """
        ).fetchall()
        return [
            Role(
                id=int(row["id"]),
                name=str(row["name"]),
                aliases=list(json.loads(str(row["aliases_json"]))),
                voice_id=row["voice_id"],
                speed=float(row["speed"]),
                is_narrator=bool(row["is_narrator"]),
            )
            for row in rows
        ]

    def save_view_state(self, last_chapter_id: int | None, last_filter: str) -> None:
        now = datetime.now(UTC).isoformat()
        with self.connection:
            self.connection.execute(
                """
                UPDATE projects
                SET last_chapter_id = ?, last_filter = ?, updated_at = ?
                WHERE id = 1
                """,
                (last_chapter_id, last_filter, now),
            )
        self.project.last_chapter_id = last_chapter_id
        self.project.last_filter = last_filter
        self.project.updated_at = now

    def close(self) -> None:
        if self._connection is not None:
            self._connection.close()
        self._connection = None
        self._root = None
        self._project = None
