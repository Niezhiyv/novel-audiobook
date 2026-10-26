from pathlib import Path

import pytest

from app.importers.text_importer import TextImportError, decode_txt, normalize_text


@pytest.mark.parametrize(
    ("encoding", "text"),
    [
        ("utf-8", "第一章 开端\n林舟说道：“走吧。”"),
        ("gb18030", "第二章 风雪\n他抬头看向远方。"),
        ("utf-16", "第三章 夜航\n海面很安静。"),
        ("utf-16-le", "第四章 归途\n天亮了。"),
    ],
)
def test_decode_txt_supports_common_encodings(
    tmp_path: Path,
    encoding: str,
    text: str,
) -> None:
    path = tmp_path / "novel.txt"
    path.write_bytes(text.encode(encoding))

    assert decode_txt(path) == text


def test_normalize_text_handles_mixed_newlines_and_invisible_characters() -> None:
    source = "\ufeff第一行\r\n\r\n第二行\r第三行\u200b  \n\n\n"

    assert normalize_text(source) == "第一行\n\n第二行\n第三行"


def test_decode_txt_rejects_empty_file(tmp_path: Path) -> None:
    path = tmp_path / "empty.txt"
    path.write_bytes(b"")

    with pytest.raises(TextImportError, match="文件为空"):
        decode_txt(path)


def test_decode_txt_rejects_undecodable_content(tmp_path: Path) -> None:
    path = tmp_path / "broken.txt"
    path.write_bytes(b"\xff\xff\xff\xff")

    with pytest.raises(TextImportError, match="无法识别"):
        decode_txt(path)
