# -*- coding: utf-8 -*-
"""
Strict temperature ablation for LEDS.

This script answers the reviewer question: does fixing temperature at 0.0
change the LLM decision quality, or is it mainly a reproducibility control?

It reports two levels of evidence:
1. Prompt-level decision quality under the same prompt suite.
2. Simulation-level propagation stability under the same frozen network.

Formal paper data should be collected with a real LLM API and cache disabled.
Mock mode is only for validating the experiment pipeline.
"""
import argparse
import json
import math
import os
import statistics
import sys
import time
from itertools import combinations, product

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
from baselines import Decider, ci95, load_graph, run_llm_sim
from prompt_config import DEBUNK_CONTENT, MSG_DEBUNK, MSG_RUMOR, RUMOR_CONTENT
from stage2_engine import DeterministicLLM


PERSONAS = ("susceptible", "neutral", "fact_checker")
STANCES = ("Neutral", "Accept", "Reject")
RUMOR_COUNTS = (0, 1, 3, 4)
DEBUNK_COUNTS = (0, 1)


def build_messages(rumor_count: int, debunk_count: int) -> list:
    """Create a minimal current-step message set consistent with the counts."""
    messages = []
    if rumor_count > 0:
        messages.append({"type": MSG_RUMOR, "content": RUMOR_CONTENT, "sender": 101})
    if debunk_count > 0:
        messages.append({"type": MSG_DEBUNK, "content": DEBUNK_CONTENT, "sender": 202})
    if not messages:
        messages.append({"type": MSG_RUMOR, "content": RUMOR_CONTENT, "sender": 101})
    return messages


def make_prompt_suite(compact: bool) -> list:
    """Balanced prompt suite covering persona, stance, exposure and debunk cases."""
    cases = []
    rumor_values = (0, 1, 4) if compact else RUMOR_COUNTS
    for persona, stance, rumor_count, debunk_count in product(
            PERSONAS, STANCES, rumor_values, DEBUNK_COUNTS):
        cases.append({
            "persona": persona,
            "stance": stance,
            "rumor_count": rumor_count,
            "debunk_count": debunk_count,
            "new_messages": build_messages(rumor_count, debunk_count),
            "oracle": DeterministicLLM._mock_decide(
                persona, stance, rumor_count, debunk_count),
        })
    return cases


def decision_match(result: dict, oracle: dict) -> dict:
    return {
        "exact": result == oracle,
        "stance": result.get("stance") == oracle.get("stance"),
        "action": result.get("action") == oracle.get("action"),
    }


def run_prompt_ablation(temps: list, repeats: int, mock: bool,
                        compact_suite: bool) -> dict:
    suite = make_prompt_suite(compact_suite)
    output = {
        "suite": "compact" if compact_suite else "full",
        "num_cases": len(suite),
        "repeats": repeats,
        "by_temperature": {},
    }
    for temp in temps:
        decider = Decider(mock=mock, temperature=temp, use_cache=False)
        exact = stance = action = 0
        persona_totals = {p: {"n": 0, "exact": 0} for p in PERSONAS}
        started = time.perf_counter()
        for _ in range(repeats):
            for case in suite:
                result = decider.decide(
                    case["persona"],
                    case["stance"],
                    case["rumor_count"],
                    case["debunk_count"],
                    case["new_messages"],
                )
                m = decision_match(result, case["oracle"])
                exact += int(m["exact"])
                stance += int(m["stance"])
                action += int(m["action"])
                persona_totals[case["persona"]]["n"] += 1
                persona_totals[case["persona"]]["exact"] += int(m["exact"])
        total = len(suite) * repeats
        output["by_temperature"][str(temp)] = {
            "total_decisions": total,
            "api_calls": decider.call_count,
            "invalid_raw_outputs": decider.invalid_count,
            "fallbacks": decider.fallback_count,
            "raw_invalid_rate": round(100.0 * decider.invalid_count /
                                      max(decider.call_count, 1), 3),
            "fallback_rate": round(100.0 * decider.fallback_count /
                                   max(total, 1), 3),
            "rule_exact_rate": round(100.0 * exact / max(total, 1), 2),
            "stance_consistency_rate": round(100.0 * stance / max(total, 1), 2),
            "action_consistency_rate": round(100.0 * action / max(total, 1), 2),
            "per_persona_exact_rate": {
                p: round(100.0 * v["exact"] / max(v["n"], 1), 2)
                for p, v in persona_totals.items()
            },
            "wall_seconds": round(time.perf_counter() - started, 2),
        }
    return output


def hamming_percent(a: dict, b: dict) -> float:
    keys = sorted(set(a) | set(b), key=lambda x: int(x))
    if not keys:
        return 0.0
    diff = sum(1 for k in keys if a.get(k) != b.get(k))
    return 100.0 * diff / len(keys)


def mean_pairwise_hamming(states: list) -> float:
    if len(states) < 2:
        return 0.0
    vals = [hamming_percent(a, b) for a, b in combinations(states, 2)]
    return statistics.mean(vals)


def summarize_samples(samples: list) -> dict:
    if not samples:
        return {"mean": None, "std": None, "ci95": None, "min": None, "max": None}
    return {
        "mean": round(statistics.mean(samples), 3),
        "std": round(statistics.stdev(samples), 3) if len(samples) > 1 else 0.0,
        "ci95": round(ci95(samples), 3),
        "min": round(min(samples), 3),
        "max": round(max(samples), 3),
    }


def run_simulation_ablation(config_path: str, temps: list, runs: int,
                            mock: bool) -> dict:
    g = load_graph(config_path)
    output = {
        "config": os.path.basename(config_path),
        "n_nodes": g["n"],
        "runs_per_temperature": runs,
        "schedule": "event",
        "cache": "disabled",
        "by_temperature": {},
    }
    temp0_reference = None
    for temp in temps:
        pens = []
        steps = []
        converged = []
        states = []
        total_calls = total_invalid = total_fallback = 0
        started = time.perf_counter()
        for run_idx in range(runs):
            decider = Decider(mock=mock, temperature=temp, use_cache=False)
            result = run_llm_sim(g, decider, "event", config.T_MAX)
            pens.append(result["penetration"])
            steps.append(result["steps"])
            converged.append(bool(result["converged"]))
            state = {str(k): v for k, v in result["final_states"].items()}
            states.append(state)
            total_calls += result["api_calls"]
            total_invalid += result["invalid"]
            total_fallback += result["fallback"]
            if temp == 0.0 and run_idx == 0:
                temp0_reference = state
        ref_hamming = None
        if temp0_reference is not None:
            ref_hamming = statistics.mean(
                hamming_percent(temp0_reference, s) for s in states)
        output["by_temperature"][str(temp)] = {
            "penetration": summarize_samples(pens),
            "penetration_samples": [round(x, 3) for x in pens],
            "steps": summarize_samples(steps),
            "convergence_rate": round(100.0 * sum(converged) / max(runs, 1), 2),
            "api_calls_total": total_calls,
            "api_calls_mean": round(total_calls / max(runs, 1), 2),
            "invalid_raw_outputs_total": total_invalid,
            "fallbacks_total": total_fallback,
            "raw_invalid_rate": round(100.0 * total_invalid /
                                      max(total_calls, 1), 3),
            "fallback_rate": round(100.0 * total_fallback /
                                   max(total_calls, 1), 3),
            "mean_pairwise_hamming": round(mean_pairwise_hamming(states), 3),
            "mean_hamming_vs_temp0_ref": (
                round(ref_hamming, 3) if ref_hamming is not None else None
            ),
            "wall_seconds": round(time.perf_counter() - started, 2),
        }
    return output


def temp_sort_key(key: str) -> float:
    try:
        return float(key)
    except ValueError:
        return math.inf


def write_markdown(result: dict, path: str) -> None:
    prompt = result["prompt_level"]
    sim = result["simulation_level"]
    lines = [
        "# Temperature Ablation Tables",
        "",
        "> Mock mode is for pipeline validation only. Use API mode for paper data.",
        "",
        "## Prompt-level judgment quality",
        "",
        "| Temperature | Decisions | Rule exact (%) | Stance (%) | Action (%) | Raw invalid (%) | Fallback (%) |",
        "| :---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for temp in sorted(prompt["by_temperature"], key=temp_sort_key):
        row = prompt["by_temperature"][temp]
        lines.append(
            f"| {temp} | {row['total_decisions']} | {row['rule_exact_rate']:.2f} | "
            f"{row['stance_consistency_rate']:.2f} | {row['action_consistency_rate']:.2f} | "
            f"{row['raw_invalid_rate']:.3f} | {row['fallback_rate']:.3f} |"
        )
    lines.extend([
        "",
        "## Simulation-level propagation stability",
        "",
        "| Temperature | Runs | Penetration mean +/- 95%CI (%) | Std | Range | Mean pairwise Hamming (%) | Hamming vs Temp0 ref (%) | Invalid (%) | Fallbacks | API calls |",
        "| :---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ])
    for temp in sorted(sim["by_temperature"], key=temp_sort_key):
        row = sim["by_temperature"][temp]
        pen = row["penetration"]
        rng = f"{pen['min']:.2f}-{pen['max']:.2f}"
        lines.append(
            f"| {temp} | {sim['runs_per_temperature']} | "
            f"{pen['mean']:.2f} +/- {pen['ci95']:.2f} | {pen['std']:.2f} | {rng} | "
            f"{row['mean_pairwise_hamming']:.2f} | {row['mean_hamming_vs_temp0_ref']:.2f} | "
            f"{row['raw_invalid_rate']:.3f} | {row['fallbacks_total']} | {row['api_calls_total']} |"
        )
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def parse_temps(values: list) -> list:
    temps = [float(v) for v in values]
    if any(t < 0 for t in temps):
        raise ValueError("Temperature values must be non-negative.")
    return temps


def main() -> None:
    ap = argparse.ArgumentParser(description="Strict LEDS temperature ablation")
    ap.add_argument("--config", default=os.path.join(config.DATA_DIR,
                    "exp1_scalefree.json"))
    ap.add_argument("--temps", nargs="+", default=["0", "0.2", "0.5", "0.7"])
    ap.add_argument("--runs", type=int, default=5,
                    help="simulation runs per temperature")
    ap.add_argument("--prompt-repeats", type=int, default=3,
                    help="prompt-suite repeats per temperature")
    ap.add_argument("--compact-suite", action="store_true",
                    help="use fewer prompt cases for a cheaper pilot run")
    ap.add_argument("--mock", action="store_true",
                    help="offline deterministic pipeline validation")
    ap.add_argument("--output", default=os.path.join(
                    config.RESULTS_DIR, "temperature_ablation.json"))
    args = ap.parse_args()

    temps = parse_temps(args.temps)
    mock = args.mock or not config.LLM_API_KEY
    if mock and not args.mock:
        print("[WARN] DEEPSEEK_API_KEY is not set; falling back to --mock.")
        print("[WARN] Mock-mode numbers are not publishable paper evidence.")

    os.makedirs(config.RESULTS_DIR, exist_ok=True)
    mode = "mock" if mock else f"api({config.LLM_MODEL})"
    print(f"[TemperatureAblation] mode={mode}, temps={temps}, "
          f"runs={args.runs}, prompt_repeats={args.prompt_repeats}")

    result = {
        "mode": mode,
        "model": config.LLM_MODEL if not mock else "mock-rule-oracle",
        "temperatures": temps,
        "top_p": config.TOP_P,
        "t_max": config.T_MAX,
        "cache": "disabled",
        "prompt_level": run_prompt_ablation(
            temps, args.prompt_repeats, mock, args.compact_suite),
        "simulation_level": run_simulation_ablation(
            args.config, temps, args.runs, mock),
    }
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    md_path = os.path.splitext(args.output)[0] + "_table.md"
    write_markdown(result, md_path)
    print(f"[TemperatureAblation] wrote {args.output}")
    print(f"[TemperatureAblation] wrote {md_path}")


if __name__ == "__main__":
    main()
