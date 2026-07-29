# -*- coding: utf-8 -*-
"""Evaluate LEDS prompt-level temperature sensitivity outputs."""
import argparse
import csv
import hashlib
import json
import math
import os
import random
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def read_jsonl(path: str) -> list:
    with open(path, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def file_sha256(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def wilson_ci(successes: int, total: int, z: float = 1.96) -> tuple:
    if total == 0:
        return (0.0, 0.0)
    p = successes / total
    denom = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denom
    half = z * math.sqrt((p * (1 - p) + z * z / (4 * total)) / total) / denom
    return (100 * (center - half), 100 * (center + half))


def pct(x: int, n: int) -> float:
    return round(100.0 * x / n, 2) if n else 0.0


def percentile(sorted_values: list, probability: float) -> float:
    """Linear-interpolated sample percentile (R/NumPy type 7)."""
    if not sorted_values:
        raise ValueError("cannot calculate a percentile of an empty sample")
    position = (len(sorted_values) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return sorted_values[lower]
    weight = position - lower
    return sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight


def derived_seed(base_seed: int, label: str) -> int:
    digest = hashlib.sha256(f"{base_seed}:{label}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


def stratified_bootstrap_mean_ci(values_by_stratum: dict, resamples: int,
                                 seed: int) -> tuple:
    """Bootstrap independent Prompt clusters while preserving persona counts."""
    rng = random.Random(seed)
    strata = [list(values) for _, values in sorted(values_by_stratum.items())]
    if not strata or any(not values for values in strata):
        raise ValueError("each bootstrap stratum must contain at least one Prompt")
    draws = []
    total_n = sum(len(values) for values in strata)
    for _ in range(resamples):
        total = 0.0
        for values in strata:
            total += sum(values[rng.randrange(len(values))]
                         for _ in range(len(values)))
        draws.append(100.0 * total / total_n)
    draws.sort()
    return percentile(draws, 0.025), percentile(draws, 0.975)


def aggregate_prompt_repeats(rows: list, expected_repeats: int = 3) -> list:
    """Collapse repeated calls so Prompt, rather than API output, is the unit."""
    groups = defaultdict(list)
    for row in rows:
        groups[(float(row["temperature"]), row["prompt_id"])].append(row)
    prompt_rows = []
    for (temperature, prompt_id), vals in sorted(groups.items()):
        repeat_ids = {int(row["repeat_id"]) for row in vals}
        if len(vals) != expected_repeats or len(repeat_ids) != expected_repeats:
            raise ValueError(
                f"{prompt_id} at T={temperature} has {len(vals)} rows and "
                f"{len(repeat_ids)} unique repeats; expected {expected_repeats}"
            )
        personas = {row["persona"] for row in vals}
        if len(personas) != 1:
            raise ValueError(f"inconsistent persona for Prompt {prompt_id}")
        prompt_rows.append({
            "temperature": temperature,
            "prompt_id": prompt_id,
            "persona": vals[0]["persona"],
            "repeat_count": len(vals),
            "joint_rule_acc": sum(bool(r["rule_correct"]) for r in vals) / len(vals),
            "stance_acc": sum(bool(r["stance_correct"]) for r in vals) / len(vals),
            "action_acc": sum(bool(r["action_correct"]) for r in vals) / len(vals),
            "json_valid": sum(bool(r["json_valid"]) for r in vals) / len(vals),
        })
    return prompt_rows


def summarize_prompt_level(rows: list, group_keys: tuple, resamples: int,
                           seed: int) -> list:
    groups = defaultdict(list)
    for row in rows:
        key = tuple(row[k] for k in group_keys)
        groups[key].append(row)
    out = []
    for key, vals in sorted(groups.items(), key=lambda item: item[0]):
        prompt_n = len(vals)
        output_n = sum(r["repeat_count"] for r in vals)
        strata = defaultdict(list)
        for row in vals:
            strata[row["persona"]].append(row["joint_rule_acc"])
        label = "|".join(str(part) for part in key)
        low, high = stratified_bootstrap_mean_ci(
            strata, resamples, derived_seed(seed, f"summary:{label}"))
        rec = {k: v for k, v in zip(group_keys, key)}
        rec.update({
            "prompt_n": prompt_n,
            "output_n": output_n,
            "repeats_per_prompt": output_n // prompt_n,
            "joint_rule_acc": round(100 * sum(r["joint_rule_acc"] for r in vals) / prompt_n, 2),
            "joint_rule_cluster_bootstrap_ci95_low": round(low, 2),
            "joint_rule_cluster_bootstrap_ci95_high": round(high, 2),
            "stance_acc": round(100 * sum(r["stance_acc"] for r in vals) / prompt_n, 2),
            "action_acc": round(100 * sum(r["action_acc"] for r in vals) / prompt_n, 2),
            "json_valid": round(100 * sum(r["json_valid"] for r in vals) / prompt_n, 2),
            "bootstrap_resamples": resamples,
            "bootstrap_seed": seed,
        })
        out.append(rec)
    return out


def prompt_disagreement(rows: list) -> list:
    groups = defaultdict(list)
    for row in rows:
        groups[(row["temperature"], row["prompt_id"])].append(row)
    by_temp = defaultdict(lambda: {"n": 0, "disagree": 0})
    examples = []
    for (temp, prompt_id), vals in groups.items():
        outputs = {(r.get("parsed_stance"), r.get("parsed_action")) for r in vals}
        by_temp[temp]["n"] += 1
        if len(outputs) > 1:
            by_temp[temp]["disagree"] += 1
            examples.append({
                "temperature": temp,
                "prompt_id": prompt_id,
                "persona": vals[0]["persona"],
                "outputs": sorted([str(x) for x in outputs]),
            })
    return [
        {"temperature": temp, "prompt_count": v["n"],
         "disagreement_rate": pct(v["disagree"], v["n"]),
         "disagreement_count": v["disagree"]}
        for temp, v in sorted(by_temp.items())
    ], examples


def write_csv(path: str, rows: list) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if not rows:
        return
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_markdown(summary: list, by_persona: list, disagreements: list,
                   output_dir: str) -> None:
    lines = [
        "# LEDS Temperature Sensitivity Summary",
        "",
        "## Overall",
        "",
        "Inference unit: Prompt. Each Prompt's three calls are averaged before analysis. "
        "Intervals are persona-stratified Prompt-cluster bootstrap percentile intervals.",
        "",
        "| Temperature | Prompts | Outputs | Joint Rule Acc. | 95% Prompt-bootstrap CI | Stance Acc. | Action Acc. | JSON Valid | Prompt Disagreement |",
        "| :---: | ---: | ---: | ---: | :---: | ---: | ---: | ---: | ---: |",
    ]
    dis_map = {d["temperature"]: d for d in disagreements}
    for row in summary:
        d = dis_map.get(row["temperature"], {"disagreement_rate": 0.0})
        lines.append(
            f"| {row['temperature']} | {row['prompt_n']} | {row['output_n']} | "
            f"{row['joint_rule_acc']:.2f}% | "
            f"[{row['joint_rule_cluster_bootstrap_ci95_low']:.2f}, "
            f"{row['joint_rule_cluster_bootstrap_ci95_high']:.2f}] | "
            f"{row['stance_acc']:.2f}% | {row['action_acc']:.2f}% | "
            f"{row['json_valid']:.2f}% | {d['disagreement_rate']:.2f}% |"
        )
    lines.extend([
        "",
        "## By Persona",
        "",
        "| Temperature | Persona | Prompts | Outputs | Joint Rule Acc. | 95% Prompt-bootstrap CI | Stance Acc. | Action Acc. | JSON Valid |",
        "| :---: | :---: | ---: | ---: | ---: | :---: | ---: | ---: | ---: |",
    ])
    for row in by_persona:
        lines.append(
            f"| {row['temperature']} | {row['persona']} | {row['prompt_n']} | "
            f"{row['output_n']} | "
            f"{row['joint_rule_acc']:.2f}% | "
            f"[{row['joint_rule_cluster_bootstrap_ci95_low']:.2f}, "
            f"{row['joint_rule_cluster_bootstrap_ci95_high']:.2f}] | "
            f"{row['stance_acc']:.2f}% | {row['action_acc']:.2f}% | "
            f"{row['json_valid']:.2f}% |"
        )
    with open(os.path.join(output_dir, "temperature_summary.md"), "w",
              encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def paired_noninferiority_rows(prompt_rows: list, margin_pct: float,
                               resamples: int, seed: int) -> list:
    by_prompt = defaultdict(dict)
    persona_by_prompt = {}
    for row in prompt_rows:
        by_prompt[row["prompt_id"]][float(row["temperature"])] = row["joint_rule_acc"]
        persona_by_prompt[row["prompt_id"]] = row["persona"]
    temperatures = sorted({float(r["temperature"]) for r in prompt_rows})
    if 0.0 not in temperatures:
        return []
    out = []
    for temp in temperatures:
        if temp == 0.0:
            continue
        differences = defaultdict(list)
        for prompt_id, values in by_prompt.items():
            if 0.0 not in values or temp not in values:
                raise ValueError(f"Prompt {prompt_id} lacks a paired temperature value")
            differences[persona_by_prompt[prompt_id]].append(values[0.0] - values[temp])
        prompt_n = sum(len(values) for values in differences.values())
        diff = 100.0 * sum(sum(values) for values in differences.values()) / prompt_n
        low, high = stratified_bootstrap_mean_ci(
            differences, resamples,
            derived_seed(seed, f"paired-difference:0.0:{temp}"))
        out.append({
            "comparison": f"T=0.0 minus T={temp}",
            "prompt_n": prompt_n,
            "joint_rule_acc_diff_pct": round(diff, 2),
            "paired_prompt_bootstrap_ci95_low": round(low, 2),
            "paired_prompt_bootstrap_ci95_high": round(high, 2),
            "noninferiority_margin_pct": margin_pct,
            "noninferiority_established": low > -margin_pct,
            "bootstrap_resamples": resamples,
            "bootstrap_seed": seed,
        })
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Evaluate LEDS temperature grid")
    ap.add_argument("--input", default=os.path.join(
        ROOT, "experiments", "temperature_sensitivity", "raw_outputs.jsonl"))
    ap.add_argument("--output-dir", default=os.path.join(
        ROOT, "experiments", "temperature_sensitivity"))
    ap.add_argument("--noninferiority-margin", type=float, default=3.0)
    ap.add_argument("--bootstrap-resamples", type=int, default=50000)
    ap.add_argument("--bootstrap-seed", type=int, default=20260729)
    args = ap.parse_args()

    rows = read_jsonl(args.input)
    if not rows:
        print("no rows")
        sys.exit(1)
    prompt_rows = aggregate_prompt_repeats(rows)
    summary = summarize_prompt_level(
        prompt_rows, ("temperature",), args.bootstrap_resamples,
        args.bootstrap_seed)
    by_persona = summarize_prompt_level(
        prompt_rows, ("temperature", "persona"), args.bootstrap_resamples,
        args.bootstrap_seed)
    disagreements, disagreement_examples = prompt_disagreement(rows)
    ni = paired_noninferiority_rows(
        prompt_rows, args.noninferiority_margin, args.bootstrap_resamples,
        args.bootstrap_seed)

    write_csv(os.path.join(args.output_dir, "temperature_summary.csv"), summary)
    write_csv(os.path.join(args.output_dir, "temperature_by_persona.csv"), by_persona)
    write_csv(os.path.join(args.output_dir, "temperature_disagreement.csv"),
              disagreements)
    write_csv(os.path.join(args.output_dir, "temperature_noninferiority.csv"), ni)
    with open(os.path.join(args.output_dir, "temperature_failures.jsonl"), "w",
              encoding="utf-8") as f:
        for row in rows:
            if (not row["json_valid"]) or (not row["rule_correct"]):
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
    with open(os.path.join(args.output_dir, "temperature_disagreement_examples.json"),
              "w", encoding="utf-8") as f:
        json.dump(disagreement_examples, f, ensure_ascii=False, indent=2)
    write_markdown(summary, by_persona, disagreements, args.output_dir)
    audit = {
        "analysis_unit": "prompt_cluster",
        "pairing_unit": "prompt_id",
        "stratification": "persona",
        "repeat_aggregation": "mean of three rule-correct indicators per Prompt and temperature",
        "interval_method": "persona-stratified paired Prompt-cluster percentile bootstrap",
        "raw_input": os.path.relpath(os.path.abspath(args.input), ROOT),
        "raw_input_sha256": file_sha256(args.input),
        "raw_output_rows": len(rows),
        "prompt_temperature_clusters": len(prompt_rows),
        "unique_prompts": len({row["prompt_id"] for row in prompt_rows}),
        "temperatures": sorted({row["temperature"] for row in prompt_rows}),
        "repeats_per_prompt_temperature": 3,
        "bootstrap_resamples": args.bootstrap_resamples,
        "bootstrap_seed": args.bootstrap_seed,
        "noninferiority_margin_percentage_points": args.noninferiority_margin,
        "noninferiority_interpretation": (
            "Exploratory support at the analysis margin; not a preregistered "
            "confirmatory noninferiority trial."
        ),
        "temperature_summary": summary,
        "paired_differences": ni,
    }
    with open(os.path.join(args.output_dir, "temperature_prompt_level_audit.json"),
              "w", encoding="utf-8") as f:
        json.dump(audit, f, ensure_ascii=False, indent=2)
    print(f"wrote summaries -> {args.output_dir}")


if __name__ == "__main__":
    main()
