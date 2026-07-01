from pathlib import Path

import numpy as np
import pytest

import cleanfig as cf


def test_public_api_surface() -> None:
    fig = cf.figure(width="single", height=3.0, grid=(1, 1), panel_labels=True)
    ax = fig.panel(0, 0)
    for name in [
        "scatter",
        "line",
        "errorbar",
        "bar",
        "histogram",
        "field",
        "colorbar",
        "violin",
        "box",
        "legend",
        "xlabel",
        "ylabel",
        "right_ylabel",
        "xscale",
        "yscale",
        "limits",
        "right_limits",
    ]:
        assert hasattr(ax, name), name


def test_svg_generation_and_panel_labels(tmp_path: Path) -> None:
    fig = cf.figure(width="double", height=4.0, grid=(1, 2), panel_labels=True)
    ax0 = fig.panel(0, 0)
    ax0.scatter([0, 1, 2], [1, 2, 3], color="orange", label="Data")
    ax0.line([0, 1, 2], [1, 1.5, 2.5], label="Fit")
    ax0.xlabel("x")
    ax0.ylabel("y")

    ax1 = fig.panel(0, 1)
    ax1.bar(["A", "B"], [2, 3])
    ax1.ylabel("value")

    out = tmp_path / "figure.svg"
    fig.save(str(out))
    text = out.read_text()

    assert ">A<" in text
    assert ">B<" in text
    assert "<circle" in text
    assert "<path" in text
    assert "<rect" in text
    assert ">A200<" not in text
    assert ">B200<" not in text


def test_field_is_vector_only(tmp_path: Path) -> None:
    fig = cf.figure(width="single", height=3.0, grid=(1, 1))
    ax = fig.panel(0, 0)
    field = ax.field(np.arange(25, dtype=float).reshape(5, 5))
    ax.colorbar(field, label="Intensity")

    out = tmp_path / "field.svg"
    fig.save(str(out))
    text = out.read_text()

    assert "<image" not in text
    assert text.count("<rect") >= 25


def test_histogram_svg_generation(tmp_path: Path) -> None:
    fig = cf.figure(width="single", height=3.0, grid=(1, 1))
    ax = fig.panel(0, 0)
    ax.histogram([0.0, 0.2, 0.4, 0.8, 1.2, 1.25, 1.4], bins=4, color="blue", label="dist")
    ax.xlabel("value")
    ax.ylabel("count")
    ax.legend()

    out = tmp_path / "histogram.svg"
    fig.save(str(out))
    text = out.read_text()

    assert text.count("<rect") >= 5
    assert ">dist<" in text
    assert ">value<" in text
    assert ">count<" in text


def test_log_scales_svg_generation(tmp_path: Path) -> None:
    fig = cf.figure(width="single", height=3.0, grid=(1, 1))
    ax = fig.panel(0, 0)
    ax.line([1, 10, 100], [1, 10, 1000])
    ax.xscale("log")
    ax.yscale("log")
    ax.xlabel("frequency")
    ax.ylabel("power")

    out = tmp_path / "loglog.svg"
    fig.save(str(out))
    text = out.read_text()

    assert 'baseline-shift="super"' in text
    assert ">frequency<" in text
    assert ">power<" in text


def test_superscript_markup_in_labels(tmp_path: Path) -> None:
    fig = cf.figure(width="single", height=3.0, grid=(1, 1))
    ax = fig.panel(0, 0)
    ax.line([1, 2], [1, 4])
    ax.ylabel("Volume [m^3]")

    out = tmp_path / "sup.svg"
    fig.save(str(out))
    text = out.read_text()

    assert 'baseline-shift="super"' in text
    assert ">3</tspan>" in text


def test_inline_math_markup_in_labels(tmp_path: Path) -> None:
    fig = cf.figure(width="single", height=3.0, grid=(1, 1))
    ax = fig.panel(0, 0)
    ax.line([0, 1], [0, 1], label=r"\alpha_i")
    ax.ylabel(r"$\partial_t u = \frac{\alpha_0 + \beta}{\sum_i x_i} \times \pi$")
    ax.legend()

    out = tmp_path / "math.svg"
    fig.save(str(out))
    text = out.read_text()

    assert "α" in text
    assert "∂" in text
    assert "∑" in text
    assert "×" in text
    assert "⁄" in text
    assert 'baseline-shift="sub"' in text


def test_dual_y_axis_svg_generation(tmp_path: Path) -> None:
    fig = cf.figure(width="single", height=3.0, grid=(1, 1))
    ax = fig.panel(0, 0)
    ax.line([0, 1, 2], [1, 2, 3], label="left")
    ax.line([0, 1, 2], [10, 20, 15], yaxis="right", label="right")
    ax.ylabel("left axis")
    ax.right_ylabel("right axis")

    out = tmp_path / "dual_y.svg"
    fig.save(str(out))
    text = out.read_text()

    assert ">left axis<" in text
    assert ">right axis<" in text
    assert "#b2382a" in text or "#ec7465" in text


def test_line_and_errorbars_svg_generation(tmp_path: Path) -> None:
    fig = cf.figure(width="single", height=3.0, grid=(1, 1))
    ax = fig.panel(0, 0)
    ax.errorbar([0, 1, 2, 3], [1.0, 2.0, 1.5, 2.5], ymin=[0.8, 1.8, 1.3, 2.2], ymax=[1.2, 2.2, 1.7, 2.8])
    ax.line([0, 1, 2, 3], [1.0, 2.0, 1.5, 2.5], label="trend")
    ax.legend()

    out = tmp_path / "line_errorbar.svg"
    fig.save(str(out))
    text = out.read_text()

    assert text.count("<path") >= 1
    assert text.count("<line") >= 8
    assert ">trend<" in text


def test_publication_theme_is_default_and_white(tmp_path: Path) -> None:
    fig = cf.figure(width="single", height=3.0, grid=(1, 1))
    ax = fig.panel(0, 0)
    ax.line([0, 1], [0, 1], label="trend")
    ax.legend()

    out = tmp_path / "publication.svg"
    fig.save(str(out))
    text = out.read_text()

    assert "#ffffff" in text
    assert text.count('class="cf-axis"') == 2
    assert "legend-frame" not in text
    assert 'font-size:8.6px' in text


@pytest.mark.skipif(getattr(cf, "BACKEND", None) != "rust", reason="PDF export requires the Rust backend")
def test_pdf_generation(tmp_path: Path) -> None:
    fig = cf.figure(width="single", height=3.0, grid=(1, 1), panel_labels=True)
    ax = fig.panel(0, 0)
    ax.scatter([0, 1, 2], [1, 2, 3], color="orange")
    ax.xlabel("x")
    ax.ylabel("y")

    out = tmp_path / "figure.pdf"
    fig.save(str(out))
    assert out.read_bytes().startswith(b"%PDF-")


def test_dark_theme_svg_generation(tmp_path: Path) -> None:
    fig = cf.figure(width="single", height=3.0, grid=(1, 1), theme="dark")
    ax = fig.panel(0, 0)
    ax.line([0, 1], [0, 1])

    out = tmp_path / "dark.svg"
    fig.save(str(out))
    text = out.read_text()

    assert "#11171f" in text
    assert "#e7edf3" in text


def test_colorbar_binned_default_and_continuous_optional(tmp_path: Path) -> None:
    fig0 = cf.figure(width="single", height=3.2, grid=(1, 1))
    ax0 = fig0.panel(0, 0)
    handle0 = ax0.scatter([0, 1, 2, 3, 4, 5], [1, 2, 3, 4, 5, 6], color=[0.0, 0.1, 0.2, 0.8, 0.9, 1.0])
    ax0.colorbar(handle0, label="metric")

    out0 = tmp_path / "default_binned.svg"
    fig0.save(str(out0))
    text0 = out0.read_text()
    assert "<linearGradient" not in text0
    assert text0.count('fill="#') >= 6

    fig = cf.figure(width="single", height=3.2, grid=(1, 1))
    ax = fig.panel(0, 0)
    handle = ax.scatter([0, 1, 2], [1, 2, 3], color=[0.0, 0.5, 1.0])
    ax.colorbar(handle, label="metric", style="continuous")

    out = tmp_path / "continuous.svg"
    fig.save(str(out))
    text = out.read_text()
    assert "<linearGradient" in text

    fig2 = cf.figure(width="single", height=3.2, grid=(1, 1))
    ax2 = fig2.panel(0, 0)
    handle2 = ax2.scatter([0, 1, 2], [1, 2, 3], color=[0.0, 0.5, 1.0])
    ax2.colorbar(handle2, label="metric", style="binned")
    out2 = tmp_path / "binned.svg"
    fig2.save(str(out2))
    text2 = out2.read_text()
    assert "<linearGradient" not in text2


def test_violin_hides_x_axis_and_supports_mapped_points(tmp_path: Path) -> None:
    fig = cf.figure(width="single", height=3.2, grid=(1, 1))
    ax = fig.panel(0, 0)
    handle = ax.violin(
        [[0.0, 0.5, 1.0], [1.5, 2.0, 2.5]],
        labels=["A", "B"],
        show_median=True,
        points=True,
        point_color=[[10.0, 20.0, 30.0], [30.0, 20.0, 10.0]],
        point_cmap="vik",
    )
    assert handle is not None
    ax.colorbar(handle, label="metric")

    out = tmp_path / "violin.svg"
    fig.save(str(out))
    text = out.read_text()

    assert text.count('class="cf-axis"') >= 1
    assert ">A<" in text and ">B<" in text
    assert text.count("<circle") >= 6
