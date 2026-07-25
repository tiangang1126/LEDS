# -*- coding: utf-8 -*-
"""
LEDS 框架 —— 补充图表生成（论文 4.6 节非确定性探针、4.7 节跨后端鲁棒性）

从已落盘的机器可读结果直接读取并绘图，保证图-数据一致、可一键复现：
  · results/determinism_probe.json      -> charts/exp4_determinism.png   （论文图 3）
  · results/summary.json                -> charts/exp5_cross_backend.png （论文图 4）
    results/summary_deepseek-reasoner.json

用法：
    python src/plot_extra.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

import config

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

GREEN = "#2ca02c"   # LEDS / 缓存重放
RED = "#d62728"     # 发散 / 基线
BLUE = "#1f77b4"    # deepseek-chat
ORANGE = "#ff7f0e"  # deepseek-reasoner


def _load(name: str) -> dict:
    with open(os.path.join(config.RESULTS_DIR, name), "r", encoding="utf-8") as f:
        return json.load(f)


def plot_determinism(out_name: str = "exp4_determinism.png") -> str:
    """图 3：Temperature=0 运行间非确定性 vs 缓存重放精确复现（双面板）。"""
    d = _load("determinism_probe.json")
    ind = d["independent_runs"]
    div = d["pairwise_divergence"]
    rep = d["cache_replay"]
    pens = ind["penetration_samples"]
    mean = ind["penetration_mean"]

    fig, (axL, axR) = plt.subplots(1, 2, figsize=(11, 5), dpi=150)

    # ---- 面板 A：宏观——最终渗透率散布 vs 重放重合 ----
    xs = list(range(1, len(pens) + 1))
    axL.axhspan(min(pens), max(pens), color=RED, alpha=0.10,
                label=f"独立运行发散带 (极差 {ind['penetration_range']}pp)")
    axL.scatter(xs, pens, color=RED, s=90, zorder=3,
                label=f"独立运行 (Temp=0, 无缓存): {pens}")
    axL.axhline(mean, color=RED, linestyle="--", linewidth=1.2, alpha=0.8,
                label=f"独立运行均值 {mean}%")
    # 缓存重放：seed 与 replay 两点完全重合
    axL.scatter([len(pens) + 1], [rep["seed_penetration"]], color=GREEN,
                s=140, marker="D", zorder=4,
                label=f"缓存重放 seed→replay: {rep['seed_penetration']}%→"
                      f"{rep['replay_penetration']}% (重合)")
    axL.scatter([len(pens) + 1], [rep["replay_penetration"]], color="white",
                s=45, marker="D", zorder=5, edgecolors=GREEN)
    axL.set_xticks(xs + [len(pens) + 1])
    axL.set_xticklabels([f"运行{i}" for i in xs] + ["重放"])
    axL.set_ylabel("最终信息渗透率 (%)")
    axL.set_title("(A) 宏观：$Temperature=0$ 运行间发散 vs 重放重合")
    axL.grid(True, axis="y", linestyle="--", alpha=0.4)
    axL.legend(loc="lower left", fontsize=8)

    # ---- 面板 B：微观——成对 Hamming 距离 vs 重放 0% ----
    pair_h = div["pairwise_hamming_pct"]
    labels = [f"运行{i}-{j}" for i in range(1, len(pens) + 1)
              for j in range(i + 1, len(pens) + 1)]
    bar_x = list(range(len(pair_h)))
    axR.bar(bar_x, pair_h, color=RED, alpha=0.85, width=0.6,
            label=f"独立运行成对 Hamming (均值 {div['hamming_mean_pct']}%, "
                  f"最大 {div['hamming_max_pct']}%)")
    axR.bar([len(pair_h)], [rep["replay_hamming_pct"]], color=GREEN, width=0.6,
            label=f"缓存重放 Hamming {rep['replay_hamming_pct']}% (精确复现)")
    for x, v in zip(bar_x, pair_h):
        axR.annotate(f"{v}%", (x, v), textcoords="offset points",
                     xytext=(0, 4), ha="center", fontsize=8)
    axR.annotate("0.0%", (len(pair_h), rep["replay_hamming_pct"]),
                 textcoords="offset points", xytext=(0, 4), ha="center",
                 fontsize=8, color=GREEN)
    axR.set_xticks(bar_x + [len(pair_h)])
    axR.set_xticklabels(labels + ["重放"], fontsize=8)
    axR.set_ylabel("最终信念向量 Hamming 距离 (%)")
    axR.set_title("(B) 微观：逐节点信念分歧 vs 重放精确复现")
    axR.set_ylim(0, max(pair_h) + 6)
    axR.grid(True, axis="y", linestyle="--", alpha=0.4)
    axR.legend(loc="upper left", fontsize=8)

    fig.suptitle(f"实验四：{d['mode']} 下 $Temperature=0$ 非确定性与缓存重放一致性 "
                 f"(同一冻结无标度网络 $N={d['N']}$)", fontsize=12)
    os.makedirs(config.CHARTS_DIR, exist_ok=True)
    out = os.path.join(config.CHARTS_DIR, out_name)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(out)
    plt.close(fig)
    print(f"[PlotExtra] 图表已保存: {out}")
    return out


def plot_cross_backend(out_name: str = "exp5_cross_backend.png") -> str:
    """图 4：主实验在两个 LLM 后端上的渗透率对照（分组柱状图）。"""
    chat = _load("summary.json")
    reasoner = _load("summary_deepseek-reasoner.json")
    order = ["exp1_smallworld", "exp1_scalefree",
             "exp2_edge_defense", "exp2_hub_defense"]
    labels = ["小世界\n(随机)", "无标度\n(随机)", "边缘部署", "中心部署"]
    chat_v = [chat[k]["final_penetration"] for k in order]
    reas_v = [reasoner[k]["final_penetration"] for k in order]

    fig, ax = plt.subplots(figsize=(8.5, 5), dpi=150)
    x = list(range(len(order)))
    w = 0.38
    b1 = ax.bar([i - w / 2 for i in x], chat_v, w, color=BLUE,
                label="deepseek-chat")
    b2 = ax.bar([i + w / 2 for i in x], reas_v, w, color=ORANGE,
                label="deepseek-reasoner")
    for bars in (b1, b2):
        for b in bars:
            ax.annotate(f"{b.get_height():.1f}%",
                        (b.get_x() + b.get_width() / 2, b.get_height()),
                        textcoords="offset points", xytext=(0, 3),
                        ha="center", fontsize=8)
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylabel("最终信息渗透率 (%)")
    ax.set_ylim(0, max(reas_v) + 12)
    ax.set_title("实验五：拓扑与干预结论的跨 LLM 后端鲁棒性 ($Temperature=0$, $N=300$)")
    ax.grid(True, axis="y", linestyle="--", alpha=0.4)
    ax.legend(loc="upper right")
    # 方向性注记：两后端下无标度 > 小世界、中心部署 ≈ 0
    ax.annotate("两后端方向一致：无标度 >> 小世界；中心部署压制至 ≈ 0",
                (0.5, 0.94), xycoords="axes fraction", ha="center",
                fontsize=9, color="#444")

    os.makedirs(config.CHARTS_DIR, exist_ok=True)
    out = os.path.join(config.CHARTS_DIR, out_name)
    fig.tight_layout()
    fig.savefig(out)
    plt.close(fig)
    print(f"[PlotExtra] 图表已保存: {out}")
    return out


def plot_facebook(out_name: str = "exp_fb_intervention.png") -> str:
    """应用案例 B：真实 Facebook ego-network 上三种部署的最终渗透率对比。"""
    d = _load("summary_facebook.json")
    order = ["fb_random", "fb_edge", "fb_hub"]
    labels = ["随机部署", "边缘部署", "中心部署"]
    vals = [d[k]["final_penetration"] for k in order]
    fig, ax = plt.subplots(figsize=(7, 5), dpi=150)
    bars = ax.bar(labels, vals, color=[BLUE, ORANGE, GREEN], width=0.55)
    for b in bars:
        ax.annotate(f"{b.get_height():.1f}%",
                    (b.get_x() + b.get_width() / 2, b.get_height()),
                    textcoords="offset points", xytext=(0, 3),
                    ha="center", fontsize=9)
    ax.set_ylabel("最终信息渗透率 (%)")
    ax.set_ylim(0, max(vals) + 6)
    ax.set_title("应用案例：真实 Facebook 网络 (N=334) 上的空间干预效能")
    ax.grid(True, axis="y", linestyle="--", alpha=0.4)
    os.makedirs(config.CHARTS_DIR, exist_ok=True)
    out = os.path.join(config.CHARTS_DIR, out_name)
    fig.tight_layout()
    fig.savefig(out)
    plt.close(fig)
    print(f"[PlotExtra] 图表已保存: {out}")
    return out


def main() -> None:
    plot_determinism()
    plot_cross_backend()
    plot_facebook()


if __name__ == "__main__":
    main()
