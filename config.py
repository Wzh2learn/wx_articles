"""
===============================================================================
                    ⚙️ 统一配置文件 (config.py)
===============================================================================
所有智能体共享的配置项，修改这里即可全局生效
===============================================================================
"""

import os
from datetime import datetime

# ================= API 配置 =================

# DeepSeek API Key（优先从环境变量读取）
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY") or "sk-28975d5a3ce447d28c558f01203ae3d7"

# DeepSeek API 地址
DEEPSEEK_BASE_URL = "https://api.deepseek.com"

# ================= 网络配置 =================

# 代理地址（如果不需要代理，设为 None）
PROXY_URL = "http://127.0.0.1:7898"

# 请求超时时间（秒）
REQUEST_TIMEOUT = 120

# ================= 路径配置 =================

# 项目根目录
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

# 数据目录
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
INPUT_DIR = os.path.join(DATA_DIR, "input")
ARCHIVE_DIR = os.path.join(DATA_DIR, "archive")

# 输入文件（当前工作笔记）
RESEARCH_NOTES_FILE = os.path.join(INPUT_DIR, "research_notes.txt")

# ================= 日期目录管理 =================

def get_today_dir():
    """获取今天的归档目录，如果不存在则创建"""
    today = datetime.now().strftime("%Y-%m-%d")
    today_dir = os.path.join(ARCHIVE_DIR, today)
    os.makedirs(today_dir, exist_ok=True)
    return today_dir

def get_today_file(filename):
    """获取今天归档目录下的文件路径"""
    return os.path.join(get_today_dir(), filename)

# 输出文件（动态获取今天的目录）
def get_draft_file():
    return get_today_file("draft.md")

def get_final_file():
    return get_today_file("final.md")

def get_html_file():
    return get_today_file("output.html")

def get_topic_report_file():
    timestamp = datetime.now().strftime("%H%M")
    return get_today_file(f"topic_report_{timestamp}.md")


# ================= 人设配置 =================

# 博主人设标签（用于选题过滤）
PERSONA_TAGS = [
    "AI", "人工智能", "大模型", "LLM", "DeepSeek", "Kimi", "ChatGPT", "Cursor",
    "效率", "工具", "工作流", "自动化", "提示词", "Prompt", "Agent", "RAG"
]

# ================= 初始化 =================

def setup_proxy():
    """设置代理环境变量"""
    if PROXY_URL:
        os.environ['HTTP_PROXY'] = PROXY_URL
        os.environ['HTTPS_PROXY'] = PROXY_URL
        os.environ['http_proxy'] = PROXY_URL
        os.environ['https_proxy'] = PROXY_URL

def ensure_dirs():
    """确保必要的目录存在"""
    os.makedirs(INPUT_DIR, exist_ok=True)
    os.makedirs(ARCHIVE_DIR, exist_ok=True)

def archive_current_notes():
    """将当前笔记备份到今天的归档目录"""
    if os.path.exists(RESEARCH_NOTES_FILE):
        import shutil
        backup_file = get_today_file("research_notes.txt")
        shutil.copy2(RESEARCH_NOTES_FILE, backup_file)
        return backup_file
    return None

# 自动初始化
setup_proxy()
ensure_dirs()
