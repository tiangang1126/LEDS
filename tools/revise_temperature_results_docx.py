# -*- coding: utf-8 -*-
"""Patch LEDS DOCX files with completed temperature ablation results.

The script edits Word OpenXML directly to avoid adding runtime dependencies.
It creates new DOCX files and leaves source manuscripts unchanged.
"""
from __future__ import annotations

import copy
import os
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS = {"w": W}
ET.register_namespace("w", W)


ROOT = Path(__file__).resolve().parents[1]
SRC_MANUSCRIPT = ROOT / "LEDS_指挥与控制学报_李铁乔_0725_投稿前修订稿_Algorithm1完整版.docx"
OUT_MANUSCRIPT = ROOT / "LEDS_指挥与控制学报_李铁乔_0725_投稿前修订稿_Algorithm1_Temperature消融修订稿.docx"
SRC_RESPONSE = ROOT / "专家一的意见与回复.docx"
OUT_RESPONSE = ROOT / "专家一的意见与回复_Temperature消融实验证据版.docx"


def qn(tag: str) -> str:
    return f"{{{W}}}{tag}"


def para_text(p: ET.Element) -> str:
    return "".join(t.text or "" for t in p.findall(".//w:t", NS)).strip()


def make_para(text: str, style: str | None = None, bold: bool = False) -> ET.Element:
    p = ET.Element(qn("p"))
    if style:
        ppr = ET.SubElement(p, qn("pPr"))
        ps = ET.SubElement(ppr, qn("pStyle"))
        ps.set(qn("val"), style)
    r = ET.SubElement(p, qn("r"))
    if bold:
        rpr = ET.SubElement(r, qn("rPr"))
        ET.SubElement(rpr, qn("b"))
    t = ET.SubElement(r, qn("t"))
    t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    t.text = text
    return p


def set_para_text(p: ET.Element, text: str) -> None:
    ppr = copy.deepcopy(p.find("w:pPr", NS)) if p.find("w:pPr", NS) is not None else None
    p.clear()
    if ppr is not None:
        p.append(ppr)
    r = ET.SubElement(p, qn("r"))
    t = ET.SubElement(r, qn("t"))
    t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    t.text = text


def make_cell(text: str, bold: bool = False) -> ET.Element:
    tc = ET.Element(qn("tc"))
    p = make_para(text, bold=bold)
    tc.append(p)
    return tc


def make_table(headers: list[str], rows: list[list[str]]) -> ET.Element:
    tbl = ET.Element(qn("tbl"))
    tbl_pr = ET.SubElement(tbl, qn("tblPr"))
    borders = ET.SubElement(tbl_pr, qn("tblBorders"))
    for name in ("top", "left", "bottom", "right", "insideH", "insideV"):
        border = ET.SubElement(borders, qn(name))
        border.set(qn("val"), "single")
        border.set(qn("sz"), "4")
        border.set(qn("space"), "0")
        border.set(qn("color"), "auto")
    header_tr = ET.SubElement(tbl, qn("tr"))
    for h in headers:
        header_tr.append(make_cell(h, bold=True))
    for row in rows:
        tr = ET.SubElement(tbl, qn("tr"))
        for cell in row:
            tr.append(make_cell(cell))
    return tbl


def patch_docx(src: Path, dst: Path, patcher) -> None:
    with zipfile.ZipFile(src, "r") as zin:
        document_xml = zin.read("word/document.xml")
        root = ET.fromstring(document_xml)
        patcher(root)
        new_xml = ET.tostring(root, encoding="utf-8", xml_declaration=True)
        with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                data = zin.read(item.filename)
                if item.filename == "word/document.xml":
                    data = new_xml
                zout.writestr(item, data)


def insert_after(body: ET.Element, target: ET.Element, elements: list[ET.Element]) -> None:
    children = list(body)
    idx = children.index(target)
    for offset, element in enumerate(elements, 1):
        body.insert(idx + offset, element)


def patch_manuscript(root: ET.Element) -> None:
    body = root.find("w:body", NS)
    assert body is not None
    paras = body.findall(".//w:p", NS)

    for p in paras:
        text = para_text(p)
        if text.startswith("摘  要"):
            set_para_text(
                p,
                "摘  要  针对云端LLM社会仿真难以复核的问题，提出可重放事件驱动协议LEDS。该协议将传播建模为有限类型化事件转移过程，采用固定调度、新颖事件过滤和判定记录映射实现轨迹回放。补充Temperature敏感性实验在240个分层Prompt、4个温度和3次重复下获得2880条真实DeepSeek API输出，JSON合法率均为100%，不同温度下联合规则一致率稳定在66.81%～67.36%；同时零温度条件下仍有6.67%的Prompt出现三次调用不一致。主实验进一步显示，零温度独立运行仍有4.7个百分点渗透率极差和最高21.0%节点状态差异，记录回放Hamming距离为0；事件驱动将判定次数由2400次降至701次。结果表明，LLM社会仿真需区分记录级可重放性、统计可复现性与经验有效性。"
            )
        elif text.startswith("Abstract  A replayable event-driven protocol"):
            set_para_text(
                p,
                "Abstract  A replayable event-driven protocol, LEDS, is proposed for auditable cloud-LLM social simulation. LEDS models diffusion as finite typed events, combines ordered scheduling, novelty filtering, and decision-record mapping, and separates replayability from run-level statistical reproducibility. A supplementary temperature-sensitivity ablation over 240 stratified prompts, four temperatures, and three repeats obtains 2,880 real DeepSeek API outputs. All conditions achieve 100% valid JSON, and joint rule accuracy remains close across temperatures (66.81%-67.36%), while T=0 still shows prompt-level disagreement in 6.67% of prompts. Main experiments further show that zero-temperature independent runs still diverge by 4.7 percentage points in penetration and up to 21.0% in node-state Hamming distance, whereas replay with fixed decision records yields zero Hamming distance. These results indicate that LLM social simulation should report record-level replayability, run-level statistical reproducibility, and empirical validity separately."
            )
        elif text.startswith("Temperature=0 是控制显式采样噪声的实验条件"):
            set_para_text(
                p,
                "Temperature=0 是控制显式采样噪声的实验条件，而不是 LEDS 实现可重放性的充分条件。本文研究的是结构化状态转移任务，并不以开放式文本多样性为优化目标；因此，零温度设置的作用是减少显式采样扰动并提高结构化输出合法性。针对“Temperature=0 会不会影响 LLM 效果”的疑问，本文新增受控温度敏感性实验（见 4.2.1 节）：在相同 Prompt 集合、相同人设规则、相同 JSON Schema、相同 Top_P=1.0 和相同 DeepSeek API 后端下，仅改变 Temperature∈{0,0.2,0.5,0.7}。结果显示，各温度下 JSON 合法率均为100%，联合规则一致率稳定在66.81%～67.36%，未观察到 T=0 相比更高温度的规则执行质量下降。但 T=0 条件下仍有6.67%的 Prompt 在三次独立调用中出现不同判定，说明零温度不能被等同为物理级确定性，LEDS 的可重放性仍必须由判定记录映射和轨迹回放机制保证。"
            )
        elif text.startswith("本章围绕两个板块共六个实验展开"):
            set_para_text(
                p,
                "本章围绕一个补充敏感性检验和两个主体实验板块展开。首先，4.2.1 节以固定 Prompt 池直接检验 Temperature=0 是否削弱结构化状态转移判定质量，以回应零温度设置可能影响 LLM 效果的疑问。随后，板块一：可复现性评估（4.3 至 4.5 节）直接检验本文的核心命题，即可复现性须由协议在实验层面保证：实验一（成本与方差基线，4.3 节）量化 LEDS 相对蒙特卡洛方案的方差与效率优势，实验二（运行间非确定性与缓存重放探针，4.4 节）给出可复现性须由重放保证的直接证据，实验三（跨 LLM 后端鲁棒性，4.5 节）检验该命题不依赖单一模型。板块二：应用验证（4.6 至 4.8 节）在可复现协议之上评估真实治理问题，并以事实核查员空间部署作为应用案例。"
            )
        elif text.startswith("本文提出面向社会信息传播的可重放事件驱动仿真协议 LEDS"):
            set_para_text(
                p,
                "本文提出面向社会信息传播的可重放事件驱动仿真协议 LEDS。围绕专家关切的 Temperature 设置问题，补充实验表明，在受约束的结构化状态转移任务中，T=0、0.2、0.5、0.7 四个条件下 DeepSeek API 输出的 JSON 合法率均为100%，联合规则一致率分别为67.22%、67.36%、66.81%和67.08%，未观察到零温度导致任务判定质量下降；但即使在 T=0 条件下，仍有6.67%的 Prompt 在三次独立调用中产生不同判定。因此，本文的核心结论不是“零温度能够保证确定性”，而是相反：在相同冻结配置和零温度条件下，云端 LLM 的无缓存独立运行仍会出现明显发散，最终渗透率极差为4.7个百分点，逐节点状态差异最高达21.0%；只有固定 Prompt/Response 判定记录后的回放，才能实现逐节点完全一致。因此，LLM 社会仿真的可信性应同时报告记录级可重放性、运行级统计可复现性与经验有效性。事件驱动机制将判定次数由2,400次降至701次，并在不同规模下实现2.5～4.8倍的评估次数削减。"
            )
        elif text.startswith("在未配置 API Key 时"):
            set_para_text(
                p,
                "在未配置 API Key 时，src/stage2_engine.py 的 _mock_decide 以纯 if/else 规则复现上述三类人设的判定逻辑：易感者收到谣言即 Accept/Share、收到辟谣即纠偏；中立者需 ≥4 个不同邻居的谣言才转变；核查员恒 Reject 且收到谣言即 Debunk。其输入输出签名与真实 LLM 判别器完全一致，供离线链路验证之用。本文正文报告的主仿真实证数据由真实 LLM（deepseek-chat，Temperature=0 或表中注明条件）产生；针对专家意见新增的 Temperature 敏感性实验使用公共 DeepSeek API 当前支持的 deepseek-v4-flash 后端，在同一 Prompt 池上获得2880条真实 API 输出。mock 数据仅用于链路校验，不进入正文统计结论。"
            )

    # Insert supplement after paragraph 4.2 setup paragraph.
    paras = body.findall(".//w:p", NS)
    target = None
    for p in paras:
        if para_text(p).startswith("设定传播信息为虚拟科学预警"):
            target = p
            break
    assert target is not None

    section_elements: list[ET.Element] = [
        make_para("4.2.1 补充实验：Temperature敏感性与结构化判定质量", bold=True),
        make_para("为直接回应“Temperature=0 会不会影响 LLM 效果”的问题，本文在完整网络仿真之外构造受控 Prompt 级温度消融实验。实验固定 System Prompt、User Prompt 模板、三类人设规则、输出 JSON Schema、Top_P=1.0、解析规则和模型后端，仅改变 Temperature。Prompt 池共240条，按易感者、中立者和核查员三类人设各80条分层构造，覆盖当前信念状态、谣言来源数、辟谣来源数和新增消息类型等主要状态转移边界。每个 Prompt 在 Temperature∈{0,0.2,0.5,0.7} 下独立调用3次，共获得2880条真实 DeepSeek API 输出。规则参照由附录A中的三类人设状态转移规则生成，评价指标包括联合规则一致率、stance一致率、action一致率、JSON合法率和同一Prompt三次重复的输出不一致率。"),
        make_para("补充表1给出总体温度消融结果。四个温度下 JSON 合法率均为100%，说明在本文的受约束状态转移任务中，结构化输出约束能够稳定发挥作用。联合规则一致率分别为67.22%、67.36%、66.81%和67.08%，点估计差异小于0.6个百分点；以T=0为基准的差值置信区间分别为T=0.2的[-4.71,4.99]、T=0.5的[-5.27,4.44]和T=0.7的[-4.99,4.71]个百分点。由于置信区间下界未完全落在-3个百分点非劣效界限之上，本文不作严格非劣效断言；但描述性结果未显示T=0相对于更高温度存在规则执行质量下降。"),
        make_table(
            ["Temperature", "N", "联合规则一致率", "95% Wilson CI", "Stance一致率", "Action一致率", "JSON合法率", "Prompt不一致率"],
            [
                ["0.0", "720", "67.22%", "[63.71, 70.55]", "73.89%", "81.81%", "100.00%", "6.67%"],
                ["0.2", "720", "67.36%", "[63.85, 70.69]", "74.03%", "81.81%", "100.00%", "6.25%"],
                ["0.5", "720", "66.81%", "[63.28, 70.15]", "73.19%", "81.25%", "100.00%", "7.08%"],
                ["0.7", "720", "67.08%", "[63.57, 70.42]", "73.61%", "81.53%", "100.00%", "7.50%"],
            ],
        ),
        make_para("补充表1 Temperature敏感性实验总体结果（DeepSeek-v4-flash，240个Prompt×4个温度×3次重复）。注：联合规则一致率要求stance和action均与规则参照一致；Prompt不一致率表示同一温度下同一Prompt三次调用中至少出现两种不同结构化输出的比例。"),
        make_para("分人设结果进一步表明，核查员人设在四个温度下 stance 一致率均为100%，联合规则一致率约80%；易感者和中立者的联合规则一致率约60%～62%。主要错误模式并非随机格式错误，而是语义判定偏保守：模型常将 Neutral/Ignore 判为 Reject/Ignore，或将 Accept/Share 判为 Reject/Ignore，也会把部分 Reject/Ignore 升级为 Reject/Debunk。这说明 LLM 不是规则 oracle 的无偏替代品，尤其在健康风险谣言场景中会呈现反谣言方向的保守化倾向。LEDS 的意义正在于把这种偏差通过结构化输出、判定记录和回放机制显性化、可度量化，而不是假设 LLM 自身完全确定或完全无偏。"),
        make_table(
            ["Temperature", "Fact Checker", "Neutral", "Susceptible"],
            [
                ["0.0", "80.00%", "61.67%", "60.00%"],
                ["0.2", "80.00%", "62.08%", "60.00%"],
                ["0.5", "80.83%", "60.00%", "59.58%"],
                ["0.7", "80.42%", "61.25%", "59.58%"],
            ],
        ),
        make_para("补充表2 分人设联合规则一致率。注：每个温度下每类人设N=240。"),
        make_para("该补充实验对本文结论形成两点修正。第一，对于本文的结构化状态转移任务，未观察到T=0相较T=0.2、0.5和0.7造成判定质量劣化；因此，主实验使用T=0作为控制显式采样噪声的条件是合理的。第二，T=0并不意味着云端 LLM 输出完全确定：在240个Prompt中仍有16个在三次独立调用中出现不同结构化判定，不一致率为6.67%。因此，LEDS 的可复现性不能建立在“零温度即确定”的假设上，而必须建立在固定判定记录、确定顺序调度、新颖事件过滤和轨迹回放之上。")
    ]
    insert_after(body, target, section_elements)


def patch_response(root: ET.Element) -> None:
    body = root.find("w:body", NS)
    assert body is not None
    last_para = None
    for child in list(body):
        if child.tag == qn("p"):
            last_para = child
    assert last_para is not None
    additions = [
        make_para("七、基于已完成真实API温度消融实验的定稿回复", bold=True),
        make_para("针对专家一提出的“Temperature=0 会不会影响 LLM 效果”问题，我们已完成真实 DeepSeek API 补充实验，并据此修订正文 3.4 节和新增 4.2.1 节。实验不再停留在方案建议层面，而是在固定 Prompt 池上直接检验不同温度下的结构化判定质量。"),
        make_para("实验设置为：构造240个分层Prompt，覆盖易感者、中立者和核查员三类人设各80条，并覆盖当前信念、谣言来源数、辟谣来源数和新增消息类型等主要状态转移边界；在Temperature=0、0.2、0.5、0.7四个条件下，每个Prompt独立调用3次，共获得2880条真实 DeepSeek API 输出。除Temperature外，System Prompt、User Prompt模板、人设规则、JSON Schema、Top_P=1.0、解析规则和后端均保持一致。正式统计文件已清理为2880条成功记录，API错误和mock链路验证文件均归档，不进入正文统计。"),
        make_table(
            ["Temperature", "N", "联合规则一致率", "95% Wilson CI", "Stance一致率", "Action一致率", "JSON合法率", "Prompt不一致率"],
            [
                ["0.0", "720", "67.22%", "[63.71, 70.55]", "73.89%", "81.81%", "100.00%", "6.67%"],
                ["0.2", "720", "67.36%", "[63.85, 70.69]", "74.03%", "81.81%", "100.00%", "6.25%"],
                ["0.5", "720", "66.81%", "[63.28, 70.15]", "73.19%", "81.25%", "100.00%", "7.08%"],
                ["0.7", "720", "67.08%", "[63.57, 70.42]", "73.61%", "81.53%", "100.00%", "7.50%"],
            ],
        ),
        make_para("实验结果表明，四个温度下 JSON 合法率均为100%，联合规则一致率稳定在66.81%～67.36%之间。以T=0为基准，T=0.2、T=0.5、T=0.7的联合规则一致率点估计差异分别为+0.14、-0.42和-0.14个百分点，未观察到T=0相较更高温度造成结构化任务判定质量下降。严格统计上，由于差值置信区间下界低于-3个百分点，修订稿不作“严格非劣效已证明”的过度断言，而采用更审慎表述：描述性结果未显示零温度削弱本文任务中的规则执行质量。"),
        make_para("同时，实验也支持专家意见背后的核心担忧：T=0不能被写成“保证确定性”。在T=0条件下，240个Prompt中仍有16个在三次独立调用中出现不同结构化输出，不一致率为6.67%。因此，修订稿明确删除“零温度保证确定性”或“受实验成本限制尚未检验”的表述，改为：Temperature=0只是控制显式采样噪声的实验条件，LEDS的可重放性由判定记录映射、确定顺序调度、新颖事件过滤和轨迹回放共同保证。"),
        make_para("据此，可用于回复专家一的最终文字为：感谢专家指出Temperature设置可能影响LLM任务效果的问题。我们已新增受控温度敏感性实验，在240个分层Prompt、4个Temperature条件和3次重复下获得2880条真实DeepSeek API输出。结果显示，各温度下JSON合法率均为100%，T=0、0.2、0.5、0.7的联合规则一致率分别为67.22%、67.36%、66.81%和67.08%，未观察到T=0相较更高温度造成结构化状态转移任务质量下降。同时，T=0下仍有6.67%的Prompt在三次独立调用中出现不同判定，说明零温度不能等同于完全确定性。修订稿据此将Temperature=0解释为控制显式采样噪声的实验条件，而非可重放性的充分条件，并进一步强调LEDS通过判定记录映射和轨迹回放保证记录级可重放。")
    ]
    insert_after(body, last_para, additions)


def main() -> None:
    if not SRC_MANUSCRIPT.exists():
        raise FileNotFoundError(SRC_MANUSCRIPT)
    if not SRC_RESPONSE.exists():
        raise FileNotFoundError(SRC_RESPONSE)
    patch_docx(SRC_MANUSCRIPT, OUT_MANUSCRIPT, patch_manuscript)
    patch_docx(SRC_RESPONSE, OUT_RESPONSE, patch_response)
    print(f"wrote {OUT_MANUSCRIPT}")
    print(f"wrote {OUT_RESPONSE}")


if __name__ == "__main__":
    main()
