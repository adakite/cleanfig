# Release Checklist

## Local Setup

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -e ".[dev]"
```

## Repository Audit

```bash
find . -name ".DS_Store" -delete
rm -rf __MACOSX
find . -name "__pycache__" -type d -prune -exec rm -rf {} +
find . -name "*.pyc" -delete

rg -i "co[d]ex|open[a]i|chat[g]pt|\\bg[p]t\\b|agent[_-]?co[d]ex|/Users/a[l]ucas|IPGP D[r]opbox|target/d[e]bug|target/r[e]lease|nicev[i]z" .
```

## Build And Test

```bash
maturin develop
pytest -q

maturin build --release
python -m pip install --force-reinstall target/wheels/*.whl
python -c "import cleanfig; print(cleanfig.__version__); print(cleanfig.BACKEND)"
python -m build --sdist
twine check dist/* target/wheels/*
```

## Example Runs

```bash
python examples/basic_line.py
python examples/four_panels.py
python examples/esec_dual_y_light.py
python examples/four_panels_light.py
python examples/four_panels_dark.py
python examples/violin_box_light.py
python examples/violin_box_dark.py
```

## Before Tagging

- confirm `README.md`, `CHANGELOG.md`, `LICENSE`, and workflows are up to date
- confirm no generated artifacts are staged
- confirm `maturin build --release` succeeds on the target machine
- confirm `pytest -q` passes

## Manual GitHub Install Check

```bash
pip install git+https://github.com/adakite/cleanfig.git
python -c "import cleanfig; print(cleanfig.__version__)"
```
