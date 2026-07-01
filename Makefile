PYTHON ?= python
VENV_PYTHON ?= .venv/bin/python
MATURIN ?= maturin

.PHONY: clean audit test develop build check-wheel

clean:
	rm -rf build dist target examples/output .pytest_cache
	find . -name "__pycache__" -type d -prune -exec rm -rf {} +
	find . -name "*.pyc" -delete
	find . -name ".DS_Store" -delete

audit:
	rg -n -i "co[d]ex|open[a]i|chat[g]pt|\\bg[p]t\\b|agent[_-]?co[d]ex|/Users/a[l]ucas|IPGP D[r]opbox|target/d[e]bug|target/r[e]lease|nicev[i]z" .

test:
	$(PYTHON) -m pytest -q

develop:
	$(MATURIN) develop

build:
	$(MATURIN) build --release
	$(PYTHON) -m build --sdist

check-wheel:
	$(PYTHON) -m pip install --force-reinstall target/wheels/*.whl
	$(PYTHON) -c "import cleanfig; print(cleanfig.__version__); print(cleanfig.BACKEND)"
	$(PYTHON) -m twine check dist/* target/wheels/*
