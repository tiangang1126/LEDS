# -*- coding: utf-8 -*-
"""
Run the LEDS prompt-level temperature grid and preserve raw LLM outputs.

Formal paper runs should use the real API with caches disabled. The --mock flag
only validates the pipeline and must not be reported as experimental evidence.
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "src"))

import config
from prompt_config import ACTIONS, STANCES, SYSTEM_PROMPT
from stage2_engine import DeterministicLLM


def read_jsonl(path: str) -> list:
    with open(path, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def append_jsonl(path: str, row: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def call_api(system_prompt: str, user_prompt: str, temperature: float) -> str:
    import requests
    payload = {
        "model": config.LLM_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": temperature,
        "top_p": config.TOP_P,
        "response_format": {"type": "json_object"},
    }
    headers = {"Authorization": f"Bearer {config.LLM_API_KEY}",
               "Content-Type": "application/json"}
    last_err = None
    for attempt in range(config.API_MAX_RETRIES):
        try:
            resp = requests.post(config.LLM_BASE_URL, json=payload,
                                 headers=headers, timeout=config.API_TIMEOUT)
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
        except Exception as err:
            last_err = repr(err)
            time.sleep(2 ** attempt)
    raise RuntimeError(f"API failed after {config.API_MAX_RETRIES} attempts: {last_err}")


def parse_raw(raw: str) -> tuple:
    try:
        parsed = DeterministicLLM._parse(raw)
        return True, parsed["stance"], parsed["action"], None
    except Exception as err:
        return False, None, None, repr(err)


def main() -> None:
    ap = argparse.ArgumentParser(description="Run temperature sensitivity grid")
    ap.add_argument("--input", default=os.path.join(
        ROOT, "experiments", "temperature_sensitivity", "prompt_pool.jsonl"))
    ap.add_argument("--output", default=os.path.join(
        ROOT, "experiments", "temperature_sensitivity", "raw_outputs.jsonl"))
    ap.add_argument("--temperatures", nargs="+", default=["0", "0.2", "0.5", "0.7"])
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--mock", action="store_true")
    ap.add_argument("--limit", type=int, default=None,
                    help="optional small pilot limit over prompt rows")
    args = ap.parse_args()

    rows = read_jsonl(args.input)
    if args.limit:
        rows = rows[:args.limit]
    temps = [float(x) for x in args.temperatures]
    mock = args.mock or not config.LLM_API_KEY
    if mock and not args.mock:
        print("[WARN] DEEPSEEK_API_KEY is not set; using mock mode.")
        print("[WARN] Mock outputs are not publishable paper evidence.")

    if os.path.exists(args.output):
        raise FileExistsError(
            f"{args.output} already exists. Move it first to avoid mixing runs.")

    total = len(rows) * len(temps) * args.repeats
    done = 0
    print(f"mode={'mock' if mock else 'api'}, prompts={len(rows)}, "
          f"temps={temps}, repeats={args.repeats}, calls={total}")
    for temp in temps:
        for repeat_id in range(1, args.repeats + 1):
            for row in rows:
                started = time.perf_counter()
                if mock:
                    oracle = {
                        "stance": row["gold_stance"],
                        "action": row["gold_action"],
                    }
                    raw = json.dumps(oracle, ensure_ascii=False)
                    api_error = None
                else:
                    try:
                        raw = call_api(row.get("system_prompt", SYSTEM_PROMPT),
                                       row["user_prompt"], temp)
                        api_error = None
                    except Exception as err:
                        raw = ""
                        api_error = repr(err)
                latency_ms = int((time.perf_counter() - started) * 1000)
                json_valid, parsed_stance, parsed_action, parse_error = parse_raw(raw)
                stance_correct = parsed_stance == row["gold_stance"]
                action_correct = parsed_action == row["gold_action"]
                out = {
                    "prompt_id": row["prompt_id"],
                    "persona": row["persona"],
                    "current_stance": row["current_stance"],
                    "rumor_count": row["rumor_count"],
                    "debunk_count": row["debunk_count"],
                    "message_kind": row.get("message_kind"),
                    "temperature": temp,
                    "repeat_id": repeat_id,
                    "model": "mock-rule-oracle" if mock else config.LLM_MODEL,
                    "endpoint": "" if mock else config.LLM_BASE_URL,
                    "top_p": config.TOP_P,
                    "raw_response": raw,
                    "parsed_stance": parsed_stance,
                    "parsed_action": parsed_action,
                    "json_valid": json_valid,
                    "stance_correct": stance_correct,
                    "action_correct": action_correct,
                    "rule_correct": stance_correct and action_correct,
                    "gold_stance": row["gold_stance"],
                    "gold_action": row["gold_action"],
                    "latency_ms": latency_ms,
                    "request_time_utc": datetime.now(timezone.utc).isoformat(),
                    "api_error": api_error,
                    "parse_error": parse_error,
                }
                append_jsonl(args.output, out)
                done += 1
                if done % 50 == 0 or done == total:
                    print(f"completed {done}/{total}")


if __name__ == "__main__":
    main()
