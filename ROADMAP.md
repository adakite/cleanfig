# Roadmap

## Scope

This roadmap covers two proposed additions to `cleanfig`:

1. log-scaled histogram rendering for colorbar histograms
2. contour and filled-contour support for 2D fields

The implementation priority is to preserve `cleanfig`'s compact API and keep the first version robust before adding extra styling complexity.

## Track 1: Log Colorbar Histogram

### Goal

Add a log-height mode for the histogram currently rendered below mapped-color handles, without changing the color mapping itself.

### Proposed API

```python
ax.colorbar(
    handle,
    label=None,
    placement=None,
    style=None,
    histogram_scale="linear",  # or "log"
)
```

### Behavioral Decision

- `histogram_scale="log"` affects only histogram bar heights
- the color axis remains linear unless a future feature explicitly adds logarithmic color mapping
- zero-count bins need explicit handling, likely via a rendering floor or `log(count + offset)`

### Implementation Steps

1. Extend the `Colorbar` scene model to store histogram scaling mode.
2. Update Python and Rust API bindings.
3. Keep histogram binning unchanged; apply log transform only at render time.
4. Define zero-bin behavior:
   - preferred first version: `log10(count + 1)` normalization
5. Keep the current horizontal histogram layout.
6. Decide whether to annotate the log behavior in labels or leave it implicit.

### Tests

- strong dynamic range in counts
- zero-count bins
- parity between Rust and Python fallback if the fallback remains feature-aligned
- SVG and PDF snapshot inspection

## Track 2: Contour Lines From Fields

### Goal

Add isoline rendering from 2D numeric grids with a minimal API first, then layer in value-scaled styling.

### Recommended API Shape

Start with a dedicated line API and a dedicated filled API:

```python
ax.contour(grid, levels=10, color=None, width=0.9, alpha=1.0, cmap=None)
ax.contourf(grid, levels=10, cmap="batlow", alpha=0.6)
```

Avoid overloading `field()` in the first iteration.

### Phase A: Minimal `contour()`

#### Supported First-Version Features

- `levels` as either:
  - integer for automatic level generation
  - explicit numeric sequence
- unique color for all contour lines
- unique line width
- global opacity
- optional colormap-driven color by level

#### Implementation Steps

1. Add `Panel.contour(...)` to the public API.
2. Implement a Marching Squares engine in Rust.
3. Generate one or more polylines per contour level.
4. Reuse field-style axis limits and tick logic.
5. Render contours as vector `Polyline` primitives.

#### Tests

- gaussian hill
- sloped plane
- multi-peak synthetic field
- flat/plateau edge cases
- stable output for explicit level lists

### Phase B: Value-Scaled Styling

#### Target Features

- color scaled to contour level
- width scaled to contour level

#### Proposed Extension

```python
ax.contour(
    grid,
    levels=10,
    color=None,
    cmap=None,
    width=0.9,          # scalar or later a range
    alpha=1.0,
)
```

Possible follow-up extension:

```python
ax.contour(..., width=(0.5, 2.0))
```

#### Implementation Steps

1. Map each contour level to a normalized scalar.
2. Sample color from `cmap` when `cmap` is provided.
3. Interpolate line width when a width range is supported.
4. Define stable render ordering across contour levels.

### Phase C: Filled Contours With Opacity

#### Goal

Provide `contourf()` for semi-transparent filled contour bands.

#### Supported First-Version Features

- explicit or automatic levels
- colormap fill by band
- global alpha

#### Implementation Steps

1. Add `Panel.contourf(...)`.
2. Build polygons or band regions between levels.
3. Render filled bands beneath contour lines.
4. Validate SVG and PDF export behavior with opacity.

#### Notes

- `contourf()` should remain separate from `contour()`
- overlay use should be straightforward:

```python
ax.contourf(grid, levels=12, cmap="batlow", alpha=0.55)
ax.contour(grid, levels=12, color="#222222", width=0.7)
```

## Recommended Delivery Order

1. `colorbar(..., histogram_scale="log")`
2. `contour()` with levels, unique color, unique width
3. `contour()` with colormap-driven color by level
4. `contour()` with width scaled by level
5. `contourf()` with opacity
6. optional contour-linked colorbar support

## API Decisions To Freeze Before Implementation

- whether fallback Python must support every new option immediately
- whether contour width scaling is needed in v1 or can wait for v2
- whether contour handles should produce a `PlotHandle` for future colorbar integration
- whether log histogram mode should be visually annotated in the exported figure

## Recommended First Cut

The most pragmatic first implementation is:

```python
ax.colorbar(handle, histogram_scale="log")
ax.contour(grid, levels=10, color=None, cmap=None, width=0.9, alpha=1.0)
ax.contourf(grid, levels=10, cmap="batlow", alpha=0.6)
```

This delivers the main capability with limited API growth and leaves width-scaling and richer contour metadata for a second pass.
