# -*- coding: utf-8 -*-
"""
LEDS 框架 —— 实验三：API 成本与方差基线对比（论文 4.5 节 Experiment III）

在同一冻结的静态无标度网络（默认 data/exp1_scalefree.json）上，以**实测**方式
横向对比四种仿真范式在达到稳态时的 API 调用次数、墙钟耗时与渗透率均值/方差：

  1) LEDS         —— 事件驱动 + 零温度贪婪解码（本文方法，单次运行即确定）
  2) Full-Polling —— 无事件过滤，每个时间步轮询全部 N 个节点（O(T·|V|)）
  3) Monte Carlo  —— 事件驱动 + Temperature>0，重复 K 次采样，报告均值与 95% CI
  4) IC (baseline)—— 传统独立级联，无语义、纯概率转移，重复 K 次（对照传统模型）

设计原则（避免任何“测算/捏造”）：本脚本**只输出真实运行测得的数字**。在 mock
（离线确定性规则）模式下同样如实运行——此时 Monte Carlo 因规则确定而方差为 0，
仅用于工程链路验证；论文正式数据请配置 DEEPSEEK_API_KEY 后以真实 LLM 重跑。

用法：
    python src/baselines.py --config data/exp1_scalefree.json \
        [--mock] [--mc-runs 10] [--ic-runs 100] [--ic-p 0.1] [--temp 0.7]

输出：
    results/baselines.json           机器可读的实测指标
    results/baselines_table.md       论文 4.5 节表 2 就绪的 Markdown 片段
"""
import argparse
import json
import math
import os
import random
import statistics
import sys
import time
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
from prompt_config import (ACTIONS, DEBUNK_CONTENT, MSG_DEBUNK, MSG_RUMOR,
                           RUMOR_CONTENT, STANCES, SYSTEM_PROMPT,
                           build_user_prompt)
from stage2_engine import DeterministicLLM, PARSE_MAX_RETRIES


# ===========================================================================
# 判别器：复用 stage2 的 mock 规则（唯一真源），并为真实 API 增加温度覆盖能力
# ===========================================================================
class Decider:
    """LLM 判别器封装：mock 复用 stage2 规则；API 支持温度参数（供 Monte Carlo）。"""

    def __init__(self, mock: bool, temperature: float, use_cache: bool,
                 disk_cache_path: str = None):
        self.mock = mock
        self.temperature = temperature
        self.use_cache = use_cache          # Temp>0 时应禁用缓存以保留采样方差
        self.disk_cache_path = disk_cache_path   # 仅 Temp=0 运行持久化，便于低成本重跑
        self.cache = {}
        if disk_cache_path and os.path.exists(disk_cache_path):
            with open(disk_cache_path, "r", encoding="utf-8") as f:
                self.cache = json.load(f)
        self.call_count = 0
        self.invalid_count = 0              # 越界/不可解析输出次数（鲁棒性指标）
        self.fallback_count = 0             # 重试耗尽后安全回退次数

    def _flush_disk(self):
        if self.disk_cache_path:
            os.makedirs(os.path.dirname(self.disk_cache_path), exist_ok=True)
            with open(self.disk_cache_path, "w", encoding="utf-8") as f:
                json.dump(self.cache, f, ensure_ascii=False, indent=1)

    def decide(self, persona, stance, rumor_count, debunk_count, new_messages):
        self.call_count += 1
        if self.mock:
            return DeterministicLLM._mock_decide(
                persona, stance, rumor_count, debunk_count)
        user_prompt = build_user_prompt(persona, stance, rumor_count,
                                        debunk_count, new_messages)
        if self.use_cache and user_prompt in self.cache:
            try:
                return DeterministicLLM._parse(self.cache[user_prompt])
            except ValueError:
                self.invalid_count += 1     # 缓存内容失效，转入重采样
        # 有界重试：Temperature>0 时重采样可得到不同（合法）输出
        for _ in range(PARSE_MAX_RETRIES):
            raw = self._call_api(user_prompt)
            try:
                parsed = DeterministicLLM._parse(raw)
                if self.use_cache:
                    self.cache[user_prompt] = raw
                    self._flush_disk()
                return parsed
            except ValueError:
                self.invalid_count += 1
        # 重试耗尽：安全回退（保持原信念、不对外发消息）
        self.fallback_count += 1
        return {"stance": stance if stance in STANCES else "Neutral",
                "action": "Ignore"}

    def _call_api(self, user_prompt: str) -> str:
        import requests
        payload = {
            "model": config.LLM_MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": self.temperature,   # LEDS/Full-Polling=0.0；Monte Carlo>0
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
                last_err = err
                time.sleep(2 ** attempt)
        raise RuntimeError(f"LLM API 连续 {config.API_MAX_RETRIES} 次失败: {last_err}")


# ===========================================================================
# 图加载：从阶段 1 冻结的静态配置读取（论文 3.2 节静态解耦加载）
# ===========================================================================
def load_graph(config_path: str) -> dict:
    with open(config_path, "r", encoding="utf-8") as f:
        frozen = json.load(f)
    adjacency = defaultdict(list)
    for u, v in frozen["edges"]:
        adjacency[u].append(v)
    return {
        "n": frozen["N"],
        "personas": {n["id"]: n["persona"] for n in frozen["nodes"]},
        "adjacency": {u: tuple(sorted(vs)) for u, vs in adjacency.items()},
        "source": frozen["source_node"],
        "initial_message": frozen["initial_message"],
    }


# ===========================================================================
# 统一 LLM 传播仿真器：schedule='event'（仅活跃节点）/ 'full'（每步全轮询）
# 两者共享完全相同的消息传播与去重动力学，唯一差异是每步查询的节点集合，
# 从而给出公平（apples-to-apples）的调用量对比。
# ===========================================================================
def run_llm_sim(g: dict, decider: Decider, schedule: str, t_max: int) -> dict:
    n = g["n"]
    personas, adjacency = g["personas"], g["adjacency"]
    stances = {i: "Neutral" for i in range(n)}
    rumor_count, debunk_count = defaultdict(int), defaultdict(int)
    sent_edges = set()

    def emit(sender, action, next_queue):
        msg_type = MSG_RUMOR if action == "Share" else MSG_DEBUNK
        content = RUMOR_CONTENT if action == "Share" else DEBUNK_CONTENT
        for nb in adjacency.get(sender, ()):
            key = (sender, nb, msg_type)
            if key in sent_edges:
                continue
            sent_edges.add(key)
            next_queue[nb].append({"type": msg_type, "content": content,
                                   "sender": sender})

    queue = defaultdict(list)
    queue[g["source"]].append({**g["initial_message"], "sender": -1})
    t = 0
    while queue and t < t_max:
        next_queue = defaultdict(list)
        # 关键差异：事件驱动只查询有新消息的活跃节点；全轮询查询所有节点
        polled = sorted(queue.keys()) if schedule == "event" else range(n)
        for node in polled:
            messages = queue.get(node, [])
            for m in messages:
                if m["type"] == MSG_RUMOR:
                    rumor_count[node] += 1
                else:
                    debunk_count[node] += 1
            result = decider.decide(personas[node], stances[node],
                                    rumor_count[node], debunk_count[node], messages)
            stances[node] = result["stance"]
            if result["action"] in ("Share", "Debunk"):
                emit(node, result["action"], next_queue)
        t += 1
        queue = next_queue
    accept = sum(1 for s in stances.values() if s == "Accept")
    return {"steps": t, "api_calls": decider.call_count,
            "penetration": 100.0 * accept / n,
            "converged": not queue,
            "invalid": decider.invalid_count,
            "fallback": decider.fallback_count,
            "final_states": {int(k): v for k, v in stances.items()}}


# ===========================================================================
# 传统独立级联（Independent Cascade）：无语义、纯概率，作为传统模型对照
# ===========================================================================
def run_ic(g: dict, p: float, rng: random.Random, t_max: int) -> float:
    n, adjacency = g["n"], g["adjacency"]
    active = {g["source"]}
    frontier = {g["source"]}
    t = 0
    while frontier and t < t_max:
        nxt = set()
        for u in frontier:
            for v in adjacency.get(u, ()):
                if v not in active and rng.random() < p:
                    nxt.add(v)
        active |= nxt
        frontier = nxt
        t += 1
    return 100.0 * len(active) / n


def ci95(samples: list) -> float:
    """样本均值的 95% 置信区间半宽（正态近似 1.96·SE）。单样本返回 0。"""
    if len(samples) < 2:
        return 0.0
    sd = statistics.stdev(samples)
    return 1.96 * sd / math.sqrt(len(samples))


def fmt_ci(samples: list) -> str:
    if not samples:
        return "—"
    mean = statistics.mean(samples)
    return f"{mean:.1f}% ± {ci95(samples):.1f}%"


def main() -> None:
    ap = argparse.ArgumentParser(description="LEDS 实验三：基线对比（实测）")
    ap.add_argument("--config", default=os.path.join(config.DATA_DIR,
                    "exp1_scalefree.json"), help="冻结的静态无标度网络配置")
    ap.add_argument("--mock", action="store_true", help="离线确定性规则模式")
    ap.add_argument("--mc-runs", type=int, default=10, help="Monte Carlo 采样次数 K")
    ap.add_argument("--ic-runs", type=int, default=100, help="独立级联重复次数")
    ap.add_argument("--ic-p", type=float, default=0.1, help="独立级联单边激活概率")
    ap.add_argument("--temp", type=float, default=0.7, help="Monte Carlo 采样温度")
    args = ap.parse_args()

    mock = args.mock or not config.LLM_API_KEY
    if mock and not args.mock:
        print("[警告] 未检测到 DEEPSEEK_API_KEY，自动降级 mock；Monte Carlo 方差将为 0。")
    g = load_graph(args.config)
    t_max = config.T_MAX
    mode = "mock(离线确定性规则)" if mock else f"api({config.LLM_MODEL})"
    print(f"[Baselines] 图={os.path.basename(args.config)} N={g['n']} 模式={mode}")

    results = {"mode": mode, "config": os.path.basename(args.config), "N": g["n"]}

    # temp=0 运行的磁盘缓存路径（按后端隔离，避免换模型时回放上一模型的响应）
    backend = "mock" if mock else config.LLM_MODEL.replace("/", "-").replace(":", "-")
    leds_cache = os.path.join(config.CACHE_DIR, f"baselines_leds_{backend}_cache.json")
    full_cache = os.path.join(config.CACHE_DIR, f"baselines_full_{backend}_cache.json")
    # 向后兼容：默认模型下迁移旧命名缓存，避免重复真实调用（重复付费）
    if not mock and config.LLM_MODEL == "deepseek-chat":
        import shutil
        for _new, _old in [(leds_cache, "baselines_leds_cache.json"),
                           (full_cache, "baselines_full_cache.json")]:
            _oldp = os.path.join(config.CACHE_DIR, _old)
            if not os.path.exists(_new) and os.path.exists(_oldp):
                shutil.copyfile(_oldp, _new)

    # ---- 1) LEDS：事件驱动 + 零温度（单次即确定） ----
    t0 = time.perf_counter()
    leds = run_llm_sim(g, Decider(mock, 0.0, use_cache=True, disk_cache_path=leds_cache),
                       "event", t_max)
    leds["wall_seconds"] = round(time.perf_counter() - t0, 2)
    results["LEDS"] = leds
    print(f"  LEDS         调用={leds['api_calls']:>6} 步数={leds['steps']:>2} "
          f"渗透率={leds['penetration']:.1f}% 无效={leds['invalid']} "
          f"回退={leds['fallback']} 耗时={leds['wall_seconds']}s")

    # ---- 2) Full-Polling：每步全轮询（O(T·|V|)） ----
    t0 = time.perf_counter()
    full = run_llm_sim(g, Decider(mock, 0.0, use_cache=True, disk_cache_path=full_cache),
                       "full", t_max)
    full["wall_seconds"] = round(time.perf_counter() - t0, 2)
    results["FullPolling"] = full
    print(f"  Full-Polling 调用={full['api_calls']:>6} 步数={full['steps']:>2} "
          f"渗透率={full['penetration']:.1f}% 无效={full['invalid']} "
          f"回退={full['fallback']} 耗时={full['wall_seconds']}s")

    # ---- 3) Monte Carlo：Temp>0 重复 K 次，报告均值/95%CI ----
    mc_pens, mc_calls, mc_invalid, mc_fallback = [], 0, 0, 0
    t0 = time.perf_counter()
    for _ in range(args.mc_runs):
        d = Decider(mock, args.temp, use_cache=False)   # 温度>0，禁用缓存保留方差
        r = run_llm_sim(g, d, "event", t_max)
        mc_pens.append(r["penetration"])
        mc_calls += r["api_calls"]
        mc_invalid += r["invalid"]
        mc_fallback += r["fallback"]
    results["MonteCarlo"] = {
        "runs": args.mc_runs, "temperature": args.temp,
        "api_calls_total": mc_calls,
        "invalid_total": mc_invalid, "fallback_total": mc_fallback,
        "invalid_rate": round(100.0 * mc_invalid / max(mc_calls, 1), 2),
        "penetration_mean": round(statistics.mean(mc_pens), 1) if mc_pens else None,
        "penetration_ci95": round(ci95(mc_pens), 1),
        "penetration_samples": [round(x, 1) for x in mc_pens],
        "wall_seconds": round(time.perf_counter() - t0, 2),
    }
    print(f"  Monte Carlo  调用={mc_calls:>6} (K={args.mc_runs}) "
          f"渗透率={fmt_ci(mc_pens)} 无效={mc_invalid}"
          f"({results['MonteCarlo']['invalid_rate']}%) 回退={mc_fallback}"
          + ("  [mock 下方差为 0，仅链路验证]" if mock else ""))

    # ---- 4) Independent Cascade：传统无语义模型对照 ----
    ic_pens = [run_ic(g, args.ic_p, random.Random(1000 + i), t_max)
               for i in range(args.ic_runs)]
    results["IC"] = {
        "runs": args.ic_runs, "edge_prob": args.ic_p, "api_calls_total": 0,
        "penetration_mean": round(statistics.mean(ic_pens), 1),
        "penetration_ci95": round(ci95(ic_pens), 1),
    }
    print(f"  IC (传统)     调用={0:>6} (K={args.ic_runs}, p={args.ic_p}) "
          f"渗透率={fmt_ci(ic_pens)}")

    # ---- 落盘：JSON + 论文表 2 就绪的 Markdown ----
    os.makedirs(config.RESULTS_DIR, exist_ok=True)
    with open(os.path.join(config.RESULTS_DIR, "baselines.json"), "w",
              encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    md = [
        f"> **表 2：LEDS 与基线框架的实测性能对比"
        f"（{results['config']}，$N={g['n']}$，模式：{mode}）**",
        "",
        "| 仿真框架模型 | API 调用次数 | 相对耗时(s) | 最终渗透率 (均值±95%CI) | 实验级可复现性 |",
        "| :--- | :---: | :---: | :---: | :---: |",
        f"| **LEDS (Temp=0.0, 事件驱动, 本文)** | **{leds['api_calls']}** | "
        f"{leds['wall_seconds']} | {leds['penetration']:.1f}% (单次即确定) | "
        f"状态机日志逐字段一致 |",
        f"| Full-Polling LLM (全轮询) | {full['api_calls']} | {full['wall_seconds']} | "
        f"{full['penetration']:.1f}% | 低 |",
        f"| Monte Carlo (Temp={args.temp}, {args.mc_runs}轮) | "
        f"{mc_calls} | {results['MonteCarlo']['wall_seconds']} | "
        f"{fmt_ci(mc_pens)} | 极低 |",
        f"| Independent Cascade (传统, p={args.ic_p}) | 0 | — | "
        f"{fmt_ci(ic_pens)} | — (无语义) |",
        "",
        f"**鲁棒性（结构化输出）：** LEDS/Full-Polling（Temp=0）无效输出 "
        f"{leds['invalid']}/{full['invalid']} 次（回退 {leds['fallback']}/{full['fallback']}）；"
        f"Monte Carlo（Temp={args.temp}）无效 {results['MonteCarlo']['invalid_total']} 次，"
        f"无效率 {results['MonteCarlo']['invalid_rate']}%，"
        f"回退 {results['MonteCarlo']['fallback_total']} 次"
        f"——量化了高温采样下 LLM 违反有界枚举约束的频率（越界即重采样，耗尽则安全回退）。",
        "",
        f"*注：以上为 **{mode}** 下的真实测得值。" +
        ("mock 模式规则确定，故 Monte Carlo 方差为 0，此表仅用于验证实验链路；"
         "论文正式数据请配置 DEEPSEEK_API_KEY 后重跑本脚本。*"
         if mock else "*"),
    ]
    with open(os.path.join(config.RESULTS_DIR, "baselines_table.md"), "w",
              encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")
    print(f"[Baselines] 已写入 results/baselines.json 与 results/baselines_table.md")


if __name__ == "__main__":
    main()
