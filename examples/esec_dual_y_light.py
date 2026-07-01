from __future__ import annotations

from pathlib import Path

import cleanfig as cf


def main() -> None:
    try:
        import pandas as pd
    except ImportError as exc:
        raise SystemExit("This example requires pandas. Install it with: pip install pandas") from exc

    data_path = Path(__file__).parent / "Data" / "IRIS_DMC_esecEventsDb.txt"
    df = pd.read_csv(data_path, sep="|", low_memory=False)
    df = df.rename(
        columns={
            "starttime": "event_time",
            "name": "name",
            "type": "event_type",
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
    df["event_time"] = pd.to_datetime(df["event_time"], format="%Y_%m_%d %H%M%S", errors="coerce")
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
    df = df.dropna(
        subset=[
            "event_time",
            "name",
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
        (df["volume_m3"] > 0.0)
        & (df["volume_high_m3"] > 0.0)
        & (df["volume_low_m3"] > 0.0)
        & (df["drop_height_m"] > 0.0)
        & (df["drop_height_high_m"] > 0.0)
        & (df["drop_height_low_m"] > 0.0)
        & (df["runout_m"] > 0.0)
        & (df["runout_high_m"] > 0.0)
        & (df["runout_low_m"] > 0.0)
    ]
    df["h_over_l"] = df["drop_height_m"] / df["runout_m"]
    df["h_over_l_low"] = df["drop_height_low_m"] / df["runout_high_m"]
    df["h_over_l_high"] = df["drop_height_high_m"] / df["runout_low_m"]
    df["event_index"] = range(1, len(df) + 1)
    df = df.sort_values("event_time").tail(24).reset_index(drop=True)
    df["event_index"] = range(1, len(df) + 1)

    fig = cf.figure(width="double", height=3.8, grid=(1, 1), theme="light")
    ax = fig.panel(0, 0)

    x = df["event_index"].to_numpy()
    volume = df["volume_m3"].to_numpy()
    mobility = df["h_over_l"].to_numpy()
    volume_low = df["volume_low_m3"].to_numpy()
    volume_high = df["volume_high_m3"].to_numpy()
    mobility_low = df["h_over_l_low"].to_numpy()
    mobility_high = df["h_over_l_high"].to_numpy()

    ax.errorbar(x, volume, ymin=volume_low, ymax=volume_high, width=0.65, alpha=0.35)
    ax.line(x, volume, width=0.9, alpha=0.9, label="Volume V")
    ax.scatter(x, volume, size=3.6, alpha=0.8)
    ax.yscale("log")
    ax.ylabel("Volume V [m^3] (log)")

    ax.errorbar(x, mobility, ymin=mobility_low, ymax=mobility_high, width=0.65, alpha=0.35, yaxis="right")
    ax.line(x, mobility, width=0.9, alpha=0.9, label="H/L", yaxis="right")
    ax.scatter(x, mobility, size=3.6, alpha=0.8, yaxis="right")
    ax.right_ylabel("H/L [-]")
    ax.right_limits(y=(0.0, max(mobility_high) * 1.15))

    ax.xlabel("ESEC events (chronological index)")
    ax.legend()

    out_dir = Path("examples/output")
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = "esec_dual_y_light"
    fig.save(str(out_dir / f"{stem}.svg"))
    fig.save(str(out_dir / f"{stem}.html"))
    if cf.BACKEND == "rust":
        fig.save(str(out_dir / f"{stem}.pdf"))

    print(df[["event_time", "name", "event_type", "volume_m3", "drop_height_m", "runout_m", "h_over_l"]].tail(8).to_string(index=False))


if __name__ == "__main__":
    main()
