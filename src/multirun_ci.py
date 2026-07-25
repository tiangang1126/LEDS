# -*- coding: utf-8 -*-
"""局限 (i) 修复：对四组主配置各独立运行 K 次，给出渗透率均值 ± 95% CI。

动机：正文主结果原为每条件单次运行。本脚本量化其运行间波动，将点估计升级为
区间估计（回应审稿人对单次运行可信度的质疑）。为暴露 Temperature=0 下云端 LLM
的天然运行间发散，每次运行使用全新的、不落盘的内存缓存（每个首见 Prompt 都真实
向云端采样），与 determinism_probe 的做法一致。

用法：
    python src/multirun_ci.py [--runs 5]
输出：
    results/multirun_ci.json   四组配置的渗透率样本、均值、95%CI、步数范围
"""
import argparse
import json
import os
import statistics
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config
from baselines import Decider, ci95, load_graph, run_llm_sim

CONFIGS = [
    ("exp1_scalefree", "无标度网络（随机核查员）"),
    ("exp1_smallworld", "小世界网络（随机核查员）"),
    ("exp2_edge_defense", "边缘部署（低度数核查员）"),
    ("exp2_hub_defense", "中心部署（Top-Hub 核查员）"),
]


def main() -> None:
    ap = argparse.ArgumentParser(description="四组主配置 K 次独立运行 + 95%CI")
    ap.add_argument("--runs", type=int, default=5, help="每条件独立运行次数 K")
    args = ap.parse_args()

    if not config.LLM_API_KEY:
        print("[错误] 未配置 DEEPSEEK_API_KEY，无法给出真实运行间波动。")
        sys.exit(1)

    t_max = config.T_MAX
    summary = {}
    for name, label in CONFIGS:
        g = load_graph(os.path.join(config.DATA_DIR, f"{name}.json"))
        pens, steps_list = [], []
        for i in range(args.runs):
            t0 = time.perf_counter()
            # 全新内存缓存、不落盘：暴露运行间非确定性
            r = run_llm_sim(g, Decider(mock=False, temperature=0.0,
                                       use_cache=True), "event", t_max)
            pens.append(r["penetration"])
            steps_list.append(r["steps"])
            print(f"  [{name}] 运行 {i + 1}/{args.runs}: "
                  f"渗透率={r['penetration']:.1f}% 步数={r['steps']} "
                  f"耗时={time.perf_counter() - t0:.0f}s")
        mean = statistics.mean(pens)
        summary[name] = {
            "label": label,
            "runs": args.runs,
            "penetration_samples": [round(p, 1) for p in pens],
            "penetration_mean": round(mean, 1),
            "penetration_ci95": round(ci95(pens), 1),
            "penetration_std": round(statistics.pstdev(pens), 2),
            "penetration_range": round(max(pens) - min(pens), 1),
            "steps_min": min(steps_list),
            "steps_max": max(steps_list),
        }
        print(f"→ [{label}] {mean:.1f}% ± {ci95(pens):.1f}% "
              f"(样本 {summary[name]['penetration_samples']})")

    out = os.path.join(config.RESULTS_DIR, "multirun_ci.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"mode": f"api({config.LLM_MODEL})", "conditions": summary},
                  f, ensure_ascii=False, indent=2)
    print(f"\n已写入 {out}")


if __name__ == "__main__":
    main()
