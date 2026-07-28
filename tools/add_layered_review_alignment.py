from copy import deepcopy
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZIP_DEFLATED, ZipFile


WORD_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
XML_NS = "http://www.w3.org/XML/1998/namespace"
W = f"{{{WORD_NS}}}"

SOURCE = Path("LEDS_指挥与控制学报_李铁乔_0725_科学论文范式全文重写稿_贡献逻辑优化版.docx")
OUTPUT = Path("LEDS_指挥与控制学报_李铁乔_0727_分层复核与方法对齐修订稿.docx")


CONTRIBUTION_3_OLD = (
    "（3）构建面向运行不确定性与记录回放一致性的分层实验验证方案。通过无判定记录独立运行量化宏观渗透率与微观节点状态的运行间差异，"
    "通过固定判定记录回放检验逐节点状态与完整轨迹的一致性，并结合温度敏感性、不同LLM后端、合成网络和真实社交网络实验考察方法的适用边界。"
    "事实核查员空间部署作为应用案例，用于说明忽略运行间不确定性可能导致不稳健的干预结论。"
)
CONTRIBUTION_3_NEW = (
    "（3）构建面向运行不确定性与记录回放一致性的分层实验验证协议。分别规定运行级与记录级复核的评价对象、实验条件、核心指标和判定准则："
    "通过无判定记录独立运行量化宏观渗透率与微观节点状态的运行间差异，通过固定判定记录回放检验逐节点状态与完整轨迹的一致性；"
    "结合温度敏感性、不同LLM后端、合成网络和真实社交网络实验考察方法的适用边界。事实核查员空间部署作为应用案例，"
    "用于说明忽略运行间不确定性可能导致不稳健的干预结论。"
)

METHOD_INTRO = (
    "为解决云端LLM状态转移难以逐事件复核的问题，本文将LEDS定义为冻结有向图上的有限事件传播方法。其基本思想是：用有限状态空间约束模型输出，"
    "用类型化消息表示传播触发，用确定顺序调度控制事件执行，用新颖事件过滤限制重复传播，并将规范化Prompt与结构化判定保存为可索引记录。"
    "API调用、JSON解析和本地存储是上述机制的实现载体，而非独立研究目标。表1进一步把引言提出的分层复核框架转化为可操作的评价对象、实验条件、指标和判定准则。"
)

LAYER_PARAGRAPH = (
    "表1所列层次回答不同问题。记录级轨迹可重放性针对一次既有运行，要求在固定拓扑、人设、初始事件、调度与解析规则及判定记录后，"
    "以零新增云端调用、节点Hamming距离为0、最终状态哈希和轨迹哈希完全一致作为精确回放判据；运行级统计可复现性针对不共享判定记录的独立运行分布，"
    "不要求逐节点完全相同，而以均值、离散程度、置信区间和节点状态差异刻画运行不确定性。经验有效性关注仿真与真实社会行为的一致程度，"
    "必须由真实传播数据或人类行为证据独立检验，不由前两个层次推出，本文亦不据此作经验有效性声明。"
)

EXPERIMENT_INTRO = (
    "实验设计与表1的分层复核目标相对应。4.2.1节首先检验零温度条件下结构化判定的质量与重复调用差异，为采用判定记录提供必要性证据；"
    "4.3节比较事件触发与全轮询的状态更新语义和LLM判定次数；4.4节实施核心的双层验证，其中无判定记录的K=5独立运行用于量化运行级不确定性，"
    "固定同一判定记录的3次回放用于检验记录级轨迹一致性；4.5—4.7节进一步考察后端与网络迁移边界，并以事实核查员部署说明分层复核对干预分析的作用。"
)

TABLE_ROWS = [
    ["复核层次", "评价对象与实验条件", "核心指标与判据", "本文证据与边界"],
    [
        "记录级轨迹可重放性",
        "一次既有运行的完整轨迹；固定拓扑、人设、初始事件、调度与解析规则及判定记录，回放不访问云端模型",
        "云端调用增量为0、节点Hamming=0，且final state hash和trace hash与seed完全一致",
        "4.4节3次回放exact match=3/3；仅保证既有轨迹的计算复核",
    ],
    [
        "运行级统计可复现性",
        "同一配置下独立运行的结果分布；每次从空判定记录开始且不共享Prompt/Response映射",
        "渗透率均值、标准差、置信区间、极差及成对Hamming；不要求轨迹完全相等",
        "4.2.1、4.4和4.6节；K=5用于揭示波动，不足以确证小效应",
    ],
    [
        "经验有效性（外部边界）",
        "仿真与真实社会行为的一致程度；须引入真实传播轨迹或人类行为数据",
        "校准误差、预测性能及外部效度；不能由精确回放或运行稳定性推出",
        "本文未建立；4.7节仅为公开拓扑上的探索性迁移",
    ],
]


def paragraph_text(paragraph: ET.Element) -> str:
    return "".join(node.text or "" for node in paragraph.iter(f"{W}t"))


def set_text(paragraph: ET.Element, text: str) -> None:
    properties = paragraph.find(f"{W}pPr")
    for child in list(paragraph):
        if child is not properties:
            paragraph.remove(child)
    run = ET.SubElement(paragraph, f"{W}r")
    text_node = ET.SubElement(run, f"{W}t")
    text_node.set(f"{{{XML_NS}}}space", "preserve")
    text_node.text = text


def styled_paragraph(template: ET.Element, text: str) -> ET.Element:
    paragraph = ET.Element(f"{W}p")
    properties = template.find(f"{W}pPr")
    if properties is not None:
        paragraph.append(deepcopy(properties))
    set_text(paragraph, text)
    return paragraph


def table_cell(text: str, width: int, header: bool = False) -> ET.Element:
    cell = ET.Element(f"{W}tc")
    cell_properties = ET.SubElement(cell, f"{W}tcPr")
    cell_width = ET.SubElement(cell_properties, f"{W}tcW")
    cell_width.set(f"{W}w", str(width))
    cell_width.set(f"{W}type", "dxa")
    vertical_align = ET.SubElement(cell_properties, f"{W}vAlign")
    vertical_align.set(f"{W}val", "center")
    if header:
        shading = ET.SubElement(cell_properties, f"{W}shd")
        shading.set(f"{W}fill", "D9EAF7")

    paragraph = ET.SubElement(cell, f"{W}p")
    p_properties = ET.SubElement(paragraph, f"{W}pPr")
    justification = ET.SubElement(p_properties, f"{W}jc")
    justification.set(f"{W}val", "center" if header else "left")
    run = ET.SubElement(paragraph, f"{W}r")
    r_properties = ET.SubElement(run, f"{W}rPr")
    fonts = ET.SubElement(r_properties, f"{W}rFonts")
    fonts.set(f"{W}ascii", "Times New Roman")
    fonts.set(f"{W}hAnsi", "Times New Roman")
    fonts.set(f"{W}eastAsia", "宋体")
    size = ET.SubElement(r_properties, f"{W}sz")
    size.set(f"{W}val", "14")
    size_cs = ET.SubElement(r_properties, f"{W}szCs")
    size_cs.set(f"{W}val", "14")
    if header:
        ET.SubElement(r_properties, f"{W}b")
    text_node = ET.SubElement(run, f"{W}t")
    text_node.text = text
    return cell


def review_table() -> ET.Element:
    widths = [700, 1300, 1350, 1050]
    table = ET.Element(f"{W}tbl")
    properties = ET.SubElement(table, f"{W}tblPr")
    table_width = ET.SubElement(properties, f"{W}tblW")
    table_width.set(f"{W}w", "4400")
    table_width.set(f"{W}type", "dxa")
    layout = ET.SubElement(properties, f"{W}tblLayout")
    layout.set(f"{W}type", "fixed")
    borders = ET.SubElement(properties, f"{W}tblBorders")
    for name in ("top", "left", "bottom", "right", "insideH", "insideV"):
        border = ET.SubElement(borders, f"{W}{name}")
        border.set(f"{W}val", "single")
        border.set(f"{W}sz", "4")
        border.set(f"{W}color", "808080")

    grid = ET.SubElement(table, f"{W}tblGrid")
    for width in widths:
        column = ET.SubElement(grid, f"{W}gridCol")
        column.set(f"{W}w", str(width))

    for row_index, values in enumerate(TABLE_ROWS):
        row = ET.SubElement(table, f"{W}tr")
        for value, width in zip(values, widths):
            row.append(table_cell(value, width, header=row_index == 0))
    return table


def main() -> None:
    with ZipFile(SOURCE, "r") as source_archive:
        root = ET.fromstring(source_archive.read("word/document.xml"))
        body = root.find(f"{W}body")
        paragraphs = list(root.iter(f"{W}p"))
        by_text = {paragraph_text(p): p for p in paragraphs if paragraph_text(p)}

        replacements = {
            CONTRIBUTION_3_OLD: CONTRIBUTION_3_NEW,
            "为解决云端LLM状态转移难以逐事件复核的问题，本文将LEDS定义为冻结有向图上的有限事件传播方法。其基本思想是：用有限状态空间约束模型输出，用类型化消息表示传播触发，用确定顺序调度控制事件执行，用新颖事件过滤限制重复传播，并将规范化Prompt与结构化判定保存为可索引记录。API调用、JSON解析和本地存储是上述机制的实现载体，而非独立研究目标。": METHOD_INTRO,
            "3.3 类型化事件、状态转移与确定调度": "3.3 类型化事件、确定顺序调度与新颖事件过滤",
            "实验围绕三个层次展开。首先检验零温度是否降低本文结构化状态转移任务的判定质量，并据此限定解码参数的证据范围；其次通过基线对照、独立运行与固定记录回放，验证事件驱动机制的评估开销、运行间差异和记录级一致性；最后在不同模型后端、合成网络和真实网络上观察方法适用性，并以事实核查员部署说明统计重复和逐事件审计对干预分析的作用。": EXPERIMENT_INTRO,
        }
        for old, new in replacements.items():
            if old not in by_text:
                raise RuntimeError(f"target paragraph not found: {old[:40]}")
            set_text(by_text[old], new)

        method_intro = by_text[next(key for key in replacements if key.startswith("为解决云端LLM"))]
        caption_cn_template = by_text["表1 LEDS与基线框架的实测性能对比（真实deepseek-chat，无标度网络）"]
        caption_en_template = by_text["Table 1 Measured performance of LEDS and baseline frameworks"]
        body_template = by_text["LEDS由静态初始化、离散事件演化和收敛评估3个阶段组成，如图1所示。三个阶段共享冻结拓扑、人设映射、状态枚举、消息类型和判定记录，从输入约束到结果审计形成闭环。"]
        insert_at = list(body).index(method_intro) + 1
        additions = [
            styled_paragraph(caption_cn_template, "表1 LEDS分层复核目标与评价准则"),
            styled_paragraph(caption_en_template, "Table 1 Layered verification objectives and evaluation criteria of LEDS"),
            review_table(),
            styled_paragraph(body_template, LAYER_PARAGRAPH),
        ]
        for offset, element in enumerate(additions):
            body.insert(insert_at + offset, element)

        bilingual_captions = [
            (
                by_text["补充表1 Temperature敏感性实验总体结果（DeepSeek-v4-flash，240个Prompt×4个温度×3次重复）。注：联合规则一致率要求stance和action均与规则参照一致；Prompt不一致率表示同一温度下同一Prompt三次调用中至少出现两种不同结构化输出的比例。"],
                "Table 2 Overall results of the temperature-sensitivity experiment",
            ),
            (
                by_text["补充表2 分人设联合规则一致率。注：每个温度下每类人设N=240。"],
                "Table 3 Joint rule consistency by persona",
            ),
        ]
        for chinese_caption, english_text in bilingual_captions:
            caption_at = list(body).index(chinese_caption) + 1
            body.insert(caption_at, styled_paragraph(caption_en_template, english_text))

        renumber_pairs = [
            ("27.0%（缓存重放可精确复现）", "27.0%（判定记录回放可精确复现）"),
            ("高（缓存重放）", "记录级可重放"),
            ("补充表1表明", "由表2可见"),
            ("补充表1 Temperature敏感性实验总体结果", "表2 Temperature敏感性实验总体结果"),
            ("分人设结果见补充表2", "分人设结果见表3"),
            ("补充表2 分人设联合规则一致率", "表3 分人设联合规则一致率"),
            ("表1 LEDS与基线框架", "表4 LEDS与基线框架"),
            ("Table 1 Measured performance", "Table 4 Measured performance"),
            ("表1从判定次数", "表4从判定次数"),
            ("表2 零温度运行间", "表5 零温度运行间"),
            ("Table 2 Run-to-run", "Table 5 Run-to-run"),
            ("图2和表2显示", "图2和表5显示"),
            ("表3 主实验", "表6 主实验"),
            ("Table 3 Comparison", "Table 6 Comparison"),
            ("表4的区间估计", "表7的区间估计"),
            ("表4 合成网络上", "表7 合成网络上"),
            ("Table 4 Topology", "Table 7 Topology"),
            ("表5 合成BA网络", "表8 合成BA网络"),
            ("Table 5 Intervention", "Table 8 Intervention"),
            ("表6从边缘部署", "表9从边缘部署"),
            ("表6 节点3", "表9 节点3"),
            ("Table 6 Auditable", "Table 9 Auditable"),
        ]
        for paragraph in root.iter(f"{W}p"):
            old_text = paragraph_text(paragraph)
            new_text = old_text
            for old, new in renumber_pairs:
                new_text = new_text.replace(old, new)
            if new_text != old_text:
                set_text(paragraph, new_text)

        updated_xml = ET.tostring(root, encoding="utf-8", xml_declaration=True)
        with ZipFile(OUTPUT, "w", compression=ZIP_DEFLATED) as output_archive:
            for entry in source_archive.infolist():
                payload = updated_xml if entry.filename == "word/document.xml" else source_archive.read(entry.filename)
                output_archive.writestr(entry, payload)
    print(f"output={OUTPUT}")


if __name__ == "__main__":
    main()
