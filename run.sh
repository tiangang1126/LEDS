#!/usr/bin/env bash
# ===========================================================
#  LEDS reproducibility pipeline (Linux / macOS / Git Bash).
#  Idempotent: every stage first checks whether usable results already
#  exist (real API data). If so it SKIPS re-running. No prompts.
#  A stage runs only when its output is missing, unparsable, or was a
#  previous mock/offline run.
#      export DEEPSEEK_API_KEY=sk-xxxx
#  Without a key, the engine auto-falls back to offline mock mode.
# ===========================================================
set -e

echo "[1/7] 安装依赖库..."
pip install networkx matplotlib requests -q

echo "[2/7] 生成静态控制变量图结构 (Stage 1)..."
if python src/check_done.py data/exp2_hub_defense.json; then
    echo "  [跳过] 静态图配置已存在"
else
    python src/stage1_generator.py
fi

echo "[3/7] 核心仿真引擎 (Stage 2；缺失或非真实数据才跑)..."
for cfg in exp1_smallworld exp1_scalefree exp2_edge_defense exp2_hub_defense; do
    if python src/check_done.py "results/logs/${cfg}.json" --require-api; then
        echo "  [跳过] ${cfg} 已存在可用真实数据"
    else
        echo "  [运行] ${cfg} ..."
        python src/stage2_engine.py --config "data/${cfg}.json"
    fi
done

echo "[4/7] 生成评估图表 (Stage 3；本地聚合、始终刷新)..."
python src/stage3_evaluate.py

echo "[5/7] 实验三：基线对比 (缺失或非真实数据才跑)..."
if python src/check_done.py results/baselines.json --require-api; then
    echo "  [跳过] 基线数据已存在可用真实数据"
else
    python src/baselines.py --config data/exp1_scalefree.json --mc-runs 5
fi

echo "[6/7] 实验四：系统扩展性 (缺失才跑)..."
if python src/check_done.py results/scalability.json; then
    echo "  [跳过] 扩展性数据已存在"
else
    python src/scalability.py
fi

echo "[7/7] 实验一补充：Temperature=0 非确定性探针 (缺失或为 mock 才跑；自动、无需选择)..."
if python src/check_done.py results/determinism_probe.json --require-api; then
    echo "  [跳过] 探针已存在可用真实数据"
else
    echo "  [运行] 真实 API 探针（约 2800 次调用，请耐心等待）..."
    python src/determinism_probe.py --config data/exp1_scalefree.json --runs 3
fi

echo ""
echo "全部完成，结果已保存至 results/ 目录（已跳过的步骤复用上次真实数据）。"
