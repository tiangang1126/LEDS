# -*- coding: utf-8 -*-
"""Evaluate LEDS prompt-level temperature sensitivity outputs."""
import argparse
import csv
import json
import math
import os
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def read_jsonl(path: str) -> list:
    with open(path, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


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


def summarize(rows: list, group_keys: tuple) -> list:
    groups = defaultdict(list)
    for row in rows:
        key = tuple(row[k] for k in group_keys)
        groups[key].append(row)
    out = []
    for key, vals in sorted(groups.items(), key=lambda item: item[0]):
        total = len(vals)
        joint = sum(1 for r in vals if r["rule_correct"])
        stance = sum(1 for r in vals if r["stance_correct"])
        action = sum(1 for r in vals if r["action_correct"])
        valid = sum(1 for r in vals if r["json_valid"])
        low, high = wilson_ci(joint, total)
        rec = {k: v for k, v in zip(group_keys, key)}
        rec.update({
            "n": total,
            "joint_rule_acc": pct(joint, total),
            "joint_rule_ci95_low": round(low, 2),
            "joint_rule_ci95_high": round(high, 2),
            "stance_acc": pct(stance, total),
            "action_acc": pct(action, total),
            "json_valid": pct(valid, total),
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
        "| Temperature | N | Joint Rule Acc. | 95% Wilson CI | Stance Acc. | Action Acc. | JSON Valid | Prompt Disagreement |",
        "| :---: | ---: | ---: | :---: | ---: | ---: | ---: | ---: |",
    ]
    dis_map = {d["temperature"]: d for d in disagreements}
    for row in summary:
        d = dis_map.get(row["temperature"], {"disagreement_rate": 0.0})
        lines.append(
            f"| {row['temperature']} | {row['n']} | {row['joint_rule_acc']:.2f}% | "
            f"[{row['joint_rule_ci95_low']:.2f}, {row['joint_rule_ci95_high']:.2f}] | "
            f"{row['stance_acc']:.2f}% | {row['action_acc']:.2f}% | "
            f"{row['json_valid']:.2f}% | {d['disagreement_rate']:.2f}% |"
        )
    lines.extend([
        "",
        "## By Persona",
        "",
        "| Temperature | Persona | N | Joint Rule Acc. | 95% Wilson CI | Stance Acc. | Action Acc. | JSON Valid |",
        "| :---: | :---: | ---: | ---: | :---: | ---: | ---: | ---: |",
    ])
    for row in by_persona:
        lines.append(
            f"| {row['temperature']} | {row['persona']} | {row['n']} | "
            f"{row['joint_rule_acc']:.2f}% | "
            f"[{row['joint_rule_ci95_low']:.2f}, {row['joint_rule_ci95_high']:.2f}] | "
            f"{row['stance_acc']:.2f}% | {row['action_acc']:.2f}% | "
            f"{row['json_valid']:.2f}% |"
        )
    with open(os.path.join(output_dir, "temperature_summary.md"), "w",
              encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def noninferiority_rows(summary: list, margin_pct: float) -> list:
    by_temp = {float(r["temperature"]): r for r in summary}
    if 0.0 not in by_temp:
        return []
    t0 = by_temp[0.0]["joint_rule_acc"]
    out = []
    for temp, row in sorted(by_temp.items()):
        if temp == 0.0:
            continue
        diff = round(t0 - row["joint_rule_acc"], 2)
        out.append({
            "comparison": f"T=0.0 minus T={temp}",
            "joint_rule_acc_diff_pct": diff,
            "noninferiority_margin_pct": margin_pct,
            "passes_descriptive_margin": diff >= -margin_pct,
        })
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Evaluate LEDS temperature grid")
    ap.add_argument("--input", default=os.path.join(
        ROOT, "experiments", "temperature_sensitivity", "raw_outputs.jsonl"))
    ap.add_argument("--output-dir", default=os.path.join(
        ROOT, "experiments", "temperature_sensitivity"))
    ap.add_argument("--noninferiority-margin", type=float, default=3.0)
    args = ap.parse_args()

    rows = read_jsonl(args.input)
    if not rows:
        print("no rows")
        sys.exit(1)
    summary = summarize(rows, ("temperature",))
    by_persona = summarize(rows, ("temperature", "persona"))
    disagreements, disagreement_examples = prompt_disagreement(rows)
    ni = noninferiority_rows(summary, args.noninferiority_margin)

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
    print(f"wrote summaries -> {args.output_dir}")


if __name__ == "__main__":
    main()
