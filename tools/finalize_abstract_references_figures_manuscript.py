# -*- coding: utf-8 -*-
"""Finalize abstract statistics, references, and publication figures in DOCX.

The preceding temperature-statistics and API-identifier revisions are retained
by using their latest DOCX as the source. Only explicitly targeted paragraphs,
five media files, and the corresponding drawing extents are changed.
"""
from __future__ import annotations

import copy
import io
import zipfile
from pathlib import Path, PurePosixPath
from xml.etree import ElementTree as ET

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "LEDS_指挥与控制学报_API服务标识与推理模式修订_投稿完善稿_2026-07-29.docx"
OUTPUT = ROOT / "LEDS_指挥与控制学报_摘要参考文献与图像终审修订_投稿完善稿_2026-07-29.docx"

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"
WP = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PR = "http://schemas.openxmlformats.org/package/2006/relationships"
NS = {"w": W, "a": A, "wp": WP, "r": R, "pr": PR}
XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"
EMU_PER_INCH = 914400

for prefix, uri in (("w", W), ("a", A), ("wp", WP), ("r", R)):
    ET.register_namespace(prefix, uri)


CHINESE_ABSTRACT = (
    "针对云端LLM社会信息传播仿真难以逐事件复核的问题，提出可重放事件驱动方法LEDS。"
    "该方法以冻结拓扑、确定顺序调度、新颖事件过滤和判定记录映射约束传播过程。"
    "实验显示，T=0时仍有6.67%的Prompt出现重复调用不一致；5次独立运行的最终状态哈希均不同，"
    "而固定判定记录的3次回放节点Hamming距离为0，状态与轨迹哈希完全一致；同场景LLM判定次数由2400次降至701次。"
    "Facebook公开拓扑的K=5探索性实验中，随机、边缘和中心部署的平均渗透率分别为13.47%、20.06%和0，"
    "95%置信区间分别为[13.02%,13.93%]、[12.06%,28.06%]和[0,0]；区间重叠表明现有小样本不足以支持边缘部署稳定优于随机部署。"
    "结果表明，LEDS能够实现逐事件审计和精确回放，并区分记录级可重放性与运行级统计可复现性。"
)

ENGLISH_ABSTRACT = (
    "LEDS, a replayable event-driven method, is developed for cloud-LLM social diffusion simulations that are difficult to verify event by event. "
    "It constrains diffusion through a frozen topology, deterministic ordered scheduling, novelty filtering, and decision-record mapping. "
    "At T=0, 6.67% of prompts still yield inconsistent repeated outputs. Five independent runs produce different final-state hashes, whereas three fixed-record replays make no cloud calls, yield zero node-level Hamming distance, and reproduce final-state and trace hashes exactly. "
    "LLM evaluations decrease from 2,400 to 701 in the same scenario. In the exploratory K=5 experiment on the public Facebook topology, mean penetration rates under random, peripheral, and central deployment are 13.47%, 20.06%, and 0, with 95% confidence intervals of [13.02%, 13.93%], [12.06%, 28.06%], and [0, 0], respectively. "
    "The overlapping intervals do not support a stable advantage of peripheral over random deployment at the current sample size. "
    "LEDS therefore enables event-level auditing and exact replay while separating record-level replayability from run-level statistical reproducibility."
)


REFERENCES = {
    1: "1 CENTOLA D. The spread of behavior in an online social network experiment[J]. Science, 2010, 329(5996): 1194-1197. DOI:10.1126/science.1185231.",
    5: "5 PARK J S, O'BRIEN J C, CAI C J, et al. Generative agents: interactive simulacra of human behavior[C]//Proceedings of the 36th Annual ACM Symposium on User Interface Software and Technology. New York: ACM, 2023: 1-22. DOI:10.1145/3586183.3606763.",
    9: "9 QU Y, WANG J. Performance and biases of large language models in public opinion simulation[J]. Humanities and Social Sciences Communications, 2024, 11(1): 1095. DOI:10.1057/s41599-024-03609-x.",
    11: "11 LAROOIJ M, TÖRNBERG P. Validation is the central challenge for generative social simulation: a critical review of LLMs in agent-based modeling[J]. Artificial Intelligence Review, 2026, 59: 15. DOI:10.1007/s10462-025-11412-6.",
    12: "12 WATTS D J, STROGATZ S H. Collective dynamics of 'small-world' networks[J]. Nature, 1998, 393(6684): 440-442. DOI:10.1038/30918.",
    13: "13 BARABÁSI A L, ALBERT R. Emergence of scaling in random networks[J]. Science, 1999, 286(5439): 509-512. DOI:10.1126/science.286.5439.509.",
    14: "14 VOSOUGHI S, ROY D, ARAL S. The spread of true and false news online[J]. Science, 2018, 359(6380): 1146-1151. DOI:10.1126/science.aap9559.",
    15: "15 KEMPE D, KLEINBERG J, TARDOS É. Maximizing the spread of influence through a social network[C]//Proceedings of the Ninth ACM SIGKDD International Conference on Knowledge Discovery and Data Mining. New York: ACM, 2003: 137-146. DOI:10.1145/956750.956769.",
    16: "16 ZHAO W X, ZHOU K, LI J, et al. A survey of large language models[J]. Frontiers of Computer Science, 2026, 20: 2012627. DOI:10.1007/s11704-026-60308-3.",
}


FIGURES = {
    "image2.png": ROOT / "figures" / "fig2_k5_determinism.png",
    "image3.png": ROOT / "figures" / "fig3_topology_publication.png",
    "image4.png": ROOT / "figures" / "fig4_intervention_publication.png",
    "image5.png": ROOT / "figures" / "fig5_facebook_k5.png",
    "image6.png": ROOT / "figures" / "figC1_scalability_publication.png",
}


def qn(namespace: str, tag: str) -> str:
    return f"{{{namespace}}}{tag}"


def paragraph_text(paragraph: ET.Element) -> str:
    return "".join(node.text or "" for node in paragraph.findall(".//w:t", NS)).strip()


def replace_abstract_body(paragraph: ET.Element, prefix: str, body: str) -> None:
    nodes = paragraph.findall(".//w:t", NS)
    if not nodes or not paragraph_text(paragraph).startswith(prefix):
        raise RuntimeError(f"Abstract prefix not found: {prefix}")
    body_index = next(
        (index for index, node in enumerate(nodes) if (node.text or "").strip() and not (node.text or "").strip().startswith(prefix)),
        None,
    )
    if body_index is None:
        raise RuntimeError(f"Abstract body node not found: {prefix}")
    nodes[body_index].set(XML_SPACE, "preserve")
    nodes[body_index].text = body
    for node in nodes[body_index + 1 :]:
        node.text = ""


def set_paragraph_text(paragraph: ET.Element, value: str) -> None:
    ppr = paragraph.find("w:pPr", NS)
    ppr_copy = copy.deepcopy(ppr) if ppr is not None else None
    rpr = paragraph.find("w:r/w:rPr", NS)
    rpr_copy = copy.deepcopy(rpr) if rpr is not None else None
    paragraph.clear()
    if ppr_copy is not None:
        paragraph.append(ppr_copy)
    run = ET.SubElement(paragraph, qn(W, "r"))
    if rpr_copy is not None:
        run.append(rpr_copy)
    text_node = ET.SubElement(run, qn(W, "t"))
    text_node.set(XML_SPACE, "preserve")
    text_node.text = value


def patch_text(root: ET.Element) -> None:
    paragraphs = root.findall(".//w:body/w:p", NS)
    chinese = [p for p in paragraphs if paragraph_text(p).startswith("摘  要")]
    english = [p for p in paragraphs if paragraph_text(p).startswith("Abstract")]
    if len(chinese) != 1 or len(english) != 1:
        raise RuntimeError(f"Unexpected abstract counts: Chinese={len(chinese)}, English={len(english)}")
    replace_abstract_body(chinese[0], "摘  要", CHINESE_ABSTRACT)
    replace_abstract_body(english[0], "Abstract", ENGLISH_ABSTRACT)

    reference_heading = next(
        (index for index, paragraph in enumerate(paragraphs) if paragraph_text(paragraph) == "References"),
        None,
    )
    appendix_heading = next(
        (
            index
            for index, paragraph in enumerate(paragraphs)
            if paragraph_text(paragraph).startswith("附录 A")
        ),
        None,
    )
    if reference_heading is None or appendix_heading is None or reference_heading >= appendix_heading:
        raise RuntimeError("Could not delimit the reference-list section")

    reference_counts = {number: 0 for number in REFERENCES}
    for paragraph in paragraphs[reference_heading + 1 : appendix_heading]:
        current = paragraph_text(paragraph)
        for number, replacement in REFERENCES.items():
            if current.startswith(f"{number} "):
                set_paragraph_text(paragraph, replacement)
                reference_counts[number] += 1
                break
    if any(count != 1 for count in reference_counts.values()):
        raise RuntimeError(f"Unexpected reference match counts: {reference_counts}")


def relationship_map(archive: zipfile.ZipFile) -> dict[str, str]:
    root = ET.fromstring(archive.read("word/_rels/document.xml.rels"))
    return {
        item.get("Id", ""): item.get("Target", "")
        for item in root.findall("pr:Relationship", NS)
    }


def patch_drawing_extents(root: ET.Element, rels: dict[str, str], image_bytes: dict[str, bytes]) -> dict[str, int]:
    counts = {name: 0 for name in FIGURES}
    width_emu = 3 * EMU_PER_INCH
    for drawing in root.findall(".//w:drawing", NS):
        blip = drawing.find(".//a:blip", NS)
        if blip is None:
            continue
        rid = blip.get(qn(R, "embed"), "")
        media_name = PurePosixPath(rels.get(rid, "")).name
        if media_name not in FIGURES:
            continue
        with Image.open(io.BytesIO(image_bytes[media_name])) as image:
            px_w, px_h = image.size
        height_emu = round(width_emu * px_h / px_w)
        wp_extent = drawing.find(".//wp:extent", NS)
        if wp_extent is None:
            raise RuntimeError(f"wp:extent missing for {media_name}")
        wp_extent.set("cx", str(width_emu))
        wp_extent.set("cy", str(height_emu))
        for a_extent in drawing.findall(".//a:xfrm/a:ext", NS):
            a_extent.set("cx", str(width_emu))
            a_extent.set("cy", str(height_emu))
        counts[media_name] += 1
    if any(count != 1 for count in counts.values()):
        raise RuntimeError(f"Unexpected drawing match counts: {counts}")
    return counts


def write_output() -> None:
    if not SOURCE.exists():
        raise FileNotFoundError(SOURCE)
    for path in FIGURES.values():
        if not path.exists():
            raise FileNotFoundError(path)
    image_bytes = {name: path.read_bytes() for name, path in FIGURES.items()}

    with zipfile.ZipFile(SOURCE, "r") as archive:
        document_root = ET.fromstring(archive.read("word/document.xml"))
        patch_text(document_root)
        extents = patch_drawing_extents(document_root, relationship_map(archive), image_bytes)
        patched_xml = ET.tostring(document_root, encoding="utf-8", xml_declaration=True)

        with zipfile.ZipFile(OUTPUT, "w", zipfile.ZIP_DEFLATED) as destination:
            for item in archive.infolist():
                data = archive.read(item.filename)
                if item.filename == "word/document.xml":
                    data = patched_xml
                elif item.filename.startswith("word/media/"):
                    media_name = PurePosixPath(item.filename).name
                    if media_name in image_bytes:
                        data = image_bytes[media_name]
                destination.writestr(item, data)

    print(f"wrote: {OUTPUT}")
    print(f"updated drawings: {extents}")


if __name__ == "__main__":
    write_output()
