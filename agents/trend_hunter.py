"""
🚀 全网选题雷达 (Trend Hunter Agent) v4.0 - 硬核价值版
核心策略：
1. 三级容错机制：Jina Primary -> Jina Backup (RSS) -> Tavily Search，确保数据源稳定。
2. 随机化扫描：B路(效率)与C路(避坑)采用随机抽取策略，避免重复。
3. 严格去重：基于历史记录的自动去重与新词扶持机制。
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
import json
import httpx
import random
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from openai import OpenAI
from config import (
    DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, PROXY_URL, REQUEST_TIMEOUT,
    TAVILY_API_KEY, get_topic_report_file, get_today_dir,
    get_stage_dir, get_research_notes_file, get_history_file
)

# ================= 历史记录管理 =================

def load_history():
    """加载最近 7 天的历史选题"""
    history_file = get_history_file()
    if not os.path.exists(history_file):
        return []
    
    try:
        with open(history_file, "r", encoding="utf-8") as f:
            history = json.load(f)
            
        # 过滤出最近 7 天的
        recent_history = []
        today = datetime.now()
        for item in history:
            date_str = item.get("date")
            try:
                item_date = datetime.strptime(date_str, "%Y-%m-%d")
                if (today - item_date).days <= 7:
                    recent_history.append(item)
            except:
                continue
        return recent_history
    except Exception:
        return []

def save_topic_to_history(topic, angle):
    """保存选中选题到历史记录"""
    history_file = get_history_file()
    history = []
    if os.path.exists(history_file):
        try:
            with open(history_file, "r", encoding="utf-8") as f:
                history = json.load(f)
        except:
            pass
            
    new_entry = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "topic": topic,
        "angle": angle
    }
    history.append(new_entry)
    
    # 只保留最近 30 条
    if len(history) > 30:
        history = history[-30:]
        
    with open(history_file, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
    print(f"   💾 历史记录已更新: {topic}")

# ================= 配置区 =================

# 长期关注矩阵 (流量基本盘)
WATCHLIST = [
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

# 运营阶段配置
OPERATIONAL_PHASE = "VALUE_HACKER" # 价值黑客

PHASE_CONFIG = {
    "VALUE_HACKER": {
        "name": "价值黑客模式",
        "weights": {"news": 1.5, "social": 2.0, "github": 1.0}, # 平衡权重：提升新闻权重，确保不漏大事件
        "strategy": "利用心理学锚点(收益/损失)，挖掘能给用户带来'获得感'的选题。",
        "prompt_suffix": "⚠️ 绝对原则：像一个'生活黑客'一样思考。但必须对'重大技术更新'保持敏感（如新模型发布）。如果是工具，必须是普通人手机/电脑能装的；如果是教程，必须是小白能看懂的。"
    }
}

CURRENT_CONFIG = PHASE_CONFIG[OPERATIONAL_PHASE]

# ================= Tavily 搜索工具 =================

class WebSearchTool:
    def __init__(self):
        self.api_key = TAVILY_API_KEY
        self.enabled = bool(self.api_key and len(self.api_key) > 10)
        if self.enabled:
            print("   ✅ Tavily Search API 已启用")
    
    def search(self, query, max_results=5, include_answer=False, topic=None, days=3):
        """Tavily 搜索，强制只返回最近 N 天的新闻"""
        if not self.enabled: return []
        print(f"   🔍 Tavily (最近{days}天): {query}")
        url = "https://api.tavily.com/search"
        payload = {
            "api_key": self.api_key,
            "query": query,
            "search_depth": "advanced",  # 使用 advanced 以支持时间过滤
            "max_results": max_results,
            "include_answer": include_answer,
            "days": days                  # 只看最近 N 天的热点
        }
        if topic:
            payload["topic"] = topic
            
        try:
            # Tavily 需要代理 (如果配置了 PROXY_URL)
            # 使用 trust_env=False 防止读取系统环境变量导致混乱，显式指定 proxy
            proxies = PROXY_URL if PROXY_URL else None
            with httpx.Client(timeout=30, proxy=proxies) as client:
                resp = client.post(url, json=payload)
                resp.raise_for_status()
                data = resp.json()
                results = []
                if data.get('answer'):
                    results.append({"title": "AI Summary", "body": data['answer'], "url": ""})
                for r in data.get('results', []):
                    results.append({
                        "title": r.get('title', ''),
                        "body": r.get('content', ''),
                        "url": r.get('url', '')
                    })
                return results
        except Exception as e:
            print(f"      ❌ 搜索失败: {e}")
            return []

# ================= 辅助函数 =================

def get_github_trending():
    print("   🔍 GitHub Trending (Weekly)...")
    url = "https://github.com/trending?since=weekly" # 全语言 Weekly，范围更广
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        with httpx.Client(proxy=PROXY_URL, timeout=15) as client:
            resp = client.get(url, headers=headers)
        soup = BeautifulSoup(resp.text, 'html.parser')
        repos = soup.select('article.Box-row')
        results = []
        for repo in repos[:5]:
            name_tag = repo.select_one('h1 a') or repo.select_one('h2 a')
            if not name_tag: continue
            name = name_tag.get_text(strip=True).replace('\n', '').replace(' ', '')
            desc = repo.select_one('p').get_text(strip=True) if repo.select_one('p') else ""
            # 过滤掉非AI/工具类的仓库(简单关键词过滤)
            results.append(f"- {name}: {desc}")
        return results
    except Exception as e:
        return [f"- GitHub 抓取失败: {e}"]

# ================= 热榜动态抓取 =================

def fetch_dynamic_trends(client, search_tool=None):
    """
    从热榜网站抓取实时关键词（三级容错机制）
    1. Jina Primary -> 2. Jina Backup (RSS) -> 3. Tavily Search
    """
    print("   🌐 [热榜抓取] 从全网热榜获取实时趋势...")
    
    sources = [
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
    
    all_keywords = []
    
    for source in sources:
        # 传入 search_tool 用于 Tavily 兜底
        content = _fetch_with_fallback(
            source["primary"], 
            source["backup"], 
            source["name"],
            search_tool
        )
        if content:
            # 对每个源单独提取关键词（带降噪 Prompt）
            keywords = _extract_keywords_from_single_source(
                client, 
                content, 
                source["name"], 
                source["tag"]
            )
            all_keywords.extend(keywords)
    
    if not all_keywords:
        print("      ⚠️ 所有热榜源提取关键词失败，返回空列表")
        return []
    
    # 去重并限制数量
    unique_keywords = list(dict.fromkeys(all_keywords))[:10]
    print(f"   🔥 [热榜汇总] 实时关键词: {unique_keywords}")
    return unique_keywords


def _fetch_with_fallback(primary_url, backup_url, source_name, search_tool=None):
    """
    三级获取策略：Jina Primary -> Jina Backup -> Tavily Search
    """
    jina_base = "https://r.jina.ai/"
    
    # 1. 尝试 Jina Primary
    content = _fetch_via_jina(jina_base + primary_url, source_name, "primary")
    if content and len(content) >= 500:
        return content
    
    # 2. 尝试 Jina Backup (RSS)
    if backup_url:
        print(f"      🔄 [{source_name}] Primary 失败，尝试 Backup (RSS)...")
        content = _fetch_via_jina(jina_base + backup_url, source_name, "backup")
        if content and len(content) >= 500:
            return content

    # 3. 尝试 Tavily 终极救援
    if search_tool and search_tool.enabled:
        print(f"      🛡️ [{source_name}] 启用 Tavily 终极救援...")
        # 构造搜索词
        query = f"{source_name} 热门 AI 科技内容 {datetime.now().strftime('%Y-%m-%d')}"
        results = search_tool.search(query, max_results=3, days=3)
        if results:
            # 拼接 Tavily 的搜索结果作为伪造的"网页内容"
            combined_text = "\n".join([f"Title: {r['title']}\nSnippet: {r['body']}" for r in results])
            print(f"      ✅ [{source_name}] Tavily 救援成功: 抓取 {len(results)} 条结果")
            return combined_text
            
    print(f"      ❌ [{source_name}] 所有通道均失败")
    return None


def _fetch_via_jina(url, source_name, url_type):
    """
    通过 Jina Reader API 获取网页内容
    """
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "x-no-cache": "true"  # 强制 Jina Reader 抓取最新页面，不返回缓存
        }
        with httpx.Client(proxy=PROXY_URL, timeout=30) as client:
            resp = client.get(url, headers=headers)
            
            if resp.status_code != 200:
                print(f"      ⚠️ [{source_name}] {url_type} 状态码: {resp.status_code}")
                return None
            
            content = resp.text
            if len(content) < 500:
                print(f"      ⚠️ [{source_name}] {url_type} 内容过短: {len(content)} 字符")
                return None
            
            print(f"      ✅ [{source_name}] {url_type} 成功: {len(content)} 字符")
            return content[:8000]  # 限制长度，避免 token 过多
            
    except httpx.TimeoutException:
        print(f"      ⚠️ [{source_name}] {url_type} 超时")
        return None
    except Exception as e:
        print(f"      ⚠️ [{source_name}] {url_type} 异常: {e}")
        return None


def _extract_keywords_from_single_source(client, content, name, tag):
    """
    使用 LLM 从单个热榜源中提取关键词（带严格降噪过滤）
    """
    if not content:
        return []
    
    # 限制内容长度（保留较多内容以覆盖热榜前50名）
    content_truncated = content[:8000]
    
    prompt = f"""
这是【{name}】今天的热榜或搜索摘要。
请从中提取 2-3 个最符合"{tag}"领域的具体技术名词或产品名称。

⚠️ 关键过滤规则（必须遵守）：
1. 🔴 **绝对排除底层技术**：严禁提取 后端框架(Spring Boot/Django)、数据库(Redis/SQL)、运维(K8s/Docker)、底层驱动(CUDA/NATS)、编程语言版本(Java 21/Vite 8)。**我们只要给小白用的工具！**
2. 🟢 **只保留应用层**：
   - AI 应用/大模型 (DeepSeek, Kimi, Claude 4.5, Sora)
   - 效率工具 (Notion, Cursor, Obsidian, Arc浏览器)
   - 落地玩法 (AI做PPT, 智能体开发, 本地部署)
   - 行业热点 (AI眼镜, 具身智能)
3. 排除娱乐明星和社会新闻。
4. 如果页面是 RSS XML 格式，请忽略 XML 标签，只提取 Title 中的技术名词。
5. 返回格式：只返回名词，用英文逗号分隔。如果不确定或无相关内容，返回 "NONE"。
6. 优先提取**知名科技公司**（如深度求索，智谱, 字节, 腾讯、阿里、OpenAI，Google ，Claude ，Bing ，月之暗面，讯飞，百度，微软，苹果，小红书）发布的**新产品名称**（如 AutoGLM, Sora），降低对不知名小工具的提取权重。

示例：
❌ 错误：Spring Boot, MySQL, React Hooks
✅ 正确：DeepSeek, Cursor, 秘塔搜索
"""
    
    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "你是一个敏锐的技术趋势捕手，擅长从杂乱的网页内容中提取有价值的技术关键词，并过滤掉无关的娱乐八卦。"},
                {"role": "user", "content": f"【{name} 热榜内容】\n{content_truncated}\n\n{prompt}"}
            ],
            temperature=0.2
        )
        result = response.choices[0].message.content.strip()
        
        # 处理 NONE 情况
        if result.upper() == "NONE" or "NONE" in result.upper():
            print(f"      ⏭️ [{name}] 无相关技术内容，跳过")
            return []
        
        # 清洗并返回
        keywords = [k.strip() for k in result.split(',') if k.strip() and len(k.strip()) < 30]
        keywords = keywords[:3]  # 每个源最多3个
        
        if keywords:
            print(f"      📌 [{name}] 提取: {keywords}")
        return keywords
        
    except Exception as e:
        print(f"      ⚠️ [{name}] 关键词提取失败: {e}")
        return []


def extract_hot_entities(client, search_results):
    """从搜索结果中提取 2-3 个热门技术名词"""
    if not search_results: return []
    
    text = "\n".join([f"- {r['title']}" for r in search_results[:10]]) # 限制输入长度
    prompt = """
    请从上述新闻标题中，提取 2-3 个当前最火的 AI 技术或产品名称。
    要求：
    1. 只返回具体名词，如 "DeepSeek V3", "MCP", "Sora 2.0"。
    2. 不要返回通用词（如 "AI", "LLM", "Technology"）。
    3. 输出格式：用英文逗号分隔，不要其他废话。
    """
    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "你是一个敏锐的技术趋势捕手。"},
                {"role": "user", "content": f"【新闻标题列表】\n{text}\n\n{prompt}"}
            ],
            temperature=0.1
        )
        content = response.choices[0].message.content.strip()
        # 简单清理
        entities = [e.strip() for e in content.split(',') if e.strip() and len(e.strip()) < 20]
        return entities[:3]
    except Exception as e:
        print(f"      ⚠️ 热点提取失败: {e}")
        return []

# ================= 核心逻辑 =================

def get_plan_prompt(history_text=""):
    """动态生成规划提示词，注入当前日期和历史记录"""
    today = datetime.now().strftime('%Y-%m-%d')
    return f"""
📅 今天是 {today}。你必须只关注最近 3-7 天内发生的 AI 圈最新大事件。
❗ 绝对禁止报道 2024 年或更早的旧闻（如 DeepSeek R1、GPT-4 发布等历史事件）。

【历史发文记录 (最近7天)】
{history_text}
⚠️ 查重指令：如果上述历史记录中已存在相似选题，请必须调整切入角度（例如：从"新闻报道"转向"深度实测"或"避坑指南"）。如果无法差异化，请直接丢弃该选题。

你是“王往AI”的首席内容策略官。
请基于【全网情报】和【心理学策略】，挖掘 3 个最具“爆款潜质”的选题方向。

心理学策略：
1. **A路 (锚点效应)**: 借势顶流 (DeepSeek/Kimi)，关注其"隐藏功能"或"最新玩法"。
2. **B路 (即时满足)**: 寻找"效率神器"、"Life Hack"，主打"3分钟上手"、"下班早走1小时"。
3. **C路 (损失厌恶)**: 寻找"避坑指南"、"智商税"、"平替"、"翻车现场"，引发用户危机感。

输入数据：
- 长期关注品类动态
- 本周热门工具/教程
- 用户吐槽与痛点

决策标准：
- ✅ **保留**：DeepSeek 联网搜索怎么用才准、Cursor 免费额度没了怎么办、夸克扫描王对比。
- ❌ **剔除**：OpenAI 融资消息、Google 发布新论文、某某行业大模型白皮书。

输出格式（严格 JSON）：
[
    {{
        "event": "选题核心词 (如: DeepSeek)",
        "angle": "切入角度 (如: 隐藏玩法 / 避坑指南)",
        "news_query": "功能性搜索词 (如: DeepSeek V3 file upload)",
        "social_query": "情绪性搜索词 (如: DeepSeek 报错 / DeepSeek 不好用)"
    }},
    ...
]
"""

# 保留历史兼容性
PLAN_PROMPT = get_plan_prompt()

def step1_broad_scan_and_plan(client, search_tool):
    """Step 1: 广域价值扫描 (心理学三路策略 + 全网雷达)"""
    print(f"\n📡 [Step 1] 广域价值扫描 (策略: {CURRENT_CONFIG['name']})...")
    
    pre_scan_results = []
    
    # === Phase 0: 全网雷达 (Global Radar) ===
    # 破除信息茧房，主动嗅探不在 WATCHLIST 里的新黑马
    print(f"   🌑 [Phase 0] 全网雷达扫描 (发现新物种)...")
    radar_queries = [
        "site:reddit.com/r/LocalLLaMA AI news today", # 硬核社区
        "site:news.ycombinator.com AI launch",        # 硅谷风向标
        "site:huggingface.co/papers trending",        # 学术前沿
        "AI technology breaking news today"           # 大众新闻
    ]
    for q in radar_queries:
        res = search_tool.search(q, max_results=2, topic="news", days=1) # 只看24小时内
        pre_scan_results.extend(res)

    # === Phase 0.5: 热点提取 ===
    hot_entities = extract_hot_entities(client, pre_scan_results)
    if hot_entities:
        print(f"   🔥 [雷达锁定] 突发热点: {hot_entities}")

    # === Phase 0.6: 热榜动态趋势 ===
    fresh_keywords = []
    try:
        fresh_keywords = fetch_dynamic_trends(client, search_tool)
    except Exception as e:
        print(f"      ⚠️ 热榜抓取异常，跳过: {e}")
    
    # === A路: 顶流锚点 (Watchlist + Hotspots + Fresh) ===
    # 随机选 3 个顶流
    targets = random.sample(WATCHLIST, 3)
    
    # 将热榜关键词加入 targets (最高优先级)
    for fk in fresh_keywords:
        if not any(fk.lower() in t.lower() for t in targets):
            targets.insert(0, fk)
    
    # 将热点加入 targets (优先侦察)
    for h in hot_entities:
        # 简单去重：如果 target 里没有类似的字符串
        if not any(h.lower() in t.lower() for t in targets):
            targets.insert(0, h)
            
    # 限制扫描数量，避免过载
    targets = targets[:6]

    print(f"   🎯 [A路-锚点] 扫描目标: {targets}")
    for t in targets:
        # 激活僵尸关键词：同时搜"隐藏功能"和"最新更新"
        queries = [
            f"{t} 隐藏功能 玩法 教程 2025",
            f"{t} new features latest update" # 英文搜更新往往更准
        ]
        for q in queries:
            res = search_tool.search(q, max_results=1, topic="news", days=3)
            pre_scan_results.extend(res)
        
    # === B路: 随机收益场景 (Life Hack) ===
    print(f"   ⚡ [B路-收益] 扫描效率神器...")
    efficiency_keywords = [
        "AI 整理很多文件", "AI 自动写周报", "AI 读长论文", "AI 做漂亮的PPT", 
        "Excel AI 公式", "Notion 替代品", "Obsidian 插件", "浏览器 AI 插件",
        "自动化工作流 Zapier", "AI 剪辑视频", "AI 录音转文字 免费"
    ]
    selected_efficiency = random.sample(efficiency_keywords, 3)
    print(f"      🎲 随机抽取: {selected_efficiency}")
    for kw in selected_efficiency:
        # B路: 强制追加高质量信源，过滤 SEO 垃圾
        q = f"{kw} 推荐 site:sspai.com OR site:36kr.com OR site:v2ex.com OR site:zhihu.com"
        res = search_tool.search(q, max_results=2, days=3)
        pre_scan_results.extend(res)
        
    # === C路: 随机避坑场景 (Pain Points) ===
    print(f"   🛡️ [C路-损失] 扫描避坑/吐槽...")
    pain_keywords = [
        "AI 写作 查重", "AI 幻觉 翻车", "收费 AI 避坑", "AI 生成图片 丑",
        "DeepSeek 报错", "ChatGPT 封号", "Cursor 太贵", "Copilot 不好用"
    ]
    selected_pain = random.sample(pain_keywords, 3)
    print(f"      🎲 随机抽取: {selected_pain}")
    for kw in selected_pain:
        # C路: 强制追加社区信源
        q = f"{kw} 吐槽 避坑 site:v2ex.com OR site:reddit.com OR site:zhihu.com"
        res = search_tool.search(q, max_results=2, days=3)
        pre_scan_results.extend(res)
    
    pre_scan_text = "\n".join([f"- {r['title']}: {r['body'][:80]}" for r in pre_scan_results])
    
    # 2. 智能筛选与规划
    print(f"   📝 情报聚合完毕，DeepSeek 正在应用心理学策略选题...")
    
    # 加载历史记录
    history = load_history()
    history_text = "\n".join([f"- {h['date']}: {h['topic']} ({h['angle']})" for h in history])
    if not history_text: history_text = "无（这是第一篇）"

    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": get_plan_prompt(history_text)},
                {"role": "user", "content": f"【混合情报池】\n{pre_scan_text}"}
            ],
            temperature=0.7,
            response_format={ "type": "json_object" }
        )
        content = response.choices[0].message.content
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        
        search_plan = json.loads(content)
        if isinstance(search_plan, dict) and "events" in search_plan:
            search_plan = search_plan["events"]
            
        print(f"   🧠 选题方向已锁定: {[i['event'] + '-' + i['angle'] for i in search_plan]}\n")
        return search_plan
    except Exception as e:
        print(f"   ❌ 规划失败: {e}")
        return [{"event": "DeepSeek", "angle": "避坑", "news_query": "DeepSeek V3", "social_query": "DeepSeek 幻觉"}]

def step2_deep_scan(search_plan, search_tool):
    """Step 2: 深度验证 (重社交/痛点)"""
    print("📡 [Step 2] 启动深度价值验证...\n")
    all_results = []
    
    w_news = CURRENT_CONFIG['weights']['news']
    w_social = CURRENT_CONFIG['weights']['social']
    
    for item in search_plan:
        event = item.get("event", "未知")
        angle = item.get("angle", "通用")
        news_q = item.get("news_query", "")
        social_q = item.get("social_query", "")
        
        print(f"   🔍 正在深挖: 【{event}】 ({angle}方向)")
        event_data = [f"=== 选题: {event} ({angle}) ==="]
        
        # 1. 社交/痛点搜索 (核心)
        if social_q:
            print(f"      💬 社交舆情 (权重 {w_social}): {social_q}")
            # 增加知乎、B站(site:bilibili.com)
            full_social_q = f"{social_q} site:mp.weixin.qq.com OR site:xiaohongshu.com OR site:zhihu.com OR site:bilibili.com"
            res = search_tool.search(full_social_q, max_results=4)
            if res:
                event_data.append(f"--- 用户真实反馈 ({social_q}) ---")
                event_data.extend([f"- {r['title']}: {r['body'][:80]}..." for r in res])
                
        # 2. 官方验证 (辅助)
        if news_q:
            print(f"      🔥 官方验证 (权重 {w_news}): {news_q}")
            res = search_tool.search(news_q, max_results=2)
            if res:
                event_data.append(f"--- 官方信息 ({news_q}) ---")
                event_data.extend([f"- {r['title']}" for r in res])
        
        all_results.append("\n".join(event_data))
        print("")
        time.sleep(1)

    # GitHub 补充 (Weekly)
    print(f"   💻 GitHub Weekly Trending...")
    github_res = get_github_trending()
    all_results.append("=== GitHub Weekly Trending ===\n" + "\n".join(github_res))
    
    return "\n\n".join(all_results)

def step3_final_decision(scan_data, client, history_text="无（这是第一篇）"):
    """Step 3: 决策（带去重和新词扶持）"""
    print("\n" + "="*50 + "\n📝 DeepSeek 主编审核中...\n" + "="*50)
    
    prompt = f"""
    {EDITOR_PROMPT}
    
    ❌ **严格去重**：以下是最近已写过的选题：
    {history_text}
    
    **绝对禁止**再次选择与上述极其相似的选题！必须换个工具或换个角度！
    
    ✨ **扶持新词**：请优先关注情报中提到的【生僻技术名词】（如 AutoGLM, Dayflow 等），如果它们有价值，优先入选。
    
    当前策略：【{CURRENT_CONFIG['name']}】
    {CURRENT_CONFIG['prompt_suffix']}
    """
    
    try:
        # 单次扫描用 chat 模型（快、便宜），综合决策才用 reasoner
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": f"【深度验证情报】\n{scan_data}"}
            ],
            stream=True
        )
        
        print("\n" + "="*20 + " 选题报告 " + "="*20 + "\n")
        collected = []
        for chunk in response:
            if chunk.choices[0].delta.content:
                c = chunk.choices[0].delta.content
                print(c, end="", flush=True)
                collected.append(c)
        return "".join(collected)
    except Exception as e:
        print(f"❌ 决策失败: {e}")
        return f"失败: {e}"

EDITOR_PROMPT = """
你叫"王往AI"，专注 AI 工作流的硬核博主。
请筛选 3 个【获得感最高】的选题。

**获得感公式** = (帮用户解决的痛点 * 节省的时间/金钱) - 阅读门槛

🛡️ **质量过滤红线**（必须遵守）：
1. **拒绝野鸡工具**：非大厂/非开源的小众工具直接剔除，尤其是那些不知名的付费套壳网站。
2. **大厂新动作优先**：如果智谱、OpenAI、DeepSeek 有新动作，优先级最高。
3. **开源优先**：GitHub 上的高星开源项目优先级高于闭源付费工具。

决策逻辑：
1. **只做人话**：拒绝所有技术黑话，把"上下文缓存"翻译成"让AI记住你上周说了啥"。
2. **只做痛点**：优先选"避坑"、"平替"、"白嫖"、"提效"类选题。
3. **关联热点**：如果涉及 WATCHLIST 中的产品，加分。

输出格式：
### 选题 1：[标题] (需极具吸引力，如：DeepSeek 居然还能这么玩？)
* **获得感**：[用户看完能得到什么？省钱？省时？]
* **心理锚点**：[利用了什么心理？贪便宜？怕落后？]
* **核心看点**：[文章大纲，包含具体的工具/技巧]
---
## 今日主推
告诉我不写会后悔的那个 (获得感最强的)。
"""

def auto_init_workflow():
    """自动初始化后续工作流文件夹和文件"""
    print("\n⚙️ 正在初始化后续工作流...")
    
    # 1. 预创建所有阶段文件夹
    from config import get_stage_dir, get_research_notes_file
    stages = ["research", "drafts", "publish", "assets"]
    for stage in stages:
        path = get_stage_dir(stage)
        print(f"   📂 目录就绪: {path}")
        
    # 2. 创建空白研究笔记
    notes_file = get_research_notes_file()
    if not os.path.exists(notes_file):
        with open(notes_file, "w", encoding="utf-8") as f:
            f.write("# 研究笔记\n\n请将 NotebookLM 生成的 Briefing Doc 粘贴在这里...\n")
        print(f"   📄 笔记文件已创建: {notes_file}")
    
    # 3. 提示下一步
    print("\n💡 下一步：")
    print("   - 可继续运行 hunt 获取更多选题")
    print("   - 或运行 `python run.py final` 综合所有报告，获得 3 个提示词")

def save_report(raw_data, analysis):
    filename = get_topic_report_file()
    content = f"# 🚀 选题雷达报告 v7.0 ({CURRENT_CONFIG['name']})\n\n**时间**: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n**策略**: {CURRENT_CONFIG['strategy']}\n\n## 深度验证情报\n{raw_data}\n\n## 选题分析\n{analysis}"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"\n\n📁 报告已保存: {filename}")
    
    # 保存后自动初始化工作流
    auto_init_workflow()

def main():
    print("\n" + "="*60 + "\n🚀 全网选题雷达 v7.0 (价值挖掘版) - 王往AI\n" + "="*60 + "\n")
    
    search_tool = WebSearchTool()
    
    # DeepSeek 建议直连，不走代理 (除非 api.deepseek.com 被墙)
    # 这里我们将 proxy 设为 None，确保它不走 PROXY_URL
    with httpx.Client(proxy=None, timeout=REQUEST_TIMEOUT) as http_client:
        client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL, http_client=http_client)
        
        # 加载历史记录用于去重
        history = load_history()
        history_text = "\n".join([f"- {h['date']}: {h['topic']} ({h['angle']})" for h in history])
        if not history_text: history_text = "无（这是第一篇）"
        
        # 1. 广域扫描 (Watchlist + Trend + Pain)
        search_plan = step1_broad_scan_and_plan(client, search_tool)
        
        # 2. 深度验证
        raw_data = step2_deep_scan(search_plan, search_tool)
        
        # 3. 决策（传入历史记录用于去重）
        analysis = step3_final_decision(raw_data, client, history_text)
        
        # 4. 保存
        save_report(raw_data, analysis)
    
    print("\n✅ 选题雷达完成！")

def final_summary():
    """综合当天所有报告，给出最终选题推荐和三个提示词"""
    import glob
    from config import get_today_dir
    
    print("\n" + "="*60)
    print("🎯 综合选题决策 - 整合今日所有报告")
    print("="*60 + "\n")
    
    # 1. 读取当天所有报告
    topics_dir = os.path.join(get_today_dir(), "1_topics")
    reports = glob.glob(os.path.join(topics_dir, "report_*.md"))
    
    if not reports:
        print("❌ 今日暂无报告，请先运行 `python run.py hunt`")
        return
    
    print(f"📊 找到 {len(reports)} 份报告：")
    all_content = []
    for r in sorted(reports):
        print(f"   📄 {os.path.basename(r)}")
        with open(r, "r", encoding="utf-8") as f:
            all_content.append(f"=== {os.path.basename(r)} ===\n{f.read()}")
    
    combined = "\n\n".join(all_content)
    
    # 2. DeepSeek 综合分析
    print("\n🧠 DeepSeek 正在综合分析...")
    
    FINAL_PROMPT = """
你是"王往AI"，一个擅长从多份情报中提炼核心选题的公众号主编。

你的任务：综合分析今天的所有选题报告，选出【1个最终选题】，并输出3个结构化提示词。

## 选题标准 (按优先级)
1. **出现频率高**：多次出现的选题说明热度持续，值得深挖
2. **获得感强**：能让读者"省钱、省时、学会新技能"的选题优先
3. **痛点尖锐**：解决的问题越具体、越痛，越有爆款潜质

## 输出格式

### 🏆 今日最终选题
**标题**：[爆款标题，15-25字]
**一句话卖点**：[用户看完能得到什么？]
**关键词**：[3-5个搜索关键词，用于后续素材搜集]

### 📡 提示词 1：Fast Research (用于 NotebookLM 搜索素材)
```
[请用中文，告诉 NotebookLM 需要搜索哪些具体内容，包括：
- 官方文档/教程
- 用户真实评价/避坑经验
- 同类工具对比
- 最新更新/版本变化
格式要求：分条列出，每条一个明确的搜索任务]
```

### 🎨 提示词 2：视觉脚本 (用于配图方案)
**使用方法**：复制到 NotebookLM Chat，然后点击右侧 Studio → **Infographic** 生成信息图
```
[请用中文，建议需要准备的配图，包括：
- 关键截图 (哪个界面、哪个步骤)
- 对比图 (什么 vs 什么)
- 流程图 (如果有复杂流程)
- 封面图风格建议
- 信息图要点 (适合用 Infographic 生成的数据/对比)]
```

### 🎨 视觉配图指南 (Visual Guide)
**说明**：请为人工配图提供详细的画面建议，帮助博主快速产出高质量素材。
[请用中文列出不少于 3 张关键配图的建议：

封面图：[画面描述，如：DeepSeek Logo 与 Excel 图标对撞，科技感，橙蓝配色]

痛点图：[描述一张能展示"旧方法很麻烦"的截图或梗图]

效果图：[描述一张展示"新方法太爽了"的对比图或最终效果]

信息图/流程图：[如果有复杂步骤，建议画一张什么样的流程图] ]


"""

    with httpx.Client(proxy=None, timeout=REQUEST_TIMEOUT) as http_client:
        client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL, http_client=http_client)
        
        try:
            response = client.chat.completions.create(
                model="deepseek-reasoner",
                messages=[
                    {"role": "system", "content": FINAL_PROMPT},
                    {"role": "user", "content": f"以下是今日的所有选题报告，请综合分析后给出最终推荐：\n\n{combined}"}
                ],
                stream=True
            )
            
            print("\n" + "="*60)
            print("🏆 最终选题推荐")
            print("="*60 + "\n")
            
            collected = []
            for chunk in response:
                if chunk.choices[0].delta.content:
                    c = chunk.choices[0].delta.content
                    print(c, end="", flush=True)
                    collected.append(c)
            
            # 保存综合报告
            final_report = os.path.join(topics_dir, "FINAL_DECISION.md")
            content_str = ''.join(collected)
            with open(final_report, "w", encoding="utf-8") as f:
                f.write(f"# 🏆 今日最终选题决策\n\n**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n**综合报告数**: {len(reports)}\n\n{content_str}")
            
            print(f"\n\n📁 综合报告已保存: {final_report}")

            # === 自动更新历史记录 (Memory Update) ===
            try:
                import re
                # 优化正则：兼容中英文冒号、忽略前后空格、多行匹配
                # 模式1: **标题**: xxx
                title_pattern1 = r'\*\*标题\*\*\s*[:：]\s*(.+)'
                # 模式2: ### 选题 1：xxx
                title_pattern2 = r'###\s*选题\s*\d+\s*[:：]\s*(.+)'
                
                final_topic = None
                
                # 尝试匹配
                match1 = re.search(title_pattern1, content_str)
                if match1:
                    final_topic = match1.group(1).strip()
                else:
                    match2 = re.search(title_pattern2, content_str)
                    if match2:
                        final_topic = match2.group(1).strip()
                
                if final_topic:
                    save_topic_to_history(final_topic, "综合决策")
                else:
                    # Fallback: 尝试提取第一行有效文本
                    lines = [l.strip() for l in content_str.split('\n') if l.strip() and not l.startswith('#')]
                    if lines:
                        fallback_title = lines[0][:50]  # 取前50字符
                        save_topic_to_history(fallback_title, "综合决策")
                        print(f"⚠️ 使用 Fallback 标题: {fallback_title}")
                    else:
                        print("⚠️ 警告: 无法从报告中提取最终选题标题，历史记录未更新。")
                        print(f"   调试信息: 内容前200字 -> {content_str[:200].replace(chr(10), ' ')}")
            
            except Exception as e:
                 print(f"⚠️ 历史记录更新失败: {e}")
            
        except Exception as e:
            print(f"❌ 综合分析失败: {e}")

    print("\n✅ 综合选题完成！")

if __name__ == "__main__":
    main()
