from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = Path(__file__).resolve().parent
PAIR_CSV = ROOT / "results" / "min_accept" / "determinism_probe_k5_deepseek_v4_flash_pairwise_hamming.csv"
JSON_PATH = ROOT / "results" / "min_accept" / "determinism_probe_k5_deepseek_v4_flash.json"


plt.rcParams.update(
    {
        "font.family": "sans-serif",
        "font.sans-serif": [
            "Microsoft YaHei",
            "SimHei",
            "Noto Sans CJK SC",
            "DejaVu Sans",
        ],
        "font.size": 10,
        "axes.titlesize": 11,
        "axes.titleweight": "bold",
        "axes.labelsize": 10,
        "legend.fontsize": 8.5,
        "legend.frameon": False,
        "figure.dpi": 300,
        "savefig.dpi": 300,
        "savefig.bbox": "tight",
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "grid.alpha": 0.2,
        "grid.linestyle": "--",
    }
)

OUR_COLOR = "#2ca02c"
RUN_COLOR = "#d62728"
MEAN_COLOR = "#c0392b"
BASE_GREY = "#b8c0cc"
BLUE = "#4a90d9"


def main() -> None:
    pair = pd.read_csv(PAIR_CSV)
    with JSON_PATH.open("r", encoding="utf-8") as f:
        import json

        data = json.load(f)

    runs = data["independent_runs"]["runs"]
    seed = data["cache_replay"]["seed"]
    replay = data["cache_replay"]["replays"]
    penetration = np.array([r["penetration"] for r in runs], dtype=float)
    run_labels = [f"运行{i}" for i in range(1, len(runs) + 1)]

    fig, axes = plt.subplots(1, 2, figsize=(11.2, 4.6), constrained_layout=True)

    # Panel A: run-to-run penetration spread
    ax = axes[0]
    x = np.arange(len(penetration))
    ax.axhspan(penetration.min(), penetration.max(), color=RUN_COLOR, alpha=0.08, label=f"独立运行发散带（极差 {penetration.max()-penetration.min():.3f}pp）")
    ax.plot(x, penetration, color=RUN_COLOR, lw=1.8, zorder=2)
    ax.scatter(x, penetration, color=RUN_COLOR, s=110, zorder=3, edgecolor="white", linewidth=0.8, label=f"独立运行（Temp=0，无缓存）：{[round(v,3) for v in penetration.tolist()]}")
    mean = penetration.mean()
    ax.axhline(mean, color=MEAN_COLOR, ls="--", lw=1.6, label=f"独立运行均值 {mean:.3f}%")
    ax.scatter([len(penetration)], [seed["penetration"]], marker="D", s=150, color=OUR_COLOR, edgecolor="white", linewidth=0.8, zorder=4, label=f"缓存重放 seed→replay：{seed['penetration']:.3f}%→{replay[0]['penetration']:.3f}%")
    ax.set_xticks(list(x) + [len(penetration)])
    ax.set_xticklabels(run_labels + ["重放"])
    ax.set_ylabel("最终信念渗透率 (%)")
    ax.set_title("(A) 宏观：Temperature=0 运行间发散 vs 重放重合")
    ax.set_ylim(min(penetration.min(), seed["penetration"]) - 0.8, max(penetration.max(), seed["penetration"]) + 0.8)
    ax.legend(loc="lower left")

    # Panel B: pairwise hamming distribution
    ax = axes[1]
    hamming = pair["hamming_pct"].to_numpy(dtype=float)
    order = np.argsort(hamming)
    sorted_vals = hamming[order]
    ax.boxplot(
        sorted_vals,
        vert=True,
        widths=0.35,
        patch_artist=True,
        boxprops=dict(facecolor=BLUE, alpha=0.18, color=BLUE),
        whiskerprops=dict(color=BLUE, linewidth=1.4),
        capprops=dict(color=BLUE, linewidth=1.4),
        medianprops=dict(color="#1f3f5b", linewidth=1.8),
        flierprops=dict(marker="o", markersize=4, markerfacecolor=BLUE, alpha=0.5, markeredgecolor="none"),
    )
    jitter = np.linspace(-0.05, 0.05, len(sorted_vals))
    ax.scatter(np.ones_like(sorted_vals) + jitter, sorted_vals, s=44, color=RUN_COLOR, alpha=0.9, edgecolor="white", linewidth=0.6, zorder=3, label="10组成对 Hamming")
    ax.scatter([1.25], [0.0], marker="D", s=120, color=OUR_COLOR, edgecolor="white", linewidth=0.8, zorder=4, label="判定记录重放 Hamming 0.0%")
    ax.set_xticks([1])
    ax.set_xticklabels(["K=5独立运行对"])
    ax.set_ylabel("最终信念向量 Hamming 距离 (%)")
    ax.set_title("(B) 微观：逐节点信念分歧 vs 重放精确复现")
    ax.set_ylim(-0.5, max(sorted_vals.max(), 0.0) + 0.8)
    ax.legend(loc="upper left")

    out_png = OUT_DIR / "fig2_k5_determinism.png"
    out_pdf = OUT_DIR / "fig2_k5_determinism.pdf"
    fig.savefig(out_png, dpi=300)
    fig.savefig(out_pdf)
    print(out_png)
    print(out_pdf)


if __name__ == "__main__":
    main()
