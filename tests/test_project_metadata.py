import tomllib
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_package_declares_open_source_license_and_repository() -> None:
    with (PROJECT_ROOT / "pyproject.toml").open("rb") as project_file:
        project = tomllib.load(project_file)["project"]

    assert project["license"] == "MIT"
    assert project["license-files"] == ["LICENSE"]
    assert project["urls"]["Repository"] == "https://github.com/Niezhiyv/novel-audiobook"
    assert (PROJECT_ROOT / "LICENSE").is_file()
