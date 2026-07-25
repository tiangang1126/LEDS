# -*- coding: utf-8 -*-
"""
LEDS 框架 —— 阶段 1：静态拓扑与人设分配生成器
对应论文 3.1 节（Stage 1: 静态环境初始化）、3.2 节（静态图解耦加载模型）
以及 4.3 / 4.4 节的四组控制变量实验配置。

产出四份冻结的静态配置文件（思路.md 第 2 节目录规划）：
  data/exp1_smallworld.json    实验一 · 配置 A：小世界网络 (Watts-Strogatz)
  data/exp1_scalefree.json     实验一 · 配置 B：无标度网络 (Barabási-Albert)
  data/exp2_edge_defense.json  实验二 · 边缘部署：核查员绑定度数最低的 5 个边缘节点
  data/exp2_hub_defense.json   实验二 · 中心部署：核查员绑定度数最高的 Top-5 Hubs

确定性说明（对应论文 4.1 节）：
  GEN_SEED 仅用于本阶段“一次性”生成并固化拓扑与人设布局，生成结果落盘为
  JSON 后即成为冻结的物理底座 G_{t=0}；阶段 2 仿真引擎以只读模式挂载该文件，
  运行期不再依赖任何伪随机数生成器。
"""
import json
import os
import random

import networkx as nx

from config import DATA_DIR, N_NODES
from prompt_config import MSG_RUMOR, RUMOR_CONTENT

# 拓扑固化专用种子：仅存在于阶段 1，仿真运行期（阶段 2）完全无随机数
GEN_SEED = 2024

# 论文 4.2 节硬编码人设比例：易感者 60% / 中立者 30% / 核查员 10%
N_SUSCEPTIBLE = int(N_NODES * 0.60)   # 30
N_NEUTRAL = int(N_NODES * 0.30)       # 15
N_CHECKER = int(N_NODES * 0.10)       # 5


def top_k_by_degree(graph: nx.Graph, k: int, lowest: bool = False) -> list:
    """按度数排序取 Top-K（或 Bottom-K）节点；度数相同时按节点 ID 升序，保证确定性。"""
    ranked = sorted(graph.nodes(), key=lambda n: (graph.degree(n), -n), reverse=not lowest)
    if lowest:
        ranked = sorted(graph.nodes(), key=lambda n: (graph.degree(n), n))
    return ranked[:k]


def canonical_persona_map(rng: random.Random) -> dict:
    """
    生成全网统一的“基准人设映射”（节点 ID -> 人设）。
    实验一的两种拓扑（配置 A/B）共用同一份映射，确保唯一控制变量是拓扑结构本身
    （对应论文 4.3 节控制变量设计）。
    """
    nodes = list(range(N_NODES))
    rng.shuffle(nodes)
    persona_map = {}
    for i, node in enumerate(nodes):
        if i < N_SUSCEPTIBLE:
            persona_map[node] = "susceptible"
        elif i < N_SUSCEPTIBLE + N_NEUTRAL:
            persona_map[node] = "neutral"
        else:
            persona_map[node] = "fact_checker"
    return persona_map


def override_checkers(base_map: dict, checker_nodes: list) -> dict:
    """
    实验二人设改写（论文 4.4 节）：在维持 10% 核查员总量不变的前提下，
    仅改变核查员的空间部署位置，其余节点尽量保持基准映射不变。
    被指定为核查员的位置直接改写；原基准映射中的核查员若不在指定位置，
    则按节点 ID 升序确定性地回填为易感者/中立者，使 30/15/5 的比例严格守恒。
    """
    new_map = dict(base_map)
    displaced = {"susceptible": 0, "neutral": 0}
    for node in checker_nodes:
        if base_map[node] in displaced:
            displaced[base_map[node]] += 1
        new_map[node] = "fact_checker"
    # 原核查员中未被指定的节点，按 ID 升序回填被挤占的名额
    freed = sorted(n for n in base_map
                   if base_map[n] == "fact_checker" and n not in set(checker_nodes))
    for node in freed:
        if displaced["susceptible"] > 0:
            new_map[node] = "susceptible"
            displaced["susceptible"] -= 1
        else:
            new_map[node] = "neutral"
            displaced["neutral"] -= 1
    return new_map


# 固定注入源（论文 4.3 节：四组实验共用的同一个“随机普通节点”）。
# 该节点从合法候选集中一次性选定并固化为常量，以满足控制变量与绝对可复现要求：
# 它在两种拓扑中均为普通易感者（无标度网络度数=2 的叶节点，小世界网络度数=4），
# 既非任一拓扑的 Top-5 Hub，也非无标度网络度数最低的 5 个边缘节点，
# 从而与实验二的核查员部署位置互不冲突。选定该源可保证四组实验稳态信念分布中
# Accept/Neutral/Reject 三态均非空（避免无标度基准因全网饱和而 Neutral 退化为 0）。
FIXED_SOURCE_NODE = 47


def pick_source_node(persona_map: dict, ws: nx.Graph, ba: nx.Graph,
                     rng: random.Random) -> int:
    """
    返回固定注入源 v_src（论文 4.3 节：相同的一个普通节点）。
    约束（断言校验）：必须是基准映射中的易感者“普通节点”——既不属于任一拓扑的
    Top-5 Hubs，也不属于无标度网络度数最低的 5 个边缘节点，保证四组实验注入点
    完全一致、满足控制变量要求。GEN_SEED 仍仅用于阶段 1 固化拓扑与人设，源节点
    本身以常量固化，仿真运行期（阶段 2）不依赖任何随机数。
    """
    excluded = set(top_k_by_degree(ws, 5)) | set(top_k_by_degree(ba, 5)) \
        | set(top_k_by_degree(ba, 5, lowest=True))
    candidates = sorted(n for n, p in persona_map.items()
                        if p == "susceptible" and n not in excluded)
    assert FIXED_SOURCE_NODE in candidates, (
        f"固定源 {FIXED_SOURCE_NODE} 不在合法普通节点候选集 {candidates} 内，"
        "请核对拓扑生成参数与人设映射。")
    return FIXED_SOURCE_NODE


def export_config(filename: str, graph: nx.Graph, persona_map: dict,
                  source: int, meta: dict) -> None:
    """
    序列化导出冻结配置（论文 3.2 节：静态有向图 G=(V,E) 与人设字典 P 通过 JSON 固化）。
    社会关系按无向生成后展开为双向有向边，供阶段 2 只读挂载。
    """
    digraph = graph.to_directed()
    payload = {
        "meta": meta,
        "N": N_NODES,
        "nodes": [
            {"id": n, "persona": persona_map[n], "degree": graph.degree(n)}
            for n in sorted(graph.nodes())
        ],
        "edges": sorted([int(u), int(v)] for u, v in digraph.edges()),
        "source_node": source,
        "initial_message": {"type": MSG_RUMOR, "content": RUMOR_CONTENT},
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    path = os.path.join(DATA_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    n_checker_hub = len(set(top_k_by_degree(graph, 5))
                        & {n for n, p in persona_map.items() if p == "fact_checker"})
    print(f"[Stage1] 已固化 {path}  (源节点={source}, Top-5 Hub 中核查员数={n_checker_hub})")


def main() -> None:
    rng = random.Random(GEN_SEED)

    # ------ 生成两类经典拓扑（论文 4.3 节：配置 A 小世界 / 配置 B 无标度） ------
    # Watts-Strogatz 小世界网络 [11]：N=50, 每节点近邻 k=4, 重连概率 p=0.1
    ws = nx.watts_strogatz_graph(N_NODES, k=4, p=0.1, seed=GEN_SEED)
    # Barabási-Albert 无标度网络 [12]：N=50, 每新节点优先连接 m=2 条边
    ba = nx.barabasi_albert_graph(N_NODES, m=2, seed=GEN_SEED)

    # ------ 基准人设映射与统一信息源 ------
    base_map = canonical_persona_map(rng)
    source = pick_source_node(base_map, ws, ba, rng)

    # ------ 实验一：拓扑决定论（同人设、同源，仅拓扑不同） ------
    export_config("exp1_smallworld.json", ws, base_map, source, {
        "experiment": "exp1_smallworld", "network_type": "watts_strogatz",
        "params": {"k": 4, "p": 0.1}, "gen_seed": GEN_SEED,
        "description": "实验一配置A：小世界网络基准（论文 4.3 节）",
    })
    export_config("exp1_scalefree.json", ba, base_map, source, {
        "experiment": "exp1_scalefree", "network_type": "barabasi_albert",
        "params": {"m": 2}, "gen_seed": GEN_SEED,
        "description": "实验一配置B：无标度网络基准（论文 4.3 节）",
    })

    # ------ 实验二：干预部署（同无标度拓扑、同源，仅核查员位置不同） ------
    edge_nodes = top_k_by_degree(ba, N_CHECKER, lowest=True)   # 度数最低的 5 个边缘节点
    hub_nodes = top_k_by_degree(ba, N_CHECKER)                 # 度数最高的 Top-5 Hubs
    export_config("exp2_edge_defense.json", ba, override_checkers(base_map, edge_nodes),
                  source, {
        "experiment": "exp2_edge_defense", "network_type": "barabasi_albert",
        "params": {"m": 2}, "gen_seed": GEN_SEED, "checker_nodes": edge_nodes,
        "description": "实验二边缘部署：核查员绑定度数最低的5个边缘节点（论文 4.4 节）",
    })
    export_config("exp2_hub_defense.json", ba, override_checkers(base_map, hub_nodes),
                  source, {
        "experiment": "exp2_hub_defense", "network_type": "barabasi_albert",
        "params": {"m": 2}, "gen_seed": GEN_SEED, "checker_nodes": hub_nodes,
        "description": "实验二中心部署：核查员绑定度数最高的Top-5 Hubs（论文 4.4 节）",
    })
    print("[Stage1] 四组静态控制变量配置生成完毕，物理底座 G_t=0 已冻结。")


if __name__ == "__main__":
    main()
