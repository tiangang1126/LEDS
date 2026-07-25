# -*- coding: utf-8 -*-
"""
产物完成/可用性检查器（供 run.bat / run.sh 的幂等跳过逻辑使用）。

判定规则：
  · 文件不存在                      -> 退出码 1（需要跑）
  · 存在但 JSON 解析失败            -> 退出码 1（需要跑）
  · 指定 --require-api 且模式非 api -> 退出码 1（需要跑；如上次是 mock 或空跑）
  · 其余（存在、可用）              -> 退出码 0（可跳过）

“api 模式”的判定：JSON 顶层有 mode 字段且以 "api" 开头；或为汇总型（每个值含
mode 字段）且全部以 "api" 开头。这样 mock/离线数据不会被误判为可用。

用法：
    python src/check_done.py <path> [--require-api]
"""
import argparse
import json
import os
import sys


def _is_api(obj) -> bool:
    if isinstance(obj, dict):
        m = obj.get("mode")
        if isinstance(m, str):
            return m.startswith("api")
        modes = [v["mode"] for v in obj.values()
                 if isinstance(v, dict) and isinstance(v.get("mode"), str)]
        if modes:
            return all(m.startswith("api") for m in modes)
    return False


def main() -> None:
    ap = argparse.ArgumentParser(description="检查实验产物是否已存在且可用")
    ap.add_argument("path")
    ap.add_argument("--require-api", action="store_true",
                    help="要求为真实 API 模式（否则视为需要重跑，如上次为 mock）")
    args = ap.parse_args()

    if not os.path.exists(args.path):
        sys.exit(1)
    if not args.require_api:
        sys.exit(0)
    try:
        with open(args.path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        sys.exit(1)
    sys.exit(0 if _is_api(data) else 1)


if __name__ == "__main__":
    main()
