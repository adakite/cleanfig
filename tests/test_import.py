import cleanfig as cf


def test_import_exposes_version_and_backend() -> None:
    assert cf.__version__ == "1.4.0"
    assert cf.BACKEND in {"rust", "python-fallback"}
    assert hasattr(cf, "figure")
    assert hasattr(cf, "Figure")
    assert hasattr(cf, "Panel")
    assert hasattr(cf, "PlotHandle")
