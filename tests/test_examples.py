import runpy
from importlib.util import find_spec
from pathlib import Path

import pytest


def test_basic_line_example_runs(tmp_path: Path, monkeypatch) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    monkeypatch.chdir(tmp_path)
    runpy.run_path(str(repo_root / "examples" / "basic_line.py"), run_name="__main__")

    assert (tmp_path / "examples" / "output" / "basic_line.svg").exists()
    assert (tmp_path / "examples" / "output" / "basic_line.html").exists()


@pytest.mark.skipif(find_spec("pandas") is None, reason="pandas is optional for the online dataframe example")
def test_esec_dual_y_example_runs(tmp_path: Path, monkeypatch) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    monkeypatch.chdir(tmp_path)
    data_dir = tmp_path / "examples" / "Data"
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "IRIS_DMC_esecEventsDb.txt").write_text((repo_root / "examples" / "Data" / "IRIS_DMC_esecEventsDb.txt").read_text())
    runpy.run_path(str(repo_root / "examples" / "esec_dual_y_light.py"), run_name="__main__")

    assert (tmp_path / "examples" / "output" / "esec_dual_y_light.svg").exists()
    assert (tmp_path / "examples" / "output" / "esec_dual_y_light.html").exists()
    assert (tmp_path / "examples" / "output" / "esec_dual_y_light.pdf").exists() == (find_spec("cleanfig._cleanfig") is not None)
