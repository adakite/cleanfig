from pathlib import Path

import numpy as np

import cleanfig as cf


def save_outputs(fig: cf.Figure, stem: str) -> None:
    out_dir = Path("examples/output")
    out_dir.mkdir(parents=True, exist_ok=True)
    fig.save(str(out_dir / f"{stem}.svg"))
    fig.save(str(out_dir / f"{stem}.html"))
    if cf.BACKEND == "rust":
        fig.save(str(out_dir / f"{stem}.pdf"))


def main(theme: str = "publication", stem: str = "violin_box_light") -> None:
    np.random.seed(19680801)
    all_data = [np.random.normal(0, std, 100) for std in range(6, 10)]

    fig = cf.figure(width="double", height=4.0, grid=(1, 2), panel_labels=True, theme=theme)

    ax = fig.panel(0, 0)
    metric = [np.linspace(0, 1, len(group)) for group in all_data]
    handle = ax.violin(
        all_data,
        labels=["L", "H", "V", "w"],
        show_median=True,
        points=True,
        point_color=metric,
        point_cmap="vik",
    )
    ax.ylabel("Observed values")
    if handle is not None:
        ax.colorbar(handle, label="Auxiliary metric")

    ax = fig.panel(0, 1)
    ax.box(all_data, labels=["L", "H", "V", "w"])
    ax.ylabel("Observed values")

    save_outputs(fig, stem)


if __name__ == "__main__":
    main()
