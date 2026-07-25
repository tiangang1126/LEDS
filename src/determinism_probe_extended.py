# -*- coding: utf-8 -*-
"""
Extended determinism probe for min-acceptance revision.

Adds the required K=5 independent zero-temperature runs, Student-t CI,
all pairwise Hamming distances, and three cache replays from one decision map.
"""
import argparse
import itertools
import json
import math
import os
import statistics
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
from baselines import Decider, load_graph, run_llm_sim


T_CRITICAL_975 = {
    1: 12.706,
    2: 4.303,
    3: 3.182,
    4: 2.776,
    5: 2.571,
    6: 2.447,
    7: 2.365,
    8: 2.306,
    9: 2.262,
    10: 2.228,
}


def hamming_pct(a: dict, b: dict) -> float:
    keys = sorted(set(a) | set(b), key=lambda x: int(x))
    if not keys:
        return 0.0
    return 100.0 * sum(1 for k in keys if a.get(k) != b.get(k)) / len(keys)


def student_t_ci95(samples: list) -> float:
    if len(samples) < 2:
        return 0.0
    df = len(samples) - 1
    tcrit = T_CRITICAL_975.get(df, 1.96)
    return tcrit * statistics.stdev(samples) / math.sqrt(len(samples))


def sample_stats(samples: list) -> dict:
    if not samples:
        return {}
    return {
        "samples": [round(x, 3) for x in samples],
        "mean": round(statistics.mean(samples), 3),
        "std_sample": round(statistics.stdev(samples), 3) if len(samples) > 1 else 0.0,
        "ci95_student_t_half_width": round(student_t_ci95(samples), 3),
        "min": round(min(samples), 3),
        "max": round(max(samples), 3),
        "range": round(max(samples) - min(samples), 3),
        "median": round(statistics.median(samples), 3),
    }


def pairwise_rows(runs: list) -> list:
    rows = []
    for i, j in itertools.combinations(range(len(runs)), 2):
        rows.append({
            "pair": f"run_{i + 1} vs run_{j + 1}",
            "hamming_pct": round(hamming_pct(runs[i]["final_states"],
                                             runs[j]["final_states"]), 3),
            "penetration_i": round(runs[i]["penetration"], 3),
            "penetration_j": round(runs[j]["penetration"], 3),
        })
    return rows


def write_csv(path: str, rows: list) -> None:
    import csv
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if not rows:
        return
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def replay_exact(seed: dict, replay: dict) -> dict:
    h = hamming_pct(seed["final_states"], replay["final_states"])
    return {
        "penetration": round(replay["penetration"], 3),
        "steps": replay["steps"],
        "hamming_pct": round(h, 3),
        "exact_replay": h == 0.0 and seed["penetration"] == replay["penetration"],
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Extended LEDS determinism probe")
    ap.add_argument("--config", default=os.path.join(config.DATA_DIR,
                    "exp1_scalefree.json"))
    ap.add_argument("--runs", type=int, default=5)
    ap.add_argument("--replays", type=int, default=3)
    ap.add_argument("--mock", action="store_true")
    ap.add_argument("--output", default=os.path.join(
                    config.RESULTS_DIR, "min_accept",
                    "determinism_probe_k5.json"))
    args = ap.parse_args()

    mock = args.mock or not config.LLM_API_KEY
    if mock and not args.mock:
        print("[WARN] DEEPSEEK_API_KEY is not set; using mock mode.")
        print("[WARN] Mock outputs are not publishable paper evidence.")
    mode = "mock" if mock else f"api({config.LLM_MODEL})"
    g = load_graph(args.config)
    runs = []
    for idx in range(args.runs):
        started = time.perf_counter()
        # Fresh in-memory cache per run. No disk cache shared across runs.
        decider = Decider(mock=mock, temperature=0.0, use_cache=True)
        result = run_llm_sim(g, decider, "event", config.T_MAX)
        result["wall_seconds"] = round(time.perf_counter() - started, 2)
        runs.append(result)
        print(f"run {idx + 1}/{args.runs}: penetration={result['penetration']:.3f}, "
              f"steps={result['steps']}, calls={result['api_calls']}")

    pair_rows = pairwise_rows(runs)
    hamming_samples = [r["hamming_pct"] for r in pair_rows]
    pens = [r["penetration"] for r in runs]
    steps = [r["steps"] for r in runs]

    replay_cache = os.path.join(config.CACHE_DIR, "probe_replay_k5_cache.json")
    if os.path.exists(replay_cache):
        os.remove(replay_cache)
    seed_run = run_llm_sim(
        g, Decider(mock=mock, temperature=0.0, use_cache=True,
                   disk_cache_path=replay_cache),
        "event", config.T_MAX)
    replays = []
    for idx in range(args.replays):
        replay_run = run_llm_sim(
            g, Decider(mock=mock, temperature=0.0, use_cache=True,
                       disk_cache_path=replay_cache),
            "event", config.T_MAX)
        rec = replay_exact(seed_run, replay_run)
        rec["replay_id"] = idx + 1
        replays.append(rec)
        print(f"replay {idx + 1}/{args.replays}: hamming={rec['hamming_pct']}, "
              f"exact={rec['exact_replay']}")

    result = {
        "mode": mode,
        "config": os.path.basename(args.config),
        "n_nodes": g["n"],
        "runs": args.runs,
        "replays": args.replays,
        "temperature": 0.0,
        "top_p": config.TOP_P,
        "independent_runs": {
            "penetration": sample_stats(pens),
            "steps": sample_stats(steps),
            "api_calls": [r["api_calls"] for r in runs],
            "wall_seconds": [r["wall_seconds"] for r in runs],
        },
        "pairwise_hamming": {
            "pairs": pair_rows,
            "summary": sample_stats(hamming_samples),
        },
        "cache_replay": {
            "seed_penetration": round(seed_run["penetration"], 3),
            "seed_steps": seed_run["steps"],
            "replays": replays,
            "all_exact": all(r["exact_replay"] for r in replays),
        },
    }

    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    write_csv(os.path.join(os.path.dirname(args.output),
                           "determinism_pairwise_hamming.csv"), pair_rows)
    write_csv(os.path.join(os.path.dirname(args.output),
                           "determinism_replay_exact_match.csv"), replays)

    md = [
        "# Determinism Probe K=5",
        "",
        f"- Mode: {mode}",
        f"- Config: {result['config']}",
        f"- Penetration: {result['independent_runs']['penetration']['mean']:.2f} "
        f"+/- {result['independent_runs']['penetration']['ci95_student_t_half_width']:.2f}% "
        "(Student-t 95% CI half width)",
        f"- Pairwise Hamming mean: {result['pairwise_hamming']['summary']['mean']:.2f}%",
        f"- Pairwise Hamming max: {result['pairwise_hamming']['summary']['max']:.2f}%",
        f"- Replay all exact: {result['cache_replay']['all_exact']}",
    ]
    with open(os.path.join(os.path.dirname(args.output),
                           "determinism_probe_k5.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
