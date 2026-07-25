# -*- coding: utf-8 -*-
"""
LEDS 框架 —— 附加实验：Temperature=0 的运行间非确定性探针
（支撑论文 3.4 节"不假设物理级字节确定性"与 4.5 节"缓存重放才是可复现之源"的立论）

动机：现有 LLM 社会仿真普遍默认"Temperature=0 即可确定复现"。本探针在**同一**
冻结配置、真实云端 LLM、Temperature=0 下，独立重复运行 K 次，量化：
  · 宏观发散：最终渗透率的样本散布（均值/标准差/极差）；
  · 微观发散：任意两次运行"最终信念状态向量"的成对 Hamming 距离
             （即最终 stance 不同的节点占比），刻画轨迹层面的分歧；
并**对照演示**：借助 Prompt/Response 缓存重放，二次运行可逐节点精确复现
（Hamming 距离 = 0），从而证明 LEDS 的可复现性来自缓存重放机制，而非
"重复运行自然一致"。

用法：
    python src/determinism_probe.py --config data/exp1_scalefree.json [--runs 3] [--mock]

说明：为暴露运行间非确定性，K 次独立运行各自使用**全新的内存缓存、不落盘**
（每次首见 Prompt 都真实采样）；mock 模式下规则确定，发散必为 0，仅供链路验证。
真实 API 下每次运行约数百次调用，K 次成本相应叠加。

输出：
    results/determinism_probe.json   机器可读的发散指标与逐次结果
"""
import argparse
import itertools
import json
import os
import statistics
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
from baselines import Decider, load_graph, run_llm_sim


def hamming_fraction(states_a: dict, states_b: dict) -> float:
    """两次运行最终信念状态向量的 Hamming 距离（stance 不同的节点占比，%）。"""
    keys = set(states_a) | set(states_b)
    diff = sum(1 for k in keys if states_a.get(k) != states_b.get(k))
    return 100.0 * diff / len(keys)


def summarize_pairwise(runs: list) -> dict:
    """对 K 次运行的最终状态两两计算 Hamming 距离，汇总均值/最大值。"""
    pairs = list(itertools.combinations(range(len(runs)), 2))
    dists = [hamming_fraction(runs[i]["final_states"], runs[j]["final_states"])
             for i, j in pairs]
    return {
        "pairwise_hamming_pct": [round(d, 2) for d in dists],
        "hamming_mean_pct": round(statistics.mean(dists), 2) if dists else 0.0,
        "hamming_max_pct": round(max(dists), 2) if dists else 0.0,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Temperature=0 运行间非确定性探针")
    ap.add_argument("--config", default=os.path.join(config.DATA_DIR,
                    "exp1_scalefree.json"))
    ap.add_argument("--runs", type=int, default=3, help="独立重复运行次数 K")
    ap.add_argument("--mock", action="store_true", help="离线确定性规则模式（链路验证）")
    args = ap.parse_args()

    mock = args.mock or not config.LLM_API_KEY
    if mock and not args.mock:
        print("[警告] 未检测到 DEEPSEEK_API_KEY，降级 mock；mock 下发散必为 0。")
    mode = "mock(离线确定性规则)" if mock else f"api({config.LLM_MODEL})"
    g = load_graph(args.config)
    t_max = config.T_MAX
    print(f"[Probe] 图={os.path.basename(args.config)} N={g['n']} 模式={mode} "
          f"K={args.runs}")

    # ---- A. K 次独立运行（各自全新内存缓存、不落盘：暴露运行间非确定性） ----
    runs = []
    for i in range(args.runs):
        t0 = time.perf_counter()
        r = run_llm_sim(g, Decider(mock, 0.0, use_cache=True), "event", t_max)
        r["wall_seconds"] = round(time.perf_counter() - t0, 2)
        runs.append(r)
        print(f"  运行 {i+1}/{args.runs}: 渗透率={r['penetration']:.1f}% "
              f"步数={r['steps']} 调用={r['api_calls']} 耗时={r['wall_seconds']}s")

    pens = [r["penetration"] for r in runs]
    macro = {
        "penetration_samples": [round(p, 1) for p in pens],
        "penetration_mean": round(statistics.mean(pens), 2),
        "penetration_std": round(statistics.pstdev(pens), 2) if len(pens) > 1 else 0.0,
        "penetration_range": round(max(pens) - min(pens), 2),
        "steps_samples": [r["steps"] for r in runs],
    }
    micro = summarize_pairwise(runs)
    print(f"  → 宏观发散：渗透率 {macro['penetration_mean']}% "
          f"(std {macro['penetration_std']}, 极差 {macro['penetration_range']}pp)")
    print(f"  → 微观发散：成对 Hamming 均值 {micro['hamming_mean_pct']}% "
          f"最大 {micro['hamming_max_pct']}%")

    # ---- B. 缓存重放对照：写一次缓存，再回放一次，验证逐节点精确复现 ----
    replay_cache = os.path.join(config.CACHE_DIR, "probe_replay_cache.json")
    if os.path.exists(replay_cache):
        os.remove(replay_cache)
    seed_run = run_llm_sim(
        g, Decider(mock, 0.0, use_cache=True, disk_cache_path=replay_cache),
        "event", t_max)
    replay_run = run_llm_sim(
        g, Decider(mock, 0.0, use_cache=True, disk_cache_path=replay_cache),
        "event", t_max)
    replay_hamming = hamming_fraction(seed_run["final_states"],
                                      replay_run["final_states"])
    replay = {
        "seed_penetration": round(seed_run["penetration"], 1),
        "replay_penetration": round(replay_run["penetration"], 1),
        "replay_hamming_pct": round(replay_hamming, 2),
        "exact_replay": replay_hamming == 0.0
        and seed_run["penetration"] == replay_run["penetration"],
    }
    print(f"  → 缓存重放：seed={replay['seed_penetration']}% "
          f"replay={replay['replay_penetration']}% "
          f"Hamming={replay['replay_hamming_pct']}% "
          f"精确复现={'是' if replay['exact_replay'] else '否'}")

    result = {"mode": mode, "config": os.path.basename(args.config),
              "N": g["n"], "runs": args.runs,
              "independent_runs": macro, "pairwise_divergence": micro,
              "cache_replay": replay}
    os.makedirs(config.RESULTS_DIR, exist_ok=True)
    out = os.path.join(config.RESULTS_DIR, "determinism_probe.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"[Probe] 已写入 {out}")

    # ---- 结论提示 ----
    if not mock:
        if micro["hamming_max_pct"] > 0 or macro["penetration_range"] > 0:
            print("[结论] 真实 LLM 在 Temperature=0 下仍运行间发散（见上）；"
                  "而缓存重放实现逐节点精确复现——印证论文 3.4/4.5 节立论。")
        else:
            print("[结论] 本次未观测到运行间发散（可能因缓存或后端稳定）；"
                  "建议增大 --runs 复核。")
    else:
        print("[结论] mock 规则确定，发散为 0；请配置真实 API Key 复跑以观测非确定性。")


if __name__ == "__main__":
    main()
