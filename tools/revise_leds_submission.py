import os
import shutil
import zipfile
from pathlib import Path

from lxml import etree


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "LEDS_指挥与控制学报_李铁乔_0725.docx"
OUT = ROOT / "LEDS_指挥与控制学报_李铁乔_0725_投稿前修订稿.docx"
WORK = ROOT / "_docx_work"

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
M_NS = "http://schemas.openxmlformats.org/officeDocument/2006/math"
NS = {"w": W_NS, "m": M_NS}


def p_text(p):
    return "".join(p.xpath(".//w:t/text() | .//m:t/text()", namespaces=NS)).strip()


def set_p_text(p, text):
    pPr = p.find(f"{{{W_NS}}}pPr")
    for child in list(p):
        if child is not pPr:
            p.remove(child)
    r = etree.Element(f"{{{W_NS}}}r")
    t = etree.SubElement(r, f"{{{W_NS}}}t")
    t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    t.text = text
    p.append(r)


def clone_after(anchor, text):
    new_p = etree.Element(f"{{{W_NS}}}p")
    pPr = anchor.find(f"{{{W_NS}}}pPr")
    if pPr is not None:
        new_p.append(etree.fromstring(etree.tostring(pPr)))
    set_p_text(new_p, text)
    anchor.addnext(new_p)
    return new_p


def paragraphs(root):
    return root.xpath("//w:body//w:p", namespaces=NS)


def first(root, predicate, label):
    matches = [p for p in paragraphs(root) if predicate(p_text(p))]
    if not matches:
        raise RuntimeError(f"anchor not found: {label}")
    return matches[0]


def replace_starts(root, prefix, text):
    p = first(root, lambda s: s.startswith(prefix), prefix)
    set_p_text(p, text)
    return p


def remove_exact(root, text):
    for p in list(paragraphs(root)):
        if p_text(p) == text:
            parent = p.getparent()
            parent.remove(p)


def main():
    if WORK.exists():
        shutil.rmtree(WORK)
    WORK.mkdir()
    with zipfile.ZipFile(SRC, "r") as z:
        z.extractall(WORK)

    doc_path = WORK / "word" / "document.xml"
    parser = etree.XMLParser(remove_blank_text=False)
    tree = etree.parse(str(doc_path), parser)
    root = tree.getroot()

    replace_starts(
        root,
        "摘  要",
        "摘  要  针对云端LLM社会仿真难以复核的问题，提出可重放事件驱动协议LEDS。该协议将传播建模为有限类型化事件转移过程，采用固定调度、新颖事件过滤和判定记录映射实现轨迹回放。实验显示，零温度独立运行仍有4.7个百分点渗透率极差和最高21.0%节点状态差异，记录回放Hamming距离为0；事件驱动将判定次数由2400次降至701次。结果表明，LLM社会仿真需区分记录级可重放性、统计可复现性与经验有效性。",
    )
    replace_starts(
        root,
        "Abstract",
        "Abstract  A replayable event-driven protocol, LEDS, is proposed for auditable cloud-LLM social simulation. LEDS models diffusion as finite typed events, combines ordered scheduling, novelty filtering, and decision-record mapping, and separates replayability from statistical reproducibility. Experiments show 4.7 percentage-point run-to-run penetration variation and up to 21.0% node-state divergence at temperature 0, while record replay yields 0 Hamming distance; event-driven execution reduces decisions from 2,400 to 701.",
    )

    replace_starts(
        root,
        "（1）提出面向语义传播的可重放协议",
        "（1）提出 LLM 社交智能体仿真的双层可复现性定义与可重放事件建模方法。将社会信息传播形式化为有限状态、有限消息类型上的事件转移过程，明确区分固定判定记录条件下的轨迹可重放性、无缓存独立运行条件下的统计可复现性和面向真实社会行为的经验有效性，为云端 LLM 社会仿真实验的复核边界提供统一描述。",
    )
    replace_starts(
        root,
        "（2）设计仅处理新增暴露事件",
        "（2）提出有序调度、新颖事件过滤和判定记录映射相结合的 LEDS 事件传播算法。算法仅调度收到新增消息的活跃节点，并对“发送节点—接收节点—消息类型”三元事件实施至多一次的传播约束；结合固定节点顺序、结构化状态转移和 Prompt/Response 记录，实现传播过程的逐事件审计，并给出轨迹唯一性、有限步终止条件与事件复杂度上界。",
    )
    replace_starts(
        root,
        "（3）在协议之上给出事实核查员",
        "（3）建立面向运行不确定性与记录回放一致性的双层验证方法。通过无缓存独立运行量化宏观渗透率和微观节点状态的运行间差异，通过固定记录回放检验逐节点轨迹一致性，并在不同 LLM 后端、合成网络和真实社交网络上验证方法适用性。事实核查员空间部署作为应用案例，用于说明忽略运行间不确定性可能导致不稳健的干预结论。",
    )

    replace_starts(root, "3 LEDS可重放事件驱动仿真框架", "3 问题定义与LEDS事件传播算法")
    replace_starts(
        root,
        "针对上述现有算法的缺陷",
        "针对上述问题，本文将 LEDS 抽象为冻结有向图上的有限事件传播算法，而非单纯的软件实现框架。算法核心不在于 API、JSON 或缓存本身，而在于：以有限状态空间约束 LLM 输出，以类型化消息事件驱动状态转移，以确定顺序调度消除额外轨迹分叉，并以判定记录映射把不可完全控制的云端调用转化为可索引、可审计、可回放的转移记录。",
    )
    replace_starts(
        root,
        "三个阶段的职责概述如下",
        "三个阶段的职责概述如下（各阶段的机制细节见 3.2 至 3.5 节）：阶段 1（静态初始化）只读解析预先固化的拓扑与人设，输出冻结的初始图状态 G_{t=0} 与首发事件队列 M_{t=0}，将网络结构与人设映射纳入协议输入；阶段 2（离散事件演化）按全局节点 ID 遍历收到新增消息的活跃节点，调用受约束 LLM 状态转移算子并解析结构化输出，产生下一状态 G_{t+1} 与新消息队列 M_{t+1}；阶段 3（收敛与评估）在事件队列耗空（M_T=∅）时聚合全网信念、计算渗透率并输出可逐源追踪的状态机日志。",
    )
    replace_starts(
        root,
        "现有方法常在运行时动态生成或更新网络边",
        "现有方法常在运行时动态生成或更新网络边（Edges），从而把结构噪声混入语义传播过程。本文将社会网络抽象为静态有向图 G=(V,E)，并把节点集合 V、边集合 E 与人设字典 P 作为算法输入固定下来。仿真过程中不允许修改 E，因此不同运行之间的结构差异不再参与结果解释，后续差异可归因于判定内核、调度和事件传播机制。",
    )
    replace_starts(
        root,
        "内部信念状态 S 和三元动作 A",
        "内部信念状态 S 和三元动作 A∈{Share,Ignore,Debunk} 仅由当前输入决定。系统按全局节点 ID 顺序执行该公式，将节点执行顺序显式纳入算法协议，在给定事件集合下构造唯一调度序列，从而消除由并发顺序不确定性引起的额外轨迹分叉。",
    )

    p33 = first(root, lambda s: s.startswith("3.3 离散事件驱动"), "3.3")
    p = clone_after(
        p33,
        "形式化地，设冻结社会网络为 G=(V,E)，其中 V 为智能体集合，E⊆V×V 为有向传播边集合。节点 v_i 在时刻 t 的状态记为 s_i^t=(b_i^t,c_{i,r}^t,c_{i,d}^t)，其中 b_i^t∈{Accept,Reject,Neutral} 表示信念状态，c_{i,r}^t 与 c_{i,d}^t 分别表示累计接收谣言和辟谣消息的不同邻居数。类型化传播事件记为 e_k=(u_k,v_k,m_k,τ_k)，其中 u_k 为发送节点，v_k 为接收节点，m_k∈M={RUMOR,DEBUNK} 为消息类型，τ_k 为逻辑时间层级。节点状态转移由受约束 LLM 算子 F_θ 实现：(s_i^{t+1},a_i^t)=F_θ(P_i,s_i^t,M_i^t)，其中 P_i 为人设，M_i^t 为本轮新接收消息集合，a_i^t∈{Share,Ignore,Debunk} 为对外动作。",
    )
    p = clone_after(
        p,
        "为保证算法有限性，定义事件访问标记 ν(u,v,m)∈{0,1}。仅当 ν(u,v,m)=0 时，事件 (u,v,m) 才允许进入下一轮队列；入队后立即置 ν(u,v,m)=1。因此，每个三元事件至多传播一次，事件总数满足 N_event≤|E|·|M|。该规则不是一般意义上的工程去重，而是 LEDS 可终止性与复杂度边界的核心算法约束。",
    )
    clone_after(
        p,
        "同时，设 A_t={v_i: M_i^t≠∅} 为活跃节点集合，LEDS 使用 π(A_t)=sort(A_t,node_id) 生成唯一调度序列。将节点执行顺序显式纳入协议后，在给定事件集合下可消除由并发顺序不确定性引起的额外轨迹分叉。",
    )

    replace_starts(
        root,
        "为确保核心转移函数",
        "Temperature=0 是控制显式采样噪声的实验条件，而不是 LEDS 实现可重放性的充分条件。本文研究的是结构化状态转移任务，并不以开放式文本多样性为优化目标；因此，零温度设置的作用是减少采样扰动并提高结构化输出合法性。是否影响判定质量，应通过不同温度下的人设规则一致率、JSON 合法率、渗透率方差、节点状态 Hamming 距离和稳态步数等指标进一步检验。受投稿前实验成本限制，本文现有实证主要刻画 Temperature=0 下的运行间发散与记录回放一致性，未将表 1 中 Temperature=0.7 的 Monte Carlo 结果解释为严格温度消融。",
    )
    p34 = first(root, lambda s: s.startswith("Temperature=0 是控制"), "temperature paragraph")
    clone_after(
        p34,
        "LEDS 的记录级可重放性来自判定记录映射。设规范化 Prompt 的哈希为 h=H(p)，判定记录映射为 C:h↦y。首次运行时调用 y=F_θ(p)，并写入 C[h]←y；回放运行时不再调用云端模型，而直接取 y=C[h]。由此，一次不可完全控制的 LLM 调用被转化为可索引、可审计、可复用的状态转移记录。本文后文所称“缓存”均指这一判定记录映射，而非单纯性能优化缓存。",
    )

    replace_starts(
        root,
        "定理 1（有限事件终止性）",
        "命题 1（记录条件下的轨迹唯一性）。在冻结拓扑、人设、初始事件、节点调度顺序、状态解析规则和判定记录映射均固定的条件下，LEDS 生成唯一的状态轨迹。证明思路如下：初始状态与初始事件队列唯一；若第 t 步状态和事件队列唯一，则固定调度序列 π(A_t) 与固定判定记录 C 使每个活跃节点的下一状态唯一，新颖事件过滤规则又使下一事件队列唯一；由数学归纳法可得全程轨迹唯一。",
    )
    p_unique = first(root, lambda s: s.startswith("命题 1（记录条件下"), "unique proposition")
    clone_after(
        p_unique,
        "定理 1（有限事件终止性）。设冻结网络包含有限条有向边 E→，消息类型集合 M 有限，且协议对每个三元组（发送节点，接收节点，消息类型）至多入队一次。若不施加 T_max 截断，则事件队列至多处理 |E→||M| 个边消息事件，并在有限步后为空。",
    )

    replace_starts(root, "Algorithm 1: LEDS 确定性信息传播演化算法", "Algorithm 1: LEDS 可重放事件驱动信息传播算法")
    replace_starts(
        root,
        "实验一在同一冻结的无标度网络",
        "实验一在同一冻结的无标度网络（N=300）上，以真实 deepseek-chat 比较四种仿真范式的开销与稳定性：LEDS（事件驱动，Temperature=0）、Full Polling（保留 JSON 结构化输出但移除事件过滤、每步轮询全部节点，Temperature=0）、Monte Carlo（事件驱动，Temperature=0.7，重复 5 次并计 95% 置信区间）与传统 Independent Cascade（无语义、纯概率转移，重复 100 次）。需要说明的是，Monte Carlo 条件用于呈现较高温度采样下的方差与结构化输出风险，并非严格的温度消融；严格消融应在完全相同调度、相同 Prompt 集合和相同评价集上仅改变 Temperature。",
    )
    replace_starts(
        root,
        "本文提出面向社会信息传播的可重放事件驱动仿真协议",
        "本文提出面向社会信息传播的可重放事件驱动仿真协议 LEDS。其核心结论不是“零温度能够保证确定性”，而是相反：在相同冻结配置和零温度条件下，云端 LLM 的无缓存独立运行仍出现明显发散，最终渗透率极差为4.7个百分点，逐节点状态差异最高达21.0%；只有固定 Prompt/Response 判定记录后的回放，才能实现逐节点完全一致。因此，LLM 社会仿真的可信性应同时报告记录级可重放性、运行级统计可复现性与经验有效性。事件驱动机制将判定次数由2,400次降至701次，并在不同规模下实现2.5～4.8倍的评估次数削减，但该指标不能直接等同于墙钟或费用优势。在应用实验中，中心节点部署核查员在合成网络重复运行中将渗透率稳定压制至0.0%，并在真实 Facebook 网络单次运行中观察到同向结果；拓扑类型及其他部署策略之间的差异仍处于运行波动范围内，尚不足以形成可靠排序。",
    )

    # Remove stale duplicate proof fragments left after the revised theorem.
    remove_exact(root, "ℋt={v,m:节点v在时间步t及之前已处理过消息类型m}")
    stale = first(root, lambda s: s.startswith("由于网络规模 V 有限"), "stale proof")
    stale.getparent().remove(stale)

    # Add submission-facing note after ethics declaration.
    ethics = first(root, lambda s: s == "伦理声明", "ethics")
    clone_after(
        ethics,
        "数据与代码可获得性声明：本文实验脚本、冻结配置、结果汇总、状态机日志、图表和判定记录缓存均随稿件材料保存。为避免真实 API 密钥泄露，提交材料不包含 .env 私密文件；响应缓存发布前需按期刊与伦理要求进行脱敏处理。",
    )

    tree.write(str(doc_path), encoding="UTF-8", xml_declaration=True, standalone=False)

    if OUT.exists():
        OUT.unlink()
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
        for path in WORK.rglob("*"):
            if path.is_file():
                z.write(path, path.relative_to(WORK).as_posix())
    shutil.rmtree(WORK)
    print(OUT)


if __name__ == "__main__":
    main()
