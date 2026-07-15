from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from math import exp, floor, log10, pi, sqrt
from pathlib import Path
from typing import Iterable


DPI = 72.0
FONT_FAMILY_DEFAULT = '"IBM Plex Sans", "Source Sans 3", Arial, sans-serif'
FIELD_LIMIT = 300_000
COLORBAR_HISTOGRAM_LEVELS = 32
TIMESERIES_WIDTH_IN = 9.5


def figure(
    width: str = "single",
    height: float = 4.0,
    grid: tuple[int, int] = (1, 1),
    panel_labels: bool = False,
    font: str | None = None,
    theme: str = "publication",
    layout: str = "standard",
) -> "Figure":
    width_map = {"single": 3.4, "double": 7.0}
    layout_mode = _parse_layout_mode(layout)
    if layout_mode == "standard" and width not in width_map:
        raise ValueError(f"unsupported width preset '{width}'; use 'single' or 'double'")
    rows, cols = grid
    if rows <= 0 or cols <= 0:
        raise ValueError("grid dimensions must be positive")
    scene = FigureScene(
        width_in=width_map[width] if layout_mode == "standard" else TIMESERIES_WIDTH_IN,
        height_in=height,
        rows=rows,
        cols=cols,
        layout_mode=layout_mode,
        panel_labels=panel_labels,
        font_family=_normalize_font_family(font or FONT_FAMILY_DEFAULT),
        theme=Theme.parse(theme),
        panels=[PanelScene(row=r, col=c, axis=AxisScene()) for r in range(rows) for c in range(cols)],
    )
    return Figure(scene)


class Figure:
    def __init__(self, scene: "FigureScene") -> None:
        self._scene = scene

    def panel(self, row: int, col: int) -> "Panel":
        self._scene.panel(row, col)
        return Panel(self._scene, row, col)

    def save(self, path: str) -> None:
        self._scene.save(path)


class Panel:
    def __init__(self, scene: "FigureScene", row: int, col: int) -> None:
        self._scene = scene
        self.row = row
        self.col = col

    def xlabel(self, label: str) -> None:
        self._scene.panel(self.row, self.col).axis.x_label = label

    def ylabel(self, label: str) -> None:
        self._scene.panel(self.row, self.col).axis.y_label = label

    def right_ylabel(self, label: str) -> None:
        self._scene.panel(self.row, self.col).axis.right_y_label = label

    def limits(self, x: tuple[float, float] | None = None, y: tuple[float, float] | None = None) -> None:
        axis = self._scene.panel(self.row, self.col).axis
        axis.x_limits = x
        axis.y_limits = y

    def right_limits(self, y: tuple[float, float] | None = None) -> None:
        axis = self._scene.panel(self.row, self.col).axis
        axis.right_y_limits = y

    def xscale(self, scale: str) -> None:
        axis = self._scene.panel(self.row, self.col).axis
        axis.x_scale = _parse_scale(scale)

    def yscale(self, scale: str, axis: str = "left") -> None:
        scene_axis = self._scene.panel(self.row, self.col).axis
        resolved = _parse_scale(scale)
        side = _parse_y_axis_side(axis)
        if side == "left":
            scene_axis.y_scale = resolved
        else:
            scene_axis.right_y_scale = resolved

    def scatter(self, x, y, color=None, size: float = 6.0, alpha: float = 0.8, label: str | None = None, cmap: str | None = None, yaxis: str = "left") -> "PlotHandle":
        xs = _vec(x)
        ys = _vec(y)
        if len(xs) != len(ys):
            raise ValueError("x and y must have the same length")
        axis = self._scene.panel(self.row, self.col).axis
        y_axis = _parse_y_axis_side(yaxis)
        cmap_name = cmap or "batlow"
        default_color = self._scene.theme.right_axis if y_axis == "right" else self._scene.theme.scatter
        color_input = _parse_color_input(color, len(xs), cmap_name, default_color)
        if isinstance(color_input, list):
            cmin, cmax = min(color_input), max(color_input)
        else:
            cmin, cmax = 0.0, 1.0
        for i, (xv, yv) in enumerate(zip(xs, ys)):
            fill = _sample_colormap(cmap_name, _normalize(color_input[i], cmin, cmax)) if isinstance(color_input, list) else color_input
            axis.layers.append(
                Layer(
                    primitive=Marker(x=xv, y=yv, radius_pt=size / 2.0, style=Style(fill=fill, stroke=None, stroke_width_pt=0.0, opacity=alpha)),
                    z_index=20,
                    y_axis=y_axis,
                )
            )
        if label:
            axis.legend = axis.legend or Legend([])
            axis.legend.entries.append(LegendEntry(label=label, glyph="marker", color=default_color if isinstance(color_input, list) else fill))
        histogram = _histogram_bins(color_input, COLORBAR_HISTOGRAM_LEVELS) if isinstance(color_input, list) else None
        return PlotHandle(min=cmin, max=cmax, cmap=cmap_name, uses_alpha=alpha < 1.0, histogram=histogram)

    def line(self, x, y, color=None, width: float = 0.8, alpha: float = 1.0, label: str | None = None, yaxis: str = "left") -> None:
        xs = _vec(x)
        ys = _vec(y)
        if len(xs) != len(ys):
            raise ValueError("x and y must have the same length")
        y_axis = _parse_y_axis_side(yaxis)
        stroke = _parse_color_literal(color) if color else (self._scene.theme.right_axis if y_axis == "right" else self._scene.theme.line)
        if self._scene.layout_mode == "timeseries" and abs(width - 0.8) < 1e-9:
            width = 0.65
        axis = self._scene.panel(self.row, self.col).axis
        axis.layers.append(
            Layer(
                primitive=Polyline(points=list(zip(xs, ys)), style=Style(fill=None, stroke=stroke, stroke_width_pt=width, opacity=alpha)),
                z_index=30,
                y_axis=y_axis,
            )
        )
        if label:
            axis.legend = axis.legend or Legend([])
            axis.legend.entries.append(LegendEntry(label=label, glyph="line", color=stroke))

    def errorbar(
        self,
        x,
        y,
        yerr=None,
        ymin=None,
        ymax=None,
        color=None,
        width: float = 0.8,
        cap: float = 4.0,
        alpha: float = 0.7,
        yaxis: str = "left",
    ) -> None:
        xs = _vec(x)
        ys = _vec(y)
        if len(xs) != len(ys):
            raise ValueError("x and y must have the same length")
        if ymin is None and ymax is None and yerr is None:
            raise ValueError("provide yerr or ymin/ymax for errorbar")
        lower = _vec(ymin) if ymin is not None else [y - err for y, err in zip(ys, _vec(yerr))]
        upper = _vec(ymax) if ymax is not None else [y + err for y, err in zip(ys, _vec(yerr))]
        if len(lower) != len(ys):
            raise ValueError("ymin must have the same length as y")
        if len(upper) != len(ys):
            raise ValueError("ymax must have the same length as y")
        y_axis = _parse_y_axis_side(yaxis)
        stroke = _parse_color_literal(color) if color else (self._scene.theme.right_axis if y_axis == "right" else self._scene.theme.line)
        axis = self._scene.panel(self.row, self.col).axis
        span = max(xs) - min(xs) if len(xs) > 1 else 1.0
        cap_half = abs(span) * (cap / 400.0) if span else 0.1
        for xv, low, high in zip(xs, lower, upper):
            axis.layers.append(Layer(primitive=Polyline(points=[(xv, low), (xv, high)], style=Style(fill=None, stroke=stroke, stroke_width_pt=width, opacity=alpha)), z_index=24, y_axis=y_axis))
            axis.layers.append(Layer(primitive=Polyline(points=[(xv - cap_half, low), (xv + cap_half, low)], style=Style(fill=None, stroke=stroke, stroke_width_pt=width, opacity=alpha)), z_index=24, y_axis=y_axis))
            axis.layers.append(Layer(primitive=Polyline(points=[(xv - cap_half, high), (xv + cap_half, high)], style=Style(fill=None, stroke=stroke, stroke_width_pt=width, opacity=alpha)), z_index=24, y_axis=y_axis))

    def legend(self) -> None:
        axis = self._scene.panel(self.row, self.col).axis
        axis.legend = axis.legend or Legend([])

    def bar(
        self,
        labels: list[str],
        values,
        yaxis: str = "left",
        color=None,
        alpha: float = 1.0,
        show_x_axis: bool = False,
    ) -> None:
        ys = _vec(values)
        if len(labels) != len(ys):
            raise ValueError("labels and values must have the same length")
        axis = self._scene.panel(self.row, self.col).axis
        y_axis = _parse_y_axis_side(yaxis)
        axis.x_categories = list(labels)
        axis.hide_x_axis = not show_x_axis
        fill = _parse_color_literal(color) if color else (self._scene.theme.right_axis if y_axis == "right" else self._scene.theme.bar)
        for i, value in enumerate(ys):
            axis.layers.append(
                Layer(
                    primitive=Rect(x=i - 0.35, y=0.0, w=0.7, h=value, style=Style(fill=fill, stroke=None, stroke_width_pt=0.0, opacity=alpha)),
                    z_index=10,
                    y_axis=y_axis,
                )
            )
        axis.x_limits = (-0.5, len(ys) - 0.5)

    def histogram(
        self,
        data,
        bins: int = 12,
        range: tuple[float, float] | None = None,
        density: bool = False,
        color=None,
        alpha: float = 1.0,
        label: str | None = None,
        yaxis: str = "left",
    ) -> None:
        values = _vec(data)
        if not values:
            raise ValueError("histogram data must be non-empty")
        if bins <= 0:
            raise ValueError("histogram bins must be positive")
        y_axis = _parse_y_axis_side(yaxis)
        fill = _parse_color_literal(color) if color else (self._scene.theme.right_axis if y_axis == "right" else self._scene.theme.bar)
        stroke = self._scene.theme.right_axis if y_axis == "right" else self._scene.theme.axis
        rects, xmin, xmax, ymax = _histogram_rects(values, bins, range, density)
        axis = self._scene.panel(self.row, self.col).axis
        axis.x_categories = None
        axis.hide_x_axis = False
        for left, right, height in rects:
            axis.layers.append(
                Layer(
                    primitive=Rect(
                        x=left,
                        y=0.0,
                        w=right - left,
                        h=height,
                        style=Style(fill=fill, stroke=stroke, stroke_width_pt=0.35, opacity=alpha),
                    ),
                    z_index=10,
                    y_axis=y_axis,
                )
            )
        axis.x_limits = (xmin, xmax)
        if y_axis == "left":
            axis.y_limits = (0.0, max(ymax, 1e-12))
        else:
            axis.right_y_limits = (0.0, max(ymax, 1e-12))
        if label:
            axis.legend = axis.legend or Legend([])
            axis.legend.entries.append(LegendEntry(label=label, glyph="marker", color=fill))

    def field(self, grid, cmap: str | None = None, cell_edges: bool = False, render: str = "auto") -> "PlotHandle":
        values = _matrix(grid)
        rows = len(values)
        cols = len(values[0]) if rows else 0
        if rows == 0 or cols == 0:
            raise ValueError("field grid must be non-empty")
        if rows * cols > FIELD_LIMIT:
            raise ValueError(f"field grid too large for vector backend prototype: {rows * cols} cells > {FIELD_LIMIT}")
        if render not in {"auto", "grid", "embedded"}:
            raise ValueError(f"unsupported field render mode '{render}'; use 'auto', 'grid', or 'embedded'")
        cmap_name = cmap or "batlow"
        vmin = min(min(row) for row in values)
        vmax = max(max(row) for row in values)
        axis = self._scene.panel(self.row, self.col).axis
        overlap = 0.015
        for r, row in enumerate(values):
            for c, value in enumerate(row):
                axis.layers.append(
                    Layer(
                        primitive=Rect(
                            x=float(c) - (overlap if not cell_edges else 0.0),
                            y=float(rows - 1 - r) - (overlap if not cell_edges else 0.0),
                            w=1.0 + (2.0 * overlap if not cell_edges else 0.0),
                            h=1.0 + (2.0 * overlap if not cell_edges else 0.0),
                            style=Style(
                                fill=_sample_colormap(cmap_name, _normalize(value, vmin, vmax)),
                                stroke=self._scene.theme.axis if cell_edges else None,
                                stroke_width_pt=0.2 if cell_edges else 0.0,
                                opacity=1.0,
                            ),
                        ),
                        z_index=5,
                        y_axis="left",
                    )
                )
        axis.x_limits = (0.0, float(cols))
        axis.y_limits = (0.0, float(rows))
        axis.x_tick_values = _field_ticks(cols)
        axis.y_tick_values = _field_ticks(rows)
        flat = [value for row in values for value in row]
        return PlotHandle(min=vmin, max=vmax, cmap=cmap_name, uses_alpha=False, histogram=_histogram_bins(flat, COLORBAR_HISTOGRAM_LEVELS))

    def colorbar(self, handle: "PlotHandle", label: str | None = None, placement: str | None = None, style: str | None = None) -> None:
        place = placement or "right"
        if place not in {"right", "inside-left"}:
            raise ValueError(f"unsupported colorbar placement '{place}'; use 'right' or 'inside-left'")
        bar_style = style or "binned"
        if bar_style not in {"continuous", "binned"}:
            raise ValueError(f"unsupported colorbar style '{bar_style}'; use 'continuous' or 'binned'")
        axis = self._scene.panel(self.row, self.col).axis
        axis.colorbars.append(Colorbar(min=handle.min, max=handle.max, cmap=handle.cmap, label=label, placement=place, style=bar_style, histogram=handle.histogram))

    def violin(
        self,
        data,
        labels: list[str] | None = None,
        show_median: bool = False,
        points: bool = False,
        point_color=None,
        point_size: float = 4.0,
        point_alpha: float = 0.75,
        point_cmap: str | None = None,
    ) -> "PlotHandle | None":
        groups = [_vec(group) for group in data]
        if labels is not None and len(labels) != len(groups):
            raise ValueError("labels length must match violin group count")
        axis = self._scene.panel(self.row, self.col).axis
        axis.x_categories = labels or [str(i + 1) for i in range(len(groups))]
        axis.hide_x_axis = True
        fill = self._scene.theme.violin_fill
        stroke = self._scene.theme.violin_stroke
        color_input = _parse_grouped_color_input(point_color, groups, point_cmap or "batlow", self._scene.theme.scatter) if points else None
        offset = 0
        for i, group in enumerate(groups):
            ymin, ymax = min(group), max(group)
            bw = _estimate_bandwidth(group)
            samples = 60
            density = []
            peak = 0.0
            for s in range(samples):
                y = _lerp(ymin, ymax, s / (samples - 1))
                d = _kde(group, y, bw)
                peak = max(peak, d)
                density.append((y, d))
            points = []
            for y, d in density:
                half = 0.0 if peak == 0.0 else 0.35 * d / peak
                points.append((i - half, y))
            for y, d in reversed(density):
                half = 0.0 if peak == 0.0 else 0.35 * d / peak
                points.append((i + half, y))
            axis.layers.append(Layer(primitive=Polygon(points=points, style=Style(fill=fill, stroke=stroke, stroke_width_pt=0.9, opacity=0.95)), z_index=15))
            if color_input is not None:
                point_fills = _mapped_group_colors(color_input, offset, len(group), point_cmap or "batlow")
                for idx, value in enumerate(group):
                    axis.layers.append(
                        Layer(
                            primitive=Marker(
                                x=i + _violin_point_offset(idx, len(group), 0.26),
                                y=value,
                                radius_pt=point_size / 2.0,
                                style=Style(fill=point_fills[idx], stroke=None, stroke_width_pt=0.0, opacity=point_alpha),
                            ),
                            z_index=22,
                            y_axis="left",
                        )
                    )
            if show_median:
                med = _quantile(group, 0.5)
                axis.layers.append(
                    Layer(
                        primitive=Polyline(points=[(i - 0.18, med), (i + 0.18, med)], style=Style(fill=None, stroke=stroke, stroke_width_pt=1.0, opacity=1.0)),
                        z_index=25,
                        y_axis="left",
                    )
                )
            offset += len(group)
        axis.x_limits = (-0.5, len(groups) - 0.5)
        if isinstance(color_input, list):
            return PlotHandle(
                min=min(color_input),
                max=max(color_input),
                cmap=point_cmap or "batlow",
                uses_alpha=point_alpha < 1.0,
                histogram=_histogram_bins(color_input, COLORBAR_HISTOGRAM_LEVELS),
            )
        return None

    def box(self, data, labels: list[str] | None = None) -> None:
        groups = [_vec(group) for group in data]
        if labels is not None and len(labels) != len(groups):
            raise ValueError("labels length must match box group count")
        axis = self._scene.panel(self.row, self.col).axis
        axis.x_categories = labels or [str(i + 1) for i in range(len(groups))]
        axis.hide_x_axis = False
        fill = self._scene.theme.box_fill
        stroke = self._scene.theme.box_stroke
        for i, group in enumerate(groups):
            q1 = _quantile(group, 0.25)
            med = _quantile(group, 0.5)
            q3 = _quantile(group, 0.75)
            iqr = q3 - q1
            lower = min(v for v in group if v >= q1 - 1.5 * iqr)
            upper = max(v for v in group if v <= q3 + 1.5 * iqr)
            axis.layers.append(Layer(primitive=Rect(x=i - 0.25, y=q1, w=0.5, h=q3 - q1, style=Style(fill=fill, stroke=stroke, stroke_width_pt=0.9, opacity=1.0)), z_index=15, y_axis="left"))
            axis.layers.append(Layer(primitive=Polyline(points=[(i - 0.25, med), (i + 0.25, med)], style=Style(fill=None, stroke=stroke, stroke_width_pt=1.0, opacity=1.0)), z_index=25, y_axis="left"))
            axis.layers.append(Layer(primitive=Polyline(points=[(i, lower), (i, q1)], style=Style(fill=None, stroke=stroke, stroke_width_pt=0.8, opacity=1.0)), z_index=20, y_axis="left"))
            axis.layers.append(Layer(primitive=Polyline(points=[(i, q3), (i, upper)], style=Style(fill=None, stroke=stroke, stroke_width_pt=0.8, opacity=1.0)), z_index=20, y_axis="left"))
            axis.layers.append(Layer(primitive=Polyline(points=[(i - 0.14, lower), (i + 0.14, lower)], style=Style(fill=None, stroke=stroke, stroke_width_pt=0.8, opacity=1.0)), z_index=20, y_axis="left"))
            axis.layers.append(Layer(primitive=Polyline(points=[(i - 0.14, upper), (i + 0.14, upper)], style=Style(fill=None, stroke=stroke, stroke_width_pt=0.8, opacity=1.0)), z_index=20, y_axis="left"))
        axis.x_limits = (-0.5, len(groups) - 0.5)


@dataclass
class PlotHandle:
    min: float
    max: float
    cmap: str
    uses_alpha: bool
    histogram: list[float] | None = None


@dataclass
class FigureScene:
    width_in: float
    height_in: float
    rows: int
    cols: int
    layout_mode: str
    panel_labels: bool
    font_family: str
    theme: "Theme"
    panels: list["PanelScene"]
    warnings: list[str] = field(default_factory=list)

    def panel(self, row: int, col: int) -> "PanelScene":
        if row >= self.rows or col >= self.cols:
            raise ValueError(f"panel index ({row}, {col}) out of bounds for grid {self.rows}x{self.cols}")
        return self.panels[row * self.cols + col]

    def save(self, path: str) -> None:
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        if out.suffix == ".svg":
            out.write_text(self.to_svg(), encoding="utf-8")
        elif out.suffix == ".html":
            out.write_text(self.to_html(), encoding="utf-8")
        elif out.suffix == ".pdf":
            raise RuntimeError("PDF backend is not implemented yet. This prototype only exports SVG and HTML.")
        else:
            raise ValueError("unsupported export format; use .svg or .html in this prototype")

    def to_html(self) -> str:
        svg = self.to_svg()
        return f'<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>cleanfig</title><style>body{{margin:0;padding:24px;background:{self.theme.background.to_hex()};}}figure{{margin:0;display:flex;justify-content:center;}}</style></head><body><figure>{svg}</figure></body></html>'

    def to_svg(self) -> str:
        layouts = _figure_layout(self.width_in, self.height_in, self.rows, self.cols, self.layout_mode)
        min_x, min_y, max_x, max_y = _figure_bounds(self, layouts)
        pad = 4.0
        width_pt = max(max_x - min_x + pad * 2.0, 1.0)
        height_pt = max(max_y - min_y + pad * 2.0, 1.0)
        tx = pad - min_x
        ty = pad - min_y
        parts = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width_pt:.2f}pt" height="{height_pt:.2f}pt" viewBox="0 0 {width_pt:.2f} {height_pt:.2f}" role="img" aria-label="cleanfig figure">',
            f'<style>.cf-text{{font-family:{_xml(self.font_family)};fill:{self.theme.text.to_hex()};font-weight:400;}} .cf-axis{{stroke:{self.theme.axis.to_hex()};stroke-width:0.55;fill:none;stroke-linecap:square;}} .cf-tick{{stroke:{self.theme.tick.to_hex()};stroke-width:0.45;}} .cf-label{{font-size:8.6px;font-weight:400;}} .cf-ticklabel{{font-size:7.2px;font-weight:400;fill:{self.theme.tick_label.to_hex()};}} .cf-panel{{font-size:11.2px;font-weight:700;}} .cf-cbarlabel{{font-size:7.8px;font-weight:400;}} .cf-legendtext{{font-size:7.2px;font-weight:400;fill:{self.theme.tick_label.to_hex()};}}</style>',
            f'<rect x="0" y="0" width="{width_pt:.2f}" height="{height_pt:.2f}" fill="{self.theme.background.to_hex()}" />',
            f'<g transform="translate({tx:.2f},{ty:.2f})">',
        ]
        for panel in self.panels:
            parts.append(_render_panel(self, panel, layouts[panel.row * self.cols + panel.col]))
        parts.append("</g>")
        parts.append("</svg>")
        return "".join(parts)


@dataclass
class PanelScene:
    row: int
    col: int
    axis: "AxisScene"


@dataclass
class AxisScene:
    x_label: str | None = None
    y_label: str | None = None
    right_y_label: str | None = None
    x_limits: tuple[float, float] | None = None
    y_limits: tuple[float, float] | None = None
    right_y_limits: tuple[float, float] | None = None
    x_scale: str = "linear"
    y_scale: str = "linear"
    right_y_scale: str = "linear"
    layers: list["Layer"] = field(default_factory=list)
    legend: "Legend | None" = None
    colorbars: list["Colorbar"] = field(default_factory=list)
    x_categories: list[str] | None = None
    hide_x_axis: bool = False
    x_tick_values: list[float] | None = None
    y_tick_values: list[float] | None = None

    def resolved_limits(self) -> tuple[tuple[float, float], tuple[float, float], tuple[float, float] | None]:
        x_bounds = _bounds(self.layers)
        left_bounds = _bounds(self.layers, y_axis="left")
        right_bounds = _bounds(self.layers, y_axis="right")
        base_bounds = x_bounds or (0.0, 1.0, 0.0, 1.0)
        xr = self.x_limits or _expand_for_scale(base_bounds[0], base_bounds[1], self.x_scale)
        yr = self.y_limits or _expand_for_scale(*(left_bounds[2:4] if left_bounds else base_bounds[2:4]), self.y_scale)
        right = self.right_y_limits or (_expand_for_scale(right_bounds[2], right_bounds[3], self.right_y_scale) if right_bounds else None)
        _validate_scale_limits(xr, self.x_scale, "x")
        _validate_scale_limits(yr, self.y_scale, "left y")
        if right is not None:
            _validate_scale_limits(right, self.right_y_scale, "right y")
        return xr, yr, right


@dataclass
class Layer:
    primitive: object
    z_index: int
    y_axis: str = "left"


@dataclass
class Style:
    fill: "Color | None"
    stroke: "Color | None"
    stroke_width_pt: float
    opacity: float


@dataclass
class Color:
    r: int
    g: int
    b: int

    def to_hex(self) -> str:
        return f"#{self.r:02x}{self.g:02x}{self.b:02x}"


@dataclass(frozen=True)
class Theme:
    name: str
    background: Color
    text: Color
    axis: Color
    tick: Color
    tick_label: Color
    scatter: Color
    line: Color
    bar: Color
    violin_fill: Color
    violin_stroke: Color
    box_fill: Color
    box_stroke: Color
    right_axis: Color

    @staticmethod
    def parse(name: str) -> "Theme":
        themes = {
            "publication": Theme(
                "publication",
                Color(255, 255, 255),
                Color(25, 28, 32),
                Color(101, 109, 118),
                Color(112, 120, 129),
                Color(73, 79, 87),
                Color(59, 102, 140),
                Color(33, 37, 42),
                Color(156, 182, 205),
                Color(214, 226, 236),
                Color(90, 118, 145),
                Color(228, 236, 243),
                Color(84, 102, 120),
                Color(178, 56, 42),
            ),
            "dark": Theme(
                "dark",
                Color(17, 23, 31),
                Color(231, 237, 243),
                Color(128, 145, 166),
                Color(109, 124, 143),
                Color(173, 186, 199),
                Color(124, 169, 214),
                Color(233, 238, 244),
                Color(92, 134, 171),
                Color(70, 97, 123),
                Color(188, 209, 229),
                Color(76, 92, 108),
                Color(201, 214, 227),
                Color(236, 116, 101),
            ),
        }
        aliases = {"light": "publication", "nature": "publication"}
        resolved = aliases.get(name, name)
        if resolved not in themes:
            raise ValueError(f"unsupported theme '{name}'; use 'publication', 'nature', 'light', or 'dark'")
        return themes[resolved]


@dataclass
class Polyline:
    points: list[tuple[float, float]]
    style: Style


@dataclass
class Marker:
    x: float
    y: float
    radius_pt: float
    style: Style


@dataclass
class Rect:
    x: float
    y: float
    w: float
    h: float
    style: Style


@dataclass
class Polygon:
    points: list[tuple[float, float]]
    style: Style


@dataclass
class LegendEntry:
    label: str
    glyph: str
    color: Color


@dataclass
class Legend:
    entries: list[LegendEntry]


@dataclass
class Colorbar:
    min: float
    max: float
    cmap: str
    label: str | None
    placement: str
    style: str
    histogram: list[float] | None = None


def _render_panel(fig: FigureScene, panel: PanelScene, layout: tuple[float, float, float, float]) -> str:
    left, top, width, height = layout
    render_axis = _panel_axis_for_render(fig, panel)
    footer_height = _footer_height(render_axis) if fig.layout_mode == "timeseries" else _max_footer_height(fig)
    axis = _axis_layout(layout, footer_height, fig.layout_mode)
    parts = [f'<g data-panel="{panel.row}-{panel.col}">']
    if fig.panel_labels:
        letter = chr(ord("A") + panel.row * fig.cols + panel.col)
        parts.append(f'<text class="cf-text cf-panel" x="{axis[4] - 22.0:.2f}" y="{axis[5] - 10.0:.2f}">{letter}</text>')
    parts.append(_render_axis(fig.theme, render_axis, axis))
    if _timeseries_uses_shared_right_legend(fig) and panel.col == 0 and panel.row == fig.rows // 2:
        legend = _timeseries_shared_legend(fig)
        if legend is not None:
            parts.append(_render_legend_right(legend, axis))
    parts.append("</g>")
    return "".join(parts)


def _panel_axis_for_render(fig: FigureScene, panel: PanelScene) -> AxisScene:
    axis = deepcopy(panel.axis)
    if fig.layout_mode == "timeseries":
        if panel.row + 1 < fig.rows:
            axis.hide_x_axis = True
            axis.x_label = None
        axis.x_limits = _timeseries_shared_x_limits(fig, panel.col, axis)
        if _timeseries_uses_shared_right_legend(fig):
            axis.legend = None
    return axis


def _timeseries_shared_x_limits(fig: FigureScene, col: int, axis: AxisScene) -> tuple[float, float]:
    min_x = float("inf")
    max_x = float("-inf")
    for panel in fig.panels:
        if panel.col != col:
            continue
        if panel.axis.x_limits is not None:
            xmin, xmax = panel.axis.x_limits
        else:
            bounds = _bounds(panel.axis.layers)
            if bounds is None:
                continue
            xmin, xmax = bounds[0], bounds[1]
        min_x = min(min_x, xmin)
        max_x = max(max_x, xmax)
    if min_x != float("inf") and max_x != float("-inf"):
        if axis.x_scale == "linear":
            return min_x, max_x
        return _expand_for_scale(min_x, max_x, axis.x_scale)
    return axis.resolved_limits()[0]


def _timeseries_uses_shared_right_legend(fig: FigureScene) -> bool:
    return fig.layout_mode == "timeseries" and fig.cols == 1 and fig.rows == 3


def _timeseries_shared_legend(fig: FigureScene) -> Legend | None:
    if not _timeseries_uses_shared_right_legend(fig):
        return None
    for panel in fig.panels:
        if panel.axis.legend and panel.axis.legend.entries:
            return deepcopy(panel.axis.legend)
    return None


def _render_axis(theme: Theme, axis: AxisScene, layout: tuple[float, float, float, float]) -> str:
    panel_left, panel_top, panel_width, panel_height, x, y, width, height = layout
    (xmin, xmax), (ymin, ymax), right_limits = axis.resolved_limits()
    x_is_datetime = _x_axis_looks_datetime(axis, xmin, xmax)
    parts = []
    right_color = theme.right_axis.to_hex()
    axis_gap = 0.0 if axis.hide_x_axis else 4.0
    if not axis.hide_x_axis:
        parts.append(f'<line class="cf-axis" x1="{x + axis_gap:.2f}" y1="{y + height:.2f}" x2="{x + width:.2f}" y2="{y + height:.2f}" />')
    parts.append(f'<line class="cf-axis" x1="{x:.2f}" y1="{y:.2f}" x2="{x:.2f}" y2="{y + height - axis_gap:.2f}" />')
    has_right_axis = right_limits is not None or axis.right_y_label is not None or any(layer.y_axis == "right" for layer in axis.layers)
    if has_right_axis:
        parts.append(f'<line class="cf-axis" x1="{x + width:.2f}" y1="{y:.2f}" x2="{x + width:.2f}" y2="{y + height - axis_gap:.2f}" stroke="{right_color}" />')
    x_ticks = [] if axis.x_categories else (axis.x_tick_values or (_datetime_ticks(xmin, xmax, _datetime_tick_target(width)) if x_is_datetime and axis.x_scale == "linear" else _nice_ticks_for_scale(xmin, xmax, axis.x_scale, 5)))
    y_ticks = axis.y_tick_values or _nice_ticks_for_scale(ymin, ymax, axis.y_scale, 5)
    if not axis.hide_x_axis:
        for tick in x_ticks:
            sx = _map_x(tick, xmin, xmax, x, width, axis.x_scale)
            parts.append(f'<line class="cf-tick" x1="{sx:.2f}" y1="{y + height:.2f}" x2="{sx:.2f}" y2="{y + height + 4.5:.2f}" />')
            parts.append(f'<text class="cf-text cf-ticklabel" text-anchor="middle" x="{sx:.2f}" y="{y + height + 13.5:.2f}">{_svg_rich_text(_fmt_x_tick(tick, axis.x_scale, x_is_datetime))}</text>')
    if axis.x_categories:
        for idx, label in enumerate(axis.x_categories):
            sx = _map_x(float(idx), xmin, xmax, x, width, axis.x_scale)
            parts.append(f'<text class="cf-text cf-ticklabel" text-anchor="middle" x="{sx:.2f}" y="{y + height + 13.5:.2f}">{_svg_rich_text(label)}</text>')
    for tick in y_ticks:
        sy = _map_y(tick, ymin, ymax, y, height, axis.y_scale)
        parts.append(f'<line class="cf-tick" x1="{x - 4.5:.2f}" y1="{sy:.2f}" x2="{x:.2f}" y2="{sy:.2f}" />')
        parts.append(f'<text class="cf-text cf-ticklabel" text-anchor="end" x="{x - 7.5:.2f}" y="{sy + 2.8:.2f}">{_svg_rich_text(_fmt_tick(tick, axis.y_scale))}</text>')
    if has_right_axis:
        right_min, right_max = right_limits or (ymin, ymax)
        for tick in _nice_ticks_for_scale(right_min, right_max, axis.right_y_scale, 5):
            sy = _map_y(tick, right_min, right_max, y, height, axis.right_y_scale)
            parts.append(f'<line class="cf-tick" x1="{x + width:.2f}" y1="{sy:.2f}" x2="{x + width + 4.5:.2f}" y2="{sy:.2f}" stroke="{right_color}" />')
            parts.append(f'<text class="cf-text cf-ticklabel" text-anchor="start" x="{x + width + 7.5:.2f}" y="{sy + 2.8:.2f}" fill="{right_color}">{_svg_rich_text(_fmt_tick(tick, axis.right_y_scale))}</text>')
    for layer in sorted(axis.layers, key=lambda item: item.z_index):
        layer_limits = (right_limits if layer.y_axis == "right" else (ymin, ymax)) or (ymin, ymax)
        layer_scale = axis.right_y_scale if layer.y_axis == "right" else axis.y_scale
        parts.append(_render_primitive(layer.primitive, x, y, width, height, xmin, xmax, layer_limits[0], layer_limits[1], axis.x_scale, layer_scale))
    if axis.x_label:
        parts.append(f'<text class="cf-text cf-label" text-anchor="middle" x="{x + width / 2.0:.2f}" y="{y + height + 26.5:.2f}">{_svg_rich_text(axis.x_label)}</text>')
    if axis.y_label:
        parts.append(f'<text class="cf-text cf-label" text-anchor="middle" transform="translate({x - 27.0:.2f},{y + height / 2.0:.2f}) rotate(-90)">{_svg_rich_text(axis.y_label)}</text>')
    if axis.right_y_label:
        parts.append(f'<text class="cf-text cf-label" text-anchor="middle" fill="{right_color}" transform="translate({x + width + 29.0:.2f},{y + height / 2.0:.2f}) rotate(90)">{_svg_rich_text(axis.right_y_label)}</text>')
    footer_top = y + height + 31.0
    if axis.legend and axis.legend.entries:
        parts.append(_render_legend(axis.legend, x, footer_top))
    offset_y = footer_top + _legend_height(axis)
    for colorbar in axis.colorbars:
        parts.append(_render_colorbar(colorbar, x, width, offset_y))
        offset_y += _colorbar_footer_height(axis)
    return "".join(parts)


def _render_primitive(primitive, x: float, y: float, width: float, height: float, xmin: float, xmax: float, ymin: float, ymax: float, x_scale: str, y_scale: str) -> str:
    if isinstance(primitive, Polyline):
        d = " ".join(
            f'{"M" if i == 0 else "L"} {_map_x(px, xmin, xmax, x, width, x_scale):.2f} {_map_y(py, ymin, ymax, y, height, y_scale):.2f}'
            for i, (px, py) in enumerate(primitive.points)
        )
        return f'<path d="{d}" {_svg_style(primitive.style)} />'
    if isinstance(primitive, Marker):
        return f'<circle cx="{_map_x(primitive.x, xmin, xmax, x, width, x_scale):.2f}" cy="{_map_y(primitive.y, ymin, ymax, y, height, y_scale):.2f}" r="{primitive.radius_pt:.2f}" {_svg_style(primitive.style)} />'
    if isinstance(primitive, Rect):
        x0 = _map_x(primitive.x, xmin, xmax, x, width, x_scale)
        x1 = _map_x(primitive.x + primitive.w, xmin, xmax, x, width, x_scale)
        y0 = _map_y(primitive.y, ymin, ymax, y, height, y_scale)
        y1 = _map_y(primitive.y + primitive.h, ymin, ymax, y, height, y_scale)
        left = min(x0, x1)
        top = min(y0, y1)
        return f'<rect x="{left:.4f}" y="{top:.4f}" width="{abs(x1 - x0):.4f}" height="{abs(y1 - y0):.4f}" shape-rendering="crispEdges" {_svg_style(primitive.style)} />'
    if isinstance(primitive, Polygon):
        pts = " ".join(f"{_map_x(px, xmin, xmax, x, width, x_scale):.2f},{_map_y(py, ymin, ymax, y, height, y_scale):.2f}" for px, py in primitive.points)
        return f'<polygon points="{pts}" {_svg_style(primitive.style)} />'
    raise TypeError("unknown primitive")


def _render_legend(legend: Legend, x: float, top: float) -> str:
    parts = []
    left = x
    cy = top + 9.0
    for entry in legend.entries:
        if entry.glyph == "line":
            parts.append(f'<line x1="{left:.2f}" y1="{cy:.2f}" x2="{left + 10.0:.2f}" y2="{cy:.2f}" stroke="{entry.color.to_hex()}" stroke-width="1.2" />')
        elif entry.glyph == "marker":
            parts.append(f'<circle cx="{left + 5.0:.2f}" cy="{cy:.2f}" r="2.6" fill="{entry.color.to_hex()}" />')
        else:
            parts.append(f'<rect x="{left + 1.0:.2f}" y="{cy - 3.0:.2f}" width="9" height="6" fill="{entry.color.to_hex()}" />')
        parts.append(f'<text class="cf-text cf-legendtext" x="{left + 13.0:.2f}" y="{cy + 2.6:.2f}">{_svg_rich_text(entry.label)}</text>')
        cy += 10.0
    return "".join(parts)


def _render_legend_right(legend: Legend, layout: tuple[float, float, float, float, float, float, float, float]) -> str:
    _, _, _, _, x0, y0, width, height = layout
    parts = []
    left = x0 + width + 22.0
    cy = y0 + (height - _legend_height_from_count(len(legend.entries))) * 0.5 + 9.0
    for entry in legend.entries:
        if entry.glyph == "line":
            parts.append(f'<line x1="{left:.2f}" y1="{cy:.2f}" x2="{left + 10.0:.2f}" y2="{cy:.2f}" stroke="{entry.color.to_hex()}" stroke-width="1.2" />')
        elif entry.glyph == "marker":
            parts.append(f'<circle cx="{left + 5.0:.2f}" cy="{cy:.2f}" r="2.6" fill="{entry.color.to_hex()}" />')
        else:
            parts.append(f'<rect x="{left + 1.0:.2f}" y="{cy - 3.0:.2f}" width="9" height="6" fill="{entry.color.to_hex()}" />')
        parts.append(f'<text class="cf-text cf-legendtext" x="{left + 13.0:.2f}" y="{cy + 2.6:.2f}">{_svg_rich_text(entry.label)}</text>')
        cy += 10.0
    return "".join(parts)


def _render_colorbar(colorbar: Colorbar, x: float, width: float, top: float) -> str:
    bar_w = min(width, 138.0)
    bar_h = 12.0
    bar_x = x + (width - bar_w) * 0.5 if colorbar.placement == "right" else x + 6.0
    bar_y = top + 12.0
    parts = []
    if colorbar.label:
        parts.append(f'<text class="cf-text cf-cbarlabel" text-anchor="middle" x="{bar_x + bar_w * 0.5:.2f}" y="{top + 7.5:.2f}">{_svg_rich_text(colorbar.label)}</text>')
    if colorbar.style == "binned" and colorbar.histogram:
        bins = max(len(colorbar.histogram), 1)
        bin_w = bar_w / bins
        max_value = max(max(colorbar.histogram), 1e-12)
        parts.append(f'<line class="cf-axis" x1="{bar_x:.2f}" y1="{bar_y + bar_h:.2f}" x2="{bar_x + bar_w:.2f}" y2="{bar_y + bar_h:.2f}" />')
        for i, value in enumerate(colorbar.histogram):
            x0 = bar_x + i * bin_w
            fill = _sample_colormap(colorbar.cmap, (i + 0.5) / bins)
            height = max(bar_h * max(0.0, min(1.0, value / max_value)), 0.8)
            y0 = bar_y + bar_h - height
            parts.append(f'<rect x="{x0:.2f}" y="{y0:.2f}" width="{max(bin_w - 0.4, 0.8):.2f}" height="{height:.2f}" fill="{fill.to_hex()}" stroke="none" opacity="0.95" />')
    else:
        grad_id = f"cf-grad-{int(bar_x * 10)}-{int(bar_y * 10)}-{colorbar.cmap}"
        stops = "".join(
            f'<stop offset="{100 * (i / 8):.0f}%" stop-color="{_sample_colormap(colorbar.cmap, i / 8).to_hex()}" />'
            for i in range(9)
        )
        parts.append(f'<defs><linearGradient id="{grad_id}" x1="0%" y1="0%" x2="100%" y2="0%">{stops}</linearGradient></defs>')
        parts.append(f'<rect x="{bar_x:.2f}" y="{bar_y:.2f}" width="{bar_w:.2f}" height="{bar_h:.2f}" rx="1.2" fill="url(#{grad_id})" stroke="{_sample_colormap(colorbar.cmap, 0.5).to_hex()}" stroke-width="0.35" />')
    for anchor, px, tick in [("start", bar_x, colorbar.min), ("middle", bar_x + bar_w * 0.5, 0.5 * (colorbar.min + colorbar.max)), ("end", bar_x + bar_w, colorbar.max)]:
        parts.append(f'<line class="cf-tick" x1="{px:.2f}" y1="{bar_y + bar_h:.2f}" x2="{px:.2f}" y2="{bar_y + bar_h + 3.5:.2f}" />')
        parts.append(f'<text class="cf-text cf-ticklabel" text-anchor="{anchor}" x="{px:.2f}" y="{bar_y + bar_h + 12.0:.2f}">{_svg_rich_text(_fmt(tick))}</text>')
    return "".join(parts)


def _bounds(layers: list[Layer], y_axis: str | None = None) -> tuple[float, float, float, float] | None:
    acc = None
    for layer in layers:
        if y_axis is not None and layer.y_axis != y_axis:
            continue
        item = layer.primitive
        if isinstance(item, (Polyline, Polygon)):
            xs = [p[0] for p in item.points]
            ys = [p[1] for p in item.points]
            cur = (min(xs), max(xs), min(ys), max(ys))
        elif isinstance(item, Marker):
            cur = (item.x, item.x, item.y, item.y)
        elif isinstance(item, Rect):
            cur = (min(item.x, item.x + item.w), max(item.x, item.x + item.w), min(item.y, item.y + item.h), max(item.y, item.y + item.h))
        else:
            continue
        if acc is None:
            acc = cur
        else:
            acc = (min(acc[0], cur[0]), max(acc[1], cur[1]), min(acc[2], cur[2]), max(acc[3], cur[3]))
    return acc


def _figure_layout(width_in: float, height_in: float, rows: int, cols: int, layout_mode: str) -> list[tuple[float, float, float, float]]:
    width = width_in * DPI
    height = height_in * DPI
    if layout_mode == "timeseries":
        margin_left = 20.0
        margin_right = 20.0
        margin_top = 16.0
        margin_bottom = 16.0
        gap_x = 18.0
        gap_y = 10.0
        panel_width = max((width - margin_left - margin_right - gap_x * max(cols - 1, 0)) / cols, 60.0)
        panel_height = max((height - margin_top - margin_bottom - gap_y * max(rows - 1, 0)) / rows, 56.0)
        return [
            (margin_left + c * (panel_width + gap_x), margin_top + r * (panel_height + gap_y), panel_width, panel_height)
            for r in range(rows)
            for c in range(cols)
        ]
    margin_left = 26.0
    margin_right = 22.0
    margin_top = 22.0
    margin_bottom = 22.0
    gap_x = 26.0
    gap_y = 22.0
    content_width = width - margin_left - margin_right
    content_height = height - margin_top - margin_bottom
    panel_size = min((content_width - gap_x * max(cols - 1, 0)) / cols, (content_height - gap_y * max(rows - 1, 0)) / rows)
    grid_width = panel_size * cols + gap_x * max(cols - 1, 0)
    grid_height = panel_size * rows + gap_y * max(rows - 1, 0)
    start_left = margin_left + max((content_width - grid_width) * 0.5, 0.0)
    start_top = margin_top + max((content_height - grid_height) * 0.5, 0.0)
    return [
        (start_left + c * (panel_size + gap_x), start_top + r * (panel_size + gap_y), panel_size, panel_size)
        for r in range(rows)
        for c in range(cols)
    ]


def _axis_layout(layout: tuple[float, float, float, float], footer_height: float, layout_mode: str) -> tuple[float, float, float, float, float, float, float, float]:
    panel_left, panel_top, panel_width, panel_height = layout
    if layout_mode == "timeseries":
        left_reserve = 52.0
        right_reserve = 14.0
        top_reserve = 10.0
        bottom_reserve = 34.0 + footer_height
    else:
        left_reserve = 40.0
        right_reserve = 16.0
        top_reserve = 22.0
        bottom_reserve = 34.0 + footer_height
    x = panel_left + left_reserve
    y = panel_top + top_reserve
    width = max(panel_width - left_reserve - right_reserve, 40.0)
    height = max(panel_height - top_reserve - bottom_reserve, 40.0)
    return panel_left, panel_top, panel_width, panel_height, x, y, width, height


def _legend_height(axis: AxisScene) -> float:
    if not axis.legend:
        return 0.0
    return _legend_height_from_count(len(axis.legend.entries))


def _legend_height_from_count(count: int) -> float:
    return 0.0 if count == 0 else 6.0 + count * 10.0


def _max_legend_height(fig: FigureScene) -> float:
    return max((_legend_height(panel.axis) for panel in fig.panels), default=0.0)


def _colorbar_footer_height(axis: AxisScene) -> float:
    return 42.0 * len(axis.colorbars) if axis.colorbars else 0.0


def _footer_height(axis: AxisScene) -> float:
    return _legend_height(axis) + _colorbar_footer_height(axis)


def _axis_bottom_extent(axis: AxisScene) -> float:
    if axis.hide_x_axis:
        return 0.0
    if axis.x_label:
        return 31.0
    return 18.0


def _max_footer_height(fig: FigureScene) -> float:
    return max((_footer_height(panel.axis) for panel in fig.panels), default=0.0)


def _figure_bounds(fig: FigureScene, layouts: list[tuple[float, float, float, float]]) -> tuple[float, float, float, float]:
    min_x = float("inf")
    min_y = float("inf")
    max_x = float("-inf")
    max_y = float("-inf")
    for panel in fig.panels:
        left, top, width, height = layouts[panel.row * fig.cols + panel.col]
        render_axis = _panel_axis_for_render(fig, panel)
        footer_height = _footer_height(render_axis) if fig.layout_mode == "timeseries" else _max_footer_height(fig)
        _, _, _, _, x, y, axis_width, axis_height = _axis_layout((left, top, width, height), footer_height, fig.layout_mode)
        if fig.layout_mode == "timeseries":
            left_pad, top_pad, right_pad, bottom_pad = 72.0, 22.0, 10.0, 18.0
        else:
            left_pad, top_pad, right_pad, bottom_pad = 34.0, 18.0, 6.0, 6.0
        min_x = min(min_x, x - left_pad)
        min_y = min(min_y, y - top_pad)
        max_x = max(max_x, x + axis_width + right_pad)
        max_y = max(max_y, y + axis_height + _axis_bottom_extent(render_axis) + footer_height + bottom_pad)
    if _timeseries_uses_shared_right_legend(fig):
        legend = _timeseries_shared_legend(fig)
        if legend is not None:
            panel = fig.panels[(fig.rows // 2) * fig.cols]
            left, top, width, height = layouts[panel.row * fig.cols + panel.col]
            render_axis = _panel_axis_for_render(fig, panel)
            footer_height = _footer_height(render_axis)
            _, _, _, _, x, y, axis_width, axis_height = _axis_layout((left, top, width, height), footer_height, fig.layout_mode)
            max_x = max(max_x, x + axis_width + 36.0 + _estimated_legend_width(legend))
    return min_x, min_y, max_x, max_y


def _parse_layout_mode(value: str) -> str:
    if value not in {"standard", "timeseries"}:
        raise ValueError(f"unsupported layout '{value}'; use 'standard' or 'timeseries'")
    return value


def _estimated_legend_width(legend: Legend) -> float:
    max_chars = max((len(entry.label) for entry in legend.entries), default=0)
    return 18.0 + max_chars * 4.4


def _expand(vmin: float, vmax: float) -> tuple[float, float]:
    if abs(vmax - vmin) < 1e-12:
        pad = 1.0 if abs(vmin) < 1.0 else abs(vmin) * 0.1
        return vmin - pad, vmax + pad
    pad = (vmax - vmin) * 0.05
    return vmin - pad, vmax + pad


def _expand_for_scale(vmin: float, vmax: float, scale: str) -> tuple[float, float]:
    if scale == "log":
        if vmin <= 0.0 or vmax <= 0.0:
            raise ValueError("log scales require strictly positive values")
        if abs(vmax - vmin) < 1e-12:
            return vmin / 1.5, vmax * 1.5
        return vmin / 1.15, vmax * 1.15
    return _expand(vmin, vmax)


def _nice_ticks(vmin: float, vmax: float, target: int) -> list[float]:
    if vmin == vmax:
        return [vmin]
    span = _nice_num(vmax - vmin, False)
    step = _nice_num(span / max(target - 1, 1), True)
    start = floor(vmin / step) * step
    end = floor(vmax / step + 1) * step
    ticks = []
    value = start
    eps = abs(step) * 1e-6
    while value <= end + step * 0.5:
        if value >= vmin - eps and value <= vmax + eps:
            ticks.append(_round_to(value, step))
        value += step
    return ticks


def _x_axis_looks_datetime(axis: AxisScene, xmin: float, xmax: float) -> bool:
    if axis.x_scale != "linear" or axis.x_categories:
        return False
    span = xmax - xmin
    label_mentions_date = bool(axis.x_label and "date" in axis.x_label.lower())
    return label_mentions_date or (xmin >= 0.0 and xmax <= 50000.0 and span >= 30.0)


def _datetime_tick_target(width: float) -> int:
    return max(3, min(6, int(width // 140.0) + 2))


def _datetime_ticks(vmin: float, vmax: float, target: int) -> list[float]:
    if not (vmin < vmax):
        return [vmin]
    count = max(target, 3)
    span = vmax - vmin
    ticks = [vmin + span * i / max(count - 1, 1) for i in range(count)]
    deduped: list[float] = []
    for tick in ticks:
        if not deduped or abs(tick - deduped[-1]) > 1e-6:
            deduped.append(float(tick))
    ticks = deduped
    if ticks[0] > vmin + 1e-6:
        ticks.insert(0, vmin)
    if ticks[-1] < vmax - 1e-6:
        ticks.append(vmax)
    return ticks


def _nice_ticks_for_scale(vmin: float, vmax: float, scale: str, target: int) -> list[float]:
    if scale == "log":
        _validate_scale_limits((vmin, vmax), scale, "axis")
        start = floor(log10(vmin))
        end = floor(log10(vmax))
        return [10.0**power for power in range(start, end + 1)]
    return _nice_ticks(vmin, vmax, target)


def _field_ticks(size: int) -> list[float]:
    if size <= 1:
        return [0.0, float(size)]
    target = 3 if size <= 96 else 4 if size <= 256 else 5
    step = max(1, round(size / (target - 1)))
    ticks = [0.0]
    for idx in range(1, target - 1):
        ticks.append(float(min(size, idx * step)))
    if ticks[-1] != float(size):
        ticks.append(float(size))
    deduped: list[float] = []
    for tick in ticks:
        if not deduped or abs(deduped[-1] - tick) > 1e-9:
            deduped.append(tick)
    return deduped


def _nice_num(value: float, rounding: bool) -> float:
    exponent = floor(log10(abs(value)))
    fraction = value / (10 ** exponent)
    if rounding:
        nice = 1.0 if fraction < 1.5 else 2.0 if fraction < 3.0 else 5.0 if fraction < 7.0 else 10.0
    else:
        nice = 1.0 if fraction <= 1.0 else 2.0 if fraction <= 2.0 else 5.0 if fraction <= 5.0 else 10.0
    return nice * (10 ** exponent)


def _round_to(value: float, step: float) -> float:
    digits = 0 if abs(step) >= 1.0 else max(int(-floor(log10(abs(step))) + 1), 0)
    scale = 10 ** digits
    return round(value * scale) / scale


def _map_x(value: float, xmin: float, xmax: float, x: float, width: float, scale: str = "linear") -> float:
    value = _transform_scale(value, scale)
    xmin = _transform_scale(xmin, scale)
    xmax = _transform_scale(xmax, scale)
    return x + (value - xmin) / (xmax - xmin) * width


def _map_y(value: float, ymin: float, ymax: float, y: float, height: float, scale: str = "linear") -> float:
    value = _transform_scale(value, scale)
    ymin = _transform_scale(ymin, scale)
    ymax = _transform_scale(ymax, scale)
    return y + height - (value - ymin) / (ymax - ymin) * height


def _svg_style(style: Style) -> str:
    fill = style.fill.to_hex() if style.fill else "none"
    stroke = style.stroke.to_hex() if style.stroke else "none"
    return f'fill="{fill}" stroke="{stroke}" stroke-width="{style.stroke_width_pt:.2f}" opacity="{style.opacity:.3f}"'


def _fmt(value: float) -> str:
    if abs(value) >= 1000.0 or (abs(value) > 0.0 and abs(value) < 0.01):
        return f"{value:.1e}"
    if abs(round(value) - value) < 1e-6:
        return f"{value:.0f}"
    if abs(round(value * 10.0) - value * 10.0) < 1e-6:
        return f"{value:.1f}"
    return f"{value:.2f}"


def _fmt_tick(value: float, scale: str) -> str:
    if scale == "log":
        return f"10^{int(round(log10(value)))}"
    return _fmt(value)


def _fmt_x_tick(value: float, scale: str, is_datetime: bool) -> str:
    if is_datetime and scale == "linear":
        return _fmt_datetime_tick(value)
    return _fmt_tick(value, scale)


def _fmt_datetime_tick(value: float) -> str:
    epoch = datetime(1970, 1, 1)
    dt = epoch + timedelta(days=float(int(value)))
    return dt.strftime("%Y-%m")


def _xml(value: str) -> str:
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _svg_rich_text(value: str) -> str:
    return _render_math_chars(list(value))


def _render_math_chars(chars: list[str]) -> str:
    out: list[str] = []
    i = 0
    while i < len(chars):
        ch = chars[i]
        if ch == "$":
            i += 1
            continue
        if ch == "\\":
            token, next_i = _parse_command(chars, i + 1)
            if token == "frac":
                num, next_num = _parse_group_expr(chars, next_i)
                den, next_den = _parse_group_expr(chars, next_num)
                out.append('<tspan baseline-shift="super" font-size="70%">')
                out.append(num)
                out.append("</tspan>")
                out.append("⁄")
                out.append('<tspan baseline-shift="sub" font-size="70%">')
                out.append(den)
                out.append("</tspan>")
                i = next_den
                continue
            symbol = _math_symbol(token)
            if symbol is not None:
                out.append(symbol)
                i = next_i
                continue
            if token:
                out.append(_xml(token))
            else:
                out.append(_xml("\\"))
            i = next_i
            continue
        if ch == "^":
            script, next_i = _parse_script_expr(chars, i + 1)
            if script:
                out.append('<tspan baseline-shift="super" font-size="70%">')
                out.append(script)
                out.append("</tspan>")
                i = next_i
                continue
        if ch == "_":
            script, next_i = _parse_script_expr(chars, i + 1)
            if script:
                out.append('<tspan baseline-shift="sub" font-size="70%">')
                out.append(script)
                out.append("</tspan>")
                i = next_i
                continue
        out.append(_xml(ch))
        i += 1
    return "".join(out)


def _parse_command(chars: list[str], start: int) -> tuple[str, int]:
    token: list[str] = []
    i = start
    while i < len(chars) and chars[i].isalpha():
        token.append(chars[i])
        i += 1
    return "".join(token), i


def _parse_group_expr(chars: list[str], start: int) -> tuple[str, int]:
    if start >= len(chars):
        return "", start
    if chars[start] == "{":
        depth = 1
        i = start + 1
        buf: list[str] = []
        while i < len(chars) and depth > 0:
            if chars[i] == "{":
                depth += 1
                buf.append(chars[i])
            elif chars[i] == "}":
                depth -= 1
                if depth > 0:
                    buf.append(chars[i])
            else:
                buf.append(chars[i])
            i += 1
        return _render_math_chars(buf), i
    return _xml(chars[start]), start + 1


def _parse_script_expr(chars: list[str], start: int) -> tuple[str, int]:
    if start >= len(chars):
        return "", start
    if chars[start] == "{":
        return _parse_group_expr(chars, start)
    if chars[start] == "\\":
        token, next_i = _parse_command(chars, start + 1)
        symbol = _math_symbol(token)
        if symbol is not None:
            return symbol, next_i
        if token:
            return _xml(token), next_i
        return _xml("\\"), next_i
    return _xml(chars[start]), start + 1


def _math_symbol(token: str) -> str | None:
    symbols = {
        "alpha": "α",
        "beta": "β",
        "gamma": "γ",
        "delta": "δ",
        "epsilon": "ε",
        "theta": "θ",
        "lambda": "λ",
        "mu": "μ",
        "pi": "π",
        "sigma": "σ",
        "phi": "φ",
        "psi": "ψ",
        "omega": "ω",
        "Gamma": "Γ",
        "Delta": "Δ",
        "Theta": "Θ",
        "Lambda": "Λ",
        "Pi": "Π",
        "Sigma": "Σ",
        "Phi": "Φ",
        "Psi": "Ψ",
        "Omega": "Ω",
        "sum": "∑",
        "int": "∫",
        "partial": "∂",
        "times": "×",
        "cdot": "·",
        "dots": "…",
        "ldots": "…",
    }
    return symbols.get(token)


def _normalize_font_family(value: str) -> str:
    families = []
    for part in [item.strip() for item in value.split(",") if item.strip()]:
        if part.lower() == "sans-serif":
            families.append("sans-serif")
        elif part.startswith(("'", '"')):
            families.append(part)
        else:
            families.append(f"'{part}'")
    if "sans-serif" not in families:
        families.append("sans-serif")
    return ", ".join(families)


def _parse_scale(scale: str) -> str:
    if scale not in {"linear", "log"}:
        raise ValueError(f"unsupported axis scale '{scale}'; use 'linear' or 'log'")
    return scale


def _parse_y_axis_side(axis: str) -> str:
    if axis not in {"left", "right"}:
        raise ValueError(f"unsupported y axis '{axis}'; use 'left' or 'right'")
    return axis


def _transform_scale(value: float, scale: str) -> float:
    if scale == "log":
        if value <= 0.0:
            raise ValueError("log scales require strictly positive values")
        return log10(value)
    return value


def _validate_scale_limits(limits: tuple[float, float], scale: str, axis_name: str) -> None:
    if scale == "log":
        lo, hi = limits
        if lo <= 0.0 or hi <= 0.0:
            raise ValueError(f"{axis_name} log scale requires strictly positive limits")


def _vec(values) -> list[float]:
    if hasattr(values, "tolist"):
        values = values.tolist()
    return [float(v) for v in values]


def _matrix(values) -> list[list[float]]:
    if hasattr(values, "tolist"):
        values = values.tolist()
    rows = [[float(v) for v in row] for row in values]
    if not rows or not rows[0]:
        return rows
    width = len(rows[0])
    if any(len(row) != width for row in rows):
        raise ValueError("all field rows must have the same length")
    return rows


def _parse_color_input(color, length: int, cmap: str, default_color: Color):
    if color is None:
        return default_color
    if isinstance(color, str):
        return _parse_color_literal(color)
    values = _vec(color)
    if len(values) != length:
        raise ValueError("mapped scatter color array must match data length")
    return values


def _parse_grouped_color_input(color, groups: list[list[float]], cmap: str, default_color: Color):
    if color is None:
        return default_color
    if isinstance(color, str):
        return _parse_color_literal(color)
    total_len = sum(len(group) for group in groups)
    try:
        values = _vec(color)
    except TypeError:
        grouped = [_vec(group) for group in color]
        if len(grouped) != len(groups):
            raise ValueError("point_color group count must match violin group count")
        values = []
        for color_group, data_group in zip(grouped, groups):
            if len(color_group) != len(data_group):
                raise ValueError("each point_color group must match the corresponding violin group length")
            values.extend(color_group)
        return values
    if len(values) != total_len:
        raise ValueError("point_color must match the total number of violin points")
    return values


def _mapped_group_colors(color_input, offset: int, group_len: int, cmap: str) -> list[Color]:
    if isinstance(color_input, list):
        vmin = min(color_input)
        vmax = max(color_input)
        return [_sample_colormap(cmap, _normalize(value, vmin, vmax)) for value in color_input[offset : offset + group_len]]
    return [color_input] * group_len


def _violin_point_offset(idx: int, length: int, width: float) -> float:
    if length <= 1:
        return 0.0
    centered = (idx + 0.5) / length - 0.5
    return centered * width * 2.0


def _parse_color_literal(value: str) -> Color:
    named = {
        "black": Color(27, 31, 36),
        "gray": Color(120, 126, 134),
        "grey": Color(120, 126, 134),
        "orange": Color(226, 134, 42),
        "blue": Color(53, 102, 153),
        "red": Color(192, 71, 58),
        "green": Color(67, 136, 99),
    }
    lower = value.lower()
    if lower in named:
        return named[lower]
    if lower.startswith("#") and len(lower) == 7:
        return Color(int(lower[1:3], 16), int(lower[3:5], 16), int(lower[5:7], 16))
    raise ValueError(f"unsupported color '{value}'")


def _sample_colormap(name: str, t: float) -> Color:
    t = max(0.0, min(1.0, t))
    maps = {
        "acton": [
            (0.000, Color(38, 13, 64)),
            (0.125, Color(65, 51, 98)),
            (0.250, Color(89, 84, 129)),
            (0.375, Color(126, 99, 142)),
            (0.500, Color(168, 102, 144)),
            (0.625, Color(208, 121, 159)),
            (0.750, Color(221, 163, 195)),
            (0.875, Color(232, 203, 226)),
            (1.000, Color(240, 234, 250)),
        ],
        "bamako": [
            (0.000, Color(0, 59, 71)),
            (0.125, Color(16, 69, 62)),
            (0.250, Color(37, 82, 49)),
            (0.375, Color(65, 100, 31)),
            (0.500, Color(99, 122, 10)),
            (0.625, Color(139, 137, 0)),
            (0.750, Color(181, 161, 36)),
            (0.875, Color(222, 197, 103)),
            (1.000, Color(255, 229, 173)),
        ],
        "batlow": [
            (0.000, Color(1, 25, 89)),
            (0.125, Color(17, 67, 96)),
            (0.250, Color(34, 96, 97)),
            (0.375, Color(77, 115, 77)),
            (0.500, Color(130, 130, 49)),
            (0.625, Color(192, 144, 54)),
            (0.750, Color(242, 157, 109)),
            (0.875, Color(253, 180, 182)),
            (1.000, Color(250, 204, 250)),
        ],
        "bone": [
            (0.0, Color(0, 0, 1)),
            (0.38, Color(53, 61, 76)),
            (0.72, Color(131, 145, 145)),
            (1.0, Color(255, 255, 255)),
        ],
        "berlin": [
            (0.000, Color(158, 176, 255)),
            (0.125, Color(81, 159, 211)),
            (0.250, Color(40, 104, 134)),
            (0.375, Color(20, 48, 62)),
            (0.500, Color(25, 12, 9)),
            (0.625, Color(65, 18, 1)),
            (0.750, Color(125, 52, 30)),
            (0.875, Color(190, 111, 99)),
            (1.000, Color(255, 173, 173)),
        ],
        "bilbao": [
            (0.000, Color(76, 0, 1)),
            (0.125, Color(120, 41, 47)),
            (0.250, Color(153, 78, 81)),
            (0.375, Color(163, 107, 89)),
            (0.500, Color(169, 130, 94)),
            (0.625, Color(177, 156, 103)),
            (0.750, Color(191, 185, 153)),
            (0.875, Color(207, 206, 201)),
            (1.000, Color(255, 255, 255)),
        ],
        "broc": [
            (0.000, Color(44, 26, 76)),
            (0.125, Color(41, 75, 125)),
            (0.250, Color(91, 130, 169)),
            (0.375, Color(165, 187, 208)),
            (0.500, Color(235, 238, 236)),
            (0.625, Color(211, 211, 167)),
            (0.750, Color(153, 153, 96)),
            (0.875, Color(91, 91, 44)),
            (1.000, Color(38, 38, 0)),
        ],
        "cork": [
            (0.000, Color(44, 25, 76)),
            (0.125, Color(40, 75, 126)),
            (0.250, Color(86, 127, 166)),
            (0.375, Color(158, 181, 204)),
            (0.500, Color(230, 237, 236)),
            (0.625, Color(166, 196, 166)),
            (0.750, Color(91, 146, 91)),
            (0.875, Color(31, 97, 29)),
            (1.000, Color(15, 41, 3)),
        ],
        "devon": [
            (0.000, Color(44, 26, 76)),
            (0.125, Color(41, 56, 106)),
            (0.250, Color(41, 88, 143)),
            (0.375, Color(66, 114, 188)),
            (0.500, Color(126, 143, 221)),
            (0.625, Color(176, 171, 238)),
            (0.750, Color(203, 198, 244)),
            (0.875, Color(229, 227, 250)),
            (1.000, Color(255, 255, 255)),
        ],
        "gray": [(0.0, Color(245, 245, 245)), (1.0, Color(45, 45, 45))],
        "hawaii": [
            (0.000, Color(140, 2, 115)),
            (0.125, Color(146, 46, 85)),
            (0.250, Color(151, 78, 62)),
            (0.375, Color(155, 111, 40)),
            (0.500, Color(156, 150, 28)),
            (0.625, Color(137, 189, 74)),
            (0.750, Color(107, 212, 142)),
            (0.875, Color(103, 233, 213)),
            (1.000, Color(179, 242, 253)),
        ],
        "imola": [
            (0.000, Color(26, 51, 179)),
            (0.125, Color(37, 73, 168)),
            (0.250, Color(48, 94, 157)),
            (0.375, Color(63, 113, 142)),
            (0.500, Color(84, 134, 127)),
            (0.625, Color(113, 164, 119)),
            (0.750, Color(146, 196, 110)),
            (0.875, Color(191, 231, 103)),
            (1.000, Color(255, 255, 102)),
        ],
        "lajolla": [
            (0.000, Color(25, 25, 0)),
            (0.125, Color(55, 36, 17)),
            (0.250, Color(103, 52, 42)),
            (0.375, Color(166, 70, 68)),
            (0.500, Color(217, 96, 78)),
            (0.625, Color(229, 136, 81)),
            (0.750, Color(237, 174, 84)),
            (0.875, Color(247, 218, 116)),
            (1.000, Color(255, 254, 203)),
        ],
        "lapaz": [
            (0.000, Color(26, 12, 100)),
            (0.125, Color(36, 50, 126)),
            (0.250, Color(45, 83, 147)),
            (0.375, Color(61, 113, 160)),
            (0.500, Color(92, 140, 163)),
            (0.625, Color(134, 158, 155)),
            (0.750, Color(181, 173, 150)),
            (0.875, Color(235, 207, 187)),
            (1.000, Color(254, 242, 243)),
        ],
        "lipari": [
            (0.000, Color(3, 19, 38)),
            (0.125, Color(24, 62, 97)),
            (0.250, Color(82, 91, 122)),
            (0.375, Color(120, 95, 114)),
            (0.500, Color(165, 98, 103)),
            (0.625, Color(218, 111, 94)),
            (0.750, Color(233, 155, 116)),
            (0.875, Color(231, 196, 154)),
            (1.000, Color(253, 245, 218)),
        ],
        "magma": [
            (0.0, Color(0, 0, 4)),
            (0.15, Color(28, 16, 68)),
            (0.35, Color(79, 18, 123)),
            (0.55, Color(129, 37, 129)),
            (0.72, Color(181, 54, 122)),
            (0.86, Color(229, 80, 100)),
            (1.0, Color(252, 253, 191)),
        ],
        "managua": [
            (0.000, Color(255, 207, 103)),
            (0.125, Color(216, 147, 83)),
            (0.250, Color(177, 98, 67)),
            (0.375, Color(129, 57, 57)),
            (0.500, Color(87, 41, 73)),
            (0.625, Color(76, 71, 129)),
            (0.750, Color(88, 119, 181)),
            (0.875, Color(107, 172, 219)),
            (1.000, Color(129, 231, 255)),
        ],
        "navia": [
            (0.000, Color(3, 19, 39)),
            (0.125, Color(7, 57, 102)),
            (0.250, Color(27, 96, 143)),
            (0.375, Color(47, 121, 139)),
            (0.500, Color(65, 138, 128)),
            (0.625, Color(90, 161, 113)),
            (0.750, Color(137, 195, 106)),
            (0.875, Color(211, 227, 161)),
            (1.000, Color(252, 244, 217)),
        ],
        "nuuk": [
            (0.000, Color(5, 89, 140)),
            (0.125, Color(45, 100, 131)),
            (0.250, Color(83, 119, 133)),
            (0.375, Color(125, 143, 145)),
            (0.500, Color(161, 166, 152)),
            (0.625, Color(181, 181, 145)),
            (0.750, Color(195, 195, 133)),
            (0.875, Color(221, 221, 139)),
            (1.000, Color(254, 254, 178)),
        ],
        "oslo": [
            (0.000, Color(1, 1, 1)),
            (0.125, Color(14, 30, 46)),
            (0.250, Color(21, 57, 91)),
            (0.375, Color(38, 87, 140)),
            (0.500, Color(80, 123, 188)),
            (0.625, Color(125, 153, 202)),
            (0.750, Color(163, 177, 202)),
            (0.875, Color(207, 210, 216)),
            (1.000, Color(255, 255, 255)),
        ],
        "roma": [
            (0.000, Color(126, 23, 0)),
            (0.125, Color(157, 88, 24)),
            (0.250, Color(182, 140, 50)),
            (0.375, Color(208, 202, 114)),
            (0.500, Color(192, 234, 195)),
            (0.625, Color(118, 209, 215)),
            (0.750, Color(56, 156, 198)),
            (0.875, Color(34, 105, 176)),
            (1.000, Color(3, 49, 152)),
        ],
        "tokyo": [
            (0.000, Color(28, 14, 52)),
            (0.125, Color(81, 36, 70)),
            (0.250, Color(108, 71, 80)),
            (0.375, Color(113, 93, 82)),
            (0.500, Color(116, 112, 83)),
            (0.625, Color(121, 141, 87)),
            (0.750, Color(135, 184, 103)),
            (0.875, Color(186, 234, 164)),
            (1.000, Color(239, 252, 221)),
        ],
        "tofino": [
            (0.000, Color(222, 217, 255)),
            (0.125, Color(136, 157, 217)),
            (0.250, Color(62, 94, 154)),
            (0.375, Color(29, 45, 74)),
            (0.500, Color(13, 22, 19)),
            (0.625, Color(29, 61, 32)),
            (0.750, Color(56, 117, 61)),
            (0.875, Color(127, 180, 107)),
            (1.000, Color(219, 230, 155)),
        ],
        "turku": [
            (0.000, Color(0, 0, 0)),
            (0.125, Color(40, 40, 35)),
            (0.250, Color(73, 73, 58)),
            (0.375, Color(107, 106, 73)),
            (0.500, Color(147, 140, 91)),
            (0.625, Color(195, 163, 116)),
            (0.750, Color(229, 170, 144)),
            (0.875, Color(251, 196, 191)),
            (1.000, Color(255, 230, 230)),
        ],
        "vanimo": [
            (0.000, Color(255, 205, 253)),
            (0.125, Color(205, 120, 189)),
            (0.250, Color(146, 62, 128)),
            (0.375, Color(64, 27, 55)),
            (0.500, Color(26, 21, 19)),
            (0.625, Color(42, 55, 22)),
            (0.750, Color(82, 114, 39)),
            (0.875, Color(127, 174, 71)),
            (1.000, Color(190, 253, 165)),
        ],
        "vik": [
            (0.000, Color(0, 18, 97)),
            (0.125, Color(3, 68, 129)),
            (0.250, Color(48, 125, 166)),
            (0.375, Color(148, 190, 210)),
            (0.500, Color(236, 229, 224)),
            (0.625, Color(219, 170, 141)),
            (0.750, Color(194, 112, 65)),
            (0.875, Color(145, 45, 6)),
            (1.000, Color(89, 0, 8)),
        ],
    }
    stops = maps.get(name, maps["batlow"])
    for (t0, c0), (t1, c1) in zip(stops, stops[1:]):
        if t0 <= t <= t1:
            local = 0.0 if t1 == t0 else (t - t0) / (t1 - t0)
            return Color(
                round(c0.r + (c1.r - c0.r) * local),
                round(c0.g + (c1.g - c0.g) * local),
                round(c0.b + (c1.b - c0.b) * local),
            )
    return stops[-1][1]


def _normalize(value: float, vmin: float, vmax: float) -> float:
    return 0.5 if abs(vmax - vmin) < 1e-12 else (value - vmin) / (vmax - vmin)


def _histogram_bins(values, bins: int) -> list[float]:
    vals = [float(v) for v in values]
    if not vals or bins <= 0:
        return []
    vmin = min(vals)
    vmax = max(vals)
    if abs(vmax - vmin) < 1e-12:
        out = [0.0] * bins
        out[bins // 2] = 1.0
        return out
    counts = [0.0] * bins
    for value in vals:
        idx = min(int(_normalize(value, vmin, vmax) * bins), bins - 1)
        counts[idx] += 1.0
    peak = max(max(counts), 1.0)
    return [count / peak for count in counts]


def _histogram_rects(
    values: list[float],
    bins: int,
    range: tuple[float, float] | None,
    density: bool,
) -> tuple[list[tuple[float, float, float]], float, float, float]:
    if not values:
        raise ValueError("histogram data must be non-empty")
    if bins <= 0:
        raise ValueError("histogram bins must be positive")
    if range is None:
        xmin = min(values)
        xmax = max(values)
    else:
        xmin, xmax = range
    if xmax < xmin:
        raise ValueError("histogram range must satisfy max >= min")
    if abs(xmax - xmin) < 1e-12:
        pad = 0.5 if abs(xmin) < 1.0 else abs(xmin) * 0.05
        xmin -= pad
        xmax += pad
    width = xmax - xmin
    bin_w = width / bins
    counts = [0.0] * bins
    kept = 0.0
    for value in values:
        if value < xmin or value > xmax:
            continue
        idx = min(int(((value - xmin) / width) * bins), bins - 1)
        counts[idx] += 1.0
        kept += 1.0
    if density and kept > 0.0:
        counts = [count / (kept * bin_w) for count in counts]
    ymax = max(counts) if counts else 0.0
    rects = []
    for idx, count in enumerate(counts):
        left = xmin + idx * bin_w
        rects.append((left, left + bin_w, count))
    return rects, xmin, xmax, ymax


def _quantile(values: list[float], p: float) -> float:
    sorted_values = sorted(values)
    if len(sorted_values) == 1:
        return sorted_values[0]
    pos = max(0.0, min(1.0, p)) * (len(sorted_values) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(sorted_values) - 1)
    if lo == hi:
        return sorted_values[lo]
    return _lerp(sorted_values[lo], sorted_values[hi], pos - lo)


def _estimate_bandwidth(values: list[float]) -> float:
    mean = sum(values) / max(len(values), 1)
    var = sum((v - mean) ** 2 for v in values) / max(len(values), 1)
    std = sqrt(var)
    n = max(len(values), 2)
    return max(1.06 * std * (n ** -0.2), 1e-3)


def _kde(values: Iterable[float], y: float, bandwidth: float) -> float:
    vals = list(values)
    norm = 1.0 / (sqrt(2.0 * pi) * bandwidth * len(vals))
    return sum(exp(-0.5 * ((y - value) / bandwidth) ** 2) for value in vals) * norm


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t
