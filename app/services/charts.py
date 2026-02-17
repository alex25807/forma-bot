"""Generate a progress chart (weight over time) as PNG bytes."""

import io
import logging
from datetime import datetime

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

logger = logging.getLogger(__name__)


def generate_weight_chart(
    weight_history: list[dict],
    target_weight: float | None = None,
    start_date_str: str | None = None,
) -> bytes | None:
    """Return PNG bytes of a weight progress chart, or None if not enough data."""
    if len(weight_history) < 1:
        return None

    dates = []
    weights = []
    for rec in weight_history:
        dt = datetime.fromisoformat(rec["logged_at"][:10])
        dates.append(dt)
        weights.append(rec["weight_kg"])

    fig, ax = plt.subplots(figsize=(8, 4.5), dpi=130)

    # Background
    fig.patch.set_facecolor("#1a1a2e")
    ax.set_facecolor("#16213e")

    # Weight line
    ax.plot(
        dates, weights,
        color="#00d2ff", linewidth=2.5, marker="o",
        markersize=7, markerfacecolor="#ffffff", markeredgecolor="#00d2ff",
        zorder=5, label="Вес",
    )

    # Fill below
    ax.fill_between(dates, weights, min(weights) - 1, alpha=0.15, color="#00d2ff")

    # Target line
    if target_weight is not None:
        ax.axhline(
            target_weight, color="#ff6b6b", linestyle="--", linewidth=1.5,
            label=f"Цель: {target_weight} кг", zorder=4,
        )

    # Start date marker
    if start_date_str:
        sd = datetime.fromisoformat(start_date_str)
        ax.axvline(sd, color="#ffd93d", linestyle=":", linewidth=1, alpha=0.7)
        ax.text(
            sd, max(weights) + 0.3, "Старт", fontsize=8,
            color="#ffd93d", ha="center",
        )

    # Annotations for first and last points
    for idx in (0, -1):
        ax.annotate(
            f"{weights[idx]:.1f}",
            (dates[idx], weights[idx]),
            textcoords="offset points", xytext=(0, 12),
            fontsize=9, color="white", ha="center", fontweight="bold",
        )

    # Delta annotation
    if len(weights) >= 2:
        delta = weights[-1] - weights[0]
        sign = "+" if delta >= 0 else ""
        ax.text(
            0.98, 0.02, f"{sign}{delta:.1f} кг",
            transform=ax.transAxes, fontsize=14, fontweight="bold",
            color="#00ff88" if delta <= 0 else "#ff6b6b",
            ha="right", va="bottom",
        )

    # Axis formatting
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m"))
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    fig.autofmt_xdate(rotation=30)

    ax.set_ylabel("кг", fontsize=11, color="white")
    ax.set_title("📈  Динамика веса", fontsize=14, color="white", pad=15)

    ax.tick_params(colors="white", labelsize=9)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#444")
    ax.spines["bottom"].set_color("#444")
    ax.grid(axis="y", color="#333", linewidth=0.5, alpha=0.5)

    legend = ax.legend(
        loc="upper right", fontsize=9,
        facecolor="#16213e", edgecolor="#444", labelcolor="white",
    )
    for text in legend.get_texts():
        text.set_color("white")

    plt.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", facecolor=fig.get_facecolor())
    plt.close(fig)
    buf.seek(0)
    return buf.read()
