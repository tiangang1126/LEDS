"""Auditable, single-variable ablation of the three LEDS mechanisms.

The experiment deliberately separates two evidence strata:

1. API-record replay: fixed versus randomized within-layer scheduling uses the
   exact decision-record protocol and seed artifact from the completed K=5
   probe. A cache miss is fatal; cloud fallback is impossible.
2. Structural replay: novelty filtering on/off uses one frozen rule-generated
   decision record. This tests event exhaustion and the T_max boundary without
   introducing cloud-model variation. It is structural evidence, not a new LLM
   effectiveness result.

The no-record row links to the completed K=5 independent-run evidence and is
never relabeled as a newly executed sample.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
from baselines import Decider, load_graph
from prompt_config import (
    DEBUNK_CONTENT,
    MSG_DEBUNK,
    MSG_RUMOR,
    RUMOR_CONTENT,
    build_user_prompt,
)
from stage2_engine import DeterministicLLM


ROOT = Path(config.BASE_DIR)
DEFAULT_SEED = (
    ROOT / "results" / "cache" / "determinism_k5" /
    "deepseek-v4-flash" / "replay_seed_run_01.json"
)
DEFAULT_OUT = ROOT / "results" / "mechanism_ablation_20260729_v2"
NO_RECORD_SOURCE = (
    ROOT / "results" / "min_accept" /
    "determinism_probe_k5_deepseek_v4_flash.json"
)
DEFAULT_SCHEDULE_SEEDS = (20260729, 20260730, 20260731, 20260732, 20260733)


class RecordCoverageError(RuntimeError):
    """Raised instead of silently falling back to a cloud API."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_json(value) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def canonical_messages(messages: list[dict]) -> list[dict]:
    """Represent M_i,t as a canonical multiset before prompt construction."""
    return sorted(
        messages,
        key=lambda item: (
            int(item["sender"]), str(item["type"]), str(item.get("content", ""))
        ),
    )


class FrozenRecordDecider:
    """Read-only Decider-compatible oracle with no cloud execution path."""

    def __init__(self, records: dict, record_path: Path, evidence_type: str):
        self.cache = records
        self.record_path = record_path
        self.evidence_type = evidence_type
        self.call_count = 0
        self.cache_hit_count = 0
        self.cloud_call_count = 0
        self.invalid_count = 0
        self.fallback_count = 0

    @classmethod
    def from_path(cls, path: Path, evidence_type: str):
        with path.open("r", encoding="utf-8") as handle:
            records = json.load(handle)
        if not isinstance(records, dict) or not records:
            raise ValueError(f"Decision record is empty or invalid: {path}")
        return cls(records, path, evidence_type)

    def decide(self, persona, stance, rumor_count, debunk_count, new_messages):
        self.call_count += 1
        prompt = build_user_prompt(
            persona, stance, rumor_count, debunk_count, new_messages
        )
        if prompt not in self.cache:
            prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
            raise RecordCoverageError(
                "Frozen decision-record miss; cloud fallback is prohibited: "
                f"prompt_sha256={prompt_hash}, persona={persona}, "
                f"stance={stance}, rumor_count={rumor_count}, "
                f"debunk_count={debunk_count}"
            )
        self.cache_hit_count += 1
        try:
            return DeterministicLLM._parse(self.cache[prompt])
        except ValueError as exc:
            self.invalid_count += 1
            raise RecordCoverageError("Invalid response in frozen record") from exc


class RuleRecordBuilder:
    """Build a closed structural oracle without using a cloud model."""

    def __init__(self):
        self.cache = {}
        self.call_count = 0
        self.cache_hit_count = 0
        self.cloud_call_count = 0
        self.invalid_count = 0
        self.fallback_count = 0

    def decide(self, persona, stance, rumor_count, debunk_count, new_messages):
        self.call_count += 1
        prompt = build_user_prompt(
            persona, stance, rumor_count, debunk_count, new_messages
        )
        if prompt in self.cache:
            self.cache_hit_count += 1
            return DeterministicLLM._parse(self.cache[prompt])
        decision = DeterministicLLM._mock_decide(
            persona, stance, rumor_count, debunk_count
        )
        self.cache[prompt] = json.dumps(decision, ensure_ascii=False)
        return decision


def state_hash(final_states: dict) -> str:
    normalized = {
        str(key): final_states[key]
        for key in sorted(final_states, key=lambda item: int(item))
    }
    return sha256_json(normalized)


def trace_hash(result: dict) -> str:
    return sha256_json({
        "steps": result["steps"],
        "penetration": round(result["penetration"], 12),
        "final_states": {
            str(key): result["final_states"][key]
            for key in sorted(result["final_states"], key=lambda item: int(item))
        },
        "trace": result["trace"],
    })


def run_simulation(
    graph: dict,
    decider,
    *,
    schedule: str,
    novelty_filter: bool,
    t_max: int,
    schedule_seed: int = 0,
) -> dict:
    """Run one controlled LEDS configuration and retain an auditable trace."""
    if schedule not in {"fixed", "random"}:
        raise ValueError("schedule must be fixed or random")
    rng = random.Random(schedule_seed)
    n = graph["n"]
    personas, adjacency = graph["personas"], graph["adjacency"]
    stances = {node: "Neutral" for node in range(n)}
    rumor_count, debunk_count = defaultdict(int), defaultdict(int)
    sent_edges = set()
    trace = []
    emitted_event_count = 0
    novelty_filtered_event_count = 0
    max_active_nodes = 0
    max_queued_messages = 0

    def emit(sender, action, next_queue):
        nonlocal emitted_event_count, novelty_filtered_event_count
        msg_type = MSG_RUMOR if action == "Share" else MSG_DEBUNK
        content = RUMOR_CONTENT if action == "Share" else DEBUNK_CONTENT
        for neighbor in adjacency.get(sender, ()):
            event_key = (sender, neighbor, msg_type)
            if novelty_filter and event_key in sent_edges:
                novelty_filtered_event_count += 1
                continue
            if novelty_filter:
                sent_edges.add(event_key)
            next_queue[neighbor].append({
                "type": msg_type,
                "content": content,
                "sender": sender,
            })
            emitted_event_count += 1

    queue = defaultdict(list)
    queue[graph["source"]].append({
        **graph["initial_message"], "sender": -1
    })
    t = 0
    while queue and t < t_max:
        for node in list(queue):
            queue[node] = canonical_messages(queue[node])
        polled = sorted(queue)
        if schedule == "random":
            rng.shuffle(polled)
        max_active_nodes = max(max_active_nodes, len(polled))
        max_queued_messages = max(
            max_queued_messages, sum(len(messages) for messages in queue.values())
        )
        next_queue = defaultdict(list)
        step_trace = {
            "step": t,
            "queue": {str(node): queue[node] for node in sorted(queue)},
            "polled": list(polled),
            "transitions": [],
        }
        for node in polled:
            messages = queue[node]
            for message in messages:
                if message["type"] == MSG_RUMOR:
                    rumor_count[node] += 1
                else:
                    debunk_count[node] += 1
            previous = stances[node]
            decision = decider.decide(
                personas[node], previous,
                rumor_count[node], debunk_count[node], messages,
            )
            stances[node] = decision["stance"]
            step_trace["transitions"].append({
                "node": node,
                "prev_stance": previous,
                "next_stance": decision["stance"],
                "action": decision["action"],
                "rumor_count": rumor_count[node],
                "debunk_count": debunk_count[node],
            })
            if decision["action"] in ("Share", "Debunk"):
                emit(node, decision["action"], next_queue)
        for node in list(next_queue):
            next_queue[node] = canonical_messages(next_queue[node])
        step_trace["next_queue"] = {
            str(node): next_queue[node] for node in sorted(next_queue)
        }
        trace.append(step_trace)
        t += 1
        queue = next_queue

    accept = sum(1 for stance in stances.values() if stance == "Accept")
    result = {
        "steps": t,
        "decision_requests": decider.call_count,
        "record_hits": decider.cache_hit_count,
        "cloud_call_delta": decider.cloud_call_count,
        "record_count": len(decider.cache),
        "penetration": 100.0 * accept / n,
        "converged": not queue,
        "termination_reason": "queue_empty" if not queue else "tmax_truncation",
        "remaining_active_nodes": len(queue),
        "remaining_queued_messages": sum(len(v) for v in queue.values()),
        "invalid": decider.invalid_count,
        "fallback": decider.fallback_count,
        "schedule": schedule,
        "schedule_seed": schedule_seed,
        "novelty_filter": novelty_filter,
        "emitted_event_count": emitted_event_count,
        "novelty_filtered_event_count": novelty_filtered_event_count,
        "max_active_nodes": max_active_nodes,
        "max_queued_messages": max_queued_messages,
        "final_states": {int(key): value for key, value in stances.items()},
        "trace": trace,
    }
    result["final_state_hash"] = state_hash(result["final_states"])
    result["trace_hash"] = trace_hash(result)
    result["schedule_order_hash"] = sha256_json([
        step["polled"] for step in trace
    ])
    return result


def replay_gate(result: dict, seed: dict) -> dict:
    checks = {
        "all_requests_hit_record": (
            result["record_hits"] == result["decision_requests"]
        ),
        "zero_cloud_calls": result["cloud_call_delta"] == 0,
        "steps_exact": result["steps"] == seed["steps"],
        "penetration_exact": result["penetration"] == seed["penetration"],
        "final_state_hash_exact": (
            result["final_state_hash"] == seed["final_state_hash"]
        ),
        "trace_hash_exact": result["trace_hash"] == seed["trace_hash"],
    }
    checks["passed"] = all(checks.values())
    return checks


def compact(result: dict) -> dict:
    return {key: value for key, value in result.items() if key != "trace"}


def write_case(output: Path, name: str, result: dict) -> None:
    case_dir = output / name
    case_dir.mkdir(parents=True, exist_ok=True)
    (case_dir / "run_summary.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def structural_oracle(graph: dict, t_max: int) -> dict:
    """Build the union record needed by both novelty configurations."""
    builder = RuleRecordBuilder()
    run_simulation(
        graph, builder, schedule="fixed", novelty_filter=True, t_max=t_max
    )
    run_simulation(
        graph, builder, schedule="fixed", novelty_filter=False, t_max=t_max
    )
    return builder.cache


def main() -> None:
    parser = argparse.ArgumentParser(description="Auditable LEDS mechanism ablation")
    parser.add_argument("--config", default=str(ROOT / "data" / "exp1_scalefree.json"))
    parser.add_argument("--seed-records", default=str(DEFAULT_SEED))
    parser.add_argument("--no-record-source", default=str(NO_RECORD_SOURCE))
    parser.add_argument("--output", default=str(DEFAULT_OUT))
    parser.add_argument("--tmax", type=int, default=config.T_MAX)
    parser.add_argument(
        "--schedule-seeds", type=int, nargs="+",
        default=list(DEFAULT_SCHEDULE_SEEDS),
    )
    args = parser.parse_args()
    config_path = Path(args.config).resolve()
    seed_path = Path(args.seed_records).resolve()
    no_record_path = Path(args.no_record_source).resolve()
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=True)

    graph = load_graph(str(config_path))
    probe = json.loads(no_record_path.read_text(encoding="utf-8"))
    seed = probe["cache_replay"]["seed"]

    api_decider = FrozenRecordDecider.from_path(seed_path, "api_record")
    full_api = run_simulation(
        graph, api_decider, schedule="fixed", novelty_filter=True,
        t_max=args.tmax,
    )
    gate = replay_gate(full_api, seed)
    full_api["replay_gate"] = gate
    full_api["evidence_type"] = "frozen_api_decision_record"
    write_case(output, "api_full_leds_replay", full_api)
    if not gate["passed"]:
        raise RuntimeError(
            "Baseline replay gate failed; ablation aborted before downstream cases: "
            + json.dumps(gate, ensure_ascii=False, sort_keys=True)
        )

    random_runs = []
    for schedule_seed in args.schedule_seeds:
        decider = FrozenRecordDecider.from_path(seed_path, "api_record")
        result = run_simulation(
            graph, decider, schedule="random", novelty_filter=True,
            t_max=args.tmax, schedule_seed=schedule_seed,
        )
        result["evidence_type"] = "frozen_api_decision_record"
        result["final_state_matches_full"] = (
            result["final_state_hash"] == full_api["final_state_hash"]
        )
        result["trace_matches_full"] = (
            result["trace_hash"] == full_api["trace_hash"]
        )
        result["all_requests_hit_record"] = (
            result["record_hits"] == result["decision_requests"]
        )
        if not result["all_requests_hit_record"] or result["cloud_call_delta"] != 0:
            raise RuntimeError("Random-order replay violated frozen-record controls")
        random_runs.append(result)
        write_case(output, f"api_random_order_seed_{schedule_seed}", result)

    oracle_path = output / "structural_rule_decision_record.json"
    records = structural_oracle(graph, args.tmax)
    oracle_path.write_text(
        json.dumps(records, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    structural_full_decider = FrozenRecordDecider.from_path(
        oracle_path, "structural_rule_record"
    )
    structural_full = run_simulation(
        graph, structural_full_decider, schedule="fixed", novelty_filter=True,
        t_max=args.tmax,
    )
    structural_full["evidence_type"] = "frozen_structural_rule_record"
    write_case(output, "structural_full_leds", structural_full)

    no_novelty_decider = FrozenRecordDecider.from_path(
        oracle_path, "structural_rule_record"
    )
    no_novelty = run_simulation(
        graph, no_novelty_decider, schedule="fixed", novelty_filter=False,
        t_max=args.tmax,
    )
    no_novelty["evidence_type"] = "frozen_structural_rule_record"
    write_case(output, "structural_no_novelty_filter", no_novelty)

    independent = probe["independent_runs"]
    no_record = {
        "evidence_type": "linked_existing_api_independent_runs",
        "evidence_source": str(no_record_path.relative_to(ROOT)),
        "sample_size": len(independent["runs"]),
        "schedule": "fixed",
        "novelty_filter": True,
        "record_read": False,
        "record_write": True,
        "cloud_api_calls": independent["cloud_api_calls"],
        "penetration": independent["penetration"],
        "final_state_hashes": independent["final_state_hashes"],
        "trace_hashes": independent["trace_hashes"],
        "all_final_state_hashes_unique": (
            len(set(independent["final_state_hashes"])) == len(independent["runs"])
        ),
        "all_trace_hashes_unique": (
            len(set(independent["trace_hashes"])) == len(independent["runs"])
        ),
        "not_counted_as_new_runs": True,
    }

    metadata = {
        "started_and_finished_utc": utc_now(),
        "model_for_api_record": probe["metadata"]["model"],
        "temperature": probe["metadata"]["temperature"],
        "top_p": probe["metadata"]["top_p"],
        "tmax": args.tmax,
        "schedule_seeds": args.schedule_seeds,
        "config": str(config_path.relative_to(ROOT)),
        "config_sha256": sha256_file(config_path),
        "prompt_config_sha256": sha256_file(ROOT / "src" / "prompt_config.py"),
        "script_sha256": sha256_file(Path(__file__).resolve()),
        "seed_records": str(seed_path.relative_to(ROOT)),
        "seed_records_sha256": sha256_file(seed_path),
        "structural_record": str(oracle_path.relative_to(ROOT)),
        "structural_record_sha256": sha256_file(oracle_path),
        "no_record_source": str(no_record_path.relative_to(ROOT)),
        "no_record_source_sha256": sha256_file(no_record_path),
        "python": sys.version,
        "platform": platform.platform(),
        "cloud_execution_permitted": False,
    }
    output_data = {
        "metadata": metadata,
        "control_policy": {
            "single_variable": True,
            "record_miss_policy": "fatal_error",
            "cloud_fallback": "prohibited",
            "canonical_message_order": "sender,type,content",
            "evidence_strata_separated": True,
        },
        "cases": {
            "api_full_leds_replay": compact(full_api),
            "api_random_order_replays": [compact(item) for item in random_runs],
            "structural_full_leds": compact(structural_full),
            "structural_no_novelty_filter": compact(no_novelty),
            "no_decision_record": no_record,
        },
    }
    result_path = output / "mechanism_ablation.json"
    result_path.write_text(
        json.dumps(output_data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    manifest = {
        "created_utc": utc_now(),
        "files": {
            str(path.relative_to(output)): {
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
            for path in sorted(output.rglob("*")) if path.is_file()
        },
    }
    (output / "audit_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(result_path)


if __name__ == "__main__":
    main()
