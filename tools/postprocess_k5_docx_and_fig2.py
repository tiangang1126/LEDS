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
PAPER_IN = ROOT / "LEDS_指挥与控制学报_李铁乔_0725_投稿前修订稿_Algorithm1_Temperature_K5消融修订稿.docx"
PAPER_OUT = ROOT / "LEDS_指挥与控制学报_李铁乔_0725_投稿前修订稿_Algorithm1_Temperature_K5消融修订稿_图2更新版.docx"
FIG2 = ROOT / "figures" / "fig2_k5_determinism.png"


def para_text(p: ET.Element) -> str:
    return "".join(t.text or "" for t in p.findall(".//w:t", NS))


def set_para_text(p: ET.Element, text: str) -> None:
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


def replace_docx(src: Path, dst: Path) -> None:
    xml_name = "word/document.xml"
    with zipfile.ZipFile(src, "r") as zin:
        root = ET.fromstring(zin.read(xml_name))

        for p in root.findall(".//w:p", NS):
            text = para_text(p)
            if not text.strip():
                continue
            if text == "成对 Hamming 距离（10 对）":
                set_para_text(p, "成对 Hamming 距离摘要（详见补充表 S2）")
            elif text == "1.000% / 1.667% / 1.333% / 1.667% / 1.333% / 1.667% / 1.333% / 1.667% / 0.667% / 1.667%":
                set_para_text(p, "0.667%～1.667%")
            elif text == "Hamming 均值、样本标准差、最大值":
                set_para_text(p, "Hamming 均值、样本标准差、95% CI")
            elif text == "1.400%，0.344%，1.667%":
                set_para_text(p, "1.400%，0.344%，[1.154%，1.646%]")
            elif text.startswith("表 2 与图2 给出三点结论。第一，K=5 下最终渗透率区间较窄"):
                set_para_text(
                    p,
                    "表 2 与图2 给出三点结论。第一，K=5 下最终渗透率区间较窄，5次独立运行的渗透率为56.000%、56.333%、55.667%、56.000%和55.667%，均值为55.933%，样本标准差为0.279%，Student-t 95% CI为[55.587%,56.280%]，极差为0.667个百分点，说明在本后端与本结构化任务中零温度能够压低宏观波动。第二，宏观指标接近不等价于逐节点轨迹一致：5次运行的final state hash均不相同，10组成对Hamming距离的完整明细已移入补充表S2，其范围为0.667%～1.667%，均值为1.400%，Student-t 95% CI为[1.154%,1.646%]。第三，固定seed判定记录后，3次replay均未产生新增云端API调用，渗透率均为56.667%，稳态步数均为8，逐节点Hamming距离均为0，final state hash和trace hash均与seed完全一致，exact match为3/3。由此可见，Temperature=0只是控制显式采样扰动的实验条件，LEDS的记录级可重放性来自判定记录映射、确定顺序调度、新颖事件过滤和轨迹回放。"
                )

        new_xml = ET.tostring(root, encoding="utf-8", xml_declaration=True)
        with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zout:
            for info in zin.infolist():
                if info.filename == xml_name:
                    zout.writestr(info, new_xml)
                elif info.filename == "word/media/image2.png":
                    zout.writestr(info, FIG2.read_bytes())
                else:
                    zout.writestr(info, zin.read(info.filename))


def main() -> None:
    replace_docx(PAPER_IN, PAPER_OUT)
    print(PAPER_OUT)


if __name__ == "__main__":
    main()
