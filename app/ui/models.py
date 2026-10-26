from __future__ import annotations

from app.domain.models import Role, Segment, SegmentKind

SEGMENT_HEADERS = ["类型", "角色", "文本", "识别置信度"]


def segment_kind_label(kind: SegmentKind) -> str:
    return "旁白" if kind is SegmentKind.NARRATION else "对白"


def role_name(segment: Segment, roles_by_id: dict[int, Role]) -> str:
    if segment.role_id is None:
        return "未分配"
    role = roles_by_id.get(segment.role_id)
    return role.name if role else "未知角色"


def segment_matches_filter(
    segment: Segment,
    roles_by_id: dict[int, Role],
    filter_text: str,
) -> bool:
    needle = filter_text.strip().casefold()
    if not needle:
        return True
    searchable = " ".join(
        [
            segment_kind_label(segment.kind),
            role_name(segment, roles_by_id),
            segment.text,
        ]
    ).casefold()
    return needle in searchable
