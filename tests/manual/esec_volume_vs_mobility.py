from __future__ import annotations

from pathlib import Path

import cleanfig as cf


def save_outputs(fig: cf.Figure, stem: str) -> None:
    out_dir = Path("tests/output")
    out_dir.mkdir(parents=True, exist_ok=True)
    fig.save(str(out_dir / f"{stem}.svg"))
    fig.save(str(out_dir / f"{stem}.html"))
    if cf.BACKEND == "rust":
        fig.save(str(out_dir / f"{stem}.pdf"))


def main(stem: str = "esec_volume_vs_mobility") -> None:
    try:
        import pandas as pd
    except ImportError as exc:
        raise SystemExit("This script requires pandas. Install it with: pip install pandas") from exc

    data_path = Path(__file__).resolve().parents[2] / "examples" / "Data" / "IRIS_DMC_esecEventsDb.txt"
    df = pd.read_csv(data_path, sep="|", low_memory=False)
    df = df.rename(
        columns={
            "starttime": "start_time",
            "endtime": "end_time",
            "name": "name",
            "volume": "volume_m3",
            "volumeHigh": "volume_high_m3",
            "volumeLow": "volume_low_m3",
            "h": "drop_height_m",
            "hHigh": "drop_height_high_m",
            "hLow": "drop_height_low_m",
            "l": "runout_m",
            "lHigh": "runout_high_m",
            "lLow": "runout_low_m",
        }
    )
    df["start_time"] = pd.to_datetime(df["start_time"], format="%Y_%m_%d %H%M%S", errors="coerce")
    df["end_time"] = pd.to_datetime(df["end_time"], format="%Y_%m_%d %H%M%S", errors="coerce")
    for col in [
        "volume_m3",
        "volume_high_m3",
        "volume_low_m3",
        "drop_height_m",
        "drop_height_high_m",
        "drop_height_low_m",
        "runout_m",
        "runout_high_m",
        "runout_low_m",
    ]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df["duration_s"] = (df["end_time"] - df["start_time"]).dt.total_seconds()
    df = df.dropna(
        subset=[
            "name",
            "start_time",
            "end_time",
            "duration_s",
            "volume_m3",
            "volume_high_m3",
            "volume_low_m3",
            "drop_height_m",
            "drop_height_high_m",
            "drop_height_low_m",
            "runout_m",
            "runout_high_m",
            "runout_low_m",
        ]
    )
    df = df[
        (df["duration_s"] > 0.0)
        & (df["volume_m3"] > 0.0)
        & (df["volume_low_m3"] > 0.0)
        & (df["volume_high_m3"] > 0.0)
        & (df["drop_height_m"] > 0.0)
        & (df["drop_height_low_m"] > 0.0)
        & (df["drop_height_high_m"] > 0.0)
        & (df["runout_m"] > 0.0)
        & (df["runout_low_m"] > 0.0)
        & (df["runout_high_m"] > 0.0)
    ].copy()

    df["mobility"] = df["drop_height_m"] / df["runout_m"]
    df["mobility_low"] = df["drop_height_low_m"] / df["runout_high_m"]
    df["mobility_high"] = df["drop_height_high_m"] / df["runout_low_m"]
    df["velocity_mps"] = df["runout_m"] / df["duration_s"]
    df = df.replace([float("inf"), float("-inf")], pd.NA).dropna(
        subset=["mobility", "mobility_low", "mobility_high", "velocity_mps"]
    )
    df = df[(df["mobility"] > 0.0) & (df["mobility_low"] > 0.0) & (df["mobility_high"] > 0.0) & (df["velocity_mps"] > 0.0)]
    df = df.sort_values("start_time").tail(80).reset_index(drop=True)

    x = df["volume_m3"].to_numpy()
    x_low = df["volume_low_m3"].to_numpy()
    x_high = df["volume_high_m3"].to_numpy()
    y = df["mobility"].to_numpy()
    y_low = df["mobility_low"].to_numpy()
    y_high = df["mobility_high"].to_numpy()
    speed = df["velocity_mps"].to_numpy()

    fig = cf.figure(width="single", height=4.2, grid=(1, 1), theme="publication")
    ax = fig.panel(0, 0)

    for left, right, mobility in zip(x_low, x_high, y):
        ax.line([left, right], [mobility, mobility], color="#616161", width=0.4, alpha=0.22)
    ax.errorbar(x, y, ymin=y_low, ymax=y_high, color="#616161", width=0.45, alpha=0.28, cap=0.0)
    handle = ax.scatter(x, y, color=speed, cmap="magma", size=6.2, alpha=0.84)

    ax.xlabel("Volume V [m^3]")
    ax.ylabel("Mobility H/L [-]")
    ax.xscale("log")
    ax.colorbar(handle, label="Velocity L / dt [m s^-1]")

    xmin = max(1.0, float(df["volume_low_m3"].min()) / 1.15)
    xmax = float(df["volume_high_m3"].max()) * 1.15
    ymin = max(0.0, float(df["mobility_low"].min()) * 0.92)
    ymax = float(df["mobility_high"].max()) * 1.06
    ax.limits(x=(xmin, xmax), y=(ymin, ymax))

    save_outputs(fig, stem)

    print(
        df[
            [
                "start_time",
                "name",
                "volume_m3",
                "volume_low_m3",
                "volume_high_m3",
                "mobility",
                "mobility_low",
                "mobility_high",
                "velocity_mps",
            ]
        ]
        .tail(10)
        .to_string(index=False)
    )


if __name__ == "__main__":
    main()
