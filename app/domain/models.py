from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path


class SegmentKind(StrEnum):
    NARRATION = "narration"
    DIALOGUE = "dialogue"


class ChapterStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(slots=True)
class Project:
    id: int
    title: str
    root: Path
    created_at: str
    updated_at: str
    last_chapter_id: int | None = None
    last_filter: str = ""


@dataclass(slots=True)
class Chapter:
    title: str
    text: str
    index: int = 0
    status: ChapterStatus = ChapterStatus.PENDING
    output_path: str | None = None
    error: str | None = None
    id: int = 0


@dataclass(slots=True)
class Segment:
    chapter_id: int
    position: int
    kind: SegmentKind
    text: str
    role_id: int | None = None
    confidence: float = 0.0
    evidence: str | None = None
    id: int = 0


@dataclass(slots=True)
class Role:
    name: str
    aliases: list[str] = field(default_factory=list)
    voice_id: str | None = None
    speed: float = 1.0
    is_narrator: bool = False
    id: int = 0
