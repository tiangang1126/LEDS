# -*- coding: utf-8 -*-
"""Update the LEDS manuscript with Prompt-level temperature statistics.

The source manuscript is preserved. Only targeted paragraphs and Table S1 are
edited in ``word/document.xml`` so that unrelated Word formatting and package
parts remain unchanged.
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
SOURCE = ROOT / "LEDS_指挥与控制学报_融合K5真实网络与核心机制消融_投稿完善稿_2026-07-29.docx"
OUTPUT = ROOT / "LEDS_指挥与控制学报_温度统计单位修订_投稿完善稿_2026-07-29.docx"


def qn(tag: str) -> str:
    return f"{{{W}}}{tag}"


def paragraph_text(paragraph: ET.Element) -> str:
    return "".join(node.text or "" for node in paragraph.findall(".//w:t", NS)).strip()


def set_paragraph_text(paragraph: ET.Element, text: str) -> None:
    """Replace visible text while retaining paragraph and first-run properties."""
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
    text_node = ET.SubElement(run, qn("t"))
    text_node.set(XML_SPACE, "preserve")
    text_node.text = text


PARAGRAPH_REPLACEMENTS = {
    "零温度解码用于减少显式采样扰动": (
        "零温度解码用于减少显式采样扰动，但不是记录级可重放性的充分条件。本文在"
        "deepseek-v4-flash后端上的补充实验表明，在所测试Prompt池和结构化状态转移任务中，"
        "T=0与较高温度的联合规则一致率接近。以Prompt为统计单元的配对Bootstrap结果显示，"
        "T=0相对T=0.2、0.5和0.7的联合规则一致率差值95%置信区间下限均高于分析脚本设定的"
        "-3个百分点界值，为本实验范围内的非劣性提供统计支持。但该界值未经外部行为效度校准，"
        "本实验也不是预注册的确证性非劣试验，故不能外推到开放式生成、其他模型后端或真实社会"
        "行为。T=0条件下仍有6.67%的Prompt在三次调用中产生不同判定，说明云端推理并未因温度"
        "置零而成为确定函数。"
    ),
    "零温度能否在减少采样扰动的同时保持结构化判定质量": (
        "零温度能否在减少采样扰动的同时保持结构化判定质量，是后续可重放实验的参数前提。"
        "为检验该问题，实验固定System Prompt、User Prompt模板、人设规则、输出JSON Schema、"
        "Top_P=1.0、解析规则和deepseek-v4-flash API标识，仅改变Temperature∈{0,0.2,0.5,0.7}。"
        "Prompt池包含240条样本，三类人设各80条，覆盖当前信念、谣言来源数、辟谣来源数和新增"
        "消息类型等状态转移边界。每条Prompt在每个温度下独立调用3次，共获得2880条真实API"
        "输出。统计推断以240个Prompt而非单个输出为单位：先对同一Prompt在每个温度下的3次"
        "联合规则一致性指标取均值，再按相同prompt_id在温度间配对，并在三类人设内对Prompt簇"
        "有放回重采样，实施50000次分层配对Prompt-cluster Bootstrap（随机种子20260729）。"
        "因此，每个温度的720条记录表示输出数量，并非720个相互独立的推断样本。由于该实验与"
        "deepseek-chat主网络实验使用不同API标识，其结果仅作为另一DeepSeek后端上的温度敏感性证据。"
    ),
    "附录 D表S1表明": (
        "附录 D表S1表明，4个温度下的JSON合法率均为100%，联合规则一致率依次为67.22%、"
        "67.36%、66.81%和67.08%，点估计最大差异小于0.6个百分点；相应的95% Prompt级"
        "Bootstrap置信区间分别为[61.53,72.78]、[61.67,72.92]、[61.11,72.36]和"
        "[61.39,72.64]。差值定义为T=0减去比较温度，T=0相对T=0.2、0.5和0.7的差值分别为"
        "-0.14、0.42和0.14个百分点，其95%配对Prompt级Bootstrap置信区间分别为[-1.53,1.25]、"
        "[-0.97,1.81]和[-1.25,1.53]个百分点。三个区间下限均高于分析脚本设定的-3个百分点"
        "界值，因而在本Prompt池和结构化任务内为T=0的非劣性提供统计支持。鉴于该界值未经外部"
        "行为效度校准，且实验并非预注册的确证性非劣试验，本文不作跨任务、跨模型的普遍非劣推断。"
    ),
    "针对云端LLM判定内核难以完全冻结": (
        "针对云端LLM判定内核难以完全冻结所导致的社会信息传播仿真复核问题，本文提出可重放事件"
        "驱动方法LEDS。该方法将传播过程形式化为冻结有向图上的有限类型事件转移系统，以固定节点"
        "顺序规范同一逻辑时间层内的调用与日志排列，以新颖事件过滤约束事件生成，并以判定记录映射"
        "保存状态转移证据；在判定记录覆盖全部实际访问Prompt、记录响应可由固定规则解析且无新增"
        "云端调用的条件下，给出规范化审计轨迹唯一性、有限事件终止性与复杂度上界。固定节点顺序"
        "仅承担规范化轨迹表示功能，本文不将其解释为最终状态一致性的独立必要条件。温度敏感性实验"
        "以Prompt为统计单元；T=0相对三个较高温度的配对Bootstrap差值区间下限均高于-3个百分点"
        "分析界值，为本文结构化任务内的非劣性提供统计支持，但不构成跨任务、跨模型或经验有效性的"
        "确证性证明，且T=0时仍有6.67%的Prompt出现重复调用不一致。K=5独立运行的宏观渗透率较"
        "接近，5次最终状态哈希却均不同，而满足全记录命中和零新增调用条件的3次回放均实现节点"
        "Hamming距离为0以及最终状态和轨迹哈希完全一致。事件驱动机制还将同一基线场景中的判定"
        "次数由2400次降至701次，并在不同网络规模下获得2.5～4.8倍的判定次数削减。核心机制消融"
        "进一步表明，在同一完整API判定记录下，5种随机同层顺序均保持最终状态不变而改变轨迹串行"
        "哈希；在同一冻结规则记录下，取消新颖过滤使事件数由917增至16727，并在Tmax=30时仍未"
        "自然终止。Facebook公开拓扑上的K=5探索性实验进一步显示，随机部署的运行间波动较小，"
        "边缘部署具有更高样本均值但区间较宽，中心部署虽获得一致的宏观终态，逐次轨迹却并不相同，"
        "从真实网络结构侧面印证了统计复现与精确回放不可相互替代。由此，LEDS保证的是在明确证据"
        "条件下使模型判定及其传播后果可记录、可度量、可审计和可回放，而不是消除模型偏差或证明"
        "经验有效性。"
    ),
    "表 S1和表 S2给出正文4.2.1节": (
        "表 S1和表 S2给出正文4.2.1节温度敏感性实验的完整统计结果。推断单位为Prompt：同一"
        "Prompt在每个温度下的3次输出先聚合为均值，再按prompt_id进行温度间配对；置信区间采用"
        "按人设分层的配对Prompt-cluster Bootstrap（50000次重采样，随机种子20260729）。所有"
        "数值均与正文汇总一致。"
    ),
    "注：联合规则一致率要求stance和action同时": (
        "注：联合规则一致率要求stance和action同时与规则参照一致；Prompt不一致率表示同一温度"
        "下同一Prompt的3次调用至少出现两种结构化输出。表中每个温度包含240个独立Prompt和720条"
        "输出，720仅为输出数量，不作为独立推断样本量。差值定义为T=0减去比较温度；T=0相对"
        "T=0.2、0.5和0.7的差值95%配对Prompt级Bootstrap置信区间依次为[-1.53,1.25]、"
        "[-0.97,1.81]和[-1.25,1.53]个百分点。"
    ),
    "注：每个温度下每类人设N=240": (
        "注：每个温度下每类人设包含80个Prompt、240条输出；统计单位为Prompt。"
    ),
}


TABLE_HEADERS = [
    "Temperature",
    "Prompt数（输出数）",
    "联合规则一致率",
    "95% Prompt级Bootstrap CI",
    "Stance一致率",
    "Action一致率",
    "JSON合法率",
    "Prompt不一致率",
]

TABLE_ROWS = [
    ["0.0", "240（720）", "67.22%", "[61.53, 72.78]", "73.89%", "81.81%", "100.00%", "6.67%"],
    ["0.2", "240（720）", "67.36%", "[61.67, 72.92]", "74.03%", "81.81%", "100.00%", "6.25%"],
    ["0.5", "240（720）", "66.81%", "[61.11, 72.36]", "73.19%", "81.25%", "100.00%", "7.08%"],
    ["0.7", "240（720）", "67.08%", "[61.39, 72.64]", "73.61%", "81.53%", "100.00%", "7.50%"],
]


def set_cell_text(cell: ET.Element, text: str) -> None:
    paragraphs = cell.findall("w:p", NS)
    if not paragraphs:
        paragraphs = [ET.SubElement(cell, qn("p"))]
    set_paragraph_text(paragraphs[0], text)
    for extra in paragraphs[1:]:
        cell.remove(extra)


def patch_document(root: ET.Element) -> None:
    replacement_counts = {prefix: 0 for prefix in PARAGRAPH_REPLACEMENTS}
    for paragraph in root.findall(".//w:p", NS):
        current = paragraph_text(paragraph)
        for prefix, replacement in PARAGRAPH_REPLACEMENTS.items():
            if current.startswith(prefix):
                set_paragraph_text(paragraph, replacement)
                replacement_counts[prefix] += 1
                break

    bad_counts = {prefix: count for prefix, count in replacement_counts.items() if count != 1}
    if bad_counts:
        raise RuntimeError(f"Expected exactly one paragraph match for each target: {bad_counts}")

    table_match_count = 0
    for table in root.findall(".//w:tbl", NS):
        rows = table.findall("w:tr", NS)
        if not rows:
            continue
        first_cells = rows[0].findall("w:tc", NS)
        header = [paragraph_text(cell) for cell in first_cells]
        if len(header) == 8 and header[:4] == ["Temperature", "N", "联合规则一致率", "95% Wilson CI"]:
            # Word stores Table S1 and Table S2 as one continuous table. Only
            # the first five rows belong to S1; the persona rows must remain
            # byte-for-byte semantically unchanged.
            if len(rows) < 5:
                raise RuntimeError(f"Unexpected combined appendix table row count: {len(rows)}")
            for cell, text in zip(first_cells, TABLE_HEADERS, strict=True):
                set_cell_text(cell, text)
            for row, values in zip(rows[1:5], TABLE_ROWS, strict=True):
                cells = row.findall("w:tc", NS)
                if len(cells) != 8:
                    raise RuntimeError(f"Unexpected Table S1 column count: {len(cells)}")
                for cell, text in zip(cells, values, strict=True):
                    set_cell_text(cell, text)
            table_match_count += 1
    if table_match_count != 1:
        raise RuntimeError(f"Expected one Table S1 match, found {table_match_count}")


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
