from __future__ import annotations

import copy
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
XML_NS = "http://www.w3.org/XML/1998/namespace"
W = f"{{{W_NS}}}"
ET.register_namespace("w", W_NS)

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "LEDS_指挥与控制学报_理论主张收缩修订稿_0728_v2.docx"
OUTPUT = ROOT / "LEDS_指挥与控制学报_核心机制消融修订稿_0729.docx"


SECTION_TITLE = "4.4.1 核心机制消融实验"
CAPTION_ZH = "表 3 LEDS三个核心机制的最小消融结果"
CAPTION_EN = "Table 3 Minimum ablation results of the three core LEDS mechanisms"

DESIGN_TEXT = (
    "为分离确定顺序调度、新颖事件过滤和判定记录映射的作用，本文在同一冻结无标度网络、源节点、"
    "人设映射、Prompt模板、解析规则和Tmax=30条件下开展最小机制消融。实验采用两个相互隔离的证据层。"
    "调度消融读取4.4节deepseek-v4-flash seed运行生成的同一判定记录，并将新增消息按“发送节点—消息类型—内容”"
    "规范化后构造Prompt；记录未命中即终止，禁止回落到云端调用。新颖过滤消融用于检验事件耗散与截断边界："
    "先由有限状态人设规则生成完整配置和无过滤配置实际访问Prompt的联合判定记录，再冻结该记录分别回放。"
    "该部分属于算法结构压力检验，不作为新的LLM传播效果证据。无判定记录配置直接复用4.4节K=5独立运行，"
    "不重复计为新增样本。"
)

RESULT_TEXT = (
    "表3显示，完整LEDS回放的615次判定全部命中既有API判定记录，云端调用增量为0，稳态步数、渗透率、"
    "final state hash和trace hash均与seed运行一致。将同层节点顺序分别按5个固定随机种子打乱后，每次仍为"
    "615/615记录命中、0次云端调用、8步自然终止，且final state hash均与完整LEDS相同；5条trace hash和"
    "schedule-order hash则均发生变化。该结果支持固定nodeid顺序主要规范同层调用和轨迹串行表示，而不是"
    "当前同步分层语义下最终状态一致性的独立原因。"
)

FILTER_TEXT = (
    "在同一冻结规则判定记录下，保留新颖过滤的结构配置经9步自然终止，完成561次判定并发出917个事件；"
    "取消过滤后，至第30步已完成6322次判定并发出16727个事件，分别增至11.27倍和18.24倍，队列中仍有"
    "234个活跃节点和614条消息，因而按预设Tmax截断。该结果验证的是三元事件访问标记对有限事件耗散和"
    "复杂度上界的作用，不用于比较两配置的最终渗透率或经验效度。结合4.4节无记录K=5独立运行中5个final "
    "state hash和5个trace hash均不同，而固定记录回放3/3精确一致，可将三项机制的证据功能区分为："
    "顺序机制规范轨迹表示，新颖过滤约束事件生成与终止边界，判定记录映射支持既有状态转移的精确复核。"
)

AUDIT_TEXT = (
    "全部消融运行保存冻结配置、Prompt配置、执行脚本、API seed判定记录、结构判定记录、逐配置日志及其"
    "SHA-256清单。正式评估阶段禁止云端调用；完整LEDS门禁要求记录全命中、云端调用增量为0，并与seed的"
    "步数、渗透率、final state hash和trace hash逐项一致。相同命令在独立输出目录复跑后，全部配置指标与"
    "哈希逐项一致。"
)

TABLE_ROWS = [
    ["配置", "调度", "新颖过滤", "判定记录", "判定/事件数", "终止状态", "哈希比较"],
    ["完整LEDS", "固定", "有", "API记录，全命中", "615/1031", "8步，自然终止", "final、trace均与seed一致"],
    ["随机顺序（5种子）", "随机", "有", "同一API记录，全命中", "每次615/1031", "均为8步，自然终止", "final 5/5一致；trace 5/5不同"],
    ["结构完整配置", "固定", "有", "冻结规则记录", "561/917", "9步，自然终止", "结构基准"],
    ["无新颖过滤", "固定", "无", "同一冻结规则记录", "6322/16727", "Tmax=30截断；余614条消息", "截断状态，不作终态优劣比较"],
    ["无共享判定记录", "固定", "有", "K=5空记录独立运行", "云端调用439～450次", "均自然终止", "final、trace均5/5不同"],
]


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


def table_cell(text: str, template_cell: ET.Element | None = None) -> ET.Element:
    cell = ET.Element(f"{W}tc")
    if template_cell is not None:
        properties = template_cell.find(f"{W}tcPr")
        if properties is not None:
            copied = copy.deepcopy(properties)
            width = copied.find(f"{W}tcW")
            if width is not None:
                width.set(f"{W}type", "auto")
                width.set(f"{W}w", "0")
            cell.append(copied)
    paragraph = ET.SubElement(cell, f"{W}p")
    set_paragraph_text(paragraph, text)
    return cell


def build_table(template: ET.Element) -> ET.Element:
    table = ET.Element(f"{W}tbl")
    properties = template.find(f"{W}tblPr")
    if properties is not None:
        copied = copy.deepcopy(properties)
        width = copied.find(f"{W}tblW")
        if width is not None:
            width.set(f"{W}type", "auto")
            width.set(f"{W}w", "0")
        table.append(copied)
    grid = ET.SubElement(table, f"{W}tblGrid")
    for _ in range(len(TABLE_ROWS[0])):
        column = ET.SubElement(grid, f"{W}gridCol")
        column.set(f"{W}w", "1100")
    template_cell = template.find(f".//{W}tc")
    for values in TABLE_ROWS:
        row = ET.SubElement(table, f"{W}tr")
        for value in values:
            row.append(table_cell(value, template_cell))
    return table


def replace_table_numbers(text: str) -> str:
    replacements = [
        ("表 6", "表 __7__"), ("Table 6", "Table __7__"),
        ("表6", "表__7__"), ("Table6", "Table__7__"),
        ("表 5", "表 __6__"), ("Table 5", "Table __6__"),
        ("表5", "表__6__"), ("Table5", "Table__6__"),
        ("表 4", "表 __5__"), ("Table 4", "Table __5__"),
        ("表4", "表__5__"), ("Table4", "Table__5__"),
        ("表 3", "表 __4__"), ("Table 3", "Table __4__"),
        ("表3", "表__4__"), ("Table3", "Table__4__"),
    ]
    for old, new in replacements:
        text = text.replace(old, new)
    return text.replace("__7__", "7").replace("__6__", "6").replace(
        "__5__", "5").replace("__4__", "4"
    )


def main() -> None:
    with zipfile.ZipFile(SOURCE, "r") as source_archive:
        root = ET.fromstring(source_archive.read("word/document.xml"))
        body = root.find(f"{W}body")
        if body is None:
            raise RuntimeError("DOCX document body not found")

        paragraphs = list(root.iter(f"{W}p"))
        heading_45 = next(
            (p for p in paragraphs if paragraph_text(p) == "4.5 跨LLM后端的方向性比较"),
            None,
        )
        heading_template = heading_45
        caption_zh_template = next(
            (p for p in paragraphs if paragraph_text(p).startswith("表 2 零温度")), None
        )
        caption_en_template = next(
            (p for p in paragraphs if paragraph_text(p).startswith("Table 2 Run-to-run")), None
        )
        body_template = next(
            (p for p in paragraphs if paragraph_text(p).startswith("为检验T=0条件下")), None
        )
        if None in (heading_45, caption_zh_template, caption_en_template, body_template):
            raise RuntimeError("Required insertion anchors not found")

        # Shift existing result table captions and references before inserting Table 3.
        for paragraph in paragraphs:
            old = paragraph_text(paragraph)
            new = replace_table_numbers(old)
            if new != old:
                set_paragraph_text(paragraph, new)

        # Update the experiment map in Section 4.
        experiment_map = next(
            (p for p in paragraphs if paragraph_text(p).startswith("实验设计与第3节的分层复核目标相对应。")),
            None,
        )
        if experiment_map is None:
            raise RuntimeError("Experiment-map paragraph not found")
        set_paragraph_text(
            experiment_map,
            "实验设计与第3节的分层复核目标相对应。4.2.1节检验零温度条件下结构化判定质量与重复调用差异；"
            "4.3节检验事件触发机制相对于全轮询的状态更新语义和评估次数；4.4节实施运行级与记录级复核，"
            "4.4.1节进一步以单变量消融分离确定顺序调度、新颖事件过滤和判定记录映射的证据作用；"
            "4.5—4.7节考察模型后端与网络结构的适用边界，并以事实核查员部署说明分层复核对干预结论的约束作用。",
        )

        # Use the current zero-temperature result table as a formatting template.
        result_tables = list(root.iter(f"{W}tbl"))
        table_template = next(
            table for table in result_tables
            if "度量" in "".join(paragraph_text(p) for p in table.iter(f"{W}p"))
            and "结果" in "".join(paragraph_text(p) for p in table.iter(f"{W}p"))
        )
        insert_at = list(body).index(heading_45)
        blocks = [
            styled_paragraph(heading_template, SECTION_TITLE),
            styled_paragraph(body_template, DESIGN_TEXT),
            styled_paragraph(caption_zh_template, CAPTION_ZH),
            styled_paragraph(caption_en_template, CAPTION_EN),
            build_table(table_template),
            styled_paragraph(body_template, RESULT_TEXT),
            styled_paragraph(body_template, FILTER_TEXT),
            styled_paragraph(body_template, AUDIT_TEXT),
        ]
        for offset, block in enumerate(blocks):
            body.insert(insert_at + offset, block)

        conclusion = next(
            (p for p in root.iter(f"{W}p") if paragraph_text(p).startswith("针对云端LLM判定内核难以完全冻结")),
            None,
        )
        if conclusion is None:
            raise RuntimeError("Conclusion paragraph not found")
        conclusion_text = paragraph_text(conclusion)
        marker = "Facebook公开拓扑上的K=5探索性实验进一步显示"
        mechanism_sentence = (
            "核心机制消融进一步表明，在同一完整API判定记录下，5种随机同层顺序均保持最终状态不变而改变轨迹串行哈希；"
            "在同一冻结规则记录下，取消新颖过滤使事件数由917增至16727，并在Tmax=30时仍未自然终止。"
        )
        if marker not in conclusion_text:
            raise RuntimeError("Conclusion insertion marker not found")
        set_paragraph_text(conclusion, conclusion_text.replace(marker, mechanism_sentence + marker))

        limitations = next(
            (p for p in root.iter(f"{W}p") if paragraph_text(p).startswith("本研究仍存在5方面限制")),
            None,
        )
        if limitations is None:
            raise RuntimeError("Limitations paragraph not found")
        set_paragraph_text(
            limitations,
            "本研究仍存在5方面限制：合成网络和Facebook网络每种条件均仅独立运行5次，小样本区间尚不足以识别较小效应；"
            "模型后端限于DeepSeek同族API标识，缺少跨厂商和本地开源模型验证；最大实测规模为1000个节点；"
            "真实网络仅包含一个Facebook ego-network，且仅使用公开拓扑，人设比例、传播文本和行为规则尚未由真实传播数据或人类行为证据校准；"
            "机制消融方面，调度实验使用同一完整API判定记录验证规范化轨迹作用，而无新颖过滤实验采用冻结规则判定记录检验结构终止边界，"
            "尚未在无过滤反事实路径上构建完整真实API判定记录，因而不对其LLM传播效应作经验声明。后续工作将扩大独立重复次数和网络规模，"
            "在多模型、多平台及多个真实网络上复核记录级与运行级性质，并结合真实传播轨迹和人类行为数据开展参数校准；"
            "同时在预算可控的小型冻结网络上构建覆盖无过滤反事实路径的真实API判定记录，以进一步检验结构结论与语义判定的耦合边界。",
        )

        updated_xml = ET.tostring(root, encoding="utf-8", xml_declaration=True)
        with zipfile.ZipFile(OUTPUT, "w", compression=zipfile.ZIP_DEFLATED) as output_archive:
            for entry in source_archive.infolist():
                payload = updated_xml if entry.filename == "word/document.xml" else source_archive.read(entry.filename)
                output_archive.writestr(entry, payload)

    print(OUTPUT)


if __name__ == "__main__":
    main()
