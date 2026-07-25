# -*- coding: utf-8 -*-
"""Build the core mechanism ablation table from existing LEDS result files."""
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
OUT_DIR = RESULTS / "min_accept"


def load_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    baselines = load_json(RESULTS / "baselines.json")
    probe = load_json(RESULTS / "determinism_probe.json")

    leds = baselines["LEDS"]
    full = baselines["FullPolling"]
    mc = baselines["MonteCarlo"]
    replay = probe["cache_replay"]
    indep = probe["independent_runs"]
    hamming = probe["pairwise_divergence"]

    rows = [
        {
            "setting": "Full LEDS replay",
            "event_trigger": "Yes",
            "novelty_filter": "Yes",
            "decision_record_map": "Yes",
            "api_calls": leds["api_calls"],
            "penetration": f"{replay['seed_penetration']}% -> {replay['replay_penetration']}%",
            "run_divergence": "Not applicable",
            "replay_hamming": f"{replay['replay_hamming_pct']}%",
            "interpretation": "Fixed decision records yield exact node-level replay.",
        },
        {
            "setting": "LEDS independent runs",
            "event_trigger": "Yes",
            "novelty_filter": "Yes",
            "decision_record_map": "No shared map",
            "api_calls": "about 700 per run",
            "penetration": (
                f"{indep['penetration_mean']}% mean, "
                f"range {indep['penetration_range']} pp"),
            "run_divergence": (
                f"Hamming mean {hamming['hamming_mean_pct']}%, "
                f"max {hamming['hamming_max_pct']}%"),
            "replay_hamming": "Not applicable",
            "interpretation": "Fresh cloud calls expose run-to-run nondeterminism.",
        },
        {
            "setting": "Full Polling LLM",
            "event_trigger": "No",
            "novelty_filter": "No/weak",
            "decision_record_map": "Yes in baseline cache",
            "api_calls": full["api_calls"],
            "penetration": f"{full['penetration']:.1f}%",
            "run_divergence": "Not systematically estimated",
            "replay_hamming": "Not applicable",
            "interpretation": "Repeatedly rejudging idle nodes changes diffusion semantics.",
        },
        {
            "setting": f"High-temperature Monte Carlo (T={mc['temperature']})",
            "event_trigger": "Yes",
            "novelty_filter": "Yes",
            "decision_record_map": "Independent samples",
            "api_calls": mc["api_calls_total"],
            "penetration": (
                f"{mc['penetration_mean']}% +/- {mc['penetration_ci95']}%, "
                f"samples {mc['penetration_samples']}"),
            "run_divergence": "High sampling variance",
            "replay_hamming": "Not applicable",
            "interpretation": "Reference for high-temperature sampling, not a strict temperature ablation.",
        },
    ]

    md = [
        "# Core Mechanism Ablation Table",
        "",
        "| Setting | Event Trigger | Novelty Filter | Decision Record Map | API Calls | Penetration / Replay | Run Divergence | Replay Hamming | Interpretation |",
        "| :--- | :---: | :---: | :---: | ---: | :--- | :--- | :---: | :--- |",
    ]
    for r in rows:
        md.append(
            f"| {r['setting']} | {r['event_trigger']} | {r['novelty_filter']} | "
            f"{r['decision_record_map']} | {r['api_calls']} | {r['penetration']} | "
            f"{r['run_divergence']} | {r['replay_hamming']} | {r['interpretation']} |"
        )
    md.extend([
        "",
        "Note: The high-temperature Monte Carlo row changes both temperature and sampling protocol; it must be described as a high-temperature sampling reference, not as the strict temperature ablation.",
    ])
    out_md = OUT_DIR / "mechanism_ablation_table.md"
    out_json = OUT_DIR / "mechanism_ablation_table.json"
    out_md.write_text("\n".join(md) + "\n", encoding="utf-8")
    out_json.write_text(json.dumps(rows, ensure_ascii=False, indent=2),
                        encoding="utf-8")
    print(out_md)
    print(out_json)


if __name__ == "__main__":
    main()
