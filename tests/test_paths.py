import sys
from pathlib import Path

from app.paths import application_root


def test_application_root_uses_executable_directory_when_frozen(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "portable" / "小说转听书.exe"))

    assert application_root() == (tmp_path / "portable").resolve()


def test_application_root_uses_repository_directory_when_running_source(
    monkeypatch,
) -> None:
    monkeypatch.delattr(sys, "frozen", raising=False)

    assert application_root() == Path(__file__).resolve().parents[1]
