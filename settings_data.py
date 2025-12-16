"""
===============================================================================
                    📋 静态配置数据 (settings_data.py)
===============================================================================
将业务相关的静态数据从逻辑代码中分离，遵循关注点分离原则。
包含：WATCHLIST、数据源列表、运营阶段配置等。
===============================================================================
"""

from typing import TypedDict, List, Dict

# ================= 类型定义 =================

class SourceConfig(TypedDict):
    name: str
    tag: str
    primary: str
    backup: str


class PhaseWeights(TypedDict):
    news: float
    social: float
    github: float


class PhaseConfigItem(TypedDict):
    name: str
    weights: PhaseWeights
    strategy: str
    prompt_suffix: str


# ================= 长期关注矩阵 (流量基本盘) =================

WATCHLIST: List[str] = [
    # 顶流模型 (国际)
    "DeepSeek V3", "Claude 3.5", "Gemini 2.0", "GPT-4o", "Llama 3",
    # 国内大厂 (新增)
    "智谱 AI", "AutoGLM", "通义千问 Qwen", "豆包", "Kimi", "秘塔搜索",
    # 热门技术
    "MCP协议", "AI Agent", "RAG", "AI 编程", "AI 视频生成", "手机智能体",
    # 编程神器
    "Cursor", "Windsurf", "Bolt.new", "Lovable",
    # 效率标杆
    "Notion", "Obsidian", "Heptabase"
]

# ================= 热榜数据源列表 =================

TREND_SOURCES: List[SourceConfig] = [
    # === 国际硬核源 ===
    {
        "name": "Hacker News",
        "tag": "硬核技术",
        "primary": "https://news.ycombinator.com",
        "backup": "https://news.ycombinator.com/rss"
    },
    {
        "name": "Product Hunt",
        "tag": "效率工具新品",
        "primary": "https://www.producthunt.com",
        "backup": "https://www.producthunt.com/feed"
    },
    
    # === 国内大众/实战源 ===
    {
        "name": "知乎热榜-科技",
        "tag": "AI观点与争议",
        "primary": "https://www.zhihu.com/hot/technology",
        "backup": "https://rsshub.app/zhihu/hotlist"
    },
    {
        "name": "掘金-后端/AI",
        "tag": "程序员实战",
        "primary": "https://juejin.cn/hot/articles",
        "backup": "https://rsshub.app/juejin/trending/all/weekly"
    },
    {
        "name": "36Kr-科技",
        "tag": "科技大众化/行业动态",
        "primary": "https://36kr.com/information/technology",
        "backup": "https://36kr.com/feed"
    },
    {
        "name": "微博热搜-科技",
        "tag": "大众舆情/突发",
        "primary": "https://s.weibo.com/top/summary?cate=scitech",
        "backup": "https://rsshub.app/weibo/search/hot"
    },
    {
        "name": "少数派",
        "tag": "生活黑客/效率方法论",
        "primary": "https://sspai.com/tag/%E6%95%88%E7%8E%87/hot",
        "backup": "https://sspai.com/feed"
    },
    {
        "name": "CSDN热榜",
        "tag": "技术教程/报错解决",
        "primary": "https://blog.csdn.net/rank/list",
        "backup": ""  # CSDN 无稳定 RSS，留空依靠 Jina 强读
    }
]

# ================= 运营阶段配置 =================

OPERATIONAL_PHASE: str = "VALUE_HACKER"  # 价值黑客

PHASE_CONFIG: Dict[str, PhaseConfigItem] = {
    "VALUE_HACKER": {
        "name": "价值黑客模式",
        "weights": {"news": 1.5, "social": 2.0, "github": 1.0},
        "strategy": "50% 效能神器 (实操) + 50% 前沿热点 (认知)。既要教用户'怎么做'，也要带用户'看未来'。",
        "prompt_suffix": "⚠️ 绝对原则：不要局限于'小工具'。如果有重大技术更新（如 Google/OpenAI 新动作、Agent 新玩法），优先级高于普通效率工具。我们追求'高获得感'，这既包括'省时间'，也包括'涨知识'和'跟热点'。"
    }
}

# ================= B路/C路 随机关键词池 =================

EFFICIENCY_KEYWORDS: List[str] = [
    "AI 整理很多文件", "AI 自动写周报", "AI 读长论文", "AI 做漂亮的PPT", 
    "Excel AI 公式", "Notion 替代品", "Obsidian 插件", "浏览器 AI 插件",
    "自动化工作流 Zapier", "AI 剪辑视频", "AI 录音转文字 免费"
]

PAIN_KEYWORDS: List[str] = [
    "AI 写作 查重", "AI 幻觉 翻车", "收费 AI 避坑", "AI 生成图片 丑",
    "DeepSeek 报错", "ChatGPT 封号", "Cursor 太贵", "Copilot 不好用"
]

# ================= 全网雷达查询 =================

RADAR_QUERIES: List[str] = [
    "site:reddit.com/r/LocalLLaMA AI news today",  # 硬核社区
    "site:news.ycombinator.com AI launch",         # 硅谷风向标
    "site:huggingface.co/papers trending",         # 学术前沿
    "AI technology breaking news today"            # 大众新闻
]

# ================= 并发配置 =================

MAX_CONCURRENT_FETCHES: int = 5      # 热榜抓取最大并发数
FETCH_TIMEOUT_SECONDS: int = 30      # 单个源抓取超时
