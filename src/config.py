# -*- coding: utf-8 -*-
"""
LEDS 框架全局配置模块
对应论文 4.1 节：实验环境与参数设置

代码规范要求（思路.md 第 4 节）：API Key 与模型名称通过环境变量注入，
避免硬编码泄露；仿真核心超参数在此集中锁定。
"""
import os

# ---------------------------------------------------------------------------
# 可选的 .env 文件加载：在项目根目录创建 .env 文件（KEY=VALUE 每行一条），
# 即可免设系统环境变量。已存在的系统环境变量优先级更高，不会被覆盖。
# .env 属于本地私密配置，严禁提交到版本库或随代码外发。
# ---------------------------------------------------------------------------
_ENV_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
if os.path.exists(_ENV_FILE):
    with open(_ENV_FILE, "r", encoding="utf-8") as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip().strip('"').strip("'"))

# ---------------------------------------------------------------------------
# LLM 推理后端配置（对应论文 4.1 节）
# API Key 严禁硬编码，通过环境变量 DEEPSEEK_API_KEY 或根目录 .env 文件注入。
# 默认模型为 DeepSeek 官方在售的对话模型 deepseek-chat（DeepSeek-V3）；
# 如需其他后端（如 deepseek-reasoner 或 OpenAI 兼容接口），通过环境变量
# LEDS_MODEL / DEEPSEEK_BASE_URL 覆盖即可，无需改动代码。
# ---------------------------------------------------------------------------
LLM_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
LLM_BASE_URL = os.environ.get(
    "DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1/chat/completions"
)
LLM_MODEL = os.environ.get("LEDS_MODEL", "deepseek-chat")

# ---------------------------------------------------------------------------
# 对应论文 3.4 节：零温度贪婪解码约束（Zero-Temperature Greedy Decoding）
# 强制锁定 Temperature = 0.0 与 Top_P = 1.0，物理切断随机采样。
# 注意：本框架彻底摒弃伪随机数生成器，仿真运行期不依赖任何 Seed 参数。
# ---------------------------------------------------------------------------
TEMPERATURE = 0.0
TOP_P = 1.0

# ---------------------------------------------------------------------------
# 对应论文 3.3 节：离散事件演化循环参数
# ---------------------------------------------------------------------------
N_NODES = 300         # 论文 4.2 节：系统共实例化 N=300 个智能体节点
T_MAX = 30            # 最大容许时间步（论文 3.6 节伪代码输入 T_max）
API_TIMEOUT = 60      # 单次 API 调用超时（秒）
API_MAX_RETRIES = 3   # 网络层瞬时故障重试次数（不影响解码确定性）

# ---------------------------------------------------------------------------
# 工程目录约定（思路.md 第 2 节）
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
RESULTS_DIR = os.path.join(BASE_DIR, "results")
LOGS_DIR = os.path.join(RESULTS_DIR, "logs")
CHARTS_DIR = os.path.join(RESULTS_DIR, "charts")
CACHE_DIR = os.path.join(RESULTS_DIR, "cache")
