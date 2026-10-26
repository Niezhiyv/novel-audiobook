from __future__ import annotations

import re
import unicodedata
from pathlib import Path


class TextImportError(ValueError):
    pass


def normalize_text(text: str) -> str:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    normalized = normalized.replace("\ufeff", "")
    normalized = re.sub(r"[\u200b\u200c\u200d\u2060]", "", normalized)
    normalized = "\n".join(line.rstrip() for line in normalized.split("\n"))
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized.strip()


def _is_reasonable_text(text: str) -> bool:
    if "\ufffd" in text:
        return False
    for character in text:
        if character in "\n\r\t":
            continue
        category = unicodedata.category(character)
        if category in {"Cc", "Cs", "Cn"}:
            return False
    return True


def _candidate_encodings(data: bytes) -> list[str]:
    if data.startswith(b"\xef\xbb\xbf"):
        return ["utf-8-sig"]
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return ["utf-16"]
    if data.count(b"\x00") >= max(2, len(data) // 5):
        return ["utf-16-le", "utf-16-be", "utf-8-sig", "gb18030"]
    return ["utf-8-sig", "gb18030", "utf-16-le", "utf-16-be"]


def decode_txt(path: Path) -> str:
    source = Path(path)
    data = source.read_bytes()
    if not data:
        raise TextImportError(f"文件为空: {source}")

    for encoding in _candidate_encodings(data):
        try:
            decoded = data.decode(encoding)
        except UnicodeDecodeError:
            continue
        if _is_reasonable_text(decoded):
            normalized = normalize_text(decoded)
            if normalized:
                return normalized

    raise TextImportError(f"无法识别文本编码: {source}")
