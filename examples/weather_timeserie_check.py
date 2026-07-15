from pathlib import Path

import numpy as np

import cleanfig as cf


DATA_PATH = Path(__file__).parent / "Data" / "weather_timeserie_check.csv"


def _altitude_key(label: str) -> int:
    try:
        return int(str(label).split("-")[0])
    except Exception:
        return 0


def _load_weather_csv(path: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    data = np.genfromtxt(path, delimiter=",", names=True, dtype=None, encoding="utf-8")
    dates = np.asarray(data["date"], dtype="datetime64[D]")
    altitude_bin = np.asarray(data["altitude_bin"], dtype=str)
    temperature = np.asarray(data["temperature_c"], dtype=float)
    rainfall = np.asarray(data["rainfall_mm"], dtype=float)
    snow_height = np.asarray(data["snow_height_m"], dtype=float)
    return dates, altitude_bin, temperature, rainfall, snow_height


def _datetime_to_float_days(dates: np.ndarray) -> np.ndarray:
    return dates.astype("datetime64[D]").astype("int64").astype(float)


def main() -> None:
    dates, altitude_bin, temperature, rainfall, snow_height = _load_weather_csv(DATA_PATH)
    altitudes = sorted(np.unique(altitude_bin).tolist(), key=_altitude_key)
    colors = ["#4C78A8", "#54A24B", "#B279A2", "#E45756", "#F58518", "#72B7B2"]
    series = [
        (temperature, "Temperature (degC)"),
        (rainfall, "Rainfall (mm)"),
        (snow_height, "Snow height (m)"),
    ]

    fig = cf.figure(layout="timeseries", height=6.0, grid=(3, 1))
    x = _datetime_to_float_days(dates)

    for row, (values, ylabel) in enumerate(series):
        ax = fig.panel(row, 0)
        for idx, altitude in enumerate(altitudes):
            mask = altitude_bin == altitude
            order = np.argsort(x[mask])
            ax.line(x[mask][order], values[mask][order], color=colors[idx % len(colors)], label=altitude if row == 0 else None)
        ax.ylabel(ylabel)
        if row == 0:
            ax.legend()
        if row == len(series) - 1:
            ax.xlabel("Date")

    out_dir = Path("examples/output")
    out_dir.mkdir(parents=True, exist_ok=True)
    if cf.BACKEND == "rust":
        fig.save(str(out_dir / "weather_timeserie_check.pdf"))


if __name__ == "__main__":
    main()
