import app


def test_package_exposes_version() -> None:
    assert app.__version__ == "0.1.0"


def test_module_entrypoint_is_importable() -> None:
    import app.__main__  # noqa: F401
