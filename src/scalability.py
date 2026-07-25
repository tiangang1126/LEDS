# -*- coding: utf-8 -*-
"""
LEDS 框架 —— 实验四：系统扩展性分析（论文 4.6 节 Experiment IV）

在 N ∈ {50, 100, 300, 1000}（可配）各档规模上，于新生成的 Barabási–Albert 无标度
网络上**实测**对比：
  · LEDS (事件驱动)  —— 仅激活收到新消息的节点，调用量 ∝ 被激活的消息事件数
  · Full-Polling     —— 每个时间步轮询全部 N 个节点，调用量 = N × 步数（O(T·|V|)）

产出真实测得的调用量与墙钟耗时随规模的增长曲线，替换论文 4.6 节此前无数据支撑的
占位数字（如 85,000 / 2,100）。mock 模式下同样真实运行，可零成本验证工程承载力；
论文正式数据请配置 DEEPSEEK_API_KEY 后重跑（注意真实 API 下大规模成本较高）。

用法：
    python src/scalability.py [--mock] [--sizes 50 100 300 1000]

输出：
    results/scalability.json                 各规模实测调用量/步数/耗时
    results/charts/exp4_scalability.png       对数尺度调用量-规模曲线（论文图 3）
"""
import argparse
import json
import os
import random
import sys
import time

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import networkx as nx

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
from prompt_config import MSG_RUMOR, RUMOR_CONTENT
from baselines import Decider, run_llm_sim

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

GEN_SEED = 2024   # 与 stage1_generator 保持一致的拓扑固化种子


def build_graph(n: int, seed: int) -> dict:
    """生成一档规模的 BA 无标度网络 + 60/30/10 人设分配，返回仿真器可用的图字典。"""
    ba = nx.barabasi_albert_graph(n, m=2, seed=seed)
    rng = random.Random(seed)
    nodes = list(range(n))
    rng.shuffle(nodes)
    n_susc, n_neu = int(n * 0.60), int(n * 0.30)
    personas = {}
    for i, node in enumerate(nodes):
        if i < n_susc:
            personas[node] = "susceptible"
        elif i < n_susc + n_neu:
            personas[node] = "neutral"
        else:
            personas[node] = "fact_checker"
    # 注入源：度数最低的易感者之一（普通节点），确定性选取（按 ID 升序取首个）
    degree = dict(ba.degree())
    candidates = sorted((node for node in range(n) if personas[node] == "susceptible"),
                        key=lambda x: (degree[x], x))
    source = candidates[0]
    adjacency = {u: tuple(sorted(v for v in ba.neighbors(u))) for u in ba.nodes()}
    return {
        "n": n, "personas": personas, "adjacency": adjacency, "source": source,
        "initial_message": {"type": MSG_RUMOR, "content": RUMOR_CONTENT},
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="LEDS 实验四：扩展性分析（实测）")
    ap.add_argument("--mock", action="store_true", help="离线确定性规则模式")
    ap.add_argument("--sizes", type=int, nargs="+", default=[50, 100, 300, 1000],
                    help="网络规模档位")
    args = ap.parse_args()

    mock = args.mock or not config.LLM_API_KEY
    if mock and not args.mock:
        print("[警告] 未检测到 DEEPSEEK_API_KEY，自动降级 mock 模式实测。")
    mode = "mock(离线确定性规则)" if mock else f"api({config.LLM_MODEL})"
    print(f"[Scalability] 模式={mode} 规模档位={args.sizes}")

    rows = []
    for n in args.sizes:
        g = build_graph(n, GEN_SEED)
        # 大规模全轮询在真实 API 下成本高，故 T_max 与主实验一致
        t0 = time.perf_counter()
        leds = run_llm_sim(g, Decider(mock, 0.0, use_cache=True), "event", config.T_MAX)
        leds_wall = time.perf_counter() - t0
        t0 = time.perf_counter()
        full = run_llm_sim(g, Decider(mock, 0.0, use_cache=True), "full", config.T_MAX)
        full_wall = time.perf_counter() - t0
        row = {
            "N": n,
            "leds_calls": leds["api_calls"], "leds_steps": leds["steps"],
            "leds_wall_seconds": round(leds_wall, 3),
            "full_calls": full["api_calls"], "full_steps": full["steps"],
            "full_wall_seconds": round(full_wall, 3),
            "speedup_calls": round(full["api_calls"] / max(leds["api_calls"], 1), 1),
        }
        rows.append(row)
        print(f"  N={n:>5} | LEDS 调用={leds['api_calls']:>6} "
              f"| Full-Polling 调用={full['api_calls']:>7} "
              f"| 削减={row['speedup_calls']}×")

    result = {"mode": mode, "rows": rows}
    os.makedirs(config.RESULTS_DIR, exist_ok=True)
    with open(os.path.join(config.RESULTS_DIR, "scalability.json"), "w",
              encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    # ---- 图 3：对数尺度调用量-规模曲线（论文 4.6 节） ----
    ns = [r["N"] for r in rows]
    fig, ax = plt.subplots(figsize=(8, 5), dpi=150)
    ax.plot(ns, [r["full_calls"] for r in rows], "--", color="#d62728",
            marker="s", linewidth=2, label="Full-Polling LLM (全轮询, $O(T|V|)$)")
    ax.plot(ns, [r["leds_calls"] for r in rows], "-", color="#2ca02c",
            marker="o", linewidth=2, label="LEDS (事件驱动, 本文)")
    ax.set_yscale("log")
    ax.set_xlabel("网络规模 $N$")
    ax.set_ylabel("LLM 判定次数（对数尺度）")
    ax.set_title(f"实验四：系统扩展性 — LLM 调用量随规模增长（{mode}）")
    ax.grid(True, which="both", linestyle="--", alpha=0.4)
    ax.legend(loc="best")
    for r in rows:
        ax.annotate(str(r["full_calls"]), (r["N"], r["full_calls"]),
                    textcoords="offset points", xytext=(0, 6), fontsize=8)
        ax.annotate(str(r["leds_calls"]), (r["N"], r["leds_calls"]),
                    textcoords="offset points", xytext=(0, -12), fontsize=8)
    os.makedirs(config.CHARTS_DIR, exist_ok=True)
    out = os.path.join(config.CHARTS_DIR, "exp4_scalability.png")
    fig.tight_layout()
    fig.savefig(out)
    plt.close(fig)
    print(f"[Scalability] 已写入 results/scalability.json 与 {out}")


if __name__ == "__main__":
    main()
