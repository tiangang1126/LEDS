# -*- coding: utf-8 -*-
"""
LEDS 框架 —— 阶段 2：离散事件驱动的马尔可夫状态机仿真引擎
对应论文 3.1 节（Stage 2: 离散事件演化循环）、3.3 节（马尔可夫状态机）、
3.4 节（零温度贪婪解码约束）、3.5 节（确定性收敛分析）与 3.6 节（Algorithm 1 伪代码）。

用法：
    python src/stage2_engine.py --config data/exp1_smallworld.json [--mock] [--tmax 30]

确定性保证：
  1. 静态图只读挂载，运行期禁止修改边结构（论文 3.2 节）；
  2. 严格按全局节点 ID 顺序单线程遍历活跃节点，根除竞态条件（论文 3.3 节）；
  3. API 层锁定 Temperature=0.0 / Top_P=1.0，不依赖任何 Seed（论文 3.4 节）；
  4. 边级去重过滤：同一条有向边对同一消息种类至多传递一次，有效消息传递次数存在
     绝对上限，系统构成有限状态可终止的事件驱动系统（论文 3.5 节 定理 1）。
  说明：本框架不假设云端 LLM 推理具备物理级字节确定性；重放一致性经由
  Prompt/Response 哈希与缓存复用在实验级实现（论文 3.4 节）。
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
import re
import sys
import time
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
from prompt_config import (ACTIONS, DEBUNK_CONTENT, MSG_DEBUNK, MSG_RUMOR,
                           RUMOR_CONTENT, STANCES, SYSTEM_PROMPT,
                           build_user_prompt)

# 解析容错：真实 LLM 在 Temperature>0 时偶发输出越界枚举（如将 Ignore 截断为
# Ignor）。对此进行有界重试重采样；耗尽后安全回退，并统计无效率作为鲁棒性指标。
PARSE_MAX_RETRIES = 3


def _is_reasoning_model(model: str) -> bool:
    """推理模型（如 deepseek-reasoner）通常不支持 response_format 且忽略 temperature，
    并会先输出思维链再给答案。对其跳过 JSON 强制模式，改由鲁棒解析从正文提取。"""
    m = (model or "").lower()
    return "reasoner" in m or "reasoning" in m or "-r1" in m or m.endswith("r1")


# ===========================================================================
# LLM 判别器封装：f_LLM(S_{i,t}, P_i, M_{i,t}) -> (S_{i,t+1}, A_{i,t+1})
# ===========================================================================
class DeterministicLLM:
    """将 LLM 降维为纯粹的逻辑判别器（论文 2 节末段、3.4 节）。"""

    def __init__(self, mock: bool, cache_path: str):
        self.mock = mock
        self.cache_path = cache_path
        self.call_count = 0
        self.cache_hit_count = 0
        self.cloud_request_count = 0
        self.cloud_response_count = 0
        self.invalid_count = 0     # 越界/不可解析的原始输出次数（鲁棒性指标）
        self.fallback_count = 0    # 重试耗尽后触发安全回退的次数
        # 确定性缓存：零温度贪婪解码下，对相同 Prompt 的重复调用复用同一缓存响应，
        # 从而在实验级实现可重放一致性（论文 3.4 节；不假设云端物理级字节确定性）。
        self.cache = {}
        if os.path.exists(cache_path):
            with open(cache_path, "r", encoding="utf-8") as f:
                self.cache = json.load(f)

    # ---- 真实 API 路径 -----------------------------------------------------
    def _call_api(self, user_prompt: str) -> str:
        import requests
        payload = {
            "model": config.LLM_MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
        }
        # 推理模型（deepseek-reasoner 等）不支持 response_format、且忽略/拒绝温度参数，
        # 故对其跳过这些字段，仅靠 System Prompt 约束 + 鲁棒解析提取 JSON；
        # 普通对话模型则施加零温度贪婪解码与 JSON 强制模式（论文 3.4 节）。
        if not _is_reasoning_model(config.LLM_MODEL):
            payload["temperature"] = config.TEMPERATURE   # 0.0
            payload["top_p"] = config.TOP_P               # 1.0
            payload["response_format"] = {"type": "json_object"}
        headers = {"Authorization": f"Bearer {config.LLM_API_KEY}",
                   "Content-Type": "application/json"}
        last_err = None
        for attempt in range(config.API_MAX_RETRIES):
            try:
                self.cloud_request_count += 1
                resp = requests.post(config.LLM_BASE_URL, json=payload,
                                     headers=headers, timeout=config.API_TIMEOUT)
                resp.raise_for_status()
                self.cloud_response_count += 1
                return resp.json()["choices"][0]["message"]["content"]
            except requests.HTTPError as err:
                status_code = err.response.status_code if err.response is not None else 0
                if status_code not in (408, 409, 425, 429) and status_code < 500:
                    raise RuntimeError(
                        f"LLM API 返回不可重试的 HTTP 状态码: {status_code}"
                    ) from err
                last_err = err
            except requests.RequestException as err:
                last_err = err
            except (KeyError, TypeError, ValueError) as err:
                raise RuntimeError("LLM API 返回结构不符合预期") from err
            if attempt + 1 < config.API_MAX_RETRIES:
                time.sleep(2 ** attempt)
        raise RuntimeError(f"LLM API 连续 {config.API_MAX_RETRIES} 次调用失败: {last_err}")

    # ---- 离线确定性规则路径（--mock） --------------------------------------
    @staticmethod
    def _mock_decide(persona: str, stance: str,
                     rumor_count: int, debunk_count: int) -> dict:
        """
        无 API Key 时的离线降级路径：以纯规则复现 prompt_config.PERSONAS 中
        声明的人设判定逻辑，保持与论文 3.3 节马尔可夫转移公式相同的输入输出签名，
        用于工程链路的端到端确定性验证。正式实验数据必须以真实 API 输出为准。
        """
        if persona == "fact_checker":
            # 核查员：恒不信谣；收到谣言即向邻居发送辟谣声明（论文 4.2 节）
            action = "Debunk" if rumor_count > 0 else "Ignore"
            return {"stance": "Reject", "action": action}
        if persona == "susceptible":
            # 易感者：倾向相信并分享风险预警；但辟谣声明具有一票纠偏效力
            if debunk_count > 0:
                corrected = "Neutral" if stance == "Accept" else "Reject"
                return {"stance": corrected, "action": "Ignore"}
            if rumor_count >= 1:
                return {"stance": "Accept", "action": "Share"}
            return {"stance": stance, "action": "Ignore"}
        # 中立者：需多重信息源交叉验证（≥4 个不同邻居）才发生信念转移
        if debunk_count >= 1:
            return {"stance": "Reject", "action": "Ignore"}
        if rumor_count >= 4:
            return {"stance": "Accept", "action": "Share"}
        return {"stance": "Neutral", "action": "Ignore"}

    # ---- 统一入口 -----------------------------------------------------------
    def decide(self, persona: str, stance: str, rumor_count: int,
               debunk_count: int, new_messages: list) -> dict:
        self.call_count += 1
        if self.mock:
            return self._mock_decide(persona, stance, rumor_count, debunk_count)

        user_prompt = build_user_prompt(persona, stance, rumor_count,
                                        debunk_count, new_messages)
        key = hashlib.sha256((SYSTEM_PROMPT + user_prompt).encode("utf-8")).hexdigest()
        # 有界重试：先用缓存，无效则重采样（Temperature>0 时可得到不同输出）
        for attempt in range(PARSE_MAX_RETRIES):
            from_record = attempt == 0 and key in self.cache
            if from_record:
                self.cache_hit_count += 1
                record = self.cache[key]
                candidate = record.get("response", "") if isinstance(record, dict) else record
            else:
                candidate = self._call_api(user_prompt)
            try:
                parsed = self._parse(candidate)
                if not from_record:
                    self.cache[key] = {
                        "prompt": user_prompt,
                        "response": candidate,
                        "created_utc": datetime.now(timezone.utc).isoformat(),
                    }
                self._flush_cache()
                parsed["_prompt_hash"] = key
                parsed["_record_source"] = "record" if from_record else "cloud"
                return parsed
            except ValueError:
                self.invalid_count += 1
        # 重试耗尽：安全回退（保持原信念、不对外发消息），并计入 fallback
        self.fallback_count += 1
        return {"stance": stance if stance in STANCES else "Neutral",
                "action": "Ignore"}

    @staticmethod
    def _parse(raw: str) -> dict:
        """稳健的离散状态解析（论文 3.1 节 Stage 2）。
        为兼容推理模型输出（思维链前言 + 正文 JSON、代码块包裹、大小写偏差），
        扫描文本中的全部扁平 {..} 候选，键名小写归一、枚举值大小写归一，
        返回首个含合法 stance/action 的对象；截断/错拼/无合法对象则判为越界。"""
        text = raw.strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.lower().startswith("json"):
                text = text[4:]
        candidates = re.findall(r"\{[^{}]*\}", text, re.DOTALL)
        if not candidates:                       # 兜底：首个 { 到末个 }
            s, e = text.find("{"), text.rfind("}")
            if s != -1 and e != -1:
                candidates = [text[s:e + 1]]
        for cand in candidates:
            try:
                obj = json.loads(cand)
            except Exception:
                continue
            if not isinstance(obj, dict):
                continue
            low = {str(k).strip().lower(): v for k, v in obj.items()}
            stance = str(low.get("stance", "")).strip().capitalize()
            action = str(low.get("action", "")).strip().capitalize()
            if stance in STANCES and action in ACTIONS:
                return {"stance": stance, "action": action}
        raise ValueError(f"LLM 输出不含合法有界 JSON: {raw!r}")

    def _flush_cache(self) -> None:
        os.makedirs(os.path.dirname(self.cache_path), exist_ok=True)
        with open(self.cache_path, "w", encoding="utf-8") as f:
            json.dump(self.cache, f, ensure_ascii=False, indent=1)


# ===========================================================================
# LEDS 主引擎：Algorithm 1 确定性信息传播演化算法（论文 3.6 节）
# ===========================================================================
class LEDSEngine:
    def __init__(self, config_path: str, mock: bool, t_max: int, tag: str = None,
                 cache_path: str = None, log_path: str = None):
        # tag: 可选输出命名后缀（用于跨后端对比，避免覆盖默认结果）
        # ------ 阶段 1 产物的只读解析（论文 3.1 节 Stage 1 / 3.2 节） ------
        with open(config_path, "r", encoding="utf-8") as f:
            frozen = json.load(f)
        self.exp_name = frozen["meta"]["experiment"]
        self.n_nodes = frozen["N"]
        self.personas = {n["id"]: n["persona"] for n in frozen["nodes"]}
        self.degrees = {n["id"]: n["degree"] for n in frozen["nodes"]}
        # 邻接表构建后即冻结：仿真引擎被剥夺对图结构的修改权限（论文 3.2 节）
        adjacency = defaultdict(list)
        for u, v in frozen["edges"]:
            adjacency[u].append(v)
        self.adjacency = {u: tuple(sorted(vs)) for u, vs in adjacency.items()}
        self.source = frozen["source_node"]
        self.initial_message = frozen["initial_message"]

        # ------ 节点认知状态初始化：全网初始为 Neutral（存疑） ------
        self.stances = {n: "Neutral" for n in range(self.n_nodes)}
        self.rumor_count = defaultdict(int)    # 累计收到谣言的不同邻居数
        self.debunk_count = defaultdict(int)   # 累计收到辟谣的不同邻居数
        self.sent_edges = set()                # 边级去重：{(u, v, msg_type)}
        self.t_max = t_max

        # 缓存按后端隔离（否则换模型会回放上一个模型的响应，导致结果串味）
        backend = "mock" if mock else config.LLM_MODEL.replace("/", "-").replace(":", "-")
        explicit_cache_path = cache_path is not None
        cache_path = cache_path or os.path.join(
            config.CACHE_DIR, f"{self.exp_name}_{backend}_cache.json")
        # 向后兼容：早期缓存无模型后缀；默认模型下若新命名缺失而旧缓存存在，则一次性
        # 迁移复用，避免 run.bat 因缓存改名而重复真实调用（重复付费）。
        if not explicit_cache_path and not mock and config.LLM_MODEL == "deepseek-chat":
            legacy = os.path.join(config.CACHE_DIR, f"{self.exp_name}_cache.json")
            if not os.path.exists(cache_path) and os.path.exists(legacy):
                import shutil
                shutil.copyfile(legacy, cache_path)
        self.llm = DeterministicLLM(mock=mock, cache_path=cache_path)
        self.mock = mock
        # 输出命名后缀：显式提供 tag 时用于跨后端对比，避免覆盖默认（chat）结果
        self.out_suffix = f"_{tag}" if tag else ""
        self.log_path = log_path

    # ------ 事件驱动传播（Algorithm 1 第 20-27 行） ------
    def _emit(self, sender: int, action: str, next_queue: dict) -> int:
        msg_type = MSG_RUMOR if action == "Share" else MSG_DEBUNK
        content = RUMOR_CONTENT if action == "Share" else DEBUNK_CONTENT
        emitted = 0
        for neighbor in self.adjacency.get(sender, ()):
            # 去重过滤机制（论文 3.5 节）：仅传递包含新信息增量的消息，
            # 同一条有向边对同一消息种类至多传递一次，保证单调耗散。
            edge_key = (sender, neighbor, msg_type)
            if edge_key in self.sent_edges:
                continue
            self.sent_edges.add(edge_key)
            next_queue[neighbor].append(
                {"type": msg_type, "content": content, "sender": sender})
            emitted += 1
        return emitted

    def run(self) -> dict:
        # Algorithm 1 第 1-2 行：初始化活跃消息队列 Q_0[v_src] <- {msg_init}
        queue = defaultdict(list)
        queue[self.source].append({**self.initial_message, "sender": -1})
        t = 0
        steps = []
        steps.append(self._snapshot(t=0, transitions=[], n_emitted=1, llm_calls=0))

        # Algorithm 1 第 3 行：while (Q_t 非空) and (t < T_max)
        while queue and t < self.t_max:
            next_queue = defaultdict(list)
            transitions = []
            emitted = 0
            calls_before = self.llm.call_count

            # Algorithm 1 第 6 行：严格按全局节点 ID 顺序单线程遍历活跃节点
            for node in sorted(queue.keys()):
                messages = queue[node]
                # 更新累计曝光计数（内部信念状态 S 的定量分量）
                for m in messages:
                    if m["type"] == MSG_RUMOR:
                        self.rumor_count[node] += 1
                    else:
                        self.debunk_count[node] += 1

                # Algorithm 1 第 8-16 行：读取状态 -> 构建 Prompt -> 零温度解码 -> 解析
                prev_stance = self.stances[node]
                result = self.llm.decide(
                    persona=self.personas[node], stance=prev_stance,
                    rumor_count=self.rumor_count[node],
                    debunk_count=self.debunk_count[node], new_messages=messages)
                self.stances[node] = result["stance"]

                # Algorithm 1 第 20-27 行：Share/Debunk 动作向邻居派发新消息
                if result["action"] in ("Share", "Debunk"):
                    emitted += self._emit(node, result["action"], next_queue)

                transitions.append({
                    "node": node, "persona": self.personas[node],
                    "received": [{"type": m["type"], "sender": m["sender"]}
                                 for m in messages],
                    "stance_before": prev_stance, "stance_after": result["stance"],
                    "action": result["action"],
                    "decision_hash": result.get("_prompt_hash"),
                    "decision_source": result.get("_record_source"),
                })

            # Algorithm 1 第 30 行：t <- t + 1
            t += 1
            queue = next_queue
            steps.append(self._snapshot(t, transitions, emitted,
                                        self.llm.call_count - calls_before))
            print(f"[{self.exp_name}] t={t:>2} 活跃节点={len(transitions):>2} "
                  f"新消息={emitted:>3} 渗透率={steps[-1]['penetration']:.3f}")

        # 阶段 3 入口条件（论文 3.1 节 Stage 3）：事件队列为空 M_T = ∅ 即系统稳态。
        # 队列一旦为空将永久为空，故等价满足论文 4.3 节“连续 3 个时间步无新消息”判据。
        converged = not queue
        # Algorithm 1 第 33 行：Penetration_Rate <- Accept 节点数 / |V|
        final_penetration = steps[-1]["penetration"]
        report = {
            "experiment": self.exp_name,
            "mode": "mock(离线确定性规则)" if self.mock else f"api({config.LLM_MODEL})",
            "decoding": {"temperature": config.TEMPERATURE, "top_p": config.TOP_P},
            "source_node": self.source,
            "converged": converged,
            "total_steps": t,
            "total_llm_calls": self.llm.call_count,
            "cache_hit_count": self.llm.cache_hit_count,
            "cloud_request_count": self.llm.cloud_request_count,
            "cloud_response_count": self.llm.cloud_response_count,
            "decision_record_count": len(self.llm.cache),
            "invalid_parse_count": self.llm.invalid_count,
            "fallback_count": self.llm.fallback_count,
            "final_penetration": final_penetration,
            "final_stance_distribution": self._distribution(),
            "steps": steps,
        }
        log_path = self.log_path or os.path.join(
            config.LOGS_DIR, f"{self.exp_name}{self.out_suffix}.json")
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        status = "稳态收敛(M_T=∅)" if converged else f"达到 T_max={self.t_max} 截断"
        print(f"[{self.exp_name}] {status} | 总时间步={t} | "
              f"LLM 判定次数={self.llm.call_count} | "
              f"最终渗透率={final_penetration:.1%} | 日志: {log_path}")
        return report

    def _distribution(self) -> dict:
        dist = {s: 0 for s in STANCES}
        for stance in self.stances.values():
            dist[stance] += 1
        return dist

    def _snapshot(self, t: int, transitions: list, n_emitted: int,
                  llm_calls: int) -> dict:
        """时序切片日志（论文 3.1 节 Stage 3：可供逐源追踪的完整状态机运行日志）。"""
        accept = sum(1 for s in self.stances.values() if s == "Accept")
        return {
            "t": t,
            "penetration": accept / self.n_nodes,
            "stance_distribution": self._distribution(),
            "new_messages_emitted": n_emitted,
            "llm_calls_this_step": llm_calls,
            "transitions": transitions,
            "states": {str(n): self.stances[n] for n in range(self.n_nodes)},
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="LEDS 阶段2：确定性仿真引擎")
    parser.add_argument("--config", required=True, help="阶段1固化的静态拓扑 JSON")
    parser.add_argument("--mock", action="store_true",
                        help="离线确定性规则模式（无 API Key 时的降级验证路径）")
    parser.add_argument("--tmax", type=int, default=config.T_MAX,
                        help=f"最大容许时间步 T_max（默认 {config.T_MAX}）")
    args = parser.parse_args()

    mock = args.mock
    if not mock and not config.LLM_API_KEY:
        print("[警告] 未检测到环境变量 DEEPSEEK_API_KEY，自动降级为 --mock "
              "离线确定性规则模式。正式实验数据请配置 API Key 后重跑。")
        mock = True

    LEDSEngine(args.config, mock=mock, t_max=args.tmax).run()


if __name__ == "__main__":
    main()
