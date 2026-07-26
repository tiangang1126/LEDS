# -*- coding: utf-8 -*-
"""
Auditable K=5 zero-temperature determinism probe for the LEDS revision.

The script upgrades the original min-acceptance probe into a paper-auditable
artifact:
- five independent zero-temperature runs with fresh decision records,
- Student-t confidence intervals,
- all ten pairwise Hamming distances,
- three decision-record replays from one seed run,
- final-state and trace hashes,
- metadata hashes for config, prompt/schema code, and the script itself,
- proof that replay does not invoke the cloud API.
"""
import argparse
import csv
import hashlib
import itertools
import json
import math
import os
import statistics
import subprocess
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
from baselines import Decider, load_graph
from prompt_config import DEBUNK_CONTENT, MSG_DEBUNK, MSG_RUMOR, RUMOR_CONTENT


ROOT = Path(config.BASE_DIR)
SRC_DIR = ROOT / "src"
DEFAULT_OUT = Path(config.RESULTS_DIR) / "min_accept" / (
    "determinism_probe_k5.json"
)

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


class AuditDecider(Decider):
    """Decider wrapper that counts true cloud calls separately from decisions."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cloud_call_count = 0

    def _call_api(self, user_prompt: str) -> str:
        self.cloud_call_count += 1
        return super()._call_api(user_prompt)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_json(obj) -> str:
    payload = json.dumps(obj, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def read_json(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def git_value(args: list[str]) -> str:
    try:
        return subprocess.check_output(
            ["git", *args], cwd=str(ROOT), text=True,
            stderr=subprocess.DEVNULL
        ).strip()
    except Exception:
        return "unavailable"


def git_dirty() -> str:
    try:
        out = subprocess.check_output(
            ["git", "status", "--short"], cwd=str(ROOT), text=True,
            stderr=subprocess.DEVNULL
        )
        return "true" if out.strip() else "false"
    except Exception:
        return "unavailable"


def state_hash(final_states: dict) -> str:
    states = {str(k): final_states[k] for k in sorted(final_states, key=int)}
    return sha256_json(states)


def trace_hash(result: dict) -> str:
    return sha256_json({
        "steps": result["steps"],
        "penetration": round(result["penetration"], 12),
        "final_states": {str(k): result["final_states"][k]
                         for k in sorted(result["final_states"], key=int)},
        "trace": result.get("trace", []),
    })


def run_llm_sim_audit(g: dict, decider: Decider, t_max: int) -> dict:
    """Run the LEDS event schedule and retain per-step audit trace."""
    n = g["n"]
    personas, adjacency = g["personas"], g["adjacency"]
    stances = {i: "Neutral" for i in range(n)}
    rumor_count, debunk_count = defaultdict(int), defaultdict(int)
    sent_edges = set()
    trace = []

    def emit(sender, action, next_queue):
        msg_type = MSG_RUMOR if action == "Share" else MSG_DEBUNK
        content = RUMOR_CONTENT if action == "Share" else DEBUNK_CONTENT
        for nb in adjacency.get(sender, ()):
            key = (sender, nb, msg_type)
            if key in sent_edges:
                continue
            sent_edges.add(key)
            next_queue[nb].append({
                "type": msg_type,
                "content": content,
                "sender": sender,
            })

    queue = defaultdict(list)
    queue[g["source"]].append({**g["initial_message"], "sender": -1})
    t = 0
    while queue and t < t_max:
        next_queue = defaultdict(list)
        polled = sorted(queue.keys())
        step_trace = {
            "step": t,
            "queue": {str(k): queue[k] for k in sorted(queue.keys())},
            "polled": list(polled),
            "transitions": [],
        }
        for node in polled:
            messages = queue.get(node, [])
            for m in messages:
                if m["type"] == MSG_RUMOR:
                    rumor_count[node] += 1
                else:
                    debunk_count[node] += 1
            prev_stance = stances[node]
            result = decider.decide(
                personas[node],
                stances[node],
                rumor_count[node],
                debunk_count[node],
                messages,
            )
            stances[node] = result["stance"]
            step_trace["transitions"].append({
                "node": node,
                "prev_stance": prev_stance,
                "next_stance": result["stance"],
                "action": result["action"],
                "rumor_count": rumor_count[node],
                "debunk_count": debunk_count[node],
            })
            if result["action"] in ("Share", "Debunk"):
                emit(node, result["action"], next_queue)
        step_trace["next_queue"] = {
            str(k): next_queue[k] for k in sorted(next_queue.keys())
        }
        trace.append(step_trace)
        t += 1
        queue = next_queue

    accept = sum(1 for s in stances.values() if s == "Accept")
    return {
        "steps": t,
        "api_calls": decider.call_count,
        "penetration": 100.0 * accept / n,
        "converged": not queue,
        "invalid": decider.invalid_count,
        "fallback": decider.fallback_count,
        "final_states": {int(k): v for k, v in stances.items()},
        "trace": trace,
    }


def hamming_pct(a: dict, b: dict) -> float:
    keys = sorted(set(a) | set(b), key=lambda x: int(x))
    if not keys:
        return 0.0
    return 100.0 * sum(1 for k in keys if a.get(k) != b.get(k)) / len(keys)


def student_t_ci95(samples: list[float]) -> float:
    if len(samples) < 2:
        return 0.0
    df = len(samples) - 1
    tcrit = T_CRITICAL_975.get(df, 1.96)
    return tcrit * statistics.stdev(samples) / math.sqrt(len(samples))


def sample_stats(samples: list[float]) -> dict:
    if not samples:
        return {}
    mean = statistics.mean(samples)
    half = student_t_ci95(samples)
    return {
        "samples": [round(x, 3) for x in samples],
        "mean": round(mean, 3),
        "std_sample": round(statistics.stdev(samples), 3)
        if len(samples) > 1 else 0.0,
        "ci95_student_t_half_width": round(half, 3),
        "ci95_student_t_lower": round(mean - half, 3),
        "ci95_student_t_upper": round(mean + half, 3),
        "min": round(min(samples), 3),
        "max": round(max(samples), 3),
        "range": round(max(samples) - min(samples), 3),
        "median": round(statistics.median(samples), 3),
    }


def output_paths(output: Path) -> dict:
    stem = output.stem
    parent = output.parent
    return {
        "json": output,
        "md": parent / f"{stem}.md",
        "pairwise_csv": parent / f"{stem}_pairwise_hamming.csv",
        "replay_csv": parent / f"{stem}_replay_exact_match.csv",
        "run_jsonl": parent / f"{stem}_independent_runs.jsonl",
    }


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        return
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def fresh_cache_path(args, run_name: str) -> Path:
    backend = "mock" if args.mock else config.LLM_MODEL
    backend = backend.replace("/", "-").replace(":", "-")
    return Path(config.CACHE_DIR) / "determinism_k5" / backend / f"{run_name}.json"


def run_once(g: dict, args, run_name: str, mock: bool,
             collect_trace: bool = True) -> dict:
    cache_path = fresh_cache_path(args, run_name)
    if cache_path.exists():
        cache_path.unlink()
    started_perf = time.perf_counter()
    started_utc = utc_now()
    decider = AuditDecider(
        mock=mock,
        temperature=0.0,
        use_cache=True,
        disk_cache_path=str(cache_path),
    )
    result = run_llm_sim_audit(g, decider, config.T_MAX)
    result["run_name"] = run_name
    result["started_utc"] = started_utc
    result["finished_utc"] = utc_now()
    result["wall_seconds"] = round(time.perf_counter() - started_perf, 2)
    result["decision_requests"] = result.pop("api_calls")
    result["cloud_api_calls"] = decider.cloud_call_count
    result["cache_path"] = str(cache_path.relative_to(ROOT))
    result["decision_record_count"] = len(decider.cache)
    result["final_state_hash"] = state_hash(result["final_states"])
    result["trace_hash"] = trace_hash(result)
    result.pop("trace", None)
    return result


def run_replay(g: dict, args, seed_cache: Path, replay_name: str,
               mock: bool, seed_result: dict) -> dict:
    started_perf = time.perf_counter()
    decider = AuditDecider(
        mock=mock,
        temperature=0.0,
        use_cache=True,
        disk_cache_path=str(seed_cache),
    )
    before_cloud = decider.cloud_call_count
    result = run_llm_sim_audit(g, decider, config.T_MAX)
    cloud_delta = decider.cloud_call_count - before_cloud
    result["run_name"] = replay_name
    result["wall_seconds"] = round(time.perf_counter() - started_perf, 2)
    result["decision_requests"] = result.pop("api_calls")
    result["cloud_api_calls"] = decider.cloud_call_count
    result["cloud_api_calls_during_replay"] = cloud_delta
    result["decision_record_count"] = len(decider.cache)
    result["final_state_hash"] = state_hash(result["final_states"])
    result["trace_hash"] = trace_hash(result)
    hamming = hamming_pct(seed_result["final_states"], result["final_states"])
    exact = (
        cloud_delta == 0
        and hamming == 0.0
        and seed_result["penetration"] == result["penetration"]
        and seed_result["steps"] == result["steps"]
        and seed_result["final_state_hash"] == result["final_state_hash"]
        and seed_result["trace_hash"] == result["trace_hash"]
    )
    result["hamming_pct"] = round(hamming, 3)
    result["penetration_exact"] = seed_result["penetration"] == result["penetration"]
    result["steps_exact"] = seed_result["steps"] == result["steps"]
    result["final_state_hash_exact"] = (
        seed_result["final_state_hash"] == result["final_state_hash"]
    )
    result["trace_hash_exact"] = seed_result["trace_hash"] == result["trace_hash"]
    result["exact_replay"] = exact
    result.pop("trace", None)
    return result


def pairwise_rows(runs: list[dict]) -> list[dict]:
    rows = []
    for i, j in itertools.combinations(range(len(runs)), 2):
        a, b = runs[i], runs[j]
        rows.append({
            "pair": f"{a['run_name']} vs {b['run_name']}",
            "hamming_pct": round(hamming_pct(a["final_states"],
                                             b["final_states"]), 3),
            "penetration_i": round(a["penetration"], 3),
            "penetration_j": round(b["penetration"], 3),
            "steps_i": a["steps"],
            "steps_j": b["steps"],
            "state_hash_i": a["final_state_hash"],
            "state_hash_j": b["final_state_hash"],
        })
    return rows


def compact_run(r: dict) -> dict:
    return {k: v for k, v in r.items() if k != "final_states"}


def metadata(args, paths: dict, started_utc: str, finished_utc: str) -> dict:
    config_path = Path(args.config)
    prompt_path = SRC_DIR / "prompt_config.py"
    stage2_path = SRC_DIR / "stage2_engine.py"
    script_path = SRC_DIR / "determinism_probe_extended.py"
    graph = read_json(config_path)
    return {
        "started_utc": started_utc,
        "finished_utc": finished_utc,
        "mode": "mock" if args.mock or not config.LLM_API_KEY
        else f"api({config.LLM_MODEL})",
        "mock": bool(args.mock or not config.LLM_API_KEY),
        "model": config.LLM_MODEL,
        "endpoint": config.LLM_BASE_URL,
        "temperature": 0.0,
        "top_p": config.TOP_P,
        "api_timeout": config.API_TIMEOUT,
        "api_max_retries": config.API_MAX_RETRIES,
        "t_max": config.T_MAX,
        "runs": args.runs,
        "replays": args.replays,
        "config_path": str(config_path),
        "config_sha256": sha256_file(config_path),
        "prompt_config_sha256": sha256_file(prompt_path),
        "schema_source_sha256": sha256_file(stage2_path),
        "script_sha256": sha256_file(script_path),
        "graph_source_node": graph.get("source_node"),
        "graph_n": graph.get("N"),
        "graph_edges": len(graph.get("edges", [])),
        "git_commit": git_value(["rev-parse", "HEAD"]),
        "git_dirty": git_dirty(),
        "output_files": {k: str(v.relative_to(ROOT)) for k, v in paths.items()},
    }


def write_run_jsonl(path: Path, runs: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in runs:
            f.write(json.dumps(compact_run(r), ensure_ascii=False,
                               sort_keys=True) + "\n")


def write_markdown(path: Path, result: dict) -> None:
    p = result["independent_runs"]["penetration"]
    s = result["independent_runs"]["steps"]
    h = result["pairwise_hamming"]["summary"]
    replay = result["cache_replay"]
    meta = result["metadata"]
    lines = [
        "# Determinism Probe K=5",
        "",
        f"- Mode: {meta['mode']}",
        f"- Model: {meta['model']}",
        f"- Endpoint: {meta['endpoint']}",
        f"- Config: {meta['config_path']}",
        f"- Config SHA256: `{meta['config_sha256']}`",
        f"- Prompt config SHA256: `{meta['prompt_config_sha256']}`",
        f"- Schema source SHA256: `{meta['schema_source_sha256']}`",
        f"- Script SHA256: `{meta['script_sha256']}`",
        f"- Git commit: `{meta['git_commit']}`; dirty: {meta['git_dirty']}",
        f"- Started UTC: {meta['started_utc']}",
        f"- Finished UTC: {meta['finished_utc']}",
        "",
        "## Independent Runs",
        "",
        f"- K: {meta['runs']}",
        f"- Temperature / Top_P: {meta['temperature']} / {meta['top_p']}",
        f"- Penetration samples: {p['samples']}",
        f"- Penetration mean: {p['mean']:.3f}%",
        f"- Penetration sample std: {p['std_sample']:.3f}%",
        f"- Penetration Student-t 95% CI: "
        f"[{p['ci95_student_t_lower']:.3f}%, "
        f"{p['ci95_student_t_upper']:.3f}%]",
        f"- Penetration range: {p['range']:.3f} pp",
        f"- Stable-step samples: {s['samples']}",
        f"- Stable-step Student-t 95% CI: "
        f"[{s['ci95_student_t_lower']:.3f}, "
        f"{s['ci95_student_t_upper']:.3f}]",
        f"- Pairwise Hamming samples: {h['samples']}",
        f"- Pairwise Hamming mean / std / max: "
        f"{h['mean']:.3f}% / {h['std_sample']:.3f}% / {h['max']:.3f}%",
        "",
        "## Decision-Record Replay",
        "",
        f"- Seed run: {replay['seed_run']}",
        f"- Replay count: {meta['replays']}",
        f"- Replay exact match: {replay['exact_match_count']}/{meta['replays']}",
        f"- Replay cloud calls during replay: "
        f"{replay['cloud_api_calls_during_replay']}",
        f"- Replay all exact: {replay['all_exact']}",
        f"- Replay all final-state hashes exact: "
        f"{replay['all_final_state_hash_exact']}",
    ]
    if meta["mock"]:
        lines.extend([
            "",
            "> WARNING: this is a mock-mode engineering check. It is not "
            "publishable paper evidence.",
        ])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description="Auditable LEDS K=5 determinism probe")
    ap.add_argument("--config", default=os.path.join(config.DATA_DIR,
                    "exp1_scalefree.json"))
    ap.add_argument("--runs", type=int, default=5)
    ap.add_argument("--replays", type=int, default=3)
    ap.add_argument("--mock", action="store_true")
    ap.add_argument("--output", default=str(DEFAULT_OUT))
    args = ap.parse_args()

    output = Path(args.output)
    if not output.is_absolute():
        output = ROOT / output
    paths = output_paths(output)
    paths["json"].parent.mkdir(parents=True, exist_ok=True)

    mock = args.mock or not config.LLM_API_KEY
    if mock and not args.mock:
        print("[WARN] DEEPSEEK_API_KEY is not set; using mock mode.")
        print("[WARN] Mock outputs are not publishable paper evidence.")

    started_utc = utc_now()
    g = load_graph(args.config)
    runs = []

    for idx in range(args.runs):
        run_name = f"fresh_run_{idx + 1:02d}"
        result = run_once(g, args, run_name, mock, collect_trace=True)
        runs.append(result)
        write_run_jsonl(paths["run_jsonl"], runs)
        print(
            f"{run_name}: penetration={result['penetration']:.3f}, "
            f"steps={result['steps']}, decisions={result['decision_requests']}, "
            f"cloud_calls={result['cloud_api_calls']}, "
            f"state_hash={result['final_state_hash'][:12]}"
        )

    # Use a separate seed run for replay so the replay proof is independent from
    # the K=5 fresh-run sample and has an explicit frozen decision-record file.
    seed_name = "replay_seed_run_01"
    seed_result = run_once(g, args, seed_name, mock, collect_trace=True)
    seed_cache = fresh_cache_path(args, seed_name)
    print(
        f"{seed_name}: penetration={seed_result['penetration']:.3f}, "
        f"steps={seed_result['steps']}, cloud_calls={seed_result['cloud_api_calls']}"
    )

    replays = []
    for idx in range(args.replays):
        replay_name = f"replay_{idx + 1:02d}_from_seed"
        replay = run_replay(g, args, seed_cache, replay_name, mock, seed_result)
        replays.append(replay)
        print(
            f"{replay_name}: hamming={replay['hamming_pct']:.3f}, "
            f"cloud_delta={replay['cloud_api_calls_during_replay']}, "
            f"exact={replay['exact_replay']}"
        )

    pair_rows = pairwise_rows(runs)
    replay_rows = [{
        "replay": r["run_name"],
        "penetration": round(r["penetration"], 3),
        "steps": r["steps"],
        "hamming_pct": r["hamming_pct"],
        "cloud_api_calls_during_replay": r["cloud_api_calls_during_replay"],
        "penetration_exact": r["penetration_exact"],
        "steps_exact": r["steps_exact"],
        "final_state_hash_exact": r["final_state_hash_exact"],
        "trace_hash_exact": r["trace_hash_exact"],
        "exact_replay": r["exact_replay"],
        "final_state_hash": r["final_state_hash"],
        "trace_hash": r["trace_hash"],
    } for r in replays]

    pens = [r["penetration"] for r in runs]
    steps = [float(r["steps"]) for r in runs]
    hamming_samples = [r["hamming_pct"] for r in pair_rows]
    replay_cloud = [r["cloud_api_calls_during_replay"] for r in replays]

    finished_utc = utc_now()
    result = {
        "metadata": metadata(args, paths, started_utc, finished_utc),
        "independent_runs": {
            "runs": [compact_run(r) for r in runs],
            "penetration": sample_stats(pens),
            "steps": sample_stats(steps),
            "decision_requests": [r["decision_requests"] for r in runs],
            "cloud_api_calls": [r["cloud_api_calls"] for r in runs],
            "wall_seconds": [r["wall_seconds"] for r in runs],
            "final_state_hashes": [r["final_state_hash"] for r in runs],
            "trace_hashes": [r["trace_hash"] for r in runs],
        },
        "pairwise_hamming": {
            "pairs": pair_rows,
            "summary": sample_stats(hamming_samples),
            "expected_pair_count": args.runs * (args.runs - 1) // 2,
            "observed_pair_count": len(pair_rows),
        },
        "cache_replay": {
            "seed_run": seed_name,
            "seed": compact_run(seed_result),
            "replays": replay_rows,
            "cloud_api_calls_during_replay": replay_cloud,
            "all_replay_cloud_calls_zero": all(x == 0 for x in replay_cloud),
            "exact_match_count": sum(1 for r in replay_rows if r["exact_replay"]),
            "all_exact": all(r["exact_replay"] for r in replay_rows),
            "all_final_state_hash_exact": all(
                r["final_state_hash_exact"] for r in replay_rows
            ),
            "all_trace_hash_exact": all(
                r["trace_hash_exact"] for r in replay_rows
            ),
        },
    }

    paths["json"].write_text(json.dumps(result, ensure_ascii=False, indent=2),
                             encoding="utf-8")
    write_csv(paths["pairwise_csv"], pair_rows)
    write_csv(paths["replay_csv"], replay_rows)
    write_markdown(paths["md"], result)

    print(f"wrote {paths['json']}")
    print(f"wrote {paths['md']}")
    print(f"wrote {paths['pairwise_csv']}")
    print(f"wrote {paths['replay_csv']}")


if __name__ == "__main__":
    main()
