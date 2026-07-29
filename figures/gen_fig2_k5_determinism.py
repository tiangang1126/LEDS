from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib import font_manager


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = Path(__file__).resolve().parent
PAIR_CSV = ROOT / "results" / "min_accept" / "determinism_probe_k5_deepseek_v4_flash_pairwise_hamming.csv"
JSON_PATH = ROOT / "results" / "min_accept" / "determinism_probe_k5_deepseek_v4_flash.json"
WSL_CJK_FONT = Path("/mnt/c/Windows/Fonts/msyh.ttc")

if WSL_CJK_FONT.exists():
    font_manager.fontManager.addfont(WSL_CJK_FONT)
    CJK_FONT_FAMILY = font_manager.FontProperties(fname=WSL_CJK_FONT).get_name()
else:
    CJK_FONT_FAMILY = "Microsoft YaHei"


plt.rcParams.update(
    {
        "font.family": "sans-serif",
        "font.sans-serif": [
            CJK_FONT_FAMILY,
            "Microsoft YaHei",
            "SimHei",
            "Noto Sans CJK SC",
            "DejaVu Sans",
        ],
        "font.size": 8,
        "axes.titlesize": 8.5,
        "axes.titleweight": "bold",
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

    # The journal uses a roughly 3-inch column.  Build at final physical size
    # so fonts remain 7--9 pt after Word placement instead of being scaled down.
    fig, axes = plt.subplots(2, 1, figsize=(3.3, 4.4), constrained_layout=True)

    # Panel A: run-to-run penetration spread
    ax = axes[0]
    x = np.arange(len(penetration))
    ax.axhspan(penetration.min(), penetration.max(), color=RUN_COLOR, alpha=0.08)
    ax.plot(x, penetration, color=RUN_COLOR, lw=1.8, zorder=2)
    ax.scatter(x, penetration, color=RUN_COLOR, s=32, zorder=3, edgecolor="white", linewidth=0.6, label="独立运行（无记录）")
    mean = penetration.mean()
    ax.axhline(mean, color=MEAN_COLOR, ls="--", lw=1.3, label=f"独立运行均值 {mean:.3f}%")
    ax.scatter([len(penetration)], [seed["penetration"]], marker="D", s=42, color=OUR_COLOR, edgecolor="white", linewidth=0.6, zorder=4, label="固定记录回放")
    ax.set_xticks(list(x) + [len(penetration)])
    ax.set_xticklabels(run_labels + ["重放"])
    ax.set_ylabel("最终信念渗透率 (%)")
    ax.set_title("(a) 宏观渗透率：独立运行与固定记录回放")
    ax.set_ylim(min(penetration.min(), seed["penetration"]) - 0.8, max(penetration.max(), seed["penetration"]) + 0.8)
    ax.legend(loc="lower left", ncol=1, handlelength=1.6)

    # Panel B: pairwise hamming distribution
    ax = axes[1]
    hamming = pair["hamming_pct"].to_numpy(dtype=float)
    order = np.argsort(hamming)
    sorted_vals = hamming[order]
    ax.boxplot(
        sorted_vals,
        vert=True,
        widths=0.28,
        patch_artist=True,
        boxprops=dict(facecolor=BLUE, alpha=0.18, color=BLUE),
        whiskerprops=dict(color=BLUE, linewidth=1.4),
        capprops=dict(color=BLUE, linewidth=1.4),
        medianprops=dict(color="#1f3f5b", linewidth=1.8),
        flierprops=dict(marker="o", markersize=4, markerfacecolor=BLUE, alpha=0.5, markeredgecolor="none"),
    )
    jitter = np.linspace(-0.05, 0.05, len(sorted_vals))
    ax.scatter(np.ones_like(sorted_vals) + jitter, sorted_vals, s=24, color=RUN_COLOR, alpha=0.9, edgecolor="white", linewidth=0.5, zorder=3, label="10组独立运行对")
    ax.scatter([1.25], [0.0], marker="D", s=36, color=OUR_COLOR, edgecolor="white", linewidth=0.6, zorder=4, label="固定记录回放（0）")
    ax.set_xticks([1])
    ax.set_xticklabels(["K=5独立运行对"])
    ax.set_ylabel("最终信念向量 Hamming 距离 (%)")
    ax.set_title("(b) 微观差异：节点状态Hamming距离")
    ax.set_ylim(-0.5, max(sorted_vals.max(), 0.0) + 0.8)
    ax.legend(loc="upper left", handlelength=1.6)

    out_png = OUT_DIR / "fig2_k5_determinism.png"
    out_pdf = OUT_DIR / "fig2_k5_determinism.pdf"
    fig.savefig(out_png, dpi=600)
    fig.savefig(out_pdf)
    print(out_png)
    print(out_pdf)


if __name__ == "__main__":
    main()
