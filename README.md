# cleanfig

`cleanfig` is a small Rust/Python plotting package for clean scientific figures with vector-first export.

It is intentionally narrow: simple publication-style defaults, light visual clutter, compact labeling, and a small public API. The focus is on figures that should look close to final output without extensive styling code.

Useful links:

- Gallery: https://adakite.github.io/cleanfig/gallery/
- Documentation landing page: https://adakite.github.io/cleanfig/
- Repository: https://github.com/adakite/cleanfig

<p align="center">
  <img src="https://adakite.github.io/cleanfig/gallery/assets/four_panels_dark.svg" width="900" alt="cleanfig four-panel dark example">
</p>

## Installation

Install the latest GitHub version:

```bash
pip install git+https://github.com/adakite/cleanfig.git
```

Planned future PyPI install:

```bash
pip install cleanfig
```

## Quick Start

```python
import numpy as np
import cleanfig as cf

x = np.linspace(0, 10, 200)
y = np.sin(x)

fig = cf.figure(width="single", height=3.4, panel_labels=False)
ax = fig.panel(0, 0)
ax.line(x, y, label="signal")
ax.scatter(x[::20], y[::20], size=5)
ax.xlabel("x")
ax.ylabel("y")

fig.save("basic_line.svg")
fig.save("basic_line.html")
fig.save("basic_line.pdf")
```

## Public API

The package is designed to be used as:

```python
import cleanfig as cf
```

Current public entry points:

- `cf.figure(...)`
- `Figure.panel(row, col)`
- `Figure.save(path)`
- `Panel.scatter(...)`
- `Panel.line(...)`
- `Panel.bar(...)`
- `Panel.histogram(...)`
- `Panel.field(...)`
- `Panel.violin(...)`
- `Panel.box(...)`
- `Panel.colorbar(...)`
- `Panel.legend()`
- `Panel.xlabel(...)`
- `Panel.ylabel(...)`
- `Panel.right_ylabel(...)`
- `Panel.xscale(...)`
- `Panel.yscale(...)`
- `Panel.limits(...)`
- `Panel.right_limits(...)`

## API Reference

### `cf.figure(width="single", height=4.0, grid=(1, 1), panel_labels=False, font=None, theme="publication")`

- `width`: `"single"` or `"double"`
- `height`: figure height in inches
- `grid`: `(rows, cols)`
- `panel_labels`: add panel letters
- `font`: custom font family string
- `theme`: `"publication"` / `"nature"` / `"light"` alias, or `"dark"`

### Axis labels, limits, and scales

- `ax.xlabel(label)`
- `ax.ylabel(label)`
- `ax.right_ylabel(label)`: label for a secondary right Y axis
- `ax.limits(x=None, y=None)`: explicit limits for the main X/Y axes
- `ax.right_limits(y=None)`: explicit limits for the right Y axis
- `ax.xscale("linear" | "log")`
- `ax.yscale("linear" | "log", axis="left" | "right")`

Log scales require strictly positive values and strictly positive limits.

### `ax.scatter(x, y, color=None, size=6.0, alpha=0.8, label=None, cmap=None, yaxis="left")`

- `x`, `y`: same-length numeric arrays
- `color`: named/hex color or numeric array for colormap mapping
- `size`: marker diameter in points
- `alpha`: opacity
- `label`: legend entry
- `cmap`: colormap name for mapped colors; see `Built-in Colormaps` below
- `yaxis`: `"left"` or `"right"` for dual-Y figures

Returns a `PlotHandle` when color mapping is used.

### `ax.line(x, y, color=None, width=1.2, alpha=1.0, label=None, yaxis="left")`

- `color`: named/hex color
- `width`: stroke width in points
- `alpha`: opacity
- `label`: legend entry
- `yaxis`: `"left"` or `"right"`

### `ax.bar(labels, values, yaxis="left", color=None, alpha=1.0, show_x_axis=False)`

- `labels`: categorical X labels
- `values`: numeric heights
- `yaxis`: `"left"` or `"right"`
- `color`: named/hex color
- `alpha`: opacity
- `show_x_axis`: draw the bottom X axis line and ticks for bar charts

### `ax.histogram(data, bins=12, range=None, density=False, color=None, alpha=1.0, label=None, yaxis="left")`

- `data`: numeric samples
- `bins`: number of bins
- `range`: optional `(min, max)` binning range
- `density`: normalize to probability density instead of counts
- `color`: named/hex fill color
- `alpha`: opacity
- `label`: legend entry
- `yaxis`: `"left"` or `"right"`

### `ax.field(grid, cmap=None, cell_edges=False, render="auto")`

- `grid`: 2D numeric array
- `cmap`: colormap name; see `Built-in Colormaps` below
- `cell_edges`: draw subtle cell borders when `True`
- `render`: `"auto"`, `"grid"`, or `"embedded"`

`render="auto"` is the default. In the Rust backend, dense fields automatically switch to an embedded raster image to avoid visible seams between cells, while smaller fields remain grid/vector based. Use `"grid"` to force cell-by-cell rendering or `"embedded"` to force the rasterized field image path.

Returns a `PlotHandle` for optional colorbar creation.

### `ax.colorbar(handle, label=None, placement=None, style=None)`

- `handle`: result of a mapped `scatter`, `field`, or mapped-point `violin`
- `label`: colorbar label
- `placement`: `"right"` or `"inside-left"`
- `style`: `"binned"` or `"continuous"`

Current default is `"binned"`.

### `ax.violin(data, labels=None, show_median=False, points=False, point_color=None, point_size=4.0, point_alpha=0.75, point_cmap=None)`

- `data`: grouped numeric data
- `labels`: category labels
- `show_median`: draw median segment
- `points`: overlay individual points
- `point_color`: constant color, flat array, or grouped arrays
- `point_size`: point diameter
- `point_alpha`: point opacity
- `point_cmap`: colormap for mapped points; see `Built-in Colormaps` below

Returns a `PlotHandle` when mapped point colors are used.

### `ax.box(data, labels=None)`

- `data`: grouped numeric data
- `labels`: category labels

### `ax.legend()`

Creates a compact frameless legend from labeled layers.

## Current Feature Status

- Supported: line, scatter, bar, histogram, violin, box, field plots with auto grid/embedded rendering
- Supported: light/dark themes, log X/Y axes, dual Y axes, SVG/HTML/PDF export
- Not supported yet: `ax.spectrogram()`, logarithmic colorbars, geographic projections

## Examples

Useful example scripts are provided in `examples/`:

- `basic_line.py`
- `four_panels.py`
- `violin_box_light.py`
- `esec_dual_y_light.py` for a light-theme dual-Y example using a `pandas.DataFrame` loaded from a bundled ESEC catalog extract in `examples/Data/`
- theme-specific wrappers for light/dark example output

## Export Formats

Supported export targets:

- `SVG`
- `HTML` with embedded SVG
- `PDF` through SVG conversion in the Rust backend

## Built-in Colormaps

`cleanfig` currently ships with a larger built-in continuous colormap set.

General:

- `gray`
- `magma`
- `bone`

Fabio Crameri family currently integrated:

- Sequential-ish: `acton`, `bamako`, `batlow`, `bilbao`, `devon`, `hawaii`, `imola`, `lajolla`, `lapaz`, `lipari`, `navia`, `nuuk`, `oslo`, `tokyo`, `turku`
- Diverging / balanced: `berlin`, `broc`, `cork`, `managua`, `roma`, `tofino`, `vanimo`, `vik`

Notes:

- These Crameri maps were integrated as built-in names so the plotting API stays unchanged: `cmap="roma"`, `cmap="batlow"`, etc.
- Unknown colormap names still fall back to `batlow`.
- Colormap attribution and licensing notice: [LICENSE-THIRD-PARTY.md](LICENSE-THIRD-PARTY.md)

Citation for the integrated Scientific colour maps:

> Crameri, F. (2023). Scientific colour maps (8.0.1). Zenodo.
> https://doi.org/10.5281/zenodo.8409685

## Design Philosophy

- vector-first output
- clean left/bottom axes by default
- minimal plot constructors
- no GUI, dashboards, or heavyweight plotting state
- useful scientific defaults over maximum flexibility

## Fallback Behavior

`cleanfig` prefers the compiled Rust extension.

If the extension is unavailable, it falls back to a pure Python implementation. The fallback is intended for graceful local use and testing, but it is not feature-complete. In particular, PDF export is only available when the Rust backend is loaded.

You can inspect the active backend with:

```python
import cleanfig as cf
print(cf.BACKEND)
```

## Current Limitations

- no `ax.spectrogram()` yet
- no logarithmic colorbars
- no standalone raster plotting backend beyond embedded dense field rendering
- no geographic projections
- visual styling is intentionally constrained
- the Python fallback keeps field rendering grid-based even when `render="embedded"` is requested

## Development Install

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -e ".[dev]"
maturin develop
pytest -q
```

The `esec_dual_y_light.py` example additionally expects `pandas`, which is included in the `dev` extra. The bundled ESEC source file and citation notes are stored under `examples/Data/`.

## Citation, License, Contact

- License: MIT, see `LICENSE`
- Changelog: `CHANGELOG.md`
- Release checklist: `RELEASE.md`
- Contact: Antoine Lucas
