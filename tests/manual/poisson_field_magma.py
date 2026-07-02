from __future__ import annotations

from pathlib import Path

import numpy as np

import cleanfig as cf


def save_outputs(fig: cf.Figure, stem: str) -> None:
    out_dir = Path("tests/output")
    out_dir.mkdir(parents=True, exist_ok=True)
    fig.save(str(out_dir / f"{stem}.svg"))
    fig.save(str(out_dir / f"{stem}.html"))
    if cf.BACKEND == "rust":
        fig.save(str(out_dir / f"{stem}.pdf"))


def main(stem: str = "poisson_field_magma") -> None:
    rng = np.random.default_rng(17)
    n = 512

    yy, xx = np.indices((n, n))
    mix_probability = 0.32 + 0.28 * np.sin(xx / 37.0) * np.cos(yy / 53.0)
    mix_probability = np.clip(mix_probability, 0.08, 0.92)
    low_mode = rng.poisson(4.0, size=(n, n))
    high_mode = rng.poisson(18.0, size=(n, n))
    selector = rng.random((n, n)) < mix_probability
    grid = np.where(selector, high_mode, low_mode).astype(float)

    fig = cf.figure(width="single", height=4.2, grid=(1, 1), theme="publication")
    ax = fig.panel(0, 0)
    handle = ax.field(grid, cmap="magma")
    ax.xlabel("Grid column")
    ax.ylabel("Grid row")
    ax.colorbar(handle, label="Poisson counts [-]")

    save_outputs(fig, stem)


if __name__ == "__main__":
    main()
