# -*- coding: utf-8 -*-
"""Correct the manuscript's interpretation of historical DeepSeek API IDs.

The source DOCX is preserved.  This script edits only targeted paragraphs and
the model-ID header cells in ``word/document.xml``.  Experimental values and
all unrelated package parts remain unchanged.
"""
from __future__ import annotations

import copy
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS = {"w": W}
XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"
ET.register_namespace("w", W)

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "LEDS_指挥与控制学报_温度统计单位修订_投稿完善稿_2026-07-29.docx"
OUTPUT = ROOT / "LEDS_指挥与控制学报_API服务标识与推理模式修订_投稿完善稿_2026-07-29.docx"


def qn(tag: str) -> str:
    return f"{{{W}}}{tag}"


def paragraph_text(paragraph: ET.Element) -> str:
    return "".join(node.text or "" for node in paragraph.findall(".//w:t", NS)).strip()


def set_paragraph_text(paragraph: ET.Element, text: str) -> None:
    paragraph_properties = paragraph.find("w:pPr", NS)
    paragraph_properties = copy.deepcopy(paragraph_properties) if paragraph_properties is not None else None
    first_run_properties = paragraph.find("w:r/w:rPr", NS)
    first_run_properties = copy.deepcopy(first_run_properties) if first_run_properties is not None else None
    paragraph.clear()
    if paragraph_properties is not None:
        paragraph.append(paragraph_properties)
    run = ET.SubElement(paragraph, qn("r"))
    if first_run_properties is not None:
        run.append(first_run_properties)
    node = ET.SubElement(run, qn("t"))
    node.set(XML_SPACE, "preserve")
    node.text = text


REPLACEMENTS = {
    "（3）构建面向运行不确定性与记录回放一致性的分层实验验证协议。": (
        "（3）构建面向运行不确定性与记录回放一致性的分层实验验证协议。分别规定运行级与记录级复核的评价对象、实验条件、核心指标和判定准则：通过无判定记录独立运行量化宏观渗透率与微观节点状态的运行间差异，通过固定且完整判定记录、全程零新增云端调用的回放检验逐节点状态与规范化轨迹的一致性；结合温度敏感性、同一模型家族下不同推理模式及历史API服务标识的方向性比较、合成网络和真实社交网络实验考察方法的适用边界。事实核查员空间部署作为应用案例，用于说明忽略运行间不确定性可能导致不稳健的干预结论。"
    ),
    "实验设计与第3节的分层复核目标相对应。": (
        "实验设计与第3节的分层复核目标相对应。4.2.1节检验零温度条件下结构化判定质量与重复调用差异；4.3节检验事件触发机制相对于全轮询的状态更新语义和评估次数；4.4节实施运行级与记录级复核，4.4.1节进一步以单变量消融分离确定顺序调度、新颖事件过滤和判定记录映射的证据作用；4.5节仅考察同一模型家族下不同推理模式及历史API服务标识的方向性现象，4.6—4.7节考察网络结构的适用边界，并以事实核查员部署说明分层复核对干预结论的约束作用。"
    ),
    "实验通过兼容OpenAI/DeepSeek规范的云端API访问模型": (
        "实验通过兼容OpenAI/DeepSeek规范的云端API访问模型，并按“请求模型ID—实验章节—请求参数—证据用途”建立对应关系。历史API服务标识deepseek-chat用于主网络实验、合成与真实网络应用和规模化开销分析；历史标识deepseek-reasoner仅用于4.5节同一模型家族下推理模式的方向性比较；deepseek-v4-flash用于4.2.1节温度敏感性实验和4.4节K=5零温度探针。据供应商2026年7月24日服务更新前的同期说明，前两者在实验时期分别对应deepseek-v4-flash的非思考模式与思考模式服务入口，并于该次更新后停止作为相互独立的旧模型名使用，故本文不将其视为两个独立模型后端。客户端归档未保存服务端返回的完整模型版本元数据，不能据此独立确认每次请求实际路由的权重快照。温度实验调用时间为2026年7月25日（UTC日志范围08:54—21:00），K=5探针调用时间为2026年7月26日（UTC日志范围02:17—07:52）。除特别注明外，主网络实验采用Temperature=0、Top_P=1.0。"
    ),
    "零温度能否在减少采样扰动的同时保持结构化判定质量": (
        "零温度能否在减少采样扰动的同时保持结构化判定质量，是后续可重放实验的参数前提。为检验该问题，实验固定System Prompt、User Prompt模板、人设规则、输出JSON Schema、Top_P=1.0、解析规则和deepseek-v4-flash API标识，仅改变Temperature∈{0,0.2,0.5,0.7}。Prompt池包含240条样本，三类人设各80条，覆盖当前信念、谣言来源数、辟谣来源数和新增消息类型等状态转移边界。每条Prompt在每个温度下独立调用3次，共获得2880条真实API输出。统计推断以240个Prompt而非单个输出为单位：先对同一Prompt在每个温度下的3次联合规则一致性指标取均值，再按相同prompt_id在温度间配对，并在三类人设内对Prompt簇有放回重采样，实施50000次分层配对Prompt-cluster Bootstrap（随机种子20260729）。因此，每个温度的720条记录表示输出数量，并非720个相互独立的推断样本。由于该实验与deepseek-chat主网络实验使用不同的API服务标识，其结果仅作为同一供应商模型家族内另一历史服务入口的温度敏感性证据，不能据此作跨模型推断。"
    ),
    "4.5 跨LLM后端的方向性比较": "4.5 不同推理模式及历史API服务标识下的方向性比较",
    "为观察方法性质是否仅出现在deepseek-chat后端": (
        "据供应商2026年7月24日服务更新前的同期说明，实验请求中的历史标识deepseek-chat和deepseek-reasoner分别对应deepseek-v4-flash的非思考模式与思考模式服务入口；该次更新后，两者停止作为相互独立的旧模型名使用。因此，本节不是跨模型、跨厂商或两个独立后端的验证，而是在两类冻结拓扑和两类干预部署构成的4组配置上进行的方向性比较。两组实验固定网络、源节点、人设和Prompt；deepseek-chat请求包含Temperature=0、Top_P=1.0和JSON格式约束，deepseek-reasoner则由历史模型ID选择思考模式，未发送独立思考模式参数，并按当时代码省略temperature、top_p和response_format字段。由此，该比较不满足严格单变量消融条件，仅用于观察中心节点部署的抑制方向是否重复出现以及响应能否由既定解析器获得合法结构化结果，不用于建立不同模型间绝对渗透率或拓扑排序的稳健结论。"
    ),
    "表 4 主实验在两个LLM后端上的对照": "表 4 同一模型家族不同推理模式及历史API服务标识下的方向性比较（最终渗透率/稳态步数）",
    "Table 4 Comparison of the main experiment on two LLM backends": "Table 4 Directional comparison between reasoning modes and historical API service identifiers in the same model family",
    "两个后端在4组配置中的无效JSON率": (
        "两类历史API服务标识对应的4组配置中，无效JSON率和兜底回退率均为0。中心节点部署在deepseek-chat和deepseek-reasoner标识下的渗透率分别为0.0%和0.3%，稳态步数均为7，未观察到抑制方向反转。其余配置的绝对渗透率差异较大；鉴于请求构造并非仅有推理模式一个变量，且每个标识下每种配置仅运行1次，不能区分推理模式、请求约束差异与运行间波动的影响。"
    ),
    "因此，跨后端结果仅支持两项有限判断": (
        "因此，该方向性比较仅支持两项有限观察：中心节点部署的强抑制方向在本组配置中重复出现；deepseek-reasoner历史标识返回的内容均可由既定解析器获得合法结构化结果。该结果既不是跨模型或跨厂商验证，也不构成推理模式的因果效应、跨后端泛化或模型无关性证据。"
    ),
    "中心部署5次最终渗透率均为0": (
        "中心部署5次最终渗透率均为0，且最终状态哈希相同，说明在当前冻结拓扑、节点选择、历史API服务标识与Prompt配置下获得了稳定的宏观终态；但5次轨迹哈希各不相同，宏观结果一致不能推出逐事件轨迹一致。该现象与分层复核定义相吻合：无判定记录独立运行用于估计结果分布，只有固定判定记录的回放才能检验轨迹精确一致性。受单一公开拓扑、固定干预节点、单一历史API服务标识和K=5小样本限制，上述结果仅作为探索性估计，不能外推为中心部署在其他网络、传播文本或真实人群中的普遍因果效应。"
    ),
    "本研究仍存在5方面限制": (
        "本研究仍存在5方面限制：合成网络和Facebook网络每种条件均仅独立运行5次，小样本区间尚不足以识别较小效应；模型证据限于DeepSeek同一模型家族的若干API服务标识，其中4.5节两种历史标识的请求构造并非严格单变量且每种配置仅运行1次，缺少跨厂商和本地开源模型验证；最大实测规模为1000个节点；真实网络仅包含一个Facebook ego-network，且仅使用公开拓扑，人设比例、传播文本和行为规则尚未由真实传播数据或人类行为证据校准；机制消融方面，调度实验使用同一完整API判定记录验证规范化轨迹作用，而无新颖过滤实验采用冻结规则判定记录检验结构终止边界，尚未在无过滤反事实路径上构建完整真实API判定记录，因而不对其LLM传播效应作经验声明。后续工作将扩大独立重复次数和网络规模，在多模型、多平台及多个真实网络上复核记录级与运行级性质，并结合真实传播轨迹和人类行为数据开展参数校准；同时在预算可控的小型冻结网络上构建覆盖无过滤反事实路径的真实API判定记录，以进一步检验结构结论与语义判定的耦合边界。"
    ),
    "未配置API Key时，src/stage2_engine.py中的_mock_decide": (
        "未配置API Key时，src/stage2_engine.py中的_mock_decide以确定性if/else规则复现3类人设逻辑，仅用于离线链路验证，不进入正文统计。真实API证据按请求模型ID分别报告：历史标识deepseek-chat用于主网络实验、应用分析与规模化开销；历史标识deepseek-reasoner仅用于4.5节同一模型家族下不同推理模式的方向性比较；deepseek-v4-flash用于4.2.1节温度敏感性实验和4.4节K=5零温度探针。不同标识的结果不混合统计，也不相互替代。4.5节旧归档保存Prompt哈希和响应正文，但未保存完整HTTP响应包、逐请求UTC时间、响应model字段、usage、服务端版本指纹或reasoning_content；因此，本文不依据历史标识推断无法独立核验的服务端权重快照。温度实验与K=5探针的请求时间、端点、Temperature、Top_P、配置哈希和逐次输出均保存在随稿日志中。"
    ),
}


METADATA_PARAGRAPH = (
    "可审计边界如下：两类请求均指向本地运行配置记录的API端点"
    "https://api.deepseek.com/v1/chat/completions。4.5节旧归档未保存逐请求UTC时间或完整HTTP响应元数据，"
    "现可恢复的UTC信息仅为各结果日志的归档完成时间：deepseek-chat对应的小世界、无标度、边缘部署和中心部署"
    "日志分别为2026-07-12T16:32:00Z、2026-07-12T02:43:52Z、2026-07-12T02:43:54Z和"
    "2026-07-12T02:43:54Z；deepseek-reasoner对应日志分别为2026-07-12T17:42:20Z、"
    "2026-07-12T18:10:34Z、2026-07-12T18:39:36Z和2026-07-12T18:52:52Z。上述文件系统时间仅作为"
    "结果归档证据，不解释为逐请求调用时刻。由于旧归档亦未保存响应model字段和服务端版本指纹，本文仅按实际请求中的"
    "历史模型ID及客户端请求构造报告结果，不对实际路由的权重版本作独立确认。"
)


def patch_document(root: ET.Element) -> None:
    counts = {prefix: 0 for prefix in REPLACEMENTS}
    insertion_anchor = None
    for paragraph in root.findall(".//w:p", NS):
        current = paragraph_text(paragraph)
        for prefix, replacement in REPLACEMENTS.items():
            if current.startswith(prefix):
                set_paragraph_text(paragraph, replacement)
                counts[prefix] += 1
                if prefix.startswith("为观察方法性质是否仅出现在"):
                    insertion_anchor = paragraph
                break
    bad = {prefix: count for prefix, count in counts.items() if count != 1}
    if bad:
        raise RuntimeError(f"Expected exactly one match for every paragraph target: {bad}")
    if insertion_anchor is None:
        raise RuntimeError("Metadata insertion anchor not found")
    parent = next(item for item in root.iter() if insertion_anchor in list(item))
    metadata = copy.deepcopy(insertion_anchor)
    set_paragraph_text(metadata, METADATA_PARAGRAPH)
    parent.insert(list(parent).index(insertion_anchor) + 1, metadata)

    table_matches = 0
    for table in root.findall(".//w:tbl", NS):
        rows = table.findall("w:tr", NS)
        if not rows:
            continue
        cells = rows[0].findall("w:tc", NS)
        headers = [paragraph_text(cell) for cell in cells]
        if headers[:3] == ["实验场景", "deepseek-chat（单次）", "deepseek-reasoner（单次）"]:
            set_paragraph_text(cells[1].find("w:p", NS), "deepseek-chat（历史服务标识，单次）")
            set_paragraph_text(cells[2].find("w:p", NS), "deepseek-reasoner（历史服务标识，单次）")
            table_matches += 1
    if table_matches != 1:
        raise RuntimeError(f"Expected one model-comparison table, found {table_matches}")


def write_patched_docx(source: Path, output: Path) -> None:
    if not source.exists():
        raise FileNotFoundError(source)
    with zipfile.ZipFile(source, "r") as archive:
        root = ET.fromstring(archive.read("word/document.xml"))
        patch_document(root)
        document_xml = ET.tostring(root, encoding="utf-8", xml_declaration=True)
        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as destination:
            for item in archive.infolist():
                data = document_xml if item.filename == "word/document.xml" else archive.read(item.filename)
                destination.writestr(item, data)


if __name__ == "__main__":
    write_patched_docx(SOURCE, OUTPUT)
    print(f"wrote {OUTPUT}")
