# -*- coding: utf-8 -*-
"""
Restore the complete Algorithm 1 pseudocode in the revised LEDS manuscript.

The script edits DOCX OpenXML directly because python-docx is not guaranteed to
be installed in the local environment. It keeps the source manuscript untouched
and writes a new DOCX file.
"""
import shutil
import zipfile
from pathlib import Path

from lxml import etree


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "LEDS_指挥与控制学报_李铁乔_0725_投稿前修订稿.docx"
OUT = ROOT / "LEDS_指挥与控制学报_李铁乔_0725_投稿前修订稿_Algorithm1完整版.docx"
WORK = ROOT / "_docx_algorithm_work"

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS = {"w": W_NS}


ALGORITHM_TITLE = "Algorithm 1: LEDS 可重放事件驱动信息传播算法"

ALGORITHM_LINES = [
    "Input: 冻结有向图 G=(V,E)；节点人设映射 P；初始源节点 v_src；初始消息 m_init；最大时间步 T_max；受约束 LLM 判定算子 F_θ；判定记录映射 C（首次运行可为空）。",
    "Output: 终止或截断时的全网状态 S_T、最终渗透率 ρ_T、逐步状态机日志 L。",
    "1:  对所有节点 v_i∈V 初始化信念 b_i←Neutral，累计谣言暴露 r_i←0，累计辟谣暴露 d_i←0。",
    "2:  初始化事件访问标记 ν(u,v,m)←0，其中 (u,v)∈E，m∈{RUMOR,DEBUNK}。",
    "3:  初始化活跃事件队列 Q_0[v_src]←{(-1,v_src,m_init)}，日志 L←∅，时间步 t←0。",
    "4:  while Q_t 非空且 t<T_max do",
    "5:      Q_{t+1}←∅，A_t←{v_i | Q_t[v_i] 非空}。",
    "6:      按全局节点编号升序遍历 v_i∈sort(A_t)。",
    "7:      for each v_i in sort(A_t) do",
    "8:          读取本轮新增消息集合 M_i^t←Q_t[v_i]，并更新暴露计数 r_i、d_i。",
    "9:          构造规范化 Prompt p_i^t←ConstructPrompt(P_i,b_i,r_i,d_i,M_i^t)。",
    "10:         计算哈希 h_i^t←H(p_i^t)。",
    "11:         if h_i^t∈C then",
    "12:             y_i^t←C[h_i^t]。  // 记录回放，不再访问云端模型",
    "13:         else",
    "14:             y_i^t←F_θ(p_i^t; Temperature=0, Top_P=1)。",
    "15:             C[h_i^t]←y_i^t。  // 首次判定写入记录映射",
    "16:         end if",
    "17:         解析 y_i^t 得到 (b_i',a_i^t)，其中 b_i'∈{Accept,Reject,Neutral}，a_i^t∈{Share,Ignore,Debunk}。",
    "18:         若解析失败或输出越界，则进行有界重试；重试耗尽时置 a_i^t←Ignore，并保持原信念 b_i 不变。",
    "19:         更新节点信念 b_i←b_i'。",
    "20:         if a_i^t=Share 或 a_i^t=Debunk then",
    "21:             由动作生成类型化消息 m_out：Share→RUMOR，Debunk→DEBUNK。",
    "22:             for each 出邻居 v_j∈N^+(v_i) do",
    "23:                 if ν(v_i,v_j,m_out)=0 then",
    "24:                     将事件 (v_i,v_j,m_out) 加入 Q_{t+1}[v_j]。",
    "25:                     ν(v_i,v_j,m_out)←1。",
    "26:                 end if",
    "27:             end for",
    "28:         end if",
    "29:         将 (t,v_i,P_i,M_i^t,b_i,a_i^t,h_i^t) 追加至日志 L。",
    "30:     end for",
    "31:     t←t+1。",
    "32:  end while",
    "33:  计算最终渗透率 ρ_T←|{v_i∈V | b_i=Accept}| / |V|。",
    "34:  return S_T={b_i | v_i∈V}, ρ_T, L。",
    "说明：第 6 行固定节点调度顺序以排除并发顺序引起的轨迹分叉；第 11-16 行对应判定记录映射，保证记录条件下的逐事件回放一致；第 23-25 行是新颖事件过滤规则，使每个“发送节点-接收节点-消息类型”三元事件至多传播一次。",
    "复杂度：在事件队列完全耗散且不考虑 T_max 截断时，消息入队次数上界为 |E|·|M|，其中 |M|=2；LLM 判定次数不超过被非空事件队列激活的节点-时间对数量，显著低于全轮询的 |V|·T_max 上界。",
]


def text_of(p):
    return "".join(p.xpath(".//w:t/text()", namespaces=NS)).strip()


def set_text(p, text):
    p_pr = p.find(f"{{{W_NS}}}pPr")
    for child in list(p):
        if child is not p_pr:
            p.remove(child)
    r = etree.Element(f"{{{W_NS}}}r")
    t = etree.SubElement(r, f"{{{W_NS}}}t")
    t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    t.text = text
    r.append(t)
    p.append(r)


def make_para_like(anchor, text):
    p = etree.Element(f"{{{W_NS}}}p")
    p_pr = anchor.find(f"{{{W_NS}}}pPr")
    if p_pr is not None:
        p.append(etree.fromstring(etree.tostring(p_pr)))
    set_text(p, text)
    return p


def paragraphs(root):
    return root.xpath(".//w:body/w:p", namespaces=NS)


def remove_existing_algorithm_body(root, title_p):
    """Remove old Algorithm 1 body until section 4, preserving the title."""
    current = title_p.getnext()
    while current is not None and current.tag == f"{{{W_NS}}}p":
        txt = text_of(current)
        if txt.startswith("4 实验分析与验证"):
            break
        nxt = current.getnext()
        current.getparent().remove(current)
        current = nxt


def main():
    if not SRC.exists():
        raise FileNotFoundError(SRC)
    if WORK.exists():
        shutil.rmtree(WORK)
    WORK.mkdir()

    with zipfile.ZipFile(SRC, "r") as z:
        z.extractall(WORK)

    doc_path = WORK / "word" / "document.xml"
    parser = etree.XMLParser(remove_blank_text=False)
    tree = etree.parse(str(doc_path), parser)
    root = tree.getroot()

    matches = [p for p in paragraphs(root) if text_of(p).startswith(ALGORITHM_TITLE)]
    if not matches:
        raise RuntimeError(f"Algorithm title not found: {ALGORITHM_TITLE}")
    title_p = matches[0]
    remove_existing_algorithm_body(root, title_p)

    anchor = title_p
    for line in ALGORITHM_LINES:
        new_p = make_para_like(title_p, line)
        anchor.addnext(new_p)
        anchor = new_p

    tree.write(str(doc_path), encoding="UTF-8", xml_declaration=True, standalone=False)

    if OUT.exists():
        OUT.unlink()
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
        for path in WORK.rglob("*"):
            if path.is_file():
                z.write(path, path.relative_to(WORK).as_posix())
    shutil.rmtree(WORK)
    print(OUT)


if __name__ == "__main__":
    main()
