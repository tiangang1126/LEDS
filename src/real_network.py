# -*- coding: utf-8 -*-
"""SNAP Facebook ego-network -> LEDS 配置（应用案例 B：真实网络干预对比）。
用法: python src/real_network.py [--ego 0]
产出 data/fb_random.json / fb_edge.json / fb_hub.json（仅 checker 布局不同）。"""
import argparse
import io
import json
import os
import sys
import tarfile
import urllib.request
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config
from prompt_config import RUMOR_CONTENT

SNAP_URL = "https://snap.stanford.edu/data/facebook.tar.gz"
SEED = 2024


def _fetch_ego_edges(ego: int) -> str:
    fb_dir = os.path.join(config.DATA_DIR, "facebook")
    edges_path = os.path.join(fb_dir, f"{ego}.edges")
    nested = os.path.join(fb_dir, "facebook", f"{ego}.edges")
    if os.path.exists(edges_path):
        return edges_path
    if os.path.exists(nested):
        return nested
    os.makedirs(fb_dir, exist_ok=True)
    print(f"[real_network] 下载 {SNAP_URL} ...")
    raw = urllib.request.urlopen(SNAP_URL, timeout=120).read()
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as tf:
        for m in tf.getmembers():
            if m.name.endswith(".edges"):
                tf.extract(m, fb_dir)
    if os.path.exists(nested):
        return nested
    return edges_path


def _build_graph(ego: int):
    """返回 (N, adj: dict[int->set[int]])，节点已重标为连续 0..N-1。"""
    path = _fetch_ego_edges(ego)
    raw_edges, nodes = [], set()
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            parts = line.split()
            if len(parts) < 2:
                continue
            a, b = int(parts[0]), int(parts[1])
            raw_edges.append((a, b))
            nodes.add(a)
            nodes.add(b)
    nodes.add(ego)                                   # ego 与其所有好友相连
    idx = {orig: i for i, orig in enumerate(sorted(nodes))}
    adj = defaultdict(set)
    for a, b in raw_edges:
        adj[idx[a]].add(idx[b])
        adj[idx[b]].add(idx[a])
    ei = idx[ego]
    for other in range(len(nodes)):
        if other != ei:
            adj[ei].add(other)
            adj[other].add(ei)
    return len(nodes), adj


def _personas(N: int, checker_set: set):
    """按 60/30/10 分配；checker 固定为 checker_set，其余确定性填充。"""
    import random
    n_susc = round(0.60 * N)
    rest = [i for i in range(N) if i not in checker_set]
    random.Random(SEED).shuffle(rest)
    persona = {i: "fact_checker" for i in checker_set}
    for k, i in enumerate(rest):
        persona[i] = "susceptible" if k < n_susc else "neutral"
    return persona


def _write_config(name: str, N: int, adj: dict, persona: dict, source: int):
    deg = {i: len(adj[i]) for i in range(N)}
    edges = sorted([i, j] for i in range(N) for j in adj[i])   # 双向
    cfg = {
        "meta": {
            "experiment": name,
            "network_type": "facebook_ego",
            "gen_seed": SEED,
            "checker_nodes": sorted(i for i in range(N)
                                    if persona[i] == "fact_checker"),
            "description": f"应用案例 B 真实网络 {name}",
        },
        "N": N,
        "nodes": [{"id": i, "persona": persona[i], "degree": deg[i]}
                  for i in range(N)],
        "edges": edges,
        "source_node": source,
        "initial_message": {"type": "RUMOR", "content": RUMOR_CONTENT},
    }
    out = os.path.join(config.DATA_DIR, f"{name}.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    print(f"[{name}] N={N} 边={len(edges)} "
          f"人设={dict(Counter(persona.values()))} 源={source}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ego", type=int, default=0)
    args = ap.parse_args()

    N, adj = _build_graph(args.ego)
    deg_order = sorted(range(N), key=lambda i: len(adj[i]))     # 度数升序
    n_check = round(0.10 * N)
    edge_set = set(deg_order[:n_check])                         # 最低度
    hub_set = set(deg_order[-n_check:])                         # 最高度
    import random
    random_set = set(random.Random(SEED).sample(range(N), n_check))

    # 源：不属于任一 checker 集、度数接近中位数的普通节点，三配置共用
    excluded = edge_set | hub_set | random_set
    med_node = deg_order[N // 2]
    med_deg = len(adj[med_node])
    candidates = [i for i in range(N) if i not in excluded]
    source = min(candidates, key=lambda i: abs(len(adj[i]) - med_deg))

    for name, cset in [("fb_random", random_set),
                       ("fb_edge", edge_set),
                       ("fb_hub", hub_set)]:
        persona = _personas(N, cset)
        if persona[source] == "fact_checker":      # 保证源为普通节点
            persona[source] = "susceptible"
        _write_config(name, N, adj, persona, source)


if __name__ == "__main__":
    main()
