from pathlib import Path

import numpy as np

import cleanfig as cf


def main(theme: str = "light", stem: str = "basic_line") -> None:
    x = np.linspace(0.0, 10.0, 200)
    y = np.sin(x)
    samples = y[::20]

    fig = cf.figure(width="single", height=3.4, grid=(1, 1), theme=theme)
    ax = fig.panel(0, 0)
    ax.line(x, y, label=r"$u(t) = \sin(\omega t)$")
    ax.scatter(x[::20], samples, size=4.2, label=r"$u_i$")
    ax.xlabel(r"Time $t$ [$\omega^{-1}$]")
    ax.ylabel(r"$\partial_t u$")
    ax.legend()

    out_dir = Path("examples/output")
    out_dir.mkdir(parents=True, exist_ok=True)
    fig.save(str(out_dir / f"{stem}.svg"))
    fig.save(str(out_dir / f"{stem}.html"))
    if cf.BACKEND == "rust":
        fig.save(str(out_dir / f"{stem}.pdf"))


if __name__ == "__main__":
    main()
