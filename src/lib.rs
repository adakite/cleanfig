use std::f64::consts::PI;
use std::fmt::Write as _;
use std::sync::{Arc, Mutex};

use pyo3::exceptions::{PyRuntimeError, PyTypeError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::{PyAny, PySequence};
use svg2pdf::{ConversionOptions, PageOptions};

const DPI: f64 = 72.0;
const FONT_FAMILY_DEFAULT: &str = "\"IBM Plex Sans\", \"Source Sans 3\", Arial, sans-serif";
const FIELD_LIMIT: usize = 10_000;
const COLORBAR_HISTOGRAM_LEVELS: usize = 32;

#[derive(Clone, Debug)]
struct FigureScene {
    width_in: f64,
    height_in: f64,
    rows: usize,
    cols: usize,
    panel_labels: bool,
    font_family: String,
    theme: Theme,
    panels: Vec<PanelScene>,
    warnings: Vec<String>,
}

#[derive(Clone, Debug)]
struct PanelScene {
    row: usize,
    col: usize,
    axis: AxisScene,
}

#[derive(Clone, Debug)]
struct AxisScene {
    x_label: Option<String>,
    y_label: Option<String>,
    right_y_label: Option<String>,
    x_limits: Option<(f64, f64)>,
    y_limits: Option<(f64, f64)>,
    right_y_limits: Option<(f64, f64)>,
    x_scale: AxisScale,
    y_scale: AxisScale,
    right_y_scale: AxisScale,
    layers: Vec<Layer>,
    legend: Option<Legend>,
    colorbars: Vec<Colorbar>,
    x_categories: Option<Vec<String>>,
    hide_x_axis: bool,
}

#[derive(Clone, Debug)]
struct Layer {
    primitive: Primitive,
    z_index: i32,
    y_axis: YAxisSide,
}

#[derive(Clone, Debug)]
enum Primitive {
    Polyline {
        points: Vec<(f64, f64)>,
        style: Style,
    },
    Marker {
        x: f64,
        y: f64,
        radius_pt: f64,
        style: Style,
    },
    Rect {
        x: f64,
        y: f64,
        w: f64,
        h: f64,
        style: Style,
    },
    Polygon {
        points: Vec<(f64, f64)>,
        style: Style,
    },
}

#[derive(Clone, Debug)]
struct Style {
    fill: Option<Color>,
    stroke: Option<Color>,
    stroke_width_pt: f64,
    opacity: f64,
}

#[derive(Clone, Debug)]
struct Color(pub u8, pub u8, pub u8);

#[derive(Clone, Debug)]
struct Legend {
    entries: Vec<LegendEntry>,
}

#[derive(Clone, Debug)]
struct LegendEntry {
    label: String,
    glyph: LegendGlyph,
    color: Color,
}

#[derive(Clone, Copy, Debug)]
enum LegendGlyph {
    Line,
    Marker,
}

#[derive(Clone, Debug)]
struct Colorbar {
    min: f64,
    max: f64,
    cmap: String,
    label: Option<String>,
    placement: ColorbarPlacement,
    style: ColorbarStyle,
    histogram: Option<Vec<f64>>,
}

#[derive(Clone, Copy, Debug)]
enum ColorbarPlacement {
    Right,
    InsideLeft,
}

#[derive(Clone, Copy, Debug)]
enum ColorbarStyle {
    Continuous,
    Binned,
}

#[derive(Clone, Debug)]
struct DataBounds {
    min_x: f64,
    max_x: f64,
    min_y: f64,
    max_y: f64,
}

#[pyclass]
struct Figure {
    inner: Arc<Mutex<FigureScene>>,
}

#[pyclass]
struct Panel {
    inner: Arc<Mutex<FigureScene>>,
    row: usize,
    col: usize,
}

#[pyclass]
#[derive(Clone)]
struct PlotHandle {
    min: f64,
    max: f64,
    cmap: String,
    uses_alpha: bool,
    histogram: Option<Vec<f64>>,
}

#[derive(Clone, Debug)]
struct PanelLayout {
    left: f64,
    top: f64,
    width: f64,
    height: f64,
}

#[derive(Clone, Debug)]
struct AxisLayout {
    x: f64,
    y: f64,
    width: f64,
    height: f64,
}

#[derive(Clone, Copy, Debug)]
struct FigureBounds {
    min_x: f64,
    min_y: f64,
    max_x: f64,
    max_y: f64,
}

#[derive(Clone, Debug)]
enum ColorInput {
    Constant(Color),
    Mapped(Vec<f64>, String),
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum AxisScale {
    Linear,
    Log,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum YAxisSide {
    Left,
    Right,
}

#[derive(Clone, Copy, Debug)]
enum Theme {
    Publication,
    Dark,
}

impl FigureScene {
    fn new(
        width_in: f64,
        height_in: f64,
        rows: usize,
        cols: usize,
        panel_labels: bool,
        font_family: String,
        theme: Theme,
    ) -> Self {
        let mut panels = Vec::with_capacity(rows * cols);
        for row in 0..rows {
            for col in 0..cols {
                panels.push(PanelScene {
                    row,
                    col,
                    axis: AxisScene {
                        x_label: None,
                        y_label: None,
                        right_y_label: None,
                        x_limits: None,
                        y_limits: None,
                        right_y_limits: None,
                        x_scale: AxisScale::Linear,
                        y_scale: AxisScale::Linear,
                        right_y_scale: AxisScale::Linear,
                        layers: Vec::new(),
                        legend: None,
                        colorbars: Vec::new(),
                        x_categories: None,
                        hide_x_axis: false,
                    },
                });
            }
        }
        Self {
            width_in,
            height_in,
            rows,
            cols,
            panel_labels,
            font_family,
            theme,
            panels,
            warnings: Vec::new(),
        }
    }

    fn panel_index(&self, row: usize, col: usize) -> PyResult<usize> {
        if row >= self.rows || col >= self.cols {
            return Err(PyValueError::new_err(format!(
                "panel index ({row}, {col}) out of bounds for grid {}x{}",
                self.rows, self.cols
            )));
        }
        Ok(row * self.cols + col)
    }

    fn panel_mut(&mut self, row: usize, col: usize) -> PyResult<&mut PanelScene> {
        let idx = self.panel_index(row, col)?;
        Ok(&mut self.panels[idx])
    }

    fn panel(&self, row: usize, col: usize) -> PyResult<&PanelScene> {
        let idx = self.panel_index(row, col)?;
        Ok(&self.panels[idx])
    }

    fn save(&mut self, path: &str) -> PyResult<()> {
        let ext = path.rsplit('.').next().unwrap_or_default().to_lowercase();
        match ext.as_str() {
            "svg" => std::fs::write(path, SvgBackend.render(self)?,).map_err(io_err)?,
            "html" => std::fs::write(path, HtmlBackend.render(self)?,).map_err(io_err)?,
            "pdf" => std::fs::write(path, self.to_pdf()?).map_err(io_err)?,
            _ => {
                return Err(PyValueError::new_err(
                    "unsupported export format; use .svg, .html, or .pdf",
                ))
            }
        }
        Ok(())
    }

    fn to_svg(&self) -> PyResult<String> {
        let layouts = figure_layout(self.width_in, self.height_in, self.rows, self.cols);
        let bounds = figure_bounds(self, &layouts);
        let pad = 4.0;
        let width_pt = (bounds.max_x - bounds.min_x + pad * 2.0).max(1.0);
        let height_pt = (bounds.max_y - bounds.min_y + pad * 2.0).max(1.0);
        let tx = pad - bounds.min_x;
        let ty = pad - bounds.min_y;
        let mut svg = String::new();
        write!(
            svg,
            "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"{width_pt:.2}pt\" height=\"{height_pt:.2}pt\" viewBox=\"0 0 {width_pt:.2} {height_pt:.2}\" role=\"img\" aria-label=\"cleanfig figure\">"
        )
        .unwrap();
        write!(
            svg,
            "<style>.cf-text{{font-family:{};fill:{};font-weight:400;}} .cf-axis{{stroke:{};stroke-width:0.55;fill:none;stroke-linecap:square;}} .cf-tick{{stroke:{};stroke-width:0.45;}} .cf-label{{font-size:8.6px;font-weight:400;}} .cf-ticklabel{{font-size:7.2px;font-weight:400;fill:{};}} .cf-panel{{font-size:11.2px;font-weight:700;}} .cf-cbarlabel{{font-size:7.8px;font-weight:400;}} .cf-legendtext{{font-size:7.2px;font-weight:400;fill:{};}}</style>",
            xml_escape(&self.font_family),
            self.theme.text_color().to_hex(),
            self.theme.axis_color().to_hex(),
            self.theme.tick_color().to_hex(),
            self.theme.tick_label_color().to_hex(),
            self.theme.tick_label_color().to_hex()
        )
        .unwrap();
        write!(
            svg,
            "<rect x=\"0\" y=\"0\" width=\"{width_pt:.2}\" height=\"{height_pt:.2}\" fill=\"{}\" />",
            self.theme.background_color().to_hex()
        )
        .unwrap();
        write!(svg, "<g transform=\"translate({tx:.2},{ty:.2})\">").unwrap();

        for panel in &self.panels {
            let panel_layout = &layouts[panel.row * self.cols + panel.col];
            render_panel(&mut svg, self, panel, panel_layout)?;
        }

        svg.push_str("</g>");
        svg.push_str("</svg>");
        Ok(svg)
    }

    fn to_pdf(&self) -> PyResult<Vec<u8>> {
        let svg = self.to_svg()?;
        let mut options = svg2pdf::usvg::Options::default();
        options.fontdb_mut().load_system_fonts();
        let tree = svg2pdf::usvg::Tree::from_str(&svg, &options)
            .map_err(|err| PyRuntimeError::new_err(format!("failed to parse generated SVG for PDF export: {err}")))?;
        svg2pdf::to_pdf(&tree, ConversionOptions::default(), PageOptions::default())
            .map_err(|err| PyRuntimeError::new_err(format!("failed to convert SVG to PDF: {err}")))
    }
}

impl AxisScene {
    fn x_bounds(&self) -> Option<(f64, f64)> {
        let mut out: Option<(f64, f64)> = None;
        for layer in &self.layers {
            if let Some(candidate) = primitive_bounds(&layer.primitive) {
                out = match out {
                    None => Some((candidate.min_x, candidate.max_x)),
                    Some((min_x, max_x)) => Some((min_x.min(candidate.min_x), max_x.max(candidate.max_x))),
                };
            }
        }
        out
    }

    fn y_bounds(&self, side: YAxisSide) -> Option<(f64, f64)> {
        let mut bounds: Option<DataBounds> = None;
        for layer in &self.layers {
            if layer.y_axis != side {
                continue;
            }
            let candidate = primitive_bounds(&layer.primitive);
            bounds = match (bounds, candidate) {
                (None, Some(next)) => Some(next),
                (Some(cur), Some(next)) => Some(DataBounds {
                    min_x: cur.min_x.min(next.min_x),
                    max_x: cur.max_x.max(next.max_x),
                    min_y: cur.min_y.min(next.min_y),
                    max_y: cur.max_y.max(next.max_y),
                }),
                (Some(cur), None) => Some(cur),
                (None, None) => None,
            };
        }
        bounds.map(|b| (b.min_y, b.max_y))
    }

    fn resolved_x_limits(&self) -> (f64, f64) {
        let (min_x, max_x) = self.x_bounds().unwrap_or((0.0, 1.0));
        self.x_limits.unwrap_or_else(|| match self.x_scale {
            AxisScale::Linear => expand_bounds(min_x, max_x),
            AxisScale::Log => expand_positive_bounds(min_x, max_x),
        })
    }

    fn resolved_y_limits(&self, side: YAxisSide) -> (f64, f64) {
        let (min_y, max_y) = self.y_bounds(side).unwrap_or((0.0, 1.0));
        match side {
            YAxisSide::Left => self.y_limits.unwrap_or_else(|| match self.y_scale {
                AxisScale::Linear => expand_bounds(min_y, max_y),
                AxisScale::Log => expand_positive_bounds(min_y, max_y),
            }),
            YAxisSide::Right => self.right_y_limits.unwrap_or_else(|| match self.right_y_scale {
                AxisScale::Linear => expand_bounds(min_y, max_y),
                AxisScale::Log => expand_positive_bounds(min_y, max_y),
            }),
        }
    }

    fn has_right_axis(&self) -> bool {
        self.right_y_label.is_some()
            || self.right_y_limits.is_some()
            || self.layers.iter().any(|layer| layer.y_axis == YAxisSide::Right)
    }
}

#[pymethods]
impl Figure {
    fn panel(&self, row: usize, col: usize) -> PyResult<Panel> {
        let guard = self.inner.lock().map_err(lock_err)?;
        guard.panel(row, col)?;
        drop(guard);
        Ok(Panel {
            inner: Arc::clone(&self.inner),
            row,
            col,
        })
    }

    fn save(&self, path: String) -> PyResult<()> {
        let mut guard = self.inner.lock().map_err(lock_err)?;
        guard.save(&path)
    }
}

#[pymethods]
impl Panel {
    fn xlabel(&self, label: String) -> PyResult<()> {
        let mut fig = self.inner.lock().map_err(lock_err)?;
        fig.panel_mut(self.row, self.col)?.axis.x_label = Some(label);
        Ok(())
    }

    fn ylabel(&self, label: String) -> PyResult<()> {
        let mut fig = self.inner.lock().map_err(lock_err)?;
        fig.panel_mut(self.row, self.col)?.axis.y_label = Some(label);
        Ok(())
    }

    fn right_ylabel(&self, label: String) -> PyResult<()> {
        let mut fig = self.inner.lock().map_err(lock_err)?;
        fig.panel_mut(self.row, self.col)?.axis.right_y_label = Some(label);
        Ok(())
    }

    fn xscale(&self, scale: String) -> PyResult<()> {
        let mut fig = self.inner.lock().map_err(lock_err)?;
        fig.panel_mut(self.row, self.col)?.axis.x_scale = parse_axis_scale(&scale)?;
        Ok(())
    }

    #[pyo3(signature = (scale, axis="left"))]
    fn yscale(&self, scale: String, axis: &str) -> PyResult<()> {
        let mut fig = self.inner.lock().map_err(lock_err)?;
        let panel = fig.panel_mut(self.row, self.col)?;
        let scale = parse_axis_scale(&scale)?;
        match parse_y_axis_side(axis)? {
            YAxisSide::Left => panel.axis.y_scale = scale,
            YAxisSide::Right => panel.axis.right_y_scale = scale,
        }
        Ok(())
    }

    #[pyo3(signature = (x=None, y=None))]
    fn limits(&self, x: Option<(f64, f64)>, y: Option<(f64, f64)>) -> PyResult<()> {
        let mut fig = self.inner.lock().map_err(lock_err)?;
        let axis = &mut fig.panel_mut(self.row, self.col)?.axis;
        axis.x_limits = x;
        axis.y_limits = y;
        Ok(())
    }

    #[pyo3(signature = (y=None))]
    fn right_limits(&self, y: Option<(f64, f64)>) -> PyResult<()> {
        let mut fig = self.inner.lock().map_err(lock_err)?;
        fig.panel_mut(self.row, self.col)?.axis.right_y_limits = y;
        Ok(())
    }

    #[pyo3(signature = (x, y, color=None, size=6.0, alpha=0.8, label=None, cmap=None, yaxis="left"))]
    fn scatter(
        &self,
        py: Python<'_>,
        x: &Bound<'_, PyAny>,
        y: &Bound<'_, PyAny>,
        color: Option<&Bound<'_, PyAny>>,
        size: f64,
        alpha: f64,
        label: Option<String>,
        cmap: Option<String>,
        yaxis: &str,
    ) -> PyResult<Py<PlotHandle>> {
        let xs = extract_vec_f64(x)?;
        let ys = extract_vec_f64(y)?;
        if xs.len() != ys.len() {
            return Err(PyValueError::new_err("x and y must have the same length"));
        }
        let mut fig = self.inner.lock().map_err(lock_err)?;
        let y_axis = parse_y_axis_side(yaxis)?;
        let theme_scatter = fig.theme.scatter_default();
        let default_scatter = if y_axis == YAxisSide::Right {
            fig.theme.right_axis_color()
        } else {
            theme_scatter.clone()
        };
        let color_input = parse_color_input(
            color,
            xs.len(),
            cmap.unwrap_or_else(|| "batlow".to_string()),
            default_scatter.clone(),
        )?;
        let (min, max, cmap_name, uses_alpha, histogram) = {
            let axis = &mut fig.panel_mut(self.row, self.col)?.axis;
            for idx in 0..xs.len() {
                let fill = match &color_input {
                    ColorInput::Constant(color) => color.clone(),
                    ColorInput::Mapped(values, cmap_name) => {
                        let min = values.iter().copied().fold(f64::INFINITY, f64::min);
                        let max = values.iter().copied().fold(f64::NEG_INFINITY, f64::max);
                        sample_colormap(cmap_name, normalize(values[idx], min, max))
                    }
                };
                axis.layers.push(Layer {
                    primitive: Primitive::Marker {
                        x: xs[idx],
                        y: ys[idx],
                        radius_pt: size / 2.0,
                        style: Style {
                            fill: Some(fill),
                            stroke: None,
                            stroke_width_pt: 0.0,
                            opacity: alpha,
                        },
                    },
                    z_index: 20,
                    y_axis,
                });
            }
            if let Some(text) = label {
                axis.legend
                    .get_or_insert(Legend { entries: Vec::new() })
                    .entries
                    .push(LegendEntry {
                        label: text,
                        glyph: LegendGlyph::Marker,
                        color: match &color_input {
                            ColorInput::Constant(c) => c.clone(),
                            ColorInput::Mapped(_, _) => default_scatter.clone(),
                        },
                    });
            }
            match &color_input {
                ColorInput::Constant(color) => (0.0, 1.0, color.to_hex(), alpha < 1.0, None),
                ColorInput::Mapped(values, cmap_name) => {
                    let min = values.iter().copied().fold(f64::INFINITY, f64::min);
                    let max = values.iter().copied().fold(f64::NEG_INFINITY, f64::max);
                    (
                        min,
                        max,
                        cmap_name.clone(),
                        alpha < 1.0,
                        Some(histogram_bins(values, COLORBAR_HISTOGRAM_LEVELS)),
                    )
                }
            }
        };
        Py::new(
            py,
            PlotHandle {
                min,
                max,
                cmap: cmap_name,
                uses_alpha,
                histogram,
            },
        )
    }

    #[pyo3(signature = (x, y, color=None, width=0.95, alpha=1.0, label=None, yaxis="left"))]
    fn line(
        &self,
        x: &Bound<'_, PyAny>,
        y: &Bound<'_, PyAny>,
        color: Option<&Bound<'_, PyAny>>,
        width: f64,
        alpha: f64,
        label: Option<String>,
        yaxis: &str,
    ) -> PyResult<()> {
        let xs = extract_vec_f64(x)?;
        let ys = extract_vec_f64(y)?;
        if xs.len() != ys.len() {
            return Err(PyValueError::new_err("x and y must have the same length"));
        }
        let mut fig = self.inner.lock().map_err(lock_err)?;
        let y_axis = parse_y_axis_side(yaxis)?;
        let stroke = match color {
            Some(value) => parse_named_or_hex_color(value)?,
            None => {
                if y_axis == YAxisSide::Right {
                    fig.theme.right_axis_color()
                } else {
                    fig.theme.line_default()
                }
            }
        };
        let points = xs.into_iter().zip(ys).collect::<Vec<_>>();
        if alpha < 1.0 {
            fig.warnings.push("alpha used in line plot; future EPS backend will need flattening or rejection".to_string());
        }
        let axis = &mut fig.panel_mut(self.row, self.col)?.axis;
        axis.layers.push(Layer {
            primitive: Primitive::Polyline {
                points,
                style: Style {
                    fill: None,
                    stroke: Some(stroke.clone()),
                    stroke_width_pt: width,
                    opacity: alpha,
                },
            },
            z_index: 30,
            y_axis,
        });
        if let Some(text) = label {
            axis.legend
                .get_or_insert(Legend { entries: Vec::new() })
                .entries
                .push(LegendEntry {
                    label: text,
                    glyph: LegendGlyph::Line,
                    color: stroke,
                });
        }
        Ok(())
    }

    #[pyo3(signature = (x, y, yerr=None, ymin=None, ymax=None, color=None, width=0.8, cap=4.0, alpha=0.7, yaxis="left"))]
    fn errorbar(
        &self,
        x: &Bound<'_, PyAny>,
        y: &Bound<'_, PyAny>,
        yerr: Option<&Bound<'_, PyAny>>,
        ymin: Option<&Bound<'_, PyAny>>,
        ymax: Option<&Bound<'_, PyAny>>,
        color: Option<&Bound<'_, PyAny>>,
        width: f64,
        cap: f64,
        alpha: f64,
        yaxis: &str,
    ) -> PyResult<()> {
        let xs = extract_vec_f64(x)?;
        let ys = extract_vec_f64(y)?;
        if xs.len() != ys.len() {
            return Err(PyValueError::new_err("x and y must have the same length"));
        }
        let lower = if let Some(values) = ymin {
            let extracted = extract_vec_f64(values)?;
            if extracted.len() != ys.len() {
                return Err(PyValueError::new_err("ymin must have the same length as y"));
            }
            extracted
        } else if let Some(values) = yerr {
            let extracted = extract_vec_f64(values)?;
            if extracted.len() != ys.len() {
                return Err(PyValueError::new_err("yerr must have the same length as y"));
            }
            ys.iter().zip(extracted.iter()).map(|(y, err)| y - err).collect()
        } else {
            return Err(PyValueError::new_err("provide yerr or ymin/ymax for errorbar"));
        };
        let upper = if let Some(values) = ymax {
            let extracted = extract_vec_f64(values)?;
            if extracted.len() != ys.len() {
                return Err(PyValueError::new_err("ymax must have the same length as y"));
            }
            extracted
        } else if let Some(values) = yerr {
            let extracted = extract_vec_f64(values)?;
            ys.iter().zip(extracted.iter()).map(|(y, err)| y + err).collect()
        } else {
            return Err(PyValueError::new_err("provide yerr or ymin/ymax for errorbar"));
        };

        let mut fig = self.inner.lock().map_err(lock_err)?;
        let y_axis = parse_y_axis_side(yaxis)?;
        let stroke = match color {
            Some(value) => parse_named_or_hex_color(value)?,
            None => {
                if y_axis == YAxisSide::Right {
                    fig.theme.right_axis_color()
                } else {
                    fig.theme.line_default()
                }
            }
        };
        let axis = &mut fig.panel_mut(self.row, self.col)?.axis;
        let span = if xs.len() > 1 {
            let min_x = xs.iter().copied().fold(f64::INFINITY, f64::min);
            let max_x = xs.iter().copied().fold(f64::NEG_INFINITY, f64::max);
            (max_x - min_x).abs()
        } else {
            1.0
        };
        let cap_half = if span > 0.0 { span * (cap / 400.0) } else { 0.1 };
        for ((xv, y0), y1) in xs.iter().zip(lower.iter()).zip(upper.iter()) {
            axis.layers.push(Layer {
                primitive: Primitive::Polyline {
                    points: vec![(*xv, *y0), (*xv, *y1)],
                    style: Style {
                        fill: None,
                        stroke: Some(stroke.clone()),
                        stroke_width_pt: width,
                        opacity: alpha,
                    },
                },
                z_index: 24,
                y_axis,
            });
            axis.layers.push(Layer {
                primitive: Primitive::Polyline {
                    points: vec![(*xv - cap_half, *y0), (*xv + cap_half, *y0)],
                    style: Style {
                        fill: None,
                        stroke: Some(stroke.clone()),
                        stroke_width_pt: width,
                        opacity: alpha,
                    },
                },
                z_index: 24,
                y_axis,
            });
            axis.layers.push(Layer {
                primitive: Primitive::Polyline {
                    points: vec![(*xv - cap_half, *y1), (*xv + cap_half, *y1)],
                    style: Style {
                        fill: None,
                        stroke: Some(stroke.clone()),
                        stroke_width_pt: width,
                        opacity: alpha,
                    },
                },
                z_index: 24,
                y_axis,
            });
        }
        Ok(())
    }

    fn legend(&self) -> PyResult<()> {
        let mut fig = self.inner.lock().map_err(lock_err)?;
        fig.panel_mut(self.row, self.col)?
            .axis
            .legend
            .get_or_insert(Legend { entries: Vec::new() });
        Ok(())
    }

    #[pyo3(signature = (labels, values, yaxis="left", color=None, alpha=1.0))]
    fn bar(
        &self,
        labels: Vec<String>,
        values: &Bound<'_, PyAny>,
        yaxis: &str,
        color: Option<&Bound<'_, PyAny>>,
        alpha: f64,
    ) -> PyResult<()> {
        let ys = extract_vec_f64(values)?;
        if labels.len() != ys.len() {
            return Err(PyValueError::new_err("labels and values must have the same length"));
        }
        let mut fig = self.inner.lock().map_err(lock_err)?;
        let y_axis = parse_y_axis_side(yaxis)?;
        let fill = match color {
            Some(value) => parse_named_or_hex_color(value)?,
            None => {
                if y_axis == YAxisSide::Right {
                    fig.theme.right_axis_color()
                } else {
                    fig.theme.bar_default()
                }
            }
        };
        let axis = &mut fig.panel_mut(self.row, self.col)?.axis;
        axis.x_categories = Some(labels);
        axis.hide_x_axis = false;
        for (i, value) in ys.iter().enumerate() {
            let center = i as f64;
            axis.layers.push(Layer {
                primitive: Primitive::Rect {
                    x: center - 0.35,
                    y: 0.0,
                    w: 0.7,
                    h: *value,
                    style: Style {
                        fill: Some(fill.clone()),
                        stroke: None,
                        stroke_width_pt: 0.0,
                        opacity: alpha,
                    },
                },
                z_index: 10,
                y_axis,
            });
        }
        axis.x_limits = Some((-0.5, ys.len() as f64 - 0.5));
        Ok(())
    }

    #[pyo3(signature = (data, bins=12, range=None, density=false, color=None, alpha=1.0, label=None, yaxis="left"))]
    fn histogram(
        &self,
        data: &Bound<'_, PyAny>,
        bins: usize,
        range: Option<(f64, f64)>,
        density: bool,
        color: Option<&Bound<'_, PyAny>>,
        alpha: f64,
        label: Option<String>,
        yaxis: &str,
    ) -> PyResult<()> {
        let values = extract_vec_f64(data)?;
        if values.is_empty() {
            return Err(PyValueError::new_err("histogram data must be non-empty"));
        }
        if bins == 0 {
            return Err(PyValueError::new_err("histogram bins must be positive"));
        }
        let mut fig = self.inner.lock().map_err(lock_err)?;
        let y_axis = parse_y_axis_side(yaxis)?;
        let fill = match color {
            Some(value) => parse_named_or_hex_color(value)?,
            None => {
                if y_axis == YAxisSide::Right {
                    fig.theme.right_axis_color()
                } else {
                    fig.theme.bar_default()
                }
            }
        };
        let stroke = if y_axis == YAxisSide::Right {
            fig.theme.right_axis_color()
        } else {
            fig.theme.axis_color()
        };
        let (hist, xmin, xmax, ymax) = histogram_rects(&values, bins, range, density)?;
        let axis = &mut fig.panel_mut(self.row, self.col)?.axis;
        axis.x_categories = None;
        axis.hide_x_axis = false;
        for (left, right, height) in hist {
            axis.layers.push(Layer {
                primitive: Primitive::Rect {
                    x: left,
                    y: 0.0,
                    w: right - left,
                    h: height,
                    style: Style {
                        fill: Some(fill.clone()),
                        stroke: Some(stroke.clone()),
                        stroke_width_pt: 0.35,
                        opacity: alpha,
                    },
                },
                z_index: 10,
                y_axis,
            });
        }
        axis.x_limits = Some((xmin, xmax));
        match y_axis {
            YAxisSide::Left => axis.y_limits = Some((0.0, ymax.max(1e-12))),
            YAxisSide::Right => axis.right_y_limits = Some((0.0, ymax.max(1e-12))),
        }
        if let Some(text) = label {
            axis.legend
                .get_or_insert(Legend { entries: Vec::new() })
                .entries
                .push(LegendEntry {
                    label: text,
                    glyph: LegendGlyph::Marker,
                    color: fill,
                });
        }
        Ok(())
    }

    #[pyo3(signature = (grid, cmap=None, cell_edges=false))]
    fn field(
        &self,
        py: Python<'_>,
        grid: &Bound<'_, PyAny>,
        cmap: Option<String>,
        cell_edges: bool,
    ) -> PyResult<Py<PlotHandle>> {
        let values = extract_matrix_f64(grid)?;
        let rows = values.len();
        let cols = values.first().map_or(0, |r| r.len());
        if rows == 0 || cols == 0 {
            return Err(PyValueError::new_err("field grid must be non-empty"));
        }
        if rows * cols > FIELD_LIMIT {
            return Err(PyValueError::new_err(format!(
                "field grid too large for vector backend prototype: {} cells > {}",
                rows * cols,
                FIELD_LIMIT
            )));
        }
        let cmap_name = cmap.unwrap_or_else(|| "batlow".to_string());
        let mut min = f64::INFINITY;
        let mut max = f64::NEG_INFINITY;
        for row in &values {
            for value in row {
                min = min.min(*value);
                max = max.max(*value);
            }
        }
        let mut fig = self.inner.lock().map_err(lock_err)?;
        let field_edge = fig.theme.axis_color();
        let axis = &mut fig.panel_mut(self.row, self.col)?.axis;
        for (r, row) in values.iter().enumerate() {
            for (c, value) in row.iter().enumerate() {
                let x = c as f64;
                let y = (rows - 1 - r) as f64;
                axis.layers.push(Layer {
                    primitive: Primitive::Rect {
                        x,
                        y,
                        w: 1.0,
                        h: 1.0,
                        style: Style {
                            fill: Some(sample_colormap(&cmap_name, normalize(*value, min, max))),
                            stroke: if cell_edges {
                                Some(field_edge.clone())
                            } else {
                                None
                            },
                            stroke_width_pt: if cell_edges { 0.2 } else { 0.0 },
                            opacity: 1.0,
                        },
                    },
                    z_index: 5,
                    y_axis: YAxisSide::Left,
                });
            }
        }
        axis.x_limits = Some((0.0, cols as f64));
        axis.y_limits = Some((0.0, rows as f64));
        Py::new(
            py,
            PlotHandle {
                min,
                max,
                cmap: cmap_name,
                uses_alpha: false,
                histogram: Some(histogram_bins_2d(&values, COLORBAR_HISTOGRAM_LEVELS)),
            },
        )
    }

    #[pyo3(signature = (handle, label=None, placement=None, style=None))]
    fn colorbar(
        &self,
        handle: &PlotHandle,
        label: Option<String>,
        placement: Option<String>,
        style: Option<String>,
    ) -> PyResult<()> {
        let mut fig = self.inner.lock().map_err(lock_err)?;
        if handle.uses_alpha {
            fig.warnings.push("alpha-mapped plot with colorbar may not translate to future EPS backend".to_string());
        }
        let axis = &mut fig.panel_mut(self.row, self.col)?.axis;
        axis.colorbars.push(Colorbar {
            min: handle.min,
            max: handle.max,
            cmap: handle.cmap.clone(),
            label,
            placement: match placement.as_deref() {
                Some("inside-left") => ColorbarPlacement::InsideLeft,
                Some("right") | None => ColorbarPlacement::Right,
                Some(other) => {
                    return Err(PyValueError::new_err(format!(
                        "unsupported colorbar placement '{other}'; use 'right' or 'inside-left'"
                    )))
                }
            },
            style: match style.as_deref() {
                Some("continuous") => ColorbarStyle::Continuous,
                Some("binned") | None => ColorbarStyle::Binned,
                Some(other) => {
                    return Err(PyValueError::new_err(format!(
                        "unsupported colorbar style '{other}'; use 'continuous' or 'binned'"
                    )))
                }
            },
            histogram: handle.histogram.clone(),
        });
        Ok(())
    }

    #[pyo3(signature = (data, labels=None, show_median=false, points=false, point_color=None, point_size=4.0, point_alpha=0.75, point_cmap=None))]
    fn violin(
        &self,
        py: Python<'_>,
        data: &Bound<'_, PyAny>,
        labels: Option<Vec<String>>,
        show_median: bool,
        points: bool,
        point_color: Option<&Bound<'_, PyAny>>,
        point_size: f64,
        point_alpha: f64,
        point_cmap: Option<String>,
    ) -> PyResult<Option<Py<PlotHandle>>> {
        let groups = extract_groups(data)?;
        if groups.is_empty() {
            return Err(PyValueError::new_err("violin data must contain at least one group"));
        }
        if let Some(ref values) = labels {
            if values.len() != groups.len() {
                return Err(PyValueError::new_err("labels length must match violin group count"));
            }
        }
        let mut fig = self.inner.lock().map_err(lock_err)?;
        let fill = fig.theme.violin_fill();
        let stroke = fig.theme.violin_stroke();
        let point_input = if points {
            Some(parse_grouped_color_input(
                point_color,
                &groups,
                point_cmap.unwrap_or_else(|| "batlow".to_string()),
                fig.theme.scatter_default(),
            )?)
        } else {
            None
        };
        let axis = &mut fig.panel_mut(self.row, self.col)?.axis;
        axis.x_categories = labels.or_else(|| Some(default_position_labels(groups.len())));
        axis.hide_x_axis = true;
        let mut point_offset = 0usize;
        for (i, group) in groups.iter().enumerate() {
            if group.is_empty() {
                continue;
            }
            let (min_y, max_y) = min_max(group);
            let bandwidth = estimate_bandwidth(group);
            let samples = 60usize;
            let mut density = Vec::with_capacity(samples);
            let mut peak: f64 = 0.0;
            for s in 0..samples {
                let y = lerp(min_y, max_y, s as f64 / (samples - 1) as f64);
                let d = kde(group, y, bandwidth);
                peak = peak.max(d);
                density.push((y, d));
            }
            let mut points = Vec::with_capacity(samples * 2);
            for (y, d) in &density {
                let half = if peak == 0.0 { 0.0 } else { 0.35 * d / peak };
                points.push((i as f64 - half, *y));
            }
            for (y, d) in density.iter().rev() {
                let half = if peak == 0.0 { 0.0 } else { 0.35 * d / peak };
                points.push((i as f64 + half, *y));
            }
            axis.layers.push(Layer {
                primitive: Primitive::Polygon {
                    points,
                    style: Style {
                        fill: Some(fill.clone()),
                        stroke: Some(stroke.clone()),
                        stroke_width_pt: 0.9,
                        opacity: 0.95,
                    },
                },
                z_index: 15,
                y_axis: YAxisSide::Left,
            });
            if let Some(color_input) = &point_input {
                let point_fills = mapped_group_colors(color_input, point_offset, group.len());
                for (idx, value) in group.iter().enumerate() {
                    axis.layers.push(Layer {
                        primitive: Primitive::Marker {
                            x: i as f64 + violin_point_offset(idx, group.len(), 0.26),
                            y: *value,
                            radius_pt: point_size / 2.0,
                            style: Style {
                                fill: Some(point_fills[idx].clone()),
                                stroke: None,
                                stroke_width_pt: 0.0,
                                opacity: point_alpha,
                            },
                        },
                        z_index: 22,
                        y_axis: YAxisSide::Left,
                    });
                }
            }
            if show_median {
                let med = quantile(group, 0.5);
                axis.layers.push(Layer {
                    primitive: Primitive::Polyline {
                        points: vec![(i as f64 - 0.18, med), (i as f64 + 0.18, med)],
                        style: Style {
                            fill: None,
                            stroke: Some(stroke.clone()),
                            stroke_width_pt: 1.0,
                            opacity: 1.0,
                        },
                    },
                    z_index: 25,
                    y_axis: YAxisSide::Left,
                });
            }
            point_offset += group.len();
        }
        axis.x_limits = Some((-0.5, groups.len() as f64 - 0.5));
        drop(fig);
        match point_input {
            Some(ColorInput::Mapped(values, cmap_name)) => {
                let min = values.iter().copied().fold(f64::INFINITY, f64::min);
                let max = values.iter().copied().fold(f64::NEG_INFINITY, f64::max);
                Ok(Some(Py::new(
                    py,
                    PlotHandle {
                        min,
                        max,
                        cmap: cmap_name,
                        uses_alpha: point_alpha < 1.0,
                        histogram: Some(histogram_bins(&values, COLORBAR_HISTOGRAM_LEVELS)),
                    },
                )?))
            }
            _ => Ok(None),
        }
    }

    #[pyo3(signature = (data, labels=None))]
    fn r#box(&self, data: &Bound<'_, PyAny>, labels: Option<Vec<String>>) -> PyResult<()> {
        let groups = extract_groups(data)?;
        if groups.is_empty() {
            return Err(PyValueError::new_err("box data must contain at least one group"));
        }
        if let Some(ref values) = labels {
            if values.len() != groups.len() {
                return Err(PyValueError::new_err("labels length must match box group count"));
            }
        }
        let mut fig = self.inner.lock().map_err(lock_err)?;
        let fill = fig.theme.box_fill();
        let stroke = fig.theme.box_stroke();
        let axis = &mut fig.panel_mut(self.row, self.col)?.axis;
        axis.x_categories = labels.or_else(|| Some(default_position_labels(groups.len())));
        axis.hide_x_axis = false;
        for (i, group) in groups.iter().enumerate() {
            if group.is_empty() {
                continue;
            }
            let q1 = quantile(group, 0.25);
            let med = quantile(group, 0.5);
            let q3 = quantile(group, 0.75);
            let iqr = q3 - q1;
            let lower = group
                .iter()
                .copied()
                .filter(|v| *v >= q1 - 1.5 * iqr)
                .fold(f64::INFINITY, f64::min);
            let upper = group
                .iter()
                .copied()
                .filter(|v| *v <= q3 + 1.5 * iqr)
                .fold(f64::NEG_INFINITY, f64::max);
            axis.layers.push(Layer {
                primitive: Primitive::Rect {
                    x: i as f64 - 0.25,
                    y: q1,
                    w: 0.5,
                    h: q3 - q1,
                    style: Style {
                        fill: Some(fill.clone()),
                        stroke: Some(stroke.clone()),
                        stroke_width_pt: 0.9,
                        opacity: 1.0,
                    },
                },
                z_index: 15,
                y_axis: YAxisSide::Left,
            });
            axis.layers.push(Layer {
                primitive: Primitive::Polyline {
                    points: vec![(i as f64 - 0.25, med), (i as f64 + 0.25, med)],
                    style: Style {
                        fill: None,
                        stroke: Some(stroke.clone()),
                        stroke_width_pt: 1.0,
                        opacity: 1.0,
                    },
                },
                z_index: 25,
                y_axis: YAxisSide::Left,
            });
            axis.layers.push(Layer {
                primitive: Primitive::Polyline {
                    points: vec![(i as f64, lower), (i as f64, q1)],
                    style: Style {
                        fill: None,
                        stroke: Some(stroke.clone()),
                        stroke_width_pt: 0.8,
                        opacity: 1.0,
                    },
                },
                z_index: 20,
                y_axis: YAxisSide::Left,
            });
            axis.layers.push(Layer {
                primitive: Primitive::Polyline {
                    points: vec![(i as f64, q3), (i as f64, upper)],
                    style: Style {
                        fill: None,
                        stroke: Some(stroke.clone()),
                        stroke_width_pt: 0.8,
                        opacity: 1.0,
                    },
                },
                z_index: 20,
                y_axis: YAxisSide::Left,
            });
            axis.layers.push(Layer {
                primitive: Primitive::Polyline {
                    points: vec![(i as f64 - 0.14, lower), (i as f64 + 0.14, lower)],
                    style: Style {
                        fill: None,
                        stroke: Some(stroke.clone()),
                        stroke_width_pt: 0.8,
                        opacity: 1.0,
                    },
                },
                z_index: 20,
                y_axis: YAxisSide::Left,
            });
            axis.layers.push(Layer {
                primitive: Primitive::Polyline {
                    points: vec![(i as f64 - 0.14, upper), (i as f64 + 0.14, upper)],
                    style: Style {
                        fill: None,
                        stroke: Some(stroke.clone()),
                        stroke_width_pt: 0.8,
                        opacity: 1.0,
                    },
                },
                z_index: 20,
                y_axis: YAxisSide::Left,
            });
        }
        axis.x_limits = Some((-0.5, groups.len() as f64 - 0.5));
        Ok(())
    }
}

#[pymethods]
impl PlotHandle {}

trait Backend {
    fn render(&self, figure: &FigureScene) -> PyResult<String>;
}

struct SvgBackend;
struct HtmlBackend;

impl Backend for SvgBackend {
    fn render(&self, figure: &FigureScene) -> PyResult<String> {
        figure.to_svg()
    }
}

impl Backend for HtmlBackend {
    fn render(&self, figure: &FigureScene) -> PyResult<String> {
        let svg = figure.to_svg()?;
        Ok(format!(
            "<!DOCTYPE html><html lang=\"en\"><head><meta charset=\"utf-8\"><title>cleanfig</title><style>body{{margin:0;padding:24px;background:{};}}figure{{margin:0;display:flex;justify-content:center;}}</style></head><body><figure>{svg}</figure></body></html>",
            figure.theme.background_color().to_hex()
        ))
    }
}

#[pyfunction]
#[pyo3(signature = (width="single", height=4.0, grid=(1, 1), panel_labels=false, font=None, theme="publication"))]
fn figure(
    width: &str,
    height: f64,
    grid: (usize, usize),
    panel_labels: bool,
    font: Option<String>,
    theme: &str,
) -> PyResult<Figure> {
    let width_in = match width {
        "single" => 3.4,
        "double" => 7.0,
        other => {
            return Err(PyValueError::new_err(format!(
                "unsupported width preset '{other}'; use 'single' or 'double'"
            )))
        }
    };
    if grid.0 == 0 || grid.1 == 0 {
        return Err(PyValueError::new_err("grid dimensions must be positive"));
    }
    Ok(Figure {
        inner: Arc::new(Mutex::new(FigureScene::new(
            width_in,
            height,
            grid.0,
            grid.1,
            panel_labels,
            normalize_font_family(font.as_deref().unwrap_or(FONT_FAMILY_DEFAULT)),
            Theme::from_str(theme)?,
        ))),
    })
}

#[pymodule]
fn _cleanfig(_py: Python<'_>, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<Figure>()?;
    m.add_class::<Panel>()?;
    m.add_class::<PlotHandle>()?;
    m.add_function(wrap_pyfunction!(figure, m)?)?;
    Ok(())
}

fn render_panel(svg: &mut String, fig: &FigureScene, panel: &PanelScene, layout: &PanelLayout) -> PyResult<()> {
    let footer_height = max_footer_height(fig);
    let axis_layout = axis_layout(layout, footer_height);
    write!(
        svg,
        "<g data-panel=\"{}-{}\">",
        panel.row,
        panel.col
    )
    .unwrap();
    if fig.panel_labels {
        let letter = ((panel.row * fig.cols + panel.col) as u8 + b'A') as char;
        write!(
            svg,
            "<text class=\"cf-text cf-panel\" x=\"{:.2}\" y=\"{:.2}\">{}</text>",
            axis_layout.x - 22.0,
            axis_layout.y - 10.0,
            letter
        )
        .unwrap();
    }
    render_axis(svg, &panel.axis, &axis_layout, fig.theme)?;
    svg.push_str("</g>");
    Ok(())
}

fn render_axis(svg: &mut String, axis: &AxisScene, layout: &AxisLayout, theme: Theme) -> PyResult<()> {
    let (xmin, xmax) = axis.resolved_x_limits();
    let (ymin, ymax) = axis.resolved_y_limits(YAxisSide::Left);
    let has_right_axis = axis.has_right_axis();
    let (rymin, rymax) = axis.resolved_y_limits(YAxisSide::Right);
    let x_ticks = if axis.x_categories.is_some() {
        Vec::new()
    } else {
        axis_ticks(xmin, xmax, axis.x_scale, 5)?
    };
    let y_ticks = axis_ticks(ymin, ymax, axis.y_scale, 5)?;
    let right_y_ticks = if has_right_axis {
        axis_ticks(rymin, rymax, axis.right_y_scale, 5)?
    } else {
        Vec::new()
    };

    let axis_gap = if axis.hide_x_axis { 0.0 } else { 4.0 };
    if !axis.hide_x_axis {
        write!(
            svg,
            "<line class=\"cf-axis\" x1=\"{:.2}\" y1=\"{:.2}\" x2=\"{:.2}\" y2=\"{:.2}\" />",
            layout.x + axis_gap,
            layout.y + layout.height,
            layout.x + layout.width,
            layout.y + layout.height
        )
        .unwrap();
    }
    write!(
        svg,
        "<line class=\"cf-axis\" x1=\"{:.2}\" y1=\"{:.2}\" x2=\"{:.2}\" y2=\"{:.2}\" />",
        layout.x,
        layout.y,
        layout.x,
        layout.y + layout.height - axis_gap
    )
    .unwrap();
    if has_right_axis {
        write!(
            svg,
            "<line x1=\"{:.2}\" y1=\"{:.2}\" x2=\"{:.2}\" y2=\"{:.2}\" stroke=\"{}\" stroke-width=\"0.7\" />",
            layout.x + layout.width,
            layout.y,
            layout.x + layout.width,
            layout.y + layout.height - axis_gap,
            theme.right_axis_color().to_hex()
        )
        .unwrap();
    }

    if !axis.hide_x_axis {
        for tick in x_ticks {
            let x = map_x_scaled(tick, xmin, xmax, axis.x_scale, layout)?;
            write!(
                svg,
                "<line class=\"cf-tick\" x1=\"{x:.2}\" y1=\"{:.2}\" x2=\"{x:.2}\" y2=\"{:.2}\" /><text class=\"cf-text cf-ticklabel\" text-anchor=\"middle\" x=\"{x:.2}\" y=\"{:.2}\">{}</text>",
                layout.y + layout.height,
                layout.y + layout.height + 4.5,
                layout.y + layout.height + 13.5,
                svg_rich_text(&format_tick_scaled(tick, axis.x_scale))
            )
            .unwrap();
        }
    }

    if let Some(labels) = &axis.x_categories {
        for (idx, label) in labels.iter().enumerate() {
            let x = map_x(idx as f64, xmin, xmax, layout);
            write!(
                svg,
                "<text class=\"cf-text cf-ticklabel\" text-anchor=\"middle\" x=\"{x:.2}\" y=\"{:.2}\">{}</text>",
                layout.y + layout.height + 13.5,
                svg_rich_text(label)
            )
            .unwrap();
        }
    }

    for tick in y_ticks {
        let y = map_y_scaled(tick, ymin, ymax, axis.y_scale, layout)?;
        write!(
            svg,
            "<line class=\"cf-tick\" x1=\"{:.2}\" y1=\"{y:.2}\" x2=\"{:.2}\" y2=\"{y:.2}\" /><text class=\"cf-text cf-ticklabel\" text-anchor=\"end\" x=\"{:.2}\" y=\"{:.2}\">{}</text>",
            layout.x - 4.5,
            layout.x,
            layout.x - 7.5,
            y + 2.8,
            svg_rich_text(&format_tick_scaled(tick, axis.y_scale))
        )
        .unwrap();
    }
    if has_right_axis {
        let axis_color = theme.right_axis_color();
        for tick in right_y_ticks {
            let y = map_y_scaled(tick, rymin, rymax, axis.right_y_scale, layout)?;
            write!(
                svg,
                "<line x1=\"{:.2}\" y1=\"{y:.2}\" x2=\"{:.2}\" y2=\"{y:.2}\" stroke=\"{}\" stroke-width=\"0.45\" /><text text-anchor=\"start\" x=\"{:.2}\" y=\"{:.2}\" font-family=\"{}\" font-size=\"7.2px\" fill=\"{}\">{}</text>",
                layout.x + layout.width,
                layout.x + layout.width + 4.5,
                axis_color.to_hex(),
                layout.x + layout.width + 7.5,
                y + 2.8,
                xml_attr_escape(FONT_FAMILY_DEFAULT),
                axis_color.to_hex(),
                svg_rich_text(&format_tick_scaled(tick, axis.right_y_scale))
            )
            .unwrap();
        }
    }

    let mut layers = axis.layers.clone();
    layers.sort_by_key(|layer| layer.z_index);
    for layer in &layers {
        let (layer_ymin, layer_ymax, layer_scale) = match layer.y_axis {
            YAxisSide::Left => (ymin, ymax, axis.y_scale),
            YAxisSide::Right => (rymin, rymax, axis.right_y_scale),
        };
        render_primitive(svg, &layer.primitive, layout, xmin, xmax, axis.x_scale, layer_ymin, layer_ymax, layer_scale)?;
    }

    if let Some(label) = &axis.x_label {
        write!(
            svg,
            "<text class=\"cf-text cf-label\" text-anchor=\"middle\" x=\"{:.2}\" y=\"{:.2}\">{}</text>",
            layout.x + layout.width / 2.0,
            layout.y + layout.height + 26.5,
            svg_rich_text(label)
        )
        .unwrap();
    }
    if let Some(label) = &axis.y_label {
        write!(
            svg,
            "<text class=\"cf-text cf-label\" text-anchor=\"middle\" transform=\"translate({:.2},{:.2}) rotate(-90)\">{}</text>",
            layout.x - 27.0,
            layout.y + layout.height / 2.0,
            svg_rich_text(label)
        )
        .unwrap();
    }
    if let Some(label) = &axis.right_y_label {
        let axis_color = theme.right_axis_color();
        write!(
            svg,
            "<text text-anchor=\"middle\" transform=\"translate({:.2},{:.2}) rotate(90)\" font-family=\"{}\" font-size=\"8.6px\" fill=\"{}\">{}</text>",
            layout.x + layout.width + 27.0,
            layout.y + layout.height / 2.0,
            xml_attr_escape(FONT_FAMILY_DEFAULT),
            axis_color.to_hex(),
            svg_rich_text(label)
        )
        .unwrap();
    }
    let footer_top = layout.y + layout.height + 31.0;
    if let Some(legend) = &axis.legend {
        render_legend(svg, legend, layout, footer_top)?;
    }
    let mut offset_y = footer_top + legend_height(axis);
    for colorbar in &axis.colorbars {
        render_colorbar(svg, colorbar, layout, offset_y)?;
        offset_y += colorbar_footer_height(axis);
    }
    Ok(())
}

fn render_primitive(
    svg: &mut String,
    primitive: &Primitive,
    layout: &AxisLayout,
    xmin: f64,
    xmax: f64,
    x_scale: AxisScale,
    ymin: f64,
    ymax: f64,
    y_scale: AxisScale,
) -> PyResult<()> {
    match primitive {
        Primitive::Polyline { points, style } => {
            let mut d = String::new();
            for (idx, (x, y)) in points.iter().enumerate() {
                let sx = map_x_scaled(*x, xmin, xmax, x_scale, layout)?;
                let sy = map_y_scaled(*y, ymin, ymax, y_scale, layout)?;
                if idx == 0 {
                    write!(d, "M {sx:.2} {sy:.2} ").unwrap();
                } else {
                    write!(d, "L {sx:.2} {sy:.2} ").unwrap();
                }
            }
            write!(
                svg,
                "<path d=\"{}\" {} />",
                d.trim(),
                svg_style(style)
            )
            .unwrap();
        }
        Primitive::Marker {
            x,
            y,
            radius_pt,
            style,
        } => {
            write!(
                svg,
                "<circle cx=\"{:.2}\" cy=\"{:.2}\" r=\"{:.2}\" {} />",
                map_x_scaled(*x, xmin, xmax, x_scale, layout)?,
                map_y_scaled(*y, ymin, ymax, y_scale, layout)?,
                radius_pt,
                svg_style(style)
            )
            .unwrap();
        }
        Primitive::Rect { x, y, w, h, style } => {
            let x0 = map_x_scaled(*x, xmin, xmax, x_scale, layout)?;
            let x1 = map_x_scaled(*x + *w, xmin, xmax, x_scale, layout)?;
            let y0 = map_y_scaled(*y, ymin, ymax, y_scale, layout)?;
            let y1 = map_y_scaled(*y + *h, ymin, ymax, y_scale, layout)?;
            let left = x0.min(x1);
            let top = y0.min(y1);
            write!(
                svg,
                "<rect x=\"{left:.2}\" y=\"{top:.2}\" width=\"{:.2}\" height=\"{:.2}\" {} />",
                (x1 - x0).abs(),
                (y1 - y0).abs(),
                svg_style(style)
            )
            .unwrap();
        }
        Primitive::Polygon { points, style } => {
            let mut buf = String::new();
            for (x, y) in points {
                write!(
                    buf,
                    "{:.2},{:.2} ",
                    map_x_scaled(*x, xmin, xmax, x_scale, layout)?,
                    map_y_scaled(*y, ymin, ymax, y_scale, layout)?
                )
                .unwrap();
            }
            write!(
                svg,
                "<polygon points=\"{}\" {} />",
                buf.trim(),
                svg_style(style)
            )
            .unwrap();
        }
    }
    Ok(())
}

fn render_legend(svg: &mut String, legend: &Legend, layout: &AxisLayout, top: f64) -> PyResult<()> {
    if legend.entries.is_empty() {
        return Ok(());
    }
    let x = layout.x;
    let mut y = top + 9.0;
    for entry in &legend.entries {
        match entry.glyph {
            LegendGlyph::Line => {
                write!(
                    svg,
                    "<line x1=\"{:.2}\" y1=\"{:.2}\" x2=\"{:.2}\" y2=\"{:.2}\" stroke=\"{}\" stroke-width=\"0.95\" />",
                    x,
                    y,
                    x + 10.0,
                    y,
                    entry.color.to_hex()
                )
                .unwrap();
            }
            LegendGlyph::Marker => {
                write!(
                    svg,
                    "<circle cx=\"{:.2}\" cy=\"{:.2}\" r=\"2.6\" fill=\"{}\" />",
                    x + 5.0,
                    y,
                    entry.color.to_hex()
                )
                .unwrap();
            }
        }
        write!(
            svg,
            "<text class=\"cf-text cf-legendtext\" x=\"{:.2}\" y=\"{:.2}\">{}</text>",
            x + 13.0,
            y + 2.6,
            svg_rich_text(&entry.label)
        )
        .unwrap();
        y += 10.0;
    }
    Ok(())
}

fn render_colorbar(svg: &mut String, colorbar: &Colorbar, layout: &AxisLayout, top: f64) -> PyResult<()> {
    let bar_w = layout.width.min(138.0);
    let bar_h = 12.0;
    let bar_x = match colorbar.placement {
        ColorbarPlacement::Right => layout.x + (layout.width - bar_w) * 0.5,
        ColorbarPlacement::InsideLeft => layout.x + 6.0,
    };
    let bar_y = top + 12.0;
    if let Some(label) = &colorbar.label {
        write!(
            svg,
            "<text class=\"cf-text cf-cbarlabel\" text-anchor=\"middle\" x=\"{:.2}\" y=\"{:.2}\">{}</text>",
            bar_x + bar_w * 0.5,
            top + 7.5,
            svg_rich_text(label)
        )
        .unwrap();
    }
    match colorbar.style {
        ColorbarStyle::Continuous => {
            let gradient_id = format!(
                "cf-grad-{}-{}-{}",
                (bar_x * 10.0).round() as i64,
                (bar_y * 10.0).round() as i64,
                colorbar.cmap
            );
            write!(
                svg,
                "<defs><linearGradient id=\"{}\" x1=\"0%\" y1=\"0%\" x2=\"100%\" y2=\"0%\">",
                gradient_id
            )
            .unwrap();
            for step in 0..=8 {
                let t = step as f64 / 8.0;
                write!(
                    svg,
                    "<stop offset=\"{:.0}%\" stop-color=\"{}\" />",
                    t * 100.0,
                    sample_colormap(&colorbar.cmap, t).to_hex()
                )
                .unwrap();
            }
            svg.push_str("</linearGradient></defs>");
            write!(
                svg,
                "<rect x=\"{bar_x:.2}\" y=\"{bar_y:.2}\" width=\"{bar_w:.2}\" height=\"{bar_h:.2}\" rx=\"1.2\" fill=\"url(#{})\" stroke=\"{}\" stroke-width=\"0.35\" />",
                gradient_id,
                sample_colormap(&colorbar.cmap, 0.5).to_hex()
            )
            .unwrap();
        }
        ColorbarStyle::Binned => {
            if let Some(histogram) = &colorbar.histogram {
                let bins = histogram.len().max(1);
                let bin_w = bar_w / bins as f64;
                let max_value = histogram
                    .iter()
                    .copied()
                    .fold(0.0_f64, f64::max)
                    .max(1e-12);
                write!(
                    svg,
                    "<line class=\"cf-axis\" x1=\"{bar_x:.2}\" y1=\"{:.2}\" x2=\"{:.2}\" y2=\"{:.2}\" />",
                    bar_y + bar_h,
                    bar_x + bar_w,
                    bar_y + bar_h
                )
                .unwrap();
                for (i, value) in histogram.iter().enumerate() {
                    let x0 = bar_x + i as f64 * bin_w;
                    let fill = sample_colormap(&colorbar.cmap, (i as f64 + 0.5) / bins as f64);
                    let height = (bar_h * (*value / max_value).clamp(0.0, 1.0)).max(0.8);
                    let y0 = bar_y + bar_h - height;
                    write!(
                        svg,
                        "<rect x=\"{x0:.2}\" y=\"{y0:.2}\" width=\"{:.2}\" height=\"{height:.2}\" fill=\"{}\" stroke=\"none\" opacity=\"0.95\" />",
                        (bin_w - 0.4).max(0.8),
                        fill.to_hex(),
                    )
                    .unwrap();
                }
            }
        }
    }
    let ticks = [colorbar.min, 0.5 * (colorbar.min + colorbar.max), colorbar.max];
    for (idx, tick) in ticks.iter().enumerate() {
        let x = match idx {
            0 => bar_x,
            1 => bar_x + bar_w * 0.5,
            _ => bar_x + bar_w,
        };
        write!(
            svg,
            "<line class=\"cf-tick\" x1=\"{x:.2}\" y1=\"{:.2}\" x2=\"{x:.2}\" y2=\"{:.2}\" /><text class=\"cf-text cf-ticklabel\" text-anchor=\"{}\" x=\"{x:.2}\" y=\"{:.2}\">{}</text>",
            bar_y + bar_h,
            bar_y + bar_h + 3.5,
            if idx == 0 { "start" } else if idx == 1 { "middle" } else { "end" },
            bar_y + bar_h + 12.0,
            svg_rich_text(&format_tick(*tick))
        )
        .unwrap();
    }
    Ok(())
}

fn primitive_bounds(primitive: &Primitive) -> Option<DataBounds> {
    match primitive {
        Primitive::Polyline { points, .. } | Primitive::Polygon { points, .. } => points_bounds(points),
        Primitive::Marker { x, y, .. } => Some(DataBounds {
            min_x: *x,
            max_x: *x,
            min_y: *y,
            max_y: *y,
        }),
        Primitive::Rect { x, y, w, h, .. } => Some(DataBounds {
            min_x: (*x).min(*x + *w),
            max_x: (*x).max(*x + *w),
            min_y: (*y).min(*y + *h),
            max_y: (*y).max(*y + *h),
        }),
    }
}

fn points_bounds(points: &[(f64, f64)]) -> Option<DataBounds> {
    let mut iter = points.iter().copied();
    let first = iter.next()?;
    let mut bounds = DataBounds {
        min_x: first.0,
        max_x: first.0,
        min_y: first.1,
        max_y: first.1,
    };
    for (x, y) in iter {
        bounds.min_x = bounds.min_x.min(x);
        bounds.max_x = bounds.max_x.max(x);
        bounds.min_y = bounds.min_y.min(y);
        bounds.max_y = bounds.max_y.max(y);
    }
    Some(bounds)
}

fn figure_layout(width_in: f64, height_in: f64, rows: usize, cols: usize) -> Vec<PanelLayout> {
    let width = width_in * DPI;
    let height = height_in * DPI;
    let margin_left = 26.0;
    let margin_right = 22.0;
    let margin_top = 22.0;
    let margin_bottom = 22.0;
    let gap_x = 26.0;
    let gap_y = 22.0;
    let content_width = width - margin_left - margin_right;
    let content_height = height - margin_top - margin_bottom;
    let panel_size = ((content_width - gap_x * (cols.saturating_sub(1) as f64)) / cols as f64)
        .min((content_height - gap_y * (rows.saturating_sub(1) as f64)) / rows as f64);
    let grid_width = panel_size * cols as f64 + gap_x * (cols.saturating_sub(1) as f64);
    let grid_height = panel_size * rows as f64 + gap_y * (rows.saturating_sub(1) as f64);
    let start_left = margin_left + ((content_width - grid_width) * 0.5).max(0.0);
    let start_top = margin_top + ((content_height - grid_height) * 0.5).max(0.0);
    let mut layouts = Vec::with_capacity(rows * cols);
    for row in 0..rows {
        for col in 0..cols {
            layouts.push(PanelLayout {
                left: start_left + col as f64 * (panel_size + gap_x),
                top: start_top + row as f64 * (panel_size + gap_y),
                width: panel_size,
                height: panel_size,
            });
        }
    }
    layouts
}

fn axis_layout(layout: &PanelLayout, footer_height: f64) -> AxisLayout {
    let left_reserve = 40.0;
    let right_reserve = 16.0;
    let top_reserve = 22.0;
    let bottom_reserve = 34.0 + footer_height;
    AxisLayout {
        x: layout.left + left_reserve,
        y: layout.top + top_reserve,
        width: (layout.width - left_reserve - right_reserve).max(40.0),
        height: (layout.height - top_reserve - bottom_reserve).max(40.0),
    }
}

fn legend_height(axis: &AxisScene) -> f64 {
    axis.legend
        .as_ref()
        .map(|legend| legend_height_from_count(legend.entries.len()))
        .unwrap_or(0.0)
}

fn legend_height_from_count(count: usize) -> f64 {
    if count == 0 {
        0.0
    } else {
        6.0 + count as f64 * 10.0
    }
}

fn colorbar_footer_height(axis: &AxisScene) -> f64 {
    if axis.colorbars.is_empty() {
        0.0
    } else {
        42.0 * axis.colorbars.len() as f64
    }
}

fn footer_height(axis: &AxisScene) -> f64 {
    legend_height(axis) + colorbar_footer_height(axis)
}

fn max_footer_height(fig: &FigureScene) -> f64 {
    fig.panels
        .iter()
        .map(|panel| footer_height(&panel.axis))
        .fold(0.0, f64::max)
}

fn figure_bounds(fig: &FigureScene, layouts: &[PanelLayout]) -> FigureBounds {
    let mut bounds = FigureBounds {
        min_x: f64::INFINITY,
        min_y: f64::INFINITY,
        max_x: f64::NEG_INFINITY,
        max_y: f64::NEG_INFINITY,
    };
    let footer_height = max_footer_height(fig);
    for panel in &fig.panels {
        let layout = &layouts[panel.row * fig.cols + panel.col];
        let axis = axis_layout(layout, footer_height);
        bounds.min_x = bounds.min_x.min(layout.left);
        bounds.min_y = bounds.min_y.min(axis.y - 18.0);
        bounds.max_x = bounds.max_x.max(layout.left + layout.width);
        bounds.max_y = bounds.max_y.max(layout.top + layout.height);
        bounds.min_x = bounds.min_x.min(axis.x - 34.0);
    }
    bounds
}

fn histogram_bins(values: &[f64], bins: usize) -> Vec<f64> {
    if values.is_empty() || bins == 0 {
        return Vec::new();
    }
    let min = values.iter().copied().fold(f64::INFINITY, f64::min);
    let max = values.iter().copied().fold(f64::NEG_INFINITY, f64::max);
    if (max - min).abs() < f64::EPSILON {
        let mut out = vec![0.0; bins];
        out[bins / 2] = 1.0;
        return out;
    }
    let mut counts = vec![0.0; bins];
    for value in values {
        let idx = (normalize(*value, min, max) * bins as f64).floor() as usize;
        let idx = idx.min(bins - 1);
        counts[idx] += 1.0;
    }
    let peak = counts.iter().copied().fold(0.0_f64, f64::max).max(1.0);
    counts.into_iter().map(|count| count / peak).collect()
}

fn histogram_bins_2d(values: &[Vec<f64>], bins: usize) -> Vec<f64> {
    let flat = values.iter().flat_map(|row| row.iter().copied()).collect::<Vec<_>>();
    histogram_bins(&flat, bins)
}

fn histogram_rects(
    values: &[f64],
    bins: usize,
    range: Option<(f64, f64)>,
    density: bool,
) -> PyResult<(Vec<(f64, f64, f64)>, f64, f64, f64)> {
    if values.is_empty() {
        return Err(PyValueError::new_err("histogram data must be non-empty"));
    }
    if bins == 0 {
        return Err(PyValueError::new_err("histogram bins must be positive"));
    }
    let (mut xmin, mut xmax) = range.unwrap_or_else(|| {
        (
            values.iter().copied().fold(f64::INFINITY, f64::min),
            values.iter().copied().fold(f64::NEG_INFINITY, f64::max),
        )
    });
    if !xmin.is_finite() || !xmax.is_finite() {
        return Err(PyValueError::new_err("histogram range must be finite"));
    }
    if xmax < xmin {
        return Err(PyValueError::new_err("histogram range must satisfy max >= min"));
    }
    if (xmax - xmin).abs() < f64::EPSILON {
        let pad = if xmin.abs() < 1.0 { 0.5 } else { xmin.abs() * 0.05 };
        xmin -= pad;
        xmax += pad;
    }
    let width = xmax - xmin;
    let bin_w = width / bins as f64;
    let mut counts = vec![0.0; bins];
    let mut kept = 0.0;
    for value in values {
        if *value < xmin || *value > xmax {
            continue;
        }
        let idx = (((*value - xmin) / width) * bins as f64).floor() as usize;
        let idx = idx.min(bins - 1);
        counts[idx] += 1.0;
        kept += 1.0;
    }
    if density && kept > 0.0 {
        for count in &mut counts {
            *count /= kept * bin_w;
        }
    }
    let ymax = counts.iter().copied().fold(0.0_f64, f64::max);
    let rects = counts
        .into_iter()
        .enumerate()
        .map(|(idx, count)| {
            let left = xmin + idx as f64 * bin_w;
            let right = left + bin_w;
            (left, right, count)
        })
        .collect::<Vec<_>>();
    Ok((rects, xmin, xmax, ymax))
}

fn expand_bounds(min: f64, max: f64) -> (f64, f64) {
    if !min.is_finite() || !max.is_finite() {
        return (0.0, 1.0);
    }
    if (max - min).abs() < f64::EPSILON {
        let pad = if min.abs() < 1.0 { 1.0 } else { min.abs() * 0.1 };
        return (min - pad, max + pad);
    }
    let pad = (max - min) * 0.05;
    (min - pad, max + pad)
}

fn expand_positive_bounds(min: f64, max: f64) -> (f64, f64) {
    let min = min.max(f64::MIN_POSITIVE);
    let max = max.max(min * 1.001);
    if (max - min).abs() < f64::EPSILON {
        return (min / 1.25, max * 1.25);
    }
    let lower = min / 1.1;
    let upper = max * 1.1;
    (lower.max(f64::MIN_POSITIVE), upper)
}

fn nice_ticks(min: f64, max: f64, target: usize) -> Vec<f64> {
    if !min.is_finite() || !max.is_finite() || min == max {
        return vec![min];
    }
    let span = nice_num(max - min, false);
    let step = nice_num(span / (target.saturating_sub(1) as f64), true);
    let start = (min / step).floor() * step;
    let end = (max / step).ceil() * step;
    let mut ticks = Vec::new();
    let mut value = start;
    while value <= end + step * 0.5 {
        if value >= min - step * 0.5 && value <= max + step * 0.5 {
            ticks.push(round_to(value, step));
        }
        value += step;
    }
    ticks
}

fn log_ticks(min: f64, max: f64) -> PyResult<Vec<f64>> {
    if min <= 0.0 || max <= 0.0 {
        return Err(PyValueError::new_err("log scales require strictly positive limits"));
    }
    let start = min.log10().floor() as i32;
    let end = max.log10().ceil() as i32;
    let mut ticks = Vec::new();
    for exp in start..=end {
        let value = 10f64.powi(exp);
        if value >= min * 0.999_999 && value <= max * 1.000_001 {
            ticks.push(value);
        }
    }
    if ticks.is_empty() {
        ticks.push(min);
        ticks.push(max);
    }
    Ok(ticks)
}

fn axis_ticks(min: f64, max: f64, scale: AxisScale, target: usize) -> PyResult<Vec<f64>> {
    match scale {
        AxisScale::Linear => Ok(nice_ticks(min, max, target)),
        AxisScale::Log => log_ticks(min, max),
    }
}

fn nice_num(range: f64, round: bool) -> f64 {
    let exponent = range.abs().log10().floor();
    let fraction = range / 10f64.powf(exponent);
    let nice_fraction = if round {
        if fraction < 1.5 {
            1.0
        } else if fraction < 3.0 {
            2.0
        } else if fraction < 7.0 {
            5.0
        } else {
            10.0
        }
    } else if fraction <= 1.0 {
        1.0
    } else if fraction <= 2.0 {
        2.0
    } else if fraction <= 5.0 {
        5.0
    } else {
        10.0
    };
    nice_fraction * 10f64.powf(exponent)
}

fn round_to(value: f64, step: f64) -> f64 {
    let digits = if step.abs() >= 1.0 {
        0
    } else {
        (-step.abs().log10().floor() as i32 + 1).max(0)
    };
    let scale = 10f64.powi(digits);
    (value * scale).round() / scale
}

fn map_x(x: f64, xmin: f64, xmax: f64, layout: &AxisLayout) -> f64 {
    layout.x + (x - xmin) / (xmax - xmin) * layout.width
}

fn map_y(y: f64, ymin: f64, ymax: f64, layout: &AxisLayout) -> f64 {
    layout.y + layout.height - (y - ymin) / (ymax - ymin) * layout.height
}

fn map_x_scaled(x: f64, xmin: f64, xmax: f64, scale: AxisScale, layout: &AxisLayout) -> PyResult<f64> {
    match scale {
        AxisScale::Linear => Ok(map_x(x, xmin, xmax, layout)),
        AxisScale::Log => {
            if x <= 0.0 || xmin <= 0.0 || xmax <= 0.0 {
                return Err(PyValueError::new_err("log scales require strictly positive x values"));
            }
            Ok(map_x(x.log10(), xmin.log10(), xmax.log10(), layout))
        }
    }
}

fn map_y_scaled(y: f64, ymin: f64, ymax: f64, scale: AxisScale, layout: &AxisLayout) -> PyResult<f64> {
    match scale {
        AxisScale::Linear => Ok(map_y(y, ymin, ymax, layout)),
        AxisScale::Log => {
            if y <= 0.0 || ymin <= 0.0 || ymax <= 0.0 {
                return Err(PyValueError::new_err("log scales require strictly positive y values"));
            }
            Ok(map_y(y.log10(), ymin.log10(), ymax.log10(), layout))
        }
    }
}

fn svg_style(style: &Style) -> String {
    format!(
        "fill=\"{}\" stroke=\"{}\" stroke-width=\"{:.2}\" opacity=\"{:.3}\"",
        style.fill.as_ref().map_or("none".to_string(), Color::to_hex),
        style.stroke.as_ref().map_or("none".to_string(), Color::to_hex),
        style.stroke_width_pt,
        style.opacity
    )
}

fn format_tick(value: f64) -> String {
    if value.abs() >= 1000.0 || (value.abs() > 0.0 && value.abs() < 0.01) {
        format!("{value:.1e}")
    } else if (value.round() - value).abs() < 1e-6 {
        format!("{value:.0}")
    } else if ((value * 10.0).round() - value * 10.0).abs() < 1e-6 {
        format!("{value:.1}")
    } else {
        format!("{value:.2}")
    }
}

fn format_tick_scaled(value: f64, scale: AxisScale) -> String {
    match scale {
        AxisScale::Linear => format_tick(value),
        AxisScale::Log => {
            let exponent = value.log10().round() as i32;
            if (10f64.powi(exponent) - value).abs() / value.abs().max(1.0) < 1e-6 {
                format!("10^{}", exponent)
            } else {
                format_tick(value)
            }
        }
    }
}

fn xml_escape(value: &str) -> String {
    value
        .replace('&', "&amp;")
        .replace('<', "&lt;")
        .replace('>', "&gt;")
}

fn svg_rich_text(value: &str) -> String {
    render_math_chars(&value.chars().collect::<Vec<_>>())
}

fn render_math_chars(chars: &[char]) -> String {
    let mut out = String::new();
    let mut i = 0usize;
    while i < chars.len() {
        match chars[i] {
            '$' => {
                i += 1;
            }
            '\\' => {
                let (token, next) = parse_command(chars, i + 1);
                if token == "frac" {
                    let (num, next_num) = parse_group_expr(chars, next);
                    let (den, next_den) = parse_group_expr(chars, next_num);
                    out.push_str("<tspan baseline-shift=\"super\" font-size=\"70%\">");
                    out.push_str(&num);
                    out.push_str("</tspan>");
                    out.push('⁄');
                    out.push_str("<tspan baseline-shift=\"sub\" font-size=\"70%\">");
                    out.push_str(&den);
                    out.push_str("</tspan>");
                    i = next_den;
                    continue;
                }
                if let Some(symbol) = math_symbol(&token) {
                    out.push_str(symbol);
                    i = next;
                    continue;
                }
                if !token.is_empty() {
                    out.push_str(&xml_escape(&token));
                } else {
                    out.push('\\');
                }
                i = next;
            }
            '^' => {
                let (script, next) = parse_script_expr(chars, i + 1);
                if !script.is_empty() {
                    out.push_str("<tspan baseline-shift=\"super\" font-size=\"70%\">");
                    out.push_str(&script);
                    out.push_str("</tspan>");
                    i = next;
                    continue;
                }
                out.push('^');
                i += 1;
            }
            '_' => {
                let (script, next) = parse_script_expr(chars, i + 1);
                if !script.is_empty() {
                    out.push_str("<tspan baseline-shift=\"sub\" font-size=\"70%\">");
                    out.push_str(&script);
                    out.push_str("</tspan>");
                    i = next;
                    continue;
                }
                out.push('_');
                i += 1;
            }
            ch => {
                out.push_str(&xml_escape(&ch.to_string()));
                i += 1;
            }
        }
    }
    out
}

fn parse_command(chars: &[char], start: usize) -> (String, usize) {
    let mut token = String::new();
    let mut i = start;
    while i < chars.len() && chars[i].is_ascii_alphabetic() {
        token.push(chars[i]);
        i += 1;
    }
    (token, i)
}

fn parse_group_expr(chars: &[char], start: usize) -> (String, usize) {
    if start >= chars.len() {
        return (String::new(), start);
    }
    if chars[start] == '{' {
        let mut depth = 1usize;
        let mut i = start + 1;
        let mut buf = Vec::new();
        while i < chars.len() && depth > 0 {
            if chars[i] == '{' {
                depth += 1;
                buf.push(chars[i]);
            } else if chars[i] == '}' {
                depth -= 1;
                if depth > 0 {
                    buf.push(chars[i]);
                }
            } else {
                buf.push(chars[i]);
            }
            i += 1;
        }
        return (render_math_chars(&buf), i);
    }
    (xml_escape(&chars[start].to_string()), start + 1)
}

fn parse_script_expr(chars: &[char], start: usize) -> (String, usize) {
    if start >= chars.len() {
        return (String::new(), start);
    }
    if chars[start] == '{' {
        return parse_group_expr(chars, start);
    }
    if chars[start] == '\\' {
        let (token, next) = parse_command(chars, start + 1);
        if let Some(symbol) = math_symbol(&token) {
            return (symbol.to_string(), next);
        }
        if !token.is_empty() {
            return (xml_escape(&token), next);
        }
        return (xml_escape("\\"), next);
    }
    (xml_escape(&chars[start].to_string()), start + 1)
}

fn math_symbol(token: &str) -> Option<&'static str> {
    match token {
        "alpha" => Some("α"),
        "beta" => Some("β"),
        "gamma" => Some("γ"),
        "delta" => Some("δ"),
        "epsilon" => Some("ε"),
        "theta" => Some("θ"),
        "lambda" => Some("λ"),
        "mu" => Some("μ"),
        "pi" => Some("π"),
        "sigma" => Some("σ"),
        "phi" => Some("φ"),
        "psi" => Some("ψ"),
        "omega" => Some("ω"),
        "Gamma" => Some("Γ"),
        "Delta" => Some("Δ"),
        "Theta" => Some("Θ"),
        "Lambda" => Some("Λ"),
        "Pi" => Some("Π"),
        "Sigma" => Some("Σ"),
        "Phi" => Some("Φ"),
        "Psi" => Some("Ψ"),
        "Omega" => Some("Ω"),
        "sum" => Some("∑"),
        "int" => Some("∫"),
        "partial" => Some("∂"),
        "times" => Some("×"),
        "cdot" => Some("·"),
        "dots" | "ldots" => Some("…"),
        _ => None,
    }
}

fn xml_attr_escape(value: &str) -> String {
    value
        .replace('&', "&amp;")
        .replace('<', "&lt;")
        .replace('>', "&gt;")
        .replace('"', "&quot;")
        .replace('\'', "&apos;")
}

fn normalize_font_family(value: &str) -> String {
    let mut families = value
        .split(',')
        .map(str::trim)
        .filter(|part| !part.is_empty())
        .map(|part| {
            if part.eq_ignore_ascii_case("sans-serif") {
                "sans-serif".to_string()
            } else if part.starts_with('"') || part.starts_with('\'') {
                part.to_string()
            } else {
                format!("'{part}'")
            }
        })
        .collect::<Vec<_>>();
    if !families.iter().any(|part| part == "sans-serif") {
        families.push("sans-serif".to_string());
    }
    families.join(", ")
}

fn parse_color_input(
    color: Option<&Bound<'_, PyAny>>,
    len: usize,
    default_cmap: String,
    default_color: Color,
) -> PyResult<ColorInput> {
    match color {
        None => Ok(ColorInput::Constant(default_color)),
        Some(value) => {
            if value.is_instance_of::<pyo3::types::PyString>() {
                Ok(ColorInput::Constant(parse_named_or_hex_color(value)?))
            } else {
                let values = extract_vec_f64(value)?;
                if values.len() != len {
                    return Err(PyValueError::new_err("mapped scatter color array must match data length"));
                }
                Ok(ColorInput::Mapped(values, default_cmap))
            }
        }
    }
}

fn parse_grouped_color_input(
    color: Option<&Bound<'_, PyAny>>,
    groups: &[Vec<f64>],
    default_cmap: String,
    default_color: Color,
) -> PyResult<ColorInput> {
    match color {
        None => Ok(ColorInput::Constant(default_color)),
        Some(value) => {
            if value.is_instance_of::<pyo3::types::PyString>() {
                return Ok(ColorInput::Constant(parse_named_or_hex_color(value)?));
            }
            let total_len = groups.iter().map(Vec::len).sum::<usize>();
            if let Ok(flat) = extract_vec_f64(value) {
                if flat.len() != total_len {
                    return Err(PyValueError::new_err(
                        "point_color must match the total number of violin points",
                    ));
                }
                return Ok(ColorInput::Mapped(flat, default_cmap));
            }
            let grouped = extract_groups(value)?;
            if grouped.len() != groups.len() {
                return Err(PyValueError::new_err(
                    "point_color group count must match violin group count",
                ));
            }
            let mut flat = Vec::with_capacity(total_len);
            for (color_group, data_group) in grouped.iter().zip(groups.iter()) {
                if color_group.len() != data_group.len() {
                    return Err(PyValueError::new_err(
                        "each point_color group must match the corresponding violin group length",
                    ));
                }
                flat.extend(color_group.iter().copied());
            }
            Ok(ColorInput::Mapped(flat, default_cmap))
        }
    }
}

fn mapped_group_colors(color_input: &ColorInput, offset: usize, group_len: usize) -> Vec<Color> {
    match color_input {
        ColorInput::Constant(color) => vec![color.clone(); group_len],
        ColorInput::Mapped(values, cmap_name) => {
            let min = values.iter().copied().fold(f64::INFINITY, f64::min);
            let max = values.iter().copied().fold(f64::NEG_INFINITY, f64::max);
            values[offset..offset + group_len]
                .iter()
                .map(|value| sample_colormap(cmap_name, normalize(*value, min, max)))
                .collect()
        }
    }
}

fn violin_point_offset(idx: usize, len: usize, width: f64) -> f64 {
    if len <= 1 {
        return 0.0;
    }
    let centered = (idx as f64 + 0.5) / len as f64 - 0.5;
    centered * width * 2.0
}

fn parse_named_or_hex_color(value: &Bound<'_, PyAny>) -> PyResult<Color> {
    let literal: String = value
        .extract()
        .map_err(|_| PyTypeError::new_err("color must be a named color or #RRGGBB string"))?;
    parse_color_literal(&literal)
}

fn parse_color_literal(value: &str) -> PyResult<Color> {
    let lower = value.to_ascii_lowercase();
    let named = match lower.as_str() {
        "black" => Some(Color(27, 31, 36)),
        "gray" | "grey" => Some(Color(120, 126, 134)),
        "orange" => Some(Color(226, 134, 42)),
        "blue" => Some(Color(53, 102, 153)),
        "red" => Some(Color(192, 71, 58)),
        "green" => Some(Color(67, 136, 99)),
        _ => None,
    };
    if let Some(color) = named {
        return Ok(color);
    }
    if let Some(stripped) = lower.strip_prefix('#') {
        if stripped.len() == 6 {
            let r = u8::from_str_radix(&stripped[0..2], 16).map_err(|_| PyValueError::new_err("invalid hex color"))?;
            let g = u8::from_str_radix(&stripped[2..4], 16).map_err(|_| PyValueError::new_err("invalid hex color"))?;
            let b = u8::from_str_radix(&stripped[4..6], 16).map_err(|_| PyValueError::new_err("invalid hex color"))?;
            return Ok(Color(r, g, b));
        }
    }
    Err(PyValueError::new_err(format!("unsupported color '{value}'")))
}

fn parse_axis_scale(value: &str) -> PyResult<AxisScale> {
    match value {
        "linear" => Ok(AxisScale::Linear),
        "log" => Ok(AxisScale::Log),
        other => Err(PyValueError::new_err(format!(
            "unsupported axis scale '{other}'; use 'linear' or 'log'"
        ))),
    }
}

fn parse_y_axis_side(value: &str) -> PyResult<YAxisSide> {
    match value {
        "left" => Ok(YAxisSide::Left),
        "right" => Ok(YAxisSide::Right),
        other => Err(PyValueError::new_err(format!(
            "unsupported yaxis '{other}'; use 'left' or 'right'"
        ))),
    }
}

impl Color {
    fn to_hex(&self) -> String {
        format!("#{:02x}{:02x}{:02x}", self.0, self.1, self.2)
    }
}

impl Theme {
    fn from_str(value: &str) -> PyResult<Self> {
        match value {
            "publication" | "nature" | "light" => Ok(Self::Publication),
            "dark" => Ok(Self::Dark),
            other => Err(PyValueError::new_err(format!(
                "unsupported theme '{other}'; use 'publication', 'nature', 'light', or 'dark'"
            ))),
        }
    }

    fn background_color(&self) -> Color {
        match self {
            Self::Publication => Color(255, 255, 255),
            Self::Dark => Color(17, 23, 31),
        }
    }

    fn text_color(&self) -> Color {
        match self {
            Self::Publication => Color(25, 28, 32),
            Self::Dark => Color(231, 237, 243),
        }
    }

    fn axis_color(&self) -> Color {
        match self {
            Self::Publication => Color(101, 109, 118),
            Self::Dark => Color(128, 145, 166),
        }
    }

    fn tick_color(&self) -> Color {
        match self {
            Self::Publication => Color(112, 120, 129),
            Self::Dark => Color(109, 124, 143),
        }
    }

    fn tick_label_color(&self) -> Color {
        match self {
            Self::Publication => Color(73, 79, 87),
            Self::Dark => Color(173, 186, 199),
        }
    }

    fn scatter_default(&self) -> Color {
        match self {
            Self::Publication => Color(59, 102, 140),
            Self::Dark => Color(124, 169, 214),
        }
    }

    fn line_default(&self) -> Color {
        match self {
            Self::Publication => Color(33, 37, 42),
            Self::Dark => Color(233, 238, 244),
        }
    }

    fn bar_default(&self) -> Color {
        match self {
            Self::Publication => Color(156, 182, 205),
            Self::Dark => Color(92, 134, 171),
        }
    }

    fn violin_fill(&self) -> Color {
        match self {
            Self::Publication => Color(214, 226, 236),
            Self::Dark => Color(70, 97, 123),
        }
    }

    fn violin_stroke(&self) -> Color {
        match self {
            Self::Publication => Color(90, 118, 145),
            Self::Dark => Color(188, 209, 229),
        }
    }

    fn box_fill(&self) -> Color {
        match self {
            Self::Publication => Color(228, 236, 243),
            Self::Dark => Color(76, 92, 108),
        }
    }

    fn box_stroke(&self) -> Color {
        match self {
            Self::Publication => Color(84, 102, 120),
            Self::Dark => Color(201, 214, 227),
        }
    }

    fn right_axis_color(&self) -> Color {
        match self {
            Self::Publication => Color(178, 56, 42),
            Self::Dark => Color(236, 116, 101),
        }
    }
}

fn sample_colormap(name: &str, t: f64) -> Color {
    let t = t.clamp(0.0, 1.0);
    let stops = match name {
        "gray" => &[(0.0, Color(245, 245, 245)), (1.0, Color(45, 45, 45))][..],
        "vik" => &[
            (0.0, Color(0, 74, 135)),
            (0.5, Color(245, 245, 245)),
            (1.0, Color(178, 34, 34)),
        ][..],
        _ => &[
            (0.0, Color(20, 60, 120)),
            (0.35, Color(39, 121, 138)),
            (0.65, Color(118, 170, 91)),
            (1.0, Color(244, 213, 89)),
        ][..],
    };
    for window in stops.windows(2) {
        let (t0, c0) = (&window[0].0, &window[0].1);
        let (t1, c1) = (&window[1].0, &window[1].1);
        if t >= *t0 && t <= *t1 {
            let local = if (t1 - t0).abs() < f64::EPSILON {
                0.0
            } else {
                (t - t0) / (t1 - t0)
            };
            return Color(
                lerp_u8(c0.0, c1.0, local),
                lerp_u8(c0.1, c1.1, local),
                lerp_u8(c0.2, c1.2, local),
            );
        }
    }
    stops.last().map(|(_, c)| c.clone()).unwrap_or(Color(0, 0, 0))
}

fn lerp_u8(a: u8, b: u8, t: f64) -> u8 {
    ((a as f64) + ((b as f64) - (a as f64)) * t).round() as u8
}

fn normalize(value: f64, min: f64, max: f64) -> f64 {
    if (max - min).abs() < f64::EPSILON {
        0.5
    } else {
        (value - min) / (max - min)
    }
}

fn extract_vec_f64(value: &Bound<'_, PyAny>) -> PyResult<Vec<f64>> {
    if let Ok(items) = value.extract::<Vec<f64>>() {
        return Ok(items);
    }
    if value.hasattr("tolist")? {
        let py_list = value.call_method0("tolist")?;
        if let Ok(items) = py_list.extract::<Vec<f64>>() {
            return Ok(items);
        }
    }
    let seq = value
        .downcast::<PySequence>()
        .map_err(|_| PyTypeError::new_err("expected a 1D sequence of floats"))?;
    let mut out = Vec::with_capacity(seq.len()?);
    for item in seq.iter()? {
        out.push(item?.extract::<f64>()?);
    }
    Ok(out)
}

fn extract_matrix_f64(value: &Bound<'_, PyAny>) -> PyResult<Vec<Vec<f64>>> {
    if let Ok(rows) = value.extract::<Vec<Vec<f64>>>() {
        return Ok(rows);
    }
    if value.hasattr("tolist")? {
        let py_list = value.call_method0("tolist")?;
        if let Ok(rows) = py_list.extract::<Vec<Vec<f64>>>() {
            return Ok(rows);
        }
    }
    let seq = value
        .downcast::<PySequence>()
        .map_err(|_| PyTypeError::new_err("expected a 2D sequence of floats"))?;
    let mut rows = Vec::with_capacity(seq.len()?);
    let mut expected: Option<usize> = None;
    for item in seq.iter()? {
        let row = extract_vec_f64(&item?)?;
        if let Some(width) = expected {
            if row.len() != width {
                return Err(PyValueError::new_err("all field rows must have the same length"));
            }
        } else {
            expected = Some(row.len());
        }
        rows.push(row);
    }
    Ok(rows)
}

fn extract_groups(value: &Bound<'_, PyAny>) -> PyResult<Vec<Vec<f64>>> {
    let seq = value
        .downcast::<PySequence>()
        .map_err(|_| PyTypeError::new_err("expected a sequence of 1D numeric groups"))?;
    let mut groups = Vec::with_capacity(seq.len()?);
    for item in seq.iter()? {
        groups.push(extract_vec_f64(&item?)?);
    }
    Ok(groups)
}

fn default_position_labels(n: usize) -> Vec<String> {
    (1..=n).map(|idx| idx.to_string()).collect()
}

fn min_max(values: &[f64]) -> (f64, f64) {
    let mut min = f64::INFINITY;
    let mut max = f64::NEG_INFINITY;
    for value in values {
        min = min.min(*value);
        max = max.max(*value);
    }
    (min, max)
}

fn quantile(values: &[f64], p: f64) -> f64 {
    let mut sorted = values.to_vec();
    sorted.sort_by(|a, b| a.total_cmp(b));
    if sorted.len() == 1 {
        return sorted[0];
    }
    let position = p.clamp(0.0, 1.0) * (sorted.len() - 1) as f64;
    let lower = position.floor() as usize;
    let upper = position.ceil() as usize;
    if lower == upper {
        sorted[lower]
    } else {
        lerp(sorted[lower], sorted[upper], position - lower as f64)
    }
}

fn estimate_bandwidth(values: &[f64]) -> f64 {
    let std = standard_deviation(values);
    let n = values.len().max(2) as f64;
    (1.06 * std * n.powf(-0.2)).max(1e-3)
}

fn standard_deviation(values: &[f64]) -> f64 {
    let mean = values.iter().sum::<f64>() / values.len().max(1) as f64;
    let var = values.iter().map(|v| (v - mean).powi(2)).sum::<f64>() / values.len().max(1) as f64;
    var.sqrt()
}

fn kde(values: &[f64], y: f64, bandwidth: f64) -> f64 {
    let norm = 1.0 / ((2.0 * PI).sqrt() * bandwidth * values.len() as f64);
    values
        .iter()
        .map(|value| {
            let z = (y - *value) / bandwidth;
            (-0.5 * z * z).exp()
        })
        .sum::<f64>()
        * norm
}

fn lerp(a: f64, b: f64, t: f64) -> f64 {
    a + (b - a) * t
}

fn lock_err<T>(_: std::sync::PoisonError<T>) -> PyErr {
    PyRuntimeError::new_err("internal figure lock poisoned")
}

fn io_err(err: std::io::Error) -> PyErr {
    PyRuntimeError::new_err(err.to_string())
}
