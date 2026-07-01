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


def main(theme: str = "publication", stem: str = "four_panels_figure") -> None:
    np.random.seed(1)

    x = np.random.rand(100) * 100
    y = np.exp(x / 20) + np.random.rand(100) * 100
    x_map = np.random.rand(10, 10)

    fig = cf.figure(width="double", height=8.0, grid=(2, 2), panel_labels=True, theme=theme)

    ax = fig.panel(0, 0)
    sc = ax.scatter(x, y, color=np.log(x * y), size=6, alpha=0.65)
    ax.xlabel("x-label [unit]")
    ax.ylabel("y-label [unit]")
    ax.limits(x=(0, 100), y=(0, 200))
    ax.colorbar(sc, label="Colorbar label [unit]", placement="inside-left")

    ax = fig.panel(0, 1)
    x_reg = np.linspace(0, 100, 100)
    y_reg1 = np.poly1d(np.polyfit(x, y, 2))(x_reg)
    y_reg2 = np.poly1d(np.polyfit(x, y, 3))(x_reg)
    ax.scatter(x, y, color="orange", label="Data", size=6, alpha=0.65)
    ax.line(x_reg, y_reg1, label="Polynomial regression, n = 2")
    ax.line(x_reg, y_reg2, color="#6d8fae", label="Polynomial regression, n = 3")
    ax.xlabel("x-label [unit]")
    ax.ylabel("y-label [unit]")
    ax.limits(x=(0, 100), y=(0, 200))
    ax.legend()

    ax = fig.panel(1, 0)
    ax.bar(["Vowels", "Consonants"], [23, 81])
    ax.ylabel("Frequency")

    ax = fig.panel(1, 1)
    field = ax.field(x_map, cmap="batlow")
    ax.xlabel("x-label [unit]")
    ax.ylabel("y-label [unit]")
    ax.colorbar(field, label="Colorbar label [unit]")

    save_outputs(fig, stem)


if __name__ == "__main__":
    main()
