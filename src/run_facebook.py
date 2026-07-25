# -*- coding: utf-8 -*-
"""应用案例 B：在真实 Facebook ego-network 上跑随机/边缘/中心三组干预对比。
用法: python src/run_facebook.py
产出 results/summary_facebook.json 与 results/logs/fb_*.json。"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config
from stage2_engine import LEDSEngine

CONFIGS = [("fb_random", "随机部署"), ("fb_edge", "边缘部署"), ("fb_hub", "中心部署")]


def main() -> None:
    if not config.LLM_API_KEY:
        print("[错误] 未配置 DEEPSEEK_API_KEY，无法跑真实网络实验。")
        sys.exit(1)
    summary = {}
    for name, label in CONFIGS:
        path = os.path.join(config.DATA_DIR, f"{name}.json")
        rep = LEDSEngine(path, mock=False, t_max=config.T_MAX).run()
        summary[name] = {
            "label": label,
            "mode": rep["mode"],
            "converged": rep["converged"],
            "total_steps": rep["total_steps"],
            "total_llm_calls": rep["total_llm_calls"],
            "invalid_parse_count": rep.get("invalid_parse_count", 0),
            "fallback_count": rep.get("fallback_count", 0),
            "final_penetration": round(rep["final_penetration"] * 100, 1),
        }
    out = os.path.join(config.RESULTS_DIR, "summary_facebook.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print("\n===== 真实网络干预对比（渗透率% / 步数）=====")
    for name, label in CONFIGS:
        s = summary[name]
        print(f"{label:<8}{s['final_penetration']}% / {s['total_steps']}步 "
              f"/ 调用 {s['total_llm_calls']}")
    print(f"已写入 {out}")


if __name__ == "__main__":
    main()
