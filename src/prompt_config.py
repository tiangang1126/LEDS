# -*- coding: utf-8 -*-
"""
LEDS 框架人设（Persona）与提示词（Prompt）配置模块
对应论文 4.2 节：传播场景与节点人设配置
对应论文 3.4 节：强制的 System Prompt 输出约束（标准化 JSON）

思路.md 阶段 2 核心约束：
  提示词中必须声明“你是一个严格的逻辑状态机”，并强制仅输出 JSON：
  {"stance": "Accept|Reject|Neutral", "action": "Share|Ignore|Debunk"}
"""

# ---------------------------------------------------------------------------
# 传播场景设定（论文 4.2 节）：虚拟科学预警
# ---------------------------------------------------------------------------
RUMOR_CONTENT = "最新研究声称：长期佩戴新型AR眼镜会导致短期隐性记忆丧失。"
DEBUNK_CONTENT = (
    "事实核查声明：经权威机构核实，“长期佩戴新型AR眼镜导致短期隐性记忆丧失”"
    "的说法缺乏任何科学依据，属于虚假信息，请勿传播。"
)

# 消息类型的有限集合（论文 3.5 节：注入的初始争议信息与核查员产生的辟谣信息种类固定）
MSG_RUMOR = "RUMOR"
MSG_DEBUNK = "DEBUNK"

# 信念状态与动作的离散有界集合（论文 3.5 节：状态空间的有界性）
STANCES = ("Accept", "Reject", "Neutral")
ACTIONS = ("Share", "Ignore", "Debunk")

# ---------------------------------------------------------------------------
# 人设字典 Persona Profiles P（论文 4.2 节：三种人设比例 60% / 30% / 10%）
# ---------------------------------------------------------------------------
PERSONAS = {
    "susceptible": {
        "label": "易感者 (Susceptible)",
        "ratio": 0.60,
        "profile": (
            "你缺乏技术背景，对新技术潜在健康风险高度焦虑，"
            "倾向于相信并转发任何风险预警信息以提醒亲友；"
            "但若收到过权威辟谣声明，你会立刻放弃相信并停止传播。"
        ),
    },
    "neutral": {
        "label": "中立者 (Neutral)",
        "ratio": 0.30,
        "profile": (
            "你理性谨慎，不轻信单一信息源。只有当至少四个不同的邻居"
            "分别向你传来同一风险预警（多重信息源交叉验证）时，你才会相信并转发；"
            "一旦收到权威辟谣声明，你会直接判定该预警为谣言。"
        ),
    },
    "fact_checker": {
        "label": "核查员 (Fact-Checker)",
        "ratio": 0.10,
        "profile": (
            "你具备专业科学素养，能立刻识别出该预警是无科学依据的谣言。"
            "你绝不传播谣言（stance 恒为 Reject），并且在收到谣言后"
            "必须向所有邻居发送辟谣声明（action 输出 Debunk）。"
        ),
    },
}

# ---------------------------------------------------------------------------
# System Prompt：对应论文 3.4 节的强制输出约束，将 LLM 降维为纯粹的逻辑判别器
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = (
    "你是一个严格的逻辑状态机，扮演社会网络中的一个信息接收节点。"
    "你必须根据给定的人设、当前信念状态和新收到的消息，输出你的下一信念状态与动作。"
    "严格仅输出如下 JSON 格式，不要输出其他任何字符（包括解释、Markdown 代码块标记）：\n"
    '{"stance": "Accept|Reject|Neutral", "action": "Share|Ignore|Debunk"}\n'
    "字段语义：stance 表示你对“AR眼镜致失忆”预警的信念"
    "（Accept=相信 / Reject=不信 / Neutral=存疑）；"
    "action 表示你本轮的对外动作（Share=向邻居转发该预警 / "
    "Ignore=不作任何传播 / Debunk=向邻居发送辟谣声明，仅核查员可用）。"
)


def build_user_prompt(persona_key: str, current_stance: str,
                      rumor_count: int, debunk_count: int,
                      new_messages: list) -> str:
    """
    组装节点级 User Prompt。
    对应论文 3.3 节马尔可夫状态转移公式：
        S_{i,t+1}, A_{i,t+1} = f_LLM(S_{i,t}, P_i, M_{i,t})
    输入严格限定为：当前信念 S_{i,t}、人设 P_i、本步新消息集 M_{i,t}
    （附带累计曝光计数，作为内部信念状态 S 的定量分量，
     用于支撑中立者的“多重信息源交叉验证”判定）。
    """
    persona = PERSONAS[persona_key]
    msg_lines = []
    for m in new_messages:
        tag = "风险预警(谣言)" if m["type"] == MSG_RUMOR else "权威辟谣声明"
        msg_lines.append(f"- 来自邻居节点 {m['sender']} 的{tag}：{m['content']}")
    return (
        f"【你的人设】{persona['label']}：{persona['profile']}\n"
        f"【你的当前信念状态 S_t】{current_stance}\n"
        f"【累计信息曝光】你至今累计从 {rumor_count} 个不同邻居收到该风险预警；"
        f"累计从 {debunk_count} 个不同邻居收到辟谣声明。\n"
        f"【本时间步新收到的消息 M_t】\n" + "\n".join(msg_lines) + "\n"
        f"请依据人设逻辑输出你的下一信念状态与动作（严格 JSON）。"
    )
