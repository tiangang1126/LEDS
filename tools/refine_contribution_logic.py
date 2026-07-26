from copy import deepcopy
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZIP_DEFLATED, ZipFile


WORD_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
XML_NS = "http://www.w3.org/XML/1998/namespace"
W = f"{{{WORD_NS}}}"

SOURCE = Path("LEDS_指挥与控制学报_李铁乔_0725_科学论文范式全文重写稿.docx")
OUTPUT = Path("LEDS_指挥与控制学报_李铁乔_0725_科学论文范式全文重写稿_贡献逻辑优化版.docx")

LEAD = "围绕云端LLM驱动社会仿真难以稳定复核的问题，本文的主要贡献如下。"

CONTRIBUTIONS = [
    "（1）提出LLM社交智能体仿真的分层复核框架与可重放事件建模方法。将社会信息传播形式化为有限状态、有限消息类型上的事件转移过程，明确区分无判定记录独立运行条件下的运行级统计可复现性与固定判定记录条件下的记录级轨迹可重放性，并将面向真实社会行为的经验有效性界定为需要独立证据支持的外部层次，为LLM社会仿真实验的复核边界提供统一描述。",
    "（2）提出融合确定顺序调度与新颖事件过滤的LEDS传播算法。算法仅调度接收到新增消息的活跃节点，并对“发送节点—接收节点—消息类型”三元事件实施至多一次的传播约束；结合固定节点顺序、结构化状态转移和Prompt/Response判定记录，实现传播过程的逐事件审计，并给出记录条件下的轨迹唯一性、有限事件终止性与事件复杂度上界。",
    "（3）构建面向运行不确定性与记录回放一致性的分层实验验证方案。通过无判定记录独立运行量化宏观渗透率与微观节点状态的运行间差异，通过固定判定记录回放检验逐节点状态与完整轨迹的一致性，并结合温度敏感性、不同LLM后端、合成网络和真实社交网络实验考察方法的适用边界。事实核查员空间部署作为应用案例，用于说明忽略运行间不确定性可能导致不稳健的干预结论。",
]


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


def main() -> None:
    with ZipFile(SOURCE, "r") as source_archive:
        root = ET.fromstring(source_archive.read("word/document.xml"))
        body = root.find(f"{W}body")
        paragraphs = [child for child in body if child.tag == f"{W}p"]
        target = paragraphs[21]
        set_text(target, LEAD)
        position = list(body).index(target) + 1
        for offset, contribution in enumerate(CONTRIBUTIONS):
            body.insert(position + offset, styled_paragraph(target, contribution))
        updated_xml = ET.tostring(root, encoding="utf-8", xml_declaration=True)

        with ZipFile(OUTPUT, "w", compression=ZIP_DEFLATED) as output_archive:
            for entry in source_archive.infolist():
                payload = updated_xml if entry.filename == "word/document.xml" else source_archive.read(entry.filename)
                output_archive.writestr(entry, payload)
    print(f"output={OUTPUT}")


if __name__ == "__main__":
    main()
