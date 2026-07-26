from __future__ import annotations

import copy
import shutil
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS = {"w": W_NS}
ET.register_namespace("w", W_NS)


ROOT = Path(__file__).resolve().parents[1]
PAPER_IN = ROOT / "LEDS_指挥与控制学报_李铁乔_0725_投稿前修订稿_Algorithm1_Temperature消融修订稿.docx"
PAPER_OUT = ROOT / "LEDS_指挥与控制学报_李铁乔_0725_投稿前修订稿_Algorithm1_Temperature_K5消融修订稿.docx"
RESPONSE_IN = ROOT / "专家一的意见与回复_Temperature消融实验证据版.docx"
RESPONSE_OUT = ROOT / "专家一的意见与回复_Temperature_K5证据版.docx"


def para_text(p: ET.Element) -> str:
    return "".join(t.text or "" for t in p.findall(".//w:t", NS))


def set_para_text(p: ET.Element, text: str) -> None:
    """Replace paragraph visible text while preserving paragraph properties."""
    ppr = p.find("w:pPr", NS)
    saved_ppr = copy.deepcopy(ppr) if ppr is not None else None
    for child in list(p):
        p.remove(child)
    if saved_ppr is not None:
        p.append(saved_ppr)
    r = ET.SubElement(p, f"{{{W_NS}}}r")
    t = ET.SubElement(r, f"{{{W_NS}}}t")
    t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    t.text = text


def patch_docx(src: Path, dst: Path, replacements: dict[str, str], contains_replacements: list[tuple[str, str]]) -> int:
    xml_name = "word/document.xml"
    changed = 0
    with zipfile.ZipFile(src, "r") as zin:
        root = ET.fromstring(zin.read(xml_name))
        for p in root.findall(".//w:p", NS):
            text = para_text(p)
            if not text.strip():
                continue
            if text in replacements:
                set_para_text(p, replacements[text])
                changed += 1
                continue
            for needle, new_text in contains_replacements:
                if needle in text:
                    set_para_text(p, new_text)
                    changed += 1
                    break
        new_xml = ET.tostring(root, encoding="utf-8", xml_declaration=True)
        with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zout:
            for info in zin.infolist():
                if info.filename == xml_name:
                    zout.writestr(info, new_xml)
                else:
                    zout.writestr(info, zin.read(info.filename))
    return changed


PAPER_EXACT = {
    "4.4 实验二：运行间非确定性与缓存重放一致性探针":
        "4.4 实验二：零温度运行间非确定性与判定记录回放一致性探针",
    "表2 运行间非确定性与缓存重放一致性（真实deepseek-chat，同一冻结无标度网络）":
        "表2 零温度运行间非确定性与判定记录回放一致性（真实deepseek-v4-flash，同一冻结无标度网络）",
    "图2 运行间非确定性与缓存重放一致性。注：（a）宏观独立运行发散与缓存重放重合；（b）逐节点Hamming距离与缓存重放精确复现":
        "图2 零温度运行间非确定性与判定记录回放一致性。注：（a）K=5独立运行的宏观渗透率分布；（b）逐节点Hamming距离与判定记录回放精确复现",
    "Fig. 2 Run-to-run nondeterminism and cache-replay consistency":
        "Fig. 2 Run-to-run nondeterminism and decision-record replay consistency",
    "Table 2 Run-to-run nondeterminism and cache-replay consistency":
        "Table 2 Run-to-run nondeterminism and decision-record replay consistency",
    "3 次独立运行渗透率样本": "5 次独立运行渗透率样本",
    "27.0% / 27.3% / 22.7%": "56.000% / 56.333% / 55.667% / 56.000% / 55.667%",
    "渗透率均值 ± 总体标准差（极差）": "渗透率均值、样本标准差、Student-t 95% CI",
    "25.7% ± 2.1%（极差 4.7 个百分点）": "55.933%，0.279%，[55.587%, 56.280%]",
    "稳态步数样本": "稳态步数样本；渗透率极差",
    "11 / 11 / 12": "8 / 9 / 9 / 8 / 8；0.667 个百分点",
    "成对 Hamming 距离（3 对）": "成对 Hamming 距离（10 对）",
    "0.33% / 21.0% / 20.67%": "1.000% / 1.667% / 1.333% / 1.667% / 1.333% / 1.667% / 1.333% / 1.667% / 0.667% / 1.667%",
    "Hamming 均值 / 最大值": "Hamming 均值、样本标准差、最大值",
    "14.0% / 21.0%": "1.400%，0.344%，1.667%",
    "缓存重放：seed 渗透率 → replay 渗透率": "判定记录回放：seed 渗透率 -> replay 渗透率",
    "28.3% → 28.3%": "56.667% -> 56.667% / 56.667% / 56.667%",
    "缓存重放：逐节点 Hamming 距离": "判定记录回放：云端调用增量；Hamming；hash一致率",
    "0.0%（精确复现）": "0 / 0 / 0；0.0% / 0.0% / 0.0%；final state hash 与 trace hash 均为100%",
}


PAPER_CONTAINS = [
    (
        "针对云端LLM社会仿真难以复核的问题",
        "摘  要  针对云端LLM社会仿真难以复核的问题，提出可重放事件驱动协议LEDS。该协议将传播建模为有限类型化事件转移过程，采用固定调度、新颖事件过滤和判定记录映射实现轨迹回放。补充Temperature敏感性实验在240个分层Prompt、4个温度和3次重复下获得2880条真实DeepSeek API输出，JSON合法率均为100%，不同温度下联合规则一致率稳定在66.81%～67.36%；同时零温度条件下仍有6.67%的Prompt出现三次调用不一致。K=5零温度独立运行实验进一步显示，在deepseek-v4-flash后端下，最终渗透率均值为55.933%，Student-t 95% CI为[55.587%,56.280%]，极差为0.667个百分点；但5次运行的最终状态哈希均不同，成对节点Hamming距离最高为1.667%。固定判定记录后的3次replay均不再调用云端模型，Hamming距离为0，final state hash和trace hash一致率均为100%。结果表明，LLM社会仿真需区分记录级可重放性、统计可复现性与经验有效性。"
    ),
    (
        "A replayable event-driven protocol, LEDS, is proposed",
        "Abstract  A replayable event-driven protocol, LEDS, is proposed for auditable cloud-LLM social simulation. LEDS models diffusion as finite typed events, combines ordered scheduling, novelty filtering, and decision-record mapping, and separates replayability from run-level statistical reproducibility. A supplementary temperature-sensitivity ablation over 240 stratified prompts, four temperatures, and three repeats obtains 2,880 real DeepSeek API outputs. All conditions achieve 100% valid JSON, and joint rule consistency remains stable from 66.81% to 67.36%; nevertheless, 6.67% of prompts at Temperature=0 still produce inconsistent outputs across three calls. A K=5 zero-temperature probe on deepseek-v4-flash further shows a penetration mean of 55.933% with a Student-t 95% CI of [55.587%, 56.280%] and a range of 0.667 percentage points, while all five final-state hashes differ and the maximum pairwise Hamming distance reaches 1.667%. After fixing the decision records, three replay trials invoke zero cloud calls and exactly match the seed run in node states, final-state hash, and trace hash. These results show that LLM social simulation should distinguish record-level replayability, run-level statistical reproducibility, and empirical validity."
    ),
    (
        "实验二旨在为 3.4 节的核心论断",
        "实验二旨在为 3.4 节的核心论断（云端 LLM 即便在 Temperature=0 下也不能保证逐事件确定复现，可复现性须由判定记录回放在实验层面保证）提供直接证据。按照 min_accept.md 的修订要求，本文将零温度无共享判定记录的独立运行由3次扩展为5次。考虑到原稿 K=3 实验使用 deepseek-chat，而当前公共 API 支持的正式后端为 deepseek-v4-flash，修订实验不将两组结果混合统计，而是在同一后端、同一冻结无标度网络、同一源节点、人设映射、Prompt模板、JSON Schema、Temperature=0 和 Top_P=1.0 条件下重新完成 K=5 独立运行。每次运行均从全新空判定记录开始，禁止共享此前运行的 Prompt/Response 映射；随后选择一条完整 seed 运行生成判定记录，并在不访问云端模型的条件下连续 replay 3 次。发散在两个层面刻画：宏观为最终渗透率的样本散布，微观为任意两次运行最终信念状态向量的成对 Hamming 距离；回放一致性进一步以云端调用增量、final state hash 和 trace hash 共同验证。"
    ),
    (
        "本章围绕一个补充敏感性检验和两个主体实验板块展开",
        "本章围绕一个补充敏感性检验和两个主体实验板块展开。首先，4.2.1 节以固定 Prompt 池直接检验 Temperature=0 是否削弱结构化状态转移判定质量，以回应零温度设置可能影响 LLM 效果的疑问。随后，板块一：可复现性评估（4.3 至 4.5 节）直接检验本文的核心命题，即可复现性须由协议在实验层面保证：实验一（成本与方差基线，4.3 节）量化 LEDS 相对蒙特卡洛方案的方差与效率优势，实验二（零温度运行间非确定性与判定记录回放一致性探针，4.4 节）给出“零温度不等于逐轨迹确定复现、判定记录回放才能精确复现”的直接证据，实验三（跨 LLM 后端鲁棒性，4.5 节）检验该命题不依赖单一模型。板块二：应用验证（4.6 至 4.8 节）在可复现协议之上评估真实治理问题，并以事实核查员空间部署作为应用案例。"
    ),
    (
        "（1）可复现性与方差。 蒙特卡洛",
        "（1）可复现性与方差。 蒙特卡洛（）5 次采样的渗透率为 （样本跨度 8.0%～21.0%），单次运行的宏观结论并不可靠。4.4 节进一步用 K=5 零温度独立运行表明，即使宏观渗透率在 deepseek-v4-flash 后端下较为接近，5次 final state hash 仍全部不同，成对 Hamming 距离均大于0；因此 LEDS 的可复现性由判定记录回放在实验层面保证，而非依赖重复运行的自然一致（见 3.4 节）。"
    ),
    (
        "表 2 与图2 给出三点结论",
        "表 2 与图2 给出三点结论。第一，K=5 下最终渗透率区间较窄，5次独立运行的渗透率为56.000%、56.333%、55.667%、56.000%和55.667%，均值为55.933%，样本标准差为0.279%，Student-t 95% CI为[55.587%,56.280%]，极差为0.667个百分点，说明在本后端与本结构化任务中零温度能够压低宏观波动。第二，宏观指标接近不等价于逐节点轨迹一致：5次运行的final state hash均不相同，10组成对Hamming距离介于0.667%～1.667%，均值为1.400%，Student-t 95% CI为[1.154%,1.646%]。第三，固定seed判定记录后，3次replay均未产生新增云端API调用，渗透率均为56.667%，稳态步数均为8，逐节点Hamming距离均为0，final state hash和trace hash均与seed完全一致，exact match为3/3。由此可见，Temperature=0只是控制显式采样扰动的实验条件，LEDS的记录级可重放性来自判定记录映射、确定顺序调度、新颖事件过滤和轨迹回放。"
    ),
    (
        "这种“可解释到单次消息事件、且可精确重放”的审计能力",
        "表 6 呈现了一条可完整追溯的因果链：节点 3 在  因收到源节点的谣言由存疑转为接受并转发；在  同时收到多条谣言与三名核查员的辟谣后被纠偏为拒绝，并停止传播；此后持续收到辟谣、信念稳定于拒绝。每一步的信念转移都能指向触发它的具体消息，且该轨迹在判定记录回放下逐字段精确复现（4.4 节 replay Hamming=0，final state hash 与 trace hash 均一致）。这种“可解释到单次消息事件、且可精确重放”的审计能力，是自由生成式仿真难以提供的：K=5独立运行虽表现出较小宏观波动，但5次final state hash均不同、成对Hamming距离最高为1.667%，说明脱离判定记录的云端重复调用不能保证逐节点轨迹一致。"
    ),
    (
        "鉴于 4.4 节已证实云端 LLM",
        "在可复现协议之上，实验四以合成拓扑评估两个应用问题：拓扑对语义传播的影响，以及事实核查员部署位置对干预效能的边际作用。所有配置于同一普通源节点（节点 47）注入相同初始谣言，仅改变受控变量（拓扑或核查员部署），人设映射与解码参数一致。鉴于 4.4 节已证实云端 LLM 在 Temperature=0 下仍存在运行间轨迹差异，本节的应用结论一律以每条件 5 次独立运行的均值 ± 95% 置信区间（CI）为准（每次运行均采用独立缓存），单次运行值仅作时序曲线（图4、图5）的示例。这一做法本身也是本文核心命题的直接体现：脱离重复运行与区间估计的单次宏观结论不足为凭。"
    ),
    (
        "本文提出面向社会信息传播的可重放事件驱动仿真协议 LEDS",
        "本文提出面向社会信息传播的可重放事件驱动仿真协议 LEDS。围绕专家关切的 Temperature 设置问题，补充实验表明，在受约束的结构化状态转移任务中，T=0、0.2、0.5、0.7 四个条件下 DeepSeek API 输出的 JSON 合法率均为100%，联合规则一致率分别为67.22%、67.36%、66.81%和67.08%，未观察到零温度导致任务判定质量下降；但即使在 T=0 条件下，仍有6.67%的 Prompt 在三次独立调用中产生不同判定。进一步的K=5修订实验表明，零温度可以使宏观渗透率波动较小，但不能保证逐节点轨迹一致：5次独立运行的渗透率极差为0.667个百分点，最终状态哈希均不同，节点状态Hamming距离最高为1.667%；而固定判定记录后的3次回放实现云端零调用、Hamming为0、final state hash和trace hash完全一致。因此，本文的核心结论不是“零温度能够保证确定性”，而是LLM社会仿真的可信性应同时报告记录级可重放性、运行级统计可复现性与经验有效性。事件驱动机制将判定次数由2,400次降至701次，并在不同规模下实现2.5～4.8倍的评估次数削减。"
    ),
]


RESPONSE_EXACT = {
    "实验二进一步给出了Temperature=0条件下三次独立运行仍然产生宏观渗透率和微观节点状态差异的证据，并说明精确复现来自缓存回放，而不是零温度本身。":
        "实验二已按最小录用修复要求扩展为K=5零温度独立运行，并补充Student-t 95% CI、10组成对Hamming明细、3次replay零云端调用证明、final state hash和trace hash一致性证明，进一步说明精确复现来自判定记录回放，而不是零温度本身。",
}


K5_RESPONSE = (
    "针对零温度运行间非确定性证据不足的问题，我们进一步将无共享判定记录的零温度独立运行由原稿的3次扩展为5次。由于原稿3次实验使用deepseek-chat，而当前公共DeepSeek API支持的正式后端为deepseek-v4-flash，我们没有将旧结果与新结果混合统计，而是在同一连续实验窗口内使用deepseek-v4-flash重新完成K=5实验。结果显示，5次独立运行的渗透率为56.000%、56.333%、55.667%、56.000%、55.667%，均值为55.933%，Student-t 95% CI为[55.587%,56.280%]，极差为0.667个百分点；10组成对Hamming距离介于0.667%～1.667%，均值为1.400%，Student-t 95% CI为[1.154%,1.646%]。这表明在该后端与结构化任务上，零温度下宏观结果较稳定，但仍不能保证逐节点状态完全一致。进一步地，我们固定一条seed运行的判定记录后连续replay 3次，三次replay的云端调用增量均为0，渗透率、稳态步数、逐节点状态、final state hash和trace hash均完全一致，exact match为3/3。修订稿据此明确区分“零温度降低采样扰动”和“判定记录条件下的确定回放”，避免将Temperature=0误写为可重放性的充分条件。"
)


RESPONSE_CONTAINS = [
    (
        "据此，可用于回复专家一的最终文字为",
        "据此，可用于回复专家一的最终文字为：感谢专家指出Temperature设置可能影响LLM任务效果的问题。我们已新增受控温度敏感性实验，在240个分层Prompt、4个Temperature条件和3次重复下获得2880条真实DeepSeek API输出。结果显示，各温度下JSON合法率均为100%，T=0、0.2、0.5、0.7的联合规则一致率分别为67.22%、67.36%、66.81%和67.08%，未观察到T=0相较更高温度造成结构化状态转移任务质量下降。同时，T=0下仍有6.67%的Prompt在三次独立调用中出现不同判定，说明零温度不能等同于完全确定性。进一步地，修订稿将零温度独立运行扩展为K=5，并报告置信区间、Hamming明细、replay零云端调用证明和state/trace hash证据。K=5结果显示渗透率均值为55.933%，Student-t 95% CI为[55.587%,56.280%]，极差为0.667个百分点；但5次final state hash均不同，成对Hamming距离最高为1.667%。固定判定记录后3次replay云端调用增量均为0，Hamming为0，final state hash和trace hash均完全一致。修订稿据此将Temperature=0解释为控制显式采样噪声的实验条件，而非可重放性的充分条件，并进一步强调LEDS通过判定记录映射和轨迹回放保证记录级可重放。"
    ),
]


def append_response_paragraph(dst: Path) -> None:
    xml_name = "word/document.xml"
    tmp = dst.with_suffix(".tmp.docx")
    with zipfile.ZipFile(dst, "r") as zin:
        root = ET.fromstring(zin.read(xml_name))
        body = root.find("w:body", NS)
        if body is None:
            return
        # Insert before sectPr when present.
        sect = body.find("w:sectPr", NS)
        p = ET.Element(f"{{{W_NS}}}p")
        set_para_text(p, K5_RESPONSE)
        if sect is None:
            body.append(p)
        else:
            body.insert(list(body).index(sect), p)
        new_xml = ET.tostring(root, encoding="utf-8", xml_declaration=True)
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
            for info in zin.infolist():
                if info.filename == xml_name:
                    zout.writestr(info, new_xml)
                else:
                    zout.writestr(info, zin.read(info.filename))
    shutil.move(tmp, dst)


def main() -> None:
    paper_changes = patch_docx(PAPER_IN, PAPER_OUT, PAPER_EXACT, PAPER_CONTAINS)
    response_changes = patch_docx(RESPONSE_IN, RESPONSE_OUT, RESPONSE_EXACT, RESPONSE_CONTAINS)
    append_response_paragraph(RESPONSE_OUT)
    print(f"paper_out={PAPER_OUT.name} changes={paper_changes}")
    print(f"response_out={RESPONSE_OUT.name} changes={response_changes}+append")


if __name__ == "__main__":
    main()
