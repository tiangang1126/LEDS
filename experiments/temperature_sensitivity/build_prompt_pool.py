# -*- coding: utf-8 -*-
"""
Build a fixed 240-prompt pool for the LEDS temperature sensitivity experiment.

The pool is balanced by persona: 80 Susceptible, 80 Neutral, 80 Fact Checker.
Each row contains the full system/user prompt inputs plus a rule-oracle label
from the same mock decision core used by the simulation code.
"""
import argparse
import json
import os
import random
import sys
from itertools import product

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "src"))

from prompt_config import (DEBUNK_CONTENT, MSG_DEBUNK, MSG_RUMOR, RUMOR_CONTENT,
                           SYSTEM_PROMPT, build_user_prompt)
from stage2_engine import DeterministicLLM


PERSONAS = ("susceptible", "neutral", "fact_checker")
STANCES = ("Neutral", "Accept", "Reject")


def messages_for(kind: str, rumor_count: int, debunk_count: int) -> list:
    messages = []
    if kind in ("rumor", "mixed") or (kind == "auto" and rumor_count > 0):
        messages.append({"type": MSG_RUMOR, "content": RUMOR_CONTENT, "sender": 101})
    if kind in ("debunk", "mixed") or (kind == "auto" and debunk_count > 0):
        messages.append({"type": MSG_DEBUNK, "content": DEBUNK_CONTENT, "sender": 202})
    if not messages:
        messages.append({"type": MSG_RUMOR, "content": RUMOR_CONTENT, "sender": 101})
    return messages


def scenario_grid(persona: str) -> list:
    """Generate more than 80 cases, then stratified-sample exactly 80."""
    if persona == "susceptible":
        rumor_counts = (0, 1, 2, 4, 5)
        debunk_counts = (0, 1, 2)
        message_kinds = ("rumor", "debunk", "mixed")
    elif persona == "neutral":
        # Dense coverage around the 4-source threshold.
        rumor_counts = (0, 1, 2, 3, 4, 5, 6)
        debunk_counts = (0, 1)
        message_kinds = ("rumor", "debunk", "mixed")
    else:
        rumor_counts = (0, 1, 2, 4)
        debunk_counts = (0, 1, 2)
        message_kinds = ("rumor", "debunk", "mixed")

    cases = []
    for stance, rumor_count, debunk_count, kind in product(
            STANCES, rumor_counts, debunk_counts, message_kinds):
        if kind == "debunk" and debunk_count == 0:
            continue
        if kind == "rumor" and rumor_count == 0:
            continue
        new_messages = messages_for(kind, rumor_count, debunk_count)
        oracle = DeterministicLLM._mock_decide(
            persona, stance, rumor_count, debunk_count)
        cases.append({
            "persona": persona,
            "current_stance": stance,
            "rumor_count": rumor_count,
            "debunk_count": debunk_count,
            "message_kind": kind,
            "message_types": [m["type"] for m in new_messages],
            "new_messages": new_messages,
            "gold_stance": oracle["stance"],
            "gold_action": oracle["action"],
            "source": "template_balanced",
        })
    return cases


def build_pool(n_per_persona: int, seed: int) -> list:
    rng = random.Random(seed)
    rows = []
    for persona in PERSONAS:
        cases = scenario_grid(persona)
        if len(cases) < n_per_persona:
            raise RuntimeError(f"Not enough cases for {persona}: {len(cases)}")
        rng.shuffle(cases)
        chosen = cases[:n_per_persona]
        chosen.sort(key=lambda x: (
            x["persona"], x["rumor_count"], x["debunk_count"],
            x["current_stance"], x["message_kind"]))
        for idx, case in enumerate(chosen, 1):
            prompt_id = f"{persona}_{idx:03d}"
            user_prompt = build_user_prompt(
                case["persona"], case["current_stance"],
                case["rumor_count"], case["debunk_count"],
                case["new_messages"])
            rows.append({
                "prompt_id": prompt_id,
                "persona": case["persona"],
                "current_stance": case["current_stance"],
                "rumor_count": case["rumor_count"],
                "debunk_count": case["debunk_count"],
                "message_kind": case["message_kind"],
                "message_types": case["message_types"],
                "system_prompt": SYSTEM_PROMPT,
                "user_prompt": user_prompt,
                "gold_stance": case["gold_stance"],
                "gold_action": case["gold_action"],
                "source": case["source"],
            })
    return rows


def main() -> None:
    ap = argparse.ArgumentParser(description="Build LEDS temperature prompt pool")
    ap.add_argument("--output", default=os.path.join(
        ROOT, "experiments", "temperature_sensitivity", "prompt_pool.jsonl"))
    ap.add_argument("--n-per-persona", type=int, default=80)
    ap.add_argument("--seed", type=int, default=20260725)
    args = ap.parse_args()

    rows = build_pool(args.n_per_persona, args.seed)
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"wrote {len(rows)} prompts -> {args.output}")


if __name__ == "__main__":
    main()
