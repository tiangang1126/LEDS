from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib import font_manager


ROOT = Path(__file__).resolve().parents[1]
SUMMARY = (
    ROOT
    / "results"
    / "facebook_k5_deepseek_chat_20260728_retry01"
    / "summary_facebook_k5.json"
)
OUT_DIR = Path(__file__).resolve().parent

DEPLOYMENTS = ["fb_random", "fb_edge", "fb_hub"]
LABELS = ["随机部署", "边缘部署", "中心部署"]
COLORS = ["#0072B2", "#D55E00", "#009E73"]
MARKERS = ["o", "s", "^"]
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
        "font.size": 8.5,
        "axes.labelsize": 9,
        "xtick.labelsize": 8,
        "ytick.labelsize": 8,
        "legend.fontsize": 7.2,
        "legend.frameon": False,
        "figure.dpi": 600,
        "savefig.dpi": 600,
        "savefig.bbox": "tight",
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "axes.axisbelow": True,
        "grid.alpha": 0.22,
        "grid.linestyle": "--",
    }
)


def main() -> None:
    with SUMMARY.open("r", encoding="utf-8") as handle:
        summary = json.load(handle)

    if summary["status"] != "completed":
        raise RuntimeError("Facebook K=5 experiment is not marked completed")
    if summary["completed_run_count"] != summary["expected_run_count"]:
        raise RuntimeError("Facebook K=5 experiment is incomplete")

    fig, ax = plt.subplots(figsize=(3.3, 2.55), constrained_layout=True)
    jitter = np.array([-0.16, -0.08, 0.0, 0.08, 0.16])

    for index, (key, label, color, marker) in enumerate(
        zip(DEPLOYMENTS, LABELS, COLORS, MARKERS)
    ):
        stats = summary["deployments"][key]["penetration"]
        samples = np.asarray(stats["samples"], dtype=float)
        if samples.size != 5:
            raise RuntimeError(f"{key} does not contain five observations")

        mean = float(stats["mean"])
        ci_low, ci_high = (float(value) for value in stats["ci95_student_t"])
        ax.scatter(
            index + jitter,
            samples,
            s=26,
            marker=marker,
            color=color,
            alpha=0.88,
            edgecolor="white",
            linewidth=0.7,
            zorder=3,
        )
        ax.errorbar(
            index,
            mean,
            yerr=np.array([[mean - ci_low], [ci_high - mean]]),
            fmt="D",
            markersize=5.5,
            markerfacecolor="white",
            markeredgecolor=color,
            markeredgewidth=1.3,
            ecolor=color,
            elinewidth=1.4,
            capsize=3.5,
            capthick=1.2,
            zorder=4,
        )

    ax.scatter([], [], s=26, color="#666666", edgecolor="white", label="独立运行")
    ax.errorbar(
        [],
        [],
        yerr=[],
        fmt="D",
        markersize=5.5,
        markerfacecolor="white",
        markeredgecolor="#444444",
        markeredgewidth=1.6,
        ecolor="#444444",
        capsize=5,
        label="均值及95%置信区间",
    )
    ax.set_xticks(range(3), LABELS)
    ax.set_ylabel("最终渗透率/%")
    ax.set_xlim(-0.45, 2.45)
    ax.set_ylim(-1.0, 30.5)
    ax.set_yticks(np.arange(0, 31, 5))
    ax.legend(loc="upper right", handlelength=1.4)

    out_png = OUT_DIR / "fig5_facebook_k5.png"
    out_pdf = OUT_DIR / "fig5_facebook_k5.pdf"
    fig.savefig(out_png, dpi=600)
    fig.savefig(out_pdf)
    plt.close(fig)
    print(out_png)
    print(out_pdf)


if __name__ == "__main__":
    main()
