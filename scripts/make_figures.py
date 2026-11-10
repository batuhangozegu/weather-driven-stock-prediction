"""Draw the README figures from the processed data (roadmap stage 3).

Only the training period (2017-2021) is used, so the charts cannot shape any
choice that is later judged on the validation or test years.

Inputs  (data/processed/): weather_daily.csv, panel_daily.csv
Outputs (reports/figures/): uri_week.png, seasonality.png, cdd_anomaly_trap.png

Usage:
    python scripts/make_figures.py
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd

from weather_stocks.splits import select_period

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "processed"
FIG_DIR = ROOT / "reports" / "figures"

REGIONS = {
    "tx": ["houston", "dallas"],
    "gas": ["new_york", "chicago"],
}

# Colours: categorical slots 1-3 of the dataviz reference palette, plus text inks.
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
INK, INK_2, INK_3 = "#0b0b0b", "#52514e", "#8a8984"
SURFACE, GRID, SHADE = "#fcfcfb", "#e6e5e1", "#efeeea"


def style() -> None:
    plt.rcParams.update({
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "savefig.facecolor": SURFACE,
        "font.size": 10,
        "text.color": INK,
        "axes.labelcolor": INK_2,
        "axes.edgecolor": GRID,
        "axes.titlesize": 11,
        "axes.titleweight": "bold",
        "axes.titlelocation": "left",
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "axes.grid.axis": "y",
        "grid.color": GRID,
        "grid.linewidth": 0.8,
        "xtick.color": INK_2,
        "ytick.color": INK_2,
        "xtick.major.size": 0,
        "ytick.major.size": 0,
        "lines.linewidth": 2,
        "legend.frameon": False,
    })


def regional_weather() -> pd.DataFrame:
    """Daily weather per region (equal-weight city mean), training period only."""
    weather = pd.read_csv(DATA_DIR / "weather_daily.csv", parse_dates=["date"])
    weather = select_period(weather, "train")
    cols = ["tmean", "hdd", "cdd", "tmean_normal", "cdd_normal", "cdd_anom"]
    frames = []
    for region, cities in REGIONS.items():
        mean = weather[weather["city"].isin(cities)].groupby("date")[cols].mean()
        frames.append(mean.assign(region=region))
    return pd.concat(frames).reset_index()


def save(fig: plt.Figure, name: str, caption: str) -> None:
    fig.text(0.01, 0.01, caption, color=INK_3, fontsize=8, ha="left", va="bottom")
    fig.savefig(FIG_DIR / name, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"saved {name}")


def uri_week(weather: pd.DataFrame, panel: pd.DataFrame) -> None:
    start, end = pd.Timestamp("2021-01-25"), pd.Timestamp("2021-03-05")
    storm = (pd.Timestamp("2021-02-13"), pd.Timestamp("2021-02-19"))

    tx = weather[(weather["region"] == "tx") & weather["date"].between(start, end)]
    prices = panel[panel["date"].between(start, end)].set_index("date")
    base = prices.loc["2021-02-01"]

    fig, (top, bottom) = plt.subplots(
        2, 1, figsize=(9, 6.2), sharex=True, gridspec_kw={"height_ratios": [1, 1.25]}
    )
    for ax in (top, bottom):
        ax.axvspan(*storm, color=SHADE, zorder=0, lw=0)

    top.plot(tx["date"], tx["tmean"], color=BLUE, label="Daily mean")
    top.plot(tx["date"], tx["tmean_normal"], color=INK_3, lw=1.5, ls="--",
             label="Normal (past 30 years)")
    top.axhline(0, color=INK_3, lw=0.8)
    top.set_title("Texas temperature, °C  (Houston + Dallas)")
    top.legend(loc="lower left", ncol=2)
    top.text(storm[0] + pd.Timedelta(hours=12), 21, "Winter Storm Uri",
             color=INK_2, fontsize=9, va="top")

    series = [("vst", "VST", ORANGE), ("nrg", "NRG", BLUE), ("spy", "S&P 500 (SPY)", AQUA)]
    for ticker, label, color in series:
        index = 100 * prices[f"adj_close_{ticker}"] / base[f"adj_close_{ticker}"]
        bottom.plot(index.index, index, color=color, label=label)
        bottom.text(index.index[-1] + pd.Timedelta(hours=18), index.iloc[-1], label,
                    color=INK_2, fontsize=9, va="center")
    bottom.axhline(100, color=INK_3, lw=0.8)
    bottom.set_title("Share price, 1 Feb 2021 = 100")
    bottom.legend(loc="upper left", ncol=3)

    drop_day = pd.Timestamp("2021-02-26")
    vst = 100 * prices["adj_close_vst"] / base["adj_close_vst"]
    bottom.annotate(
        f"VST {vst.pct_change().loc[drop_day]:+.0%} on {drop_day:%d %b},\n"
        "a week after the storm ended",
        xy=(drop_day, vst.loc[drop_day]), xytext=(pd.Timestamp("2021-02-12"), 79),
        color=INK, fontsize=9, va="center",
        arrowprops={"arrowstyle": "-", "color": INK_3, "lw": 1},
    )
    bottom.set_ylim(75, 121)
    bottom.xaxis.set_major_locator(mdates.WeekdayLocator(byweekday=mdates.MO))
    bottom.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
    bottom.set_xlim(start, end + pd.Timedelta(days=5))

    fig.suptitle("Same storm, different timing: NRG fell during the cold, VST a week later",
                 x=0.01, ha="left", fontsize=13, fontweight="bold")
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    save(fig, "uri_week.png",
         "Weather: ERA5 via Open-Meteo, plotted on its own date. Prices: Yahoo Finance adjusted close.")


def seasonality(weather: pd.DataFrame) -> None:
    weather = weather.assign(month=weather["date"].dt.month)
    monthly = weather.groupby(["region", "month"])[["hdd", "cdd"]].mean()
    titles = {"tx": "Texas  (NRG, VST)", "gas": "New York + Chicago  (UNG)"}

    fig, axes = plt.subplots(1, 2, figsize=(9, 3.6), sharey=True)
    for ax, region in zip(axes, REGIONS):
        data = monthly.loc[region]
        ax.plot(data.index, data["hdd"], color=BLUE, marker="o", ms=4,
                label="HDD (heating)")
        ax.plot(data.index, data["cdd"], color=ORANGE, marker="o", ms=4,
                label="CDD (cooling)")
        ax.set_title(titles[region])
        ax.set_xticks(range(1, 13), list("JFMAMJJASOND"))
    axes[0].set_ylabel("Average degree days per day, °C")
    axes[0].legend(loc="upper center")

    fig.suptitle("Texas needs cooling, the gas region needs heating",
                 x=0.01, ha="left", fontsize=13, fontweight="bold")
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    save(fig, "seasonality.png",
         "Training period 2017-2021. Degree days use a base of 18.3 °C (65 °F).")


def cdd_anomaly_trap(weather: pd.DataFrame) -> None:
    tx = weather[(weather["region"] == "tx") & (weather["date"].dt.year == 2017)]
    tx = tx.set_index("date")
    hottest = tx["cdd"].idxmax()
    biggest_anomaly = tx["cdd_anom"].idxmax()

    fig, (top, bottom) = plt.subplots(2, 1, figsize=(9, 5.4), sharex=True)
    top.plot(tx.index, tx["cdd"], color=ORANGE, lw=1.2, label="CDD")
    top.plot(tx.index, tx["cdd_normal"], color=INK_3, lw=1.5, ls="--", label="Normal")
    top.set_title("Texas cooling degree days, 2017  (what the grid feels)")
    top.legend(loc="upper left")

    bottom.plot(tx.index, tx["cdd_anom"], color=BLUE, lw=1.2)
    bottom.axhline(0, color=INK_3, lw=0.8)
    bottom.set_title("CDD anomaly = CDD − normal  (what a model would see)")

    for day, label in [(hottest, "hottest day"), (biggest_anomaly, "largest anomaly")]:
        for ax, col in [(top, "cdd"), (bottom, "cdd_anom")]:
            ax.plot(day, tx.loc[day, col], "o", ms=8, color=INK, mec=SURFACE, mew=2)
        top.annotate(
            f"{label}, {day:%d %b}\nCDD {tx.loc[day, 'cdd']:.1f}, "
            f"anomaly {tx.loc[day, 'cdd_anom']:+.1f}",
            xy=(day, tx.loc[day, "cdd"]), xytext=(0, 14), textcoords="offset points",
            ha="center", fontsize=9, color=INK,
        )
    top.set_ylim(top=tx["cdd"].max() * 1.45)
    bottom.xaxis.set_major_locator(mdates.MonthLocator())
    bottom.xaxis.set_major_formatter(mdates.DateFormatter("%b"))

    fig.suptitle("A warm November day looks more extreme than a summer heat wave",
                 x=0.01, ha="left", fontsize=13, fontweight="bold")
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    save(fig, "cdd_anomaly_trap.png",
         "So stage 5 tests degree-day levels as well as anomalies.")


def main() -> None:
    style()
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    weather = regional_weather()
    panel = select_period(pd.read_csv(DATA_DIR / "panel_daily.csv", parse_dates=["date"]), "train")
    uri_week(weather, panel)
    seasonality(weather)
    cdd_anomaly_trap(weather)


if __name__ == "__main__":
    main()
