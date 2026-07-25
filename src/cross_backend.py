# -*- coding: utf-8 -*-
"""
LEDS 框架 —— 跨 LLM 后端鲁棒性对比（论文局限性回应：证明结论非单一模型特例）

在同一批冻结配置上，用 `LEDS_MODEL` 指定的第二后端重跑四组主实验，输出按模型
命名（**不覆盖**默认 chat 的 logs/summary），并与已有 `results/summary.json`
（默认 chat 结果）逐组对比渗透率、步数与调用量。

关键隔离（避免结果串味 / 覆盖）：
  · 缓存按后端命名：results/cache/<exp>_<model>_cache.json（见 stage2）；
  · 日志按后端命名：results/logs/<exp>_<model>.json（LEDSEngine tag）；
  · 汇总写入：results/summary_<model>.json。

用法：
    # Windows
    set LEDS_MODEL=deepseek-reasoner
    python src\\cross_backend.py
    # bash
    LEDS_MODEL=deepseek-reasoner python src/cross_backend.py
可选：--configs exp1_scalefree exp2_hub_defense   （只跑子集以控成本）

注意：deepseek-reasoner 为推理模型，单次调用显著慢于 chat；四组约 2000+ 次调用，
真实成本与耗时较高。若仅需佐证鲁棒性，可先跑 exp1_scalefree 与 exp2_hub_defense 两组。
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
from stage2_engine import LEDSEngine

ALL_CONFIGS = ["exp1_smallworld", "exp1_scalefree",
               "exp2_edge_defense", "exp2_hub_defense"]
LABELS = {
    "exp1_smallworld": "小世界网络",
    "exp1_scalefree": "无标度网络(随机核查员)",
    "exp2_edge_defense": "边缘部署",
    "exp2_hub_defense": "中心部署",
}


def main() -> None:
    ap = argparse.ArgumentParser(description="LEDS 跨后端鲁棒性对比")
    ap.add_argument("--configs", nargs="+", default=ALL_CONFIGS,
                    help="要重跑的实验配置名（默认四组全跑）")
    ap.add_argument("--tmax", type=int, default=config.T_MAX)
    args = ap.parse_args()

    if not config.LLM_API_KEY:
        print("[错误] 跨后端对比需要真实 API：未检测到 DEEPSEEK_API_KEY。"
              "请先设置 API Key 与 LEDS_MODEL 后重试。")
        sys.exit(1)

    model = config.LLM_MODEL
    tag = model.replace("/", "-").replace(":", "-")
    print(f"[CrossBackend] 后端模型={model} 输出后缀=_{tag} 配置={args.configs}")

    summary = {}
    for cfg in args.configs:
        cfg_path = os.path.join(config.DATA_DIR, f"{cfg}.json")
        if not os.path.exists(cfg_path):
            print(f"[跳过] 缺少配置 {cfg_path}")
            continue
        # 幂等：若已有该后端的真实(api)日志，直接复用、不重复调用 API
        log_path = os.path.join(config.LOGS_DIR, f"{cfg}_{tag}.json")
        rep = None
        if os.path.exists(log_path):
            try:
                with open(log_path, "r", encoding="utf-8") as f:
                    cached = json.load(f)
                if str(cached.get("mode", "")).startswith("api"):
                    print(f"[复用] {cfg} 已有 {tag} 真实数据，跳过重跑。")
                    rep = cached
            except Exception:
                rep = None
        if rep is None:
            rep = LEDSEngine(cfg_path, mock=False, t_max=args.tmax, tag=tag).run()
        summary[cfg] = {
            "label": LABELS.get(cfg, cfg),
            "mode": rep["mode"],
            "converged": rep["converged"],
            "total_steps": rep["total_steps"],
            "total_llm_calls": rep["total_llm_calls"],
            "invalid_parse_count": rep.get("invalid_parse_count", 0),
            "fallback_count": rep.get("fallback_count", 0),
            "final_penetration": round(rep["final_penetration"] * 100, 1),
        }

    out = os.path.join(config.RESULTS_DIR, f"summary_{tag}.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"[CrossBackend] 已写入 {out}")

    # ---- 与默认 chat 结果对比（若存在 results/summary.json） ----
    base_path = os.path.join(config.RESULTS_DIR, "summary.json")
    if not os.path.exists(base_path):
        print("[提示] 未找到 results/summary.json（默认后端结果），跳过对比。")
        return
    with open(base_path, "r", encoding="utf-8") as f:
        base = json.load(f)

    print("\n===== 跨后端鲁棒性对比（渗透率 %；步数）=====")
    print(f"{'实验':<24}{'默认(chat)':>14}{model:>18}")
    for cfg in args.configs:
        if cfg not in summary:
            continue
        b = base.get(cfg, {})
        n = summary[cfg]
        b_str = (f"{b.get('final_penetration','NA')}% / {b.get('total_steps','NA')}步"
                 if b else "NA")
        n_str = f"{n['final_penetration']}% / {n['total_steps']}步"
        print(f"{n['label']:<24}{b_str:>14}{n_str:>18}")
    print("\n[判读] 若两后端下定性结论一致（无标度>小世界、中心部署≈0%、"
          "边缘≈随机），即可佐证结论非单一模型特例。绝对数值差异属正常模型差异。")


if __name__ == "__main__":
    main()
