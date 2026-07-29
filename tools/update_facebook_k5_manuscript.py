from __future__ import annotations

import copy
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
XML_NS = "http://www.w3.org/XML/1998/namespace"
NS = {"w": W_NS}
W = f"{{{W_NS}}}"
ET.register_namespace("w", W_NS)

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "LEDS_指挥与控制学报_李铁乔_0727_分层复核与方法对齐修订稿.docx"
OUTPUT = ROOT / "LEDS_指挥与控制学报_李铁乔_0728_Facebook_K5真实网络更新稿.docx"
FIGURE = ROOT / "figures" / "fig5_facebook_k5.png"


OLD_PROTOCOL = (
    "为考察中心节点抑制方向在真实拓扑上是否出现反向证据，将同一干预协议迁移至SNAP Facebook ego-network。"
    "网络重标为334个连续节点，包含5704条双向边，平均度约17；沿用60%/30%/10%的人设比例和同一普通源节点，"
    "仅改变10%核查员的部署方式，并使用deepseek-chat完成单次运行。由于真实网络尚未逐条件重复，该实验定位为外部效度的探索性观察。"
)
NEW_PROTOCOL = (
    "为考察合成网络中观察到的部署差异能否迁移至另一类网络结构，将同一干预协议应用于SNAP Facebook ego-network。"
    "该网络重标为334个连续节点，包含5704条双向边，平均度约17；沿用60%/30%/10%的人设比例、同一普通源节点和10%核查员比例，"
    "仅改变核查员的随机、低度数边缘和高度数中心部署。每种部署在deepseek-chat（Temperature=0，Top_P=1）上实施5次无判定记录独立运行，"
    "共15次；各次运行从空判定记录开始，不跨运行共享Prompt/Response映射，并按轮次循环改变3种部署的执行先后，以降低服务时段与固定执行顺序的混杂。"
    "由于实验只使用公开网络拓扑，未使用真实用户文本、属性或传播轨迹，本节检验的是方法在真实网络结构上的探索性迁移，而非真实用户行为的经验有效性。"
)

OLD_AUDIT = "3种部署的无效JSON率均为0，与合成网络中的结构化输出结果一致。"
NEW_AUDIT = (
    "15次运行均自然收敛并分别保存冻结配置、Prompt/Response判定记录、状态轨迹和哈希，共形成10954组云端请求与响应；"
    "汇总记录数与逐次文件中的判定记录数一致，无效JSON与回退次数均为0。15个运行目录、判定记录路径和轨迹哈希互不重复，"
    "且所有运行共享同一Prompt配置哈希、事件引擎哈希和运行器哈希；3种部署各自具有固定配置哈希。"
    "这些证据表明本批结果来自冻结代码与配置下彼此隔离的真实API运行，而非既有判定记录的跨运行复用。"
)

OLD_ANALYSIS = (
    "Facebook网络中，随机、边缘和中心部署的单次渗透率分别为0.0%、9.9%和0.0%。其中，中心部署与合成网络5次重复实验的0.0%方向一致，"
    "未出现反向证据；随机与边缘部署仅有单次观测，不能据此推断稳定差异。综合两类网络，现有证据较充分地支持中心节点部署的强抑制方向，"
    "但仍不足以说明该效应可推广至其他真实网络、传播文本和人群规则。进一步验证需要在多个真实网络上逐条件重复，并以真实传播数据校准人设比例和状态转移。"
)
NEW_ANALYSIS = (
    "如图6和表8所示，随机部署的最终渗透率为13.47%±0.37%，边缘部署为20.06%±6.44%，中心部署为0.00%±0.00%（均为均值±样本标准差）。"
    "随机部署5次观测范围为12.87%～13.77%，95% Student-t置信区间为[13.02%,13.93%]，表现出较小的运行间波动；"
    "边缘部署范围为8.98%～23.95%，95%置信区间为[12.06%,28.06%]。边缘部署虽具有更高的样本均值，但区间较宽并与随机部署区间重叠，"
    "K=5证据不足以支持其稳定优于随机部署。第5次边缘运行的8.98%并非应剔除的异常值，而是当前云端判定条件下运行不确定性的组成部分。"
)
ADDITIONAL_ANALYSIS = (
    "中心部署5次最终渗透率均为0，且最终状态哈希相同，说明在当前冻结拓扑、节点选择、模型和Prompt配置下获得了稳定的宏观终态；"
    "但5次轨迹哈希各不相同，宏观结果一致因而不能推出逐事件轨迹一致。该现象与本文的分层复核定义相吻合："
    "无判定记录独立运行用于估计结果分布，只有固定判定记录的回放才能检验轨迹精确一致性。受单一公开拓扑、固定干预节点、单一模型后端和K=5小样本限制，"
    "上述区间仅作为探索性估计，不能外推为中心部署在其他网络、文本或真实人群中的普遍因果效应。"
)

OLD_LIMITATIONS = (
    "本研究仍存在4方面限制：合成网络每种条件仅独立运行5次，真实网络尚未开展重复实验；模型后端限于DeepSeek同族API标识，缺少跨厂商和本地开源模型验证；"
    "最大实测规模为1000个节点；真实网络仅包含一个Facebook ego-network，人设比例、传播文本和行为规则尚未由真实数据校准。"
    "后续工作将扩大独立重复次数和网络规模，在多模型、多平台及多真实网络上复核记录级与运行级性质，并结合真实传播轨迹和人类行为数据开展参数校准，"
    "以分别提升统计稳健性、系统可扩展性和经验有效性。"
)
NEW_LIMITATIONS = (
    "本研究仍存在4方面限制：合成网络和Facebook网络每种条件均仅独立运行5次，小样本区间尚不足以识别较小效应；"
    "模型后端限于DeepSeek同族API标识，缺少跨厂商和本地开源模型验证；最大实测规模为1000个节点；"
    "真实网络仅包含一个Facebook ego-network，且只使用公开拓扑，人设比例、传播文本和行为规则尚未由真实传播数据或人类行为证据校准。"
    "后续工作将扩大独立重复次数和网络规模，在多模型、多平台及多个真实网络上复核记录级与运行级性质，并结合真实传播轨迹和人类行为数据开展参数校准，"
    "以分别提升统计稳健性、系统可扩展性和经验有效性。"
)

OLD_CONCLUSION = (
    "针对云端LLM判定内核难以完全冻结所导致的社会信息传播仿真复核问题，本文提出可重放事件驱动方法LEDS。"
    "该方法将传播过程形式化为冻结有向图上的有限类型事件转移系统，通过确定顺序调度、新颖事件过滤和判定记录映射，分别约束执行顺序、事件生成和状态转移证据，"
    "并给出记录条件下的轨迹唯一性、有限事件终止性与复杂度上界。实验表明，Temperature=0在deepseek-v4-flash后端和本文结构化任务中未表现出描述性质量下降，"
    "但置信区间不足以建立严格非劣性，且仍有6.67%的Prompt出现重复调用不一致；K=5独立运行的宏观渗透率较接近，5次最终状态哈希却均不同，"
    "而固定判定记录后的3次回放均实现云端零调用、节点Hamming距离为0以及最终状态和轨迹哈希完全一致。事件驱动机制还将同一基线场景中的判定次数由2400次降至701次，"
    "并在不同网络规模下获得2.5～4.8倍的判定次数削减。由此，LEDS保证的是模型偏差及其传播后果可记录、可度量、可审计和可回放，而不是消除模型偏差或证明经验有效性。"
)
NEW_CONCLUSION = (
    "针对云端LLM判定内核难以完全冻结所导致的社会信息传播仿真复核问题，本文提出可重放事件驱动方法LEDS。"
    "该方法将传播过程形式化为冻结有向图上的有限类型事件转移系统，通过确定顺序调度、新颖事件过滤和判定记录映射，分别约束执行顺序、事件生成和状态转移证据，"
    "并给出记录条件下的轨迹唯一性、有限事件终止性与复杂度上界。实验表明，Temperature=0在deepseek-v4-flash后端和本文结构化任务中未表现出描述性质量下降，"
    "但置信区间不足以建立严格非劣性，且仍有6.67%的Prompt出现重复调用不一致；K=5独立运行的宏观渗透率较接近，5次最终状态哈希却均不同，"
    "而固定判定记录后的3次回放均实现云端零调用、节点Hamming距离为0以及最终状态和轨迹哈希完全一致。事件驱动机制还将同一基线场景中的判定次数由2400次降至701次，"
    "并在不同网络规模下获得2.5～4.8倍的判定次数削减。Facebook公开拓扑上的K=5探索性实验进一步显示，随机部署的运行间波动较小，边缘部署具有更高样本均值但区间较宽，"
    "中心部署虽获得一致的宏观终态，逐次轨迹却并不相同，从真实网络结构侧面印证了统计复现与精确回放不可相互替代。"
    "由此，LEDS保证的是模型偏差及其传播后果可记录、可度量、可审计和可回放，而不是消除模型偏差或证明经验有效性。"
)


def paragraph_text(paragraph: ET.Element) -> str:
    return "".join(node.text or "" for node in paragraph.iter(f"{W}t"))


def set_paragraph_text(paragraph: ET.Element, text: str) -> None:
    properties = paragraph.find(f"{W}pPr")
    saved_properties = copy.deepcopy(properties) if properties is not None else None
    for child in list(paragraph):
        paragraph.remove(child)
    if saved_properties is not None:
        paragraph.append(saved_properties)
    run = ET.SubElement(paragraph, f"{W}r")
    text_node = ET.SubElement(run, f"{W}t")
    text_node.set(f"{{{XML_NS}}}space", "preserve")
    text_node.text = text


def styled_paragraph(template: ET.Element, text: str) -> ET.Element:
    paragraph = ET.Element(f"{W}p")
    properties = template.find(f"{W}pPr")
    if properties is not None:
        paragraph.append(copy.deepcopy(properties))
    set_paragraph_text(paragraph, text)
    return paragraph


def set_table_cell_text(cell: ET.Element, text: str) -> None:
    paragraphs = cell.findall(f"{W}p")
    if not paragraphs:
        paragraphs = [ET.SubElement(cell, f"{W}p")]
    set_paragraph_text(paragraphs[0], text)
    for extra in paragraphs[1:]:
        cell.remove(extra)


def main() -> None:
    if not FIGURE.exists():
        raise FileNotFoundError(f"generate the figure first: {FIGURE}")

    with zipfile.ZipFile(SOURCE, "r") as source_archive:
        root = ET.fromstring(source_archive.read("word/document.xml"))
        body = root.find(f"{W}body")
        if body is None:
            raise RuntimeError("DOCX document body not found")

        paragraphs = list(root.iter(f"{W}p"))
        by_text = {paragraph_text(p): p for p in paragraphs if paragraph_text(p)}
        required = [OLD_PROTOCOL, OLD_AUDIT, OLD_ANALYSIS, OLD_CONCLUSION, OLD_LIMITATIONS]
        missing = [text[:50] for text in required if text not in by_text]
        if missing:
            raise RuntimeError(f"target paragraphs not found: {missing}")

        replacements = {
            OLD_PROTOCOL: NEW_PROTOCOL,
            OLD_AUDIT: NEW_AUDIT,
            OLD_ANALYSIS: NEW_ANALYSIS,
            OLD_CONCLUSION: NEW_CONCLUSION,
            OLD_LIMITATIONS: NEW_LIMITATIONS,
            "4.2.1、4.4和4.6节；K=5用于揭示波动，不足以确证小效应": (
                "4.2.1、4.4、4.6和4.7节；K=5用于揭示波动，不足以确证小效应"
            ),
            "图6 真实Facebook网络三种部署的最终渗透率对比（单次运行）。注：随机部署0.0%、边缘部署9.9%、中心部署0.0%": (
                "图6 Facebook网络三种部署的K=5最终渗透率。注：小点表示无判定记录独立运行，大菱形表示均值，误差线表示均值的95% Student-t置信区间；中心部署5次观测均重合于0"
            ),
            "Fig. 6 Final penetration rates under three deployments on the Facebook network (single run)": (
                "Fig. 6 Final penetration rates of three deployments on the Facebook network (K=5)"
            ),
            "表8 合成BA网络与真实Facebook网络上的干预效能对照（真实deepseek-chat）": (
                "表8 Facebook网络三种部署的K=5独立运行结果（真实deepseek-chat）"
            ),
            "Table 8 Intervention effectiveness on synthetic BA and real Facebook networks": (
                "Table 8 Results of K=5 independent runs on the Facebook network"
            ),
        }
        for old, new in replacements.items():
            target = by_text.get(old)
            if target is None:
                raise RuntimeError(f"target paragraph not found: {old[:50]}")
            set_paragraph_text(target, new)

        analysis_paragraph = by_text[OLD_ANALYSIS]
        insert_at = list(body).index(analysis_paragraph) + 1
        body.insert(insert_at, styled_paragraph(analysis_paragraph, ADDITIONAL_ANALYSIS))

        tables = list(root.iter(f"{W}tbl"))
        target_table = None
        for table in tables:
            text = "".join(paragraph_text(p) for p in table.iter(f"{W}p"))
            if "合成 BA（N=300）" in text and "真实 Facebook（N=334）" in text:
                target_table = table
                break
        if target_table is None:
            raise RuntimeError("Facebook result table not found")

        table_rows = [
            ["部署策略", "5次最终渗透率/%", "均值±样本标准差/%（95%CI）"],
            ["随机部署", "13.47, 13.47, 13.77, 13.77, 12.87", "13.47±0.37（[13.02,13.93]）"],
            ["边缘部署（低度数）", "23.65, 23.95, 19.76, 23.95, 8.98", "20.06±6.44（[12.06,28.06]）"],
            ["中心部署（Hub）", "0.00, 0.00, 0.00, 0.00, 0.00", "0.00±0.00（[0.00,0.00]）"],
        ]
        rows = target_table.findall(f"{W}tr")
        if len(rows) != len(table_rows):
            raise RuntimeError(f"unexpected Facebook table row count: {len(rows)}")
        for row, values in zip(rows, table_rows):
            cells = row.findall(f"{W}tc")
            if len(cells) != len(values):
                raise RuntimeError(f"unexpected Facebook table column count: {len(cells)}")
            for cell, value in zip(cells, values):
                set_table_cell_text(cell, value)

        # The latest manuscript inserted a synthetic-network figure earlier, so the
        # real-network figure is image6/Fig. 6 even though older drafts called it Fig. 5.
        updated_xml = ET.tostring(root, encoding="utf-8", xml_declaration=True)
        with zipfile.ZipFile(OUTPUT, "w", compression=zipfile.ZIP_DEFLATED) as output_archive:
            for entry in source_archive.infolist():
                if entry.filename == "word/document.xml":
                    payload = updated_xml
                elif entry.filename == "word/media/image6.png":
                    payload = FIGURE.read_bytes()
                else:
                    payload = source_archive.read(entry.filename)
                output_archive.writestr(entry, payload)

    print(OUTPUT)


if __name__ == "__main__":
    main()
