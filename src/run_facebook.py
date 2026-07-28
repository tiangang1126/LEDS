# -*- coding: utf-8 -*-
"""Run independent multi-round interventions on the Facebook ego-network."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import statistics
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config
from stage2_engine import LEDSEngine


CONFIGS = [
    ("fb_random", "随机部署"),
    ("fb_edge", "边缘部署"),
    ("fb_hub", "中心部署"),
]
T_CRITICAL_975 = {
    1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571,
    6: 2.447, 7: 2.365, 8: 2.306, 9: 2.262, 10: 2.228,
    11: 2.201, 12: 2.179, 13: 2.160, 14: 2.145, 15: 2.131,
    16: 2.120, 17: 2.110, 18: 2.101, 19: 2.093, 20: 2.086,
    21: 2.080, 22: 2.074, 23: 2.069, 24: 2.064, 25: 2.060,
    26: 2.056, 27: 2.052, 28: 2.048, 29: 2.045, 30: 2.042,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_hash(value) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def atomic_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as target:
        json.dump(value, target, ensure_ascii=False, indent=2)
        target.flush()
        os.fsync(target.fileno())
    os.replace(temporary, path)


def git_value(*args: str) -> str:
    try:
        return subprocess.check_output(
            ["git", *args], cwd=config.BASE_DIR, text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return "unavailable"


def sample_stats(samples: list[float]) -> dict:
    if not samples:
        return {"n": 0, "samples": []}
    mean = statistics.mean(samples)
    result = {
        "n": len(samples),
        "samples": samples,
        "mean": mean,
        "median": statistics.median(samples),
        "min": min(samples),
        "max": max(samples),
        "range": max(samples) - min(samples),
    }
    if len(samples) > 1:
        std = statistics.stdev(samples)
        critical = T_CRITICAL_975.get(len(samples) - 1, 1.96)
        half_width = critical * std / math.sqrt(len(samples))
        result.update({
            "std_sample": std,
            "ci95_student_t": [mean - half_width, mean + half_width],
        })
    return result


def completed_summaries(output_root: Path) -> list[dict]:
    summaries = []
    for path in sorted(output_root.glob("*/run_*/run_summary.json")):
        with path.open("r", encoding="utf-8") as source:
            summary = json.load(source)
        if summary.get("status") == "completed":
            summaries.append(summary)
    return summaries


def write_master_summary(output_root: Path, requested_runs: int,
                         experiment_started_utc: str) -> None:
    runs = completed_summaries(output_root)
    deployments = {}
    for name, label in CONFIGS:
        rows = [row for row in runs if row["deployment"] == name]
        penetrations = [row["final_penetration_pct"] for row in rows]
        steps = [float(row["total_steps"]) for row in rows]
        deployments[name] = {
            "label": label,
            "completed_runs": len(rows),
            "penetration": sample_stats(penetrations),
            "steps": sample_stats(steps),
            "runs": rows,
        }
    atomic_json(output_root / "summary_facebook_k5.json", {
        "status": "completed" if len(runs) == requested_runs * len(CONFIGS)
        else "in_progress",
        "started_utc": experiment_started_utc,
        "updated_utc": utc_now(),
        "requested_runs_per_deployment": requested_runs,
        "completed_run_count": len(runs),
        "expected_run_count": requested_runs * len(CONFIGS),
        "model": config.LLM_MODEL,
        "temperature": config.TEMPERATURE,
        "top_p": config.TOP_P,
        "deployments": deployments,
    })


def run_one(config_name: str, label: str, run_index: int, mock: bool,
            output_root: Path, order_index: int) -> dict:
    run_name = f"run_{run_index:02d}"
    run_dir = output_root / config_name / run_name
    run_summary_path = run_dir / "run_summary.json"
    if run_summary_path.exists():
        with run_summary_path.open("r", encoding="utf-8") as source:
            existing = json.load(source)
        if existing.get("status") == "completed":
            return existing
        raise RuntimeError(f"发现未完成轮次，拒绝自动重试: {run_dir}")
    if run_dir.exists() and any(run_dir.iterdir()):
        raise RuntimeError(f"轮次目录非空且没有完成摘要: {run_dir}")

    run_dir.mkdir(parents=True, exist_ok=True)
    config_path = Path(config.DATA_DIR) / f"{config_name}.json"
    cache_path = run_dir / "decision_records.json"
    log_path = run_dir / "trajectory.json"
    manifest_path = run_dir / "run_manifest.json"
    atomic_json(cache_path, {})

    manifest = {
        "status": "running",
        "deployment": config_name,
        "label": label,
        "run_index": run_index,
        "order_index_within_round": order_index,
        "started_utc": utc_now(),
        "mode": "mock" if mock else f"api({config.LLM_MODEL})",
        "model": config.LLM_MODEL,
        "endpoint": config.LLM_BASE_URL,
        "temperature": config.TEMPERATURE,
        "top_p": config.TOP_P,
        "t_max": config.T_MAX,
        "config_path": str(config_path.relative_to(config.BASE_DIR)),
        "config_sha256": sha256_file(config_path),
        "prompt_config_sha256": sha256_file(Path(__file__).parent / "prompt_config.py"),
        "stage2_engine_sha256": sha256_file(Path(__file__).parent / "stage2_engine.py"),
        "runner_sha256": sha256_file(Path(__file__)),
        "git_commit": git_value("rev-parse", "HEAD"),
        "git_dirty": bool(git_value("status", "--porcelain")),
        "decision_records_path": str(cache_path.relative_to(config.BASE_DIR)),
        "trajectory_path": str(log_path.relative_to(config.BASE_DIR)),
    }
    atomic_json(manifest_path, manifest)
    started = time.perf_counter()
    try:
        report = LEDSEngine(
            str(config_path), mock=mock, t_max=config.T_MAX,
            cache_path=str(cache_path), log_path=str(log_path),
        ).run()
    except Exception as error:
        manifest.update({
            "status": "failed",
            "finished_utc": utc_now(),
            "error_type": type(error).__name__,
            "error_message": str(error),
        })
        atomic_json(manifest_path, manifest)
        raise

    wall_seconds = round(time.perf_counter() - started, 2)
    final_states = report["steps"][-1]["states"]
    summary = {
        "status": "completed",
        "deployment": config_name,
        "label": label,
        "run_index": run_index,
        "mode": report["mode"],
        "converged": report["converged"],
        "total_steps": report["total_steps"],
        "decision_requests": report["total_llm_calls"],
        "cache_hit_count": report["cache_hit_count"],
        "cloud_request_count": report["cloud_request_count"],
        "cloud_response_count": report["cloud_response_count"],
        "decision_record_count": report["decision_record_count"],
        "invalid_parse_count": report["invalid_parse_count"],
        "fallback_count": report["fallback_count"],
        "final_penetration_pct": report["final_penetration"] * 100,
        "final_state_hash": canonical_hash(final_states),
        "trace_hash": canonical_hash(report["steps"]),
        "wall_seconds": wall_seconds,
        "started_utc": manifest["started_utc"],
        "finished_utc": utc_now(),
        "config_sha256": manifest["config_sha256"],
        "prompt_config_sha256": manifest["prompt_config_sha256"],
        "stage2_engine_sha256": manifest["stage2_engine_sha256"],
        "runner_sha256": manifest["runner_sha256"],
        "decision_records_path": manifest["decision_records_path"],
        "trajectory_path": manifest["trajectory_path"],
    }
    atomic_json(run_summary_path, summary)
    manifest.update({
        "status": "completed",
        "finished_utc": summary["finished_utc"],
        "run_summary_path": str(run_summary_path.relative_to(config.BASE_DIR)),
    })
    atomic_json(manifest_path, manifest)
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Facebook三种部署的多轮独立LEDS实验"
    )
    parser.add_argument("--runs", type=int, default=1,
                        help="每种部署的独立运行次数")
    parser.add_argument("--output-dir", default="results/facebook_multirun",
                        help="独立运行输出根目录")
    parser.add_argument("--mock", action="store_true",
                        help="使用离线规则核验多轮工程流程")
    parser.add_argument("--resume", action="store_true",
                        help="跳过已完成轮次；遇到失败或不完整轮次时停止")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.runs < 1:
        raise SystemExit("--runs 必须大于等于1")
    if not args.mock and (
        not config.LLM_API_KEY
        or not config.LLM_API_KEY.startswith("sk-")
        or len(config.LLM_API_KEY) < 20
    ):
        raise SystemExit("DEEPSEEK_API_KEY缺失或仍为占位值，无法运行真实API实验")

    output_root = Path(args.output_dir)
    if not output_root.is_absolute():
        output_root = Path(config.BASE_DIR) / output_root
    if output_root.exists() and any(output_root.iterdir()) and not args.resume:
        raise SystemExit(f"输出目录已存在且非空；如需续跑请使用 --resume: {output_root}")
    output_root.mkdir(parents=True, exist_ok=True)

    experiment_manifest_path = output_root / "experiment_manifest.json"
    if experiment_manifest_path.exists():
        with experiment_manifest_path.open("r", encoding="utf-8") as source:
            experiment_manifest = json.load(source)
        experiment_started_utc = experiment_manifest["started_utc"]
        if experiment_manifest["runs_per_deployment"] != args.runs:
            raise SystemExit("续跑时--runs必须与首次启动一致")
        if experiment_manifest["mock"] != args.mock:
            raise SystemExit("续跑时--mock模式必须与首次启动一致")
    else:
        experiment_started_utc = utc_now()
        experiment_manifest = {
            "status": "running",
            "started_utc": experiment_started_utc,
            "runs_per_deployment": args.runs,
            "expected_run_count": args.runs * len(CONFIGS),
            "mock": args.mock,
            "model": config.LLM_MODEL,
            "deployment_order_policy": "cyclic_rotation_by_round",
        }
        atomic_json(experiment_manifest_path, experiment_manifest)

    try:
        for run_index in range(1, args.runs + 1):
            offset = (run_index - 1) % len(CONFIGS)
            ordered_configs = CONFIGS[offset:] + CONFIGS[:offset]
            for order_index, (name, label) in enumerate(ordered_configs, start=1):
                print(f"\n===== {name} / run_{run_index:02d} =====", flush=True)
                summary = run_one(
                    name, label, run_index, args.mock, output_root, order_index
                )
                write_master_summary(output_root, args.runs, experiment_started_utc)
                print(
                    f"完成 {name}/run_{run_index:02d}: "
                    f"渗透率={summary['final_penetration_pct']:.3f}% | "
                    f"步数={summary['total_steps']} | "
                    f"云端请求={summary['cloud_request_count']} | "
                    f"耗时={summary['wall_seconds']:.2f}s",
                    flush=True,
                )
    except Exception as error:
        experiment_manifest.update({
            "status": "failed",
            "finished_utc": utc_now(),
            "error_type": type(error).__name__,
            "error_message": str(error),
        })
        atomic_json(experiment_manifest_path, experiment_manifest)
        write_master_summary(output_root, args.runs, experiment_started_utc)
        raise

    experiment_manifest.update({"status": "completed", "finished_utc": utc_now()})
    atomic_json(experiment_manifest_path, experiment_manifest)
    write_master_summary(output_root, args.runs, experiment_started_utc)
    print(f"\n全部完成，汇总文件: {output_root / 'summary_facebook_k5.json'}")


if __name__ == "__main__":
    main()
