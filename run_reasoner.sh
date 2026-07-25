#!/usr/bin/env bash
# ===========================================================
#  LEDS cross-backend robustness run (SECOND LLM backend) — Linux / macOS / Git Bash
#  Reuses the already-completed default (deepseek-chat) results and runs ONLY the
#  deepseek-reasoner backend. Outputs are model-namespaced
#  (results/logs/<exp>_deepseek-reasoner.json, results/summary_deepseek-reasoner.json)
#  so the existing chat data is NOT overwritten.
#  Requires: export DEEPSEEK_API_KEY=sk-xxxx
#
#  Usage:
#    ./run_reasoner.sh                         # all four experiments (full table)
#    ./run_reasoner.sh exp1_scalefree exp2_hub_defense   # subset, to control cost
# ===========================================================
set -e

if ! command -v python >/dev/null 2>&1; then
    echo "[错误] 未找到 python 命令，请先安装 Python。"
    exit 1
fi

if [ -z "${DEEPSEEK_API_KEY}" ]; then
    echo "[错误] 未设置 DEEPSEEK_API_KEY，无法进行真实后端对比。"
    echo "        请先执行:  export DEEPSEEK_API_KEY=sk-xxxx"
    exit 1
fi

# Second backend: reasoning model. stage2 auto-skips response_format/temperature
# for reasoning models and relies on robust JSON extraction.
export LEDS_MODEL=deepseek-reasoner

echo "[跨后端] 使用第二后端 ${LEDS_MODEL} 重跑主实验（不覆盖 chat 结果）..."
# Pass any config names as arguments to run a subset; otherwise run all four.
if [ "$#" -gt 0 ]; then
    python src/cross_backend.py --configs "$@"
else
    python src/cross_backend.py
fi

echo ""
echo "跨后端对比完成：results/summary_deepseek-reasoner.json"
echo "（对比表已在上方打印；把该 JSON 发回即可并入论文的跨后端鲁棒性小节）"
