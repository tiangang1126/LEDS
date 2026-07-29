# -*- coding: utf-8 -*-
"""Regenerate LEDS line charts at final single-column physical dimensions."""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib import font_manager


ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent
LOGS = ROOT / "results" / "logs"
WSL_CJK_FONT = Path("/mnt/c/Windows/Fonts/msyh.ttc")

if WSL_CJK_FONT.exists():
    font_manager.fontManager.addfont(WSL_CJK_FONT)
    CJK = font_manager.FontProperties(fname=WSL_CJK_FONT).get_name()
else:
    CJK = "Microsoft YaHei"

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": [CJK, "Microsoft YaHei", "Noto Sans CJK SC", "DejaVu Sans"],
    "axes.unicode_minus": False,
    "font.size": 8,
    "axes.labelsize": 8.5,
    "xtick.labelsize": 7.5,
    "ytick.labelsize": 7.5,
    "legend.fontsize": 7.2,
    "legend.frameon": False,
    "figure.dpi": 600,
    "savefig.dpi": 600,
    "savefig.bbox": "tight",
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "grid.alpha": 0.22,
    "grid.linestyle": "--",
    "lines.linewidth": 1.45,
    "lines.markersize": 3.2,
})

BLUE = "#0072B2"
ORANGE = "#D55E00"
GREEN = "#009E73"
GREY = "#6F6F6F"


def load_curve(name: str) -> tuple[list[int], list[float]]:
    data = json.loads((LOGS / f"{name}.json").read_text(encoding="utf-8"))
    return [row["t"] for row in data["steps"]], [100 * row["penetration"] for row in data["steps"]]


def save(fig: plt.Figure, stem: str) -> None:
    fig.savefig(OUT / f"{stem}.png", dpi=600)
    fig.savefig(OUT / f"{stem}.pdf")
    plt.close(fig)


def topology() -> None:
    fig, ax = plt.subplots(figsize=(3.3, 2.45), constrained_layout=True)
    for name, label, color in [
        ("exp1_smallworld", "小世界（17.0%）", BLUE),
        ("exp1_scalefree", "无标度（31.7%）", ORANGE),
    ]:
        x, y = load_curve(name)
        ax.plot(x, y, marker="o", color=color, label=label)
    ax.set_xlabel("离散时间步 $t$")
    ax.set_ylabel("信息渗透率/%")
    ax.set_ylim(-2, 102)
    ax.legend(loc="upper right", handlelength=1.7)
    save(fig, "fig3_topology_publication")


def intervention() -> None:
    fig, ax = plt.subplots(figsize=(3.3, 2.45), constrained_layout=True)
    for name, label, color, style in [
        ("exp1_scalefree", "随机（31.7%）", GREY, "--"),
        ("exp2_edge_defense", "边缘（30.0%）", ORANGE, "-"),
        ("exp2_hub_defense", "中心（0.0%）", GREEN, "-"),
    ]:
        x, y = load_curve(name)
        ax.plot(x, y, marker="o", color=color, linestyle=style, label=label)
    ax.set_xlabel("离散时间步 $t$")
    ax.set_ylabel("信息渗透率/%")
    ax.set_ylim(-2, 102)
    ax.legend(loc="upper right", handlelength=1.7)
    save(fig, "fig4_intervention_publication")


def scalability() -> None:
    data = json.loads((ROOT / "results" / "scalability.json").read_text(encoding="utf-8"))
    rows = data["rows"]
    n = [row["N"] for row in rows]
    full = [row["full_calls"] for row in rows]
    leds = [row["leds_calls"] for row in rows]
    fig, ax = plt.subplots(figsize=(3.3, 2.45), constrained_layout=True)
    ax.plot(n, full, "s--", color=ORANGE, label="全轮询")
    ax.plot(n, leds, "o-", color=GREEN, label="LEDS")
    ax.set_yscale("log")
    ax.set_xlabel("网络规模 $N$")
    ax.set_ylabel("LLM判定次数（对数）")
    ax.legend(loc="upper left", handlelength=1.7)
    for x, y in zip(n, full):
        ax.annotate(str(y), (x, y), xytext=(0, 4), textcoords="offset points", ha="center", fontsize=6.8)
    for x, y in zip(n, leds):
        ax.annotate(str(y), (x, y), xytext=(0, -9), textcoords="offset points", ha="center", fontsize=6.8)
    save(fig, "figC1_scalability_publication")


if __name__ == "__main__":
    topology()
    intervention()
    scalability()
