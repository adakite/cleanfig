from pathlib import Path

import numpy as np

import cleanfig as cf

try:
    from IPython.display import SVG, display
except Exception:  # pragma: no cover - optional notebook dependency
    SVG = None
    display = None


def main() -> None:
    rng = np.random.default_rng(42)

    local_incidence_angle_deg = np.linspace(-32.0, -10.0, 120)
    satellite_sigma0_vv_db = -17.0 + 1.5 * np.sin(np.linspace(0.0, 3.2, 120)) + 0.15 * rng.normal(size=120)
    lc_cm = np.linspace(2.0, 40.0, 120)

    fig = cf.figure(width="double", height=6.0, grid=(1, 1), theme="light")
    ax = fig.panel(0, 0)

    sc = ax.scatter(local_incidence_angle_deg, satellite_sigma0_vv_db, color=lc_cm, size=6, alpha=0.85)
    ax.colorbar(sc, label="h_rms [cm]", placement="inside-left")
    ax.limits(x=(-32, -10), y=(-22, -8))
    ax.xlabel(r"Inc. angle [$^o$]")
    ax.ylabel(r"$\sigma^0$ [dB]")
    ax.legend()

    out_dir = Path("examples/output")
    out_dir.mkdir(parents=True, exist_ok=True)
    filename = out_dir / "notebook_example.svg"
    fig.save(str(filename))

    if display is not None and SVG is not None:
        display(SVG(filename=str(filename)))


if __name__ == "__main__":
    main()
