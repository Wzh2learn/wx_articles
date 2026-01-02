"""
🚀 全网选题雷达 (Trend Hunter Agent) v4.0 (Hardcore Edition)
核心策略：
1. 三级容错机制：Jina Primary -> Jina Backup (RSS) -> Tavily Search，确保数据源稳定。
2. 随机化扫描：B路(效率)与C路(避坑)采用随机抽取策略，避免重复。
3. 严格去重：基于历史记录的自动去重与新词扶持机制。
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
import json
import re
import httpx
import random
from pathlib import Path
from difflib import SequenceMatcher
from json_repair import repair_json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import List, Dict, Optional, Any, Tuple
from bs4 import BeautifulSoup
from openai import OpenAI
from config import (
    DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, PROXY_URL, REQUEST_TIMEOUT,
    TAVILY_API_KEY, PERPLEXITY_API_KEY, EXA_API_KEY, get_topic_report_file, get_today_dir,
    get_stage_dir, get_research_notes_file, get_history_file, get_logger, retryable,
    track_cost, WATCHLIST, TREND_SOURCES, OPERATIONAL_PHASE, PHASE_CONFIG,
    EFFICIENCY_KEYWORDS, PAIN_KEYWORDS, RADAR_QUERIES,
    MAX_CONCURRENT_FETCHES, FETCH_TIMEOUT_SECONDS
)


logger = get_logger(__name__)


def log_print(*args, **kwargs):
    end = kwargs.get("end", "\n")
    flush = kwargs.get("flush", False)
    msg = " ".join(str(a) for a in args)

    if end == "" or flush:
        sys.stdout.write(msg + end)
        if flush:
            sys.stdout.flush()
        return

    if "❌" in msg:
        logger.error(msg)
    elif "⚠️" in msg or "🛡️" in msg:
        logger.warning(msg)
    else:
        logger.info(msg)

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
    log_print(f"   💾 历史记录已更新: {topic}")

# ================= 去重与相似度辅助 =================

def _max_similarity_to_history(title: str, history_items: List[Dict[str, str]]) -> float:
    """计算标题与历史记录的最大相似度"""
    if not title or not history_items:
        return 0.0
    sims = []
    for h in history_items:
        hist_title = (h.get("topic") or "").strip()
        if not hist_title:
            continue
        sims.append(SequenceMatcher(None, title.lower(), hist_title.lower()).ratio())
    return max(sims) if sims else 0.0

def _dedup_search_plan(search_plan: List[Dict[str, str]], history_items: List[Dict[str, str]], threshold: float = 0.82) -> List[Dict[str, str]]:
    """
    根据历史选题做简单去重，若全部被判定为重复，则强制保留相似度最低的一个，避免饥饿。
    """
    if not search_plan:
        return search_plan
    scored = []
    for item in search_plan:
        title = (item.get("event") or "").strip()
        max_sim = _max_similarity_to_history(title, history_items)
        new_item = dict(item)
        new_item["_max_sim"] = max_sim
        scored.append(new_item)
    deduped = [i for i in scored if i["_max_sim"] < threshold]
    if not deduped and scored:
        fallback = min(scored, key=lambda x: x["_max_sim"])
        log_print(f"⚠️ All topics were flagged as duplicates. Force-keeping the least similar one: {fallback.get('event', '(unknown)')}")
        deduped = [fallback]
    # 移除内部评分字段
    for i in deduped:
        i.pop("_max_sim", None)
    return deduped

# ================= 配置区 =================

CURRENT_CONFIG = PHASE_CONFIG[OPERATIONAL_PHASE]

# ================= 搜索工具 (多级降级) =================

class WebSearchTool:
    def __init__(self):
        self.tavily_key = TAVILY_API_KEY
        self.pplx_key = PERPLEXITY_API_KEY
        self.exa_key = EXA_API_KEY
        
        self.pplx_enabled = bool(self.pplx_key and len(self.pplx_key) > 10)
        self.tavily_enabled = bool(self.tavily_key and len(self.tavily_key) > 10)
        self.exa_enabled = bool(self.exa_key and len(self.exa_key) > 10)
        
        self.enabled = self.pplx_enabled or self.tavily_enabled or self.exa_enabled
        
        if self.pplx_enabled: log_print("   ✅ Perplexity API 已就绪 (首选)")
        if self.tavily_enabled: log_print("   ✅ Tavily API 已就绪 (备选)")
        if self.exa_enabled: log_print("   ✅ Exa AI API 已就绪 (兜底)")

    def search(self, query, max_results=5, include_answer=True, topic=None, days=3):
        """
        多级搜索降级逻辑: Perplexity -> Tavily -> Exa
        """
        if not self.enabled: return []

        # 1. 首选 Perplexity
        if self.pplx_enabled:
            results = self._search_perplexity(query)
            if results: return results

        # 2. 备选 Tavily
        if self.tavily_enabled:
            results = self._search_tavily(query, max_results, include_answer, topic, days)
            if results: return results

        # 3. 兜底 Exa
        if self.exa_enabled:
            results = self._search_exa(query, max_results)
            if results: return results

        return []

    def _search_perplexity(self, query):
        """Perplexity API: 获取模型生成的摘要作为核心研究素材"""
        log_print(f"   🔍 Perplexity 搜索: {query}")
        url = "https://api.perplexity.ai/chat/completions"
        payload = {
            "model": "sonar",
            "messages": [
                {"role": "system", "content": "你是一个专业的AI研究助手。请针对用户的查询提供详细、准确且带有来源摘要的回答。"},
                {"role": "user", "content": query}
            ],
            "temperature": 0.2,
            "top_p": 0.9,
            "search_domain_filter": None,
            "return_images": False,
            "return_related_questions": False,
            "search_recency_filter": "week",
            "top_k": 0,
            "stream": False,
            "presence_penalty": 0,
            "frequency_penalty": 1
        }
        headers = {
            "Authorization": f"Bearer {self.pplx_key}",
            "Content-Type": "application/json"
        }
        
        try:
            proxies = PROXY_URL if PROXY_URL else None
            with httpx.Client(timeout=45, proxy=proxies, trust_env=False) as client:
                @retryable
                @track_cost(context="perplexity_search")
                def _post():
                    return client.post(url, json=payload, headers=headers)
                
                resp = _post()
                if resp.status_code != 200:
                    log_print(f"      ⚠️ Perplexity 报错: {resp.status_code}")
                    return None
                
                data = resp.json()
                content = data['choices'][0]['message']['content']
                # 将生成的摘要作为第一个结果返回，body 设为全文
                return [{"title": "Perplexity AI Summary", "body": content, "url": "https://perplexity.ai"}]
        except Exception as e:
            log_print(f"      ❌ Perplexity 调用失败: {e}")
            return None

    def _search_tavily(self, query, max_results=5, include_answer=False, topic=None, days=3):
        """原有的 Tavily 搜索逻辑"""
        log_print(f"   🔍 Tavily 搜索 (最近{days}天): {query}")
        url = "https://api.tavily.com/search"
        payload = {
            "api_key": self.tavily_key,
            "query": query,
            "search_depth": "advanced",
            "max_results": max_results,
            "include_answer": include_answer,
            "days": days
        }
        if topic: payload["topic"] = topic
            
        try:
            proxies = PROXY_URL if PROXY_URL else None
            with httpx.Client(timeout=30, proxy=proxies, trust_env=False) as client:
                @retryable
                def _post():
                    resp = client.post(url, json=payload)
                    if resp.status_code in [429, 432]:
                        log_print(f"      ⚠️ Tavily 额度受限 ({resp.status_code})")
                        return resp
                    resp.raise_for_status()
                    return resp

                resp = _post()
                if resp.status_code != 200: return None
                
                data = resp.json()
                results = []
                if data.get('answer'):
                    results.append({"title": "Tavily AI Summary", "body": data['answer'], "url": ""})
                for r in data.get('results', []):
                    results.append({
                        "title": r.get('title', ''),
                        "body": r.get('content', ''),
                        "url": r.get('url', '')
                    })
                return results
        except Exception as e:
            log_print(f"      ❌ Tavily 失败: {e}")
            return None

    def _search_exa(self, query, max_results=5):
        """Exa AI (原 Metaphor) 兜底搜索"""
        log_print(f"   🔍 Exa AI 兜底搜索: {query}")
        url = "https://api.exa.ai/search"
        headers = {
            "x-api-key": self.exa_key,
            "Content-Type": "application/json"
        }
        payload = {
            "query": query,
            "useAutoprompt": True,
            "numResults": max_results,
            "type": "neural"
        }
        try:
            proxies = PROXY_URL if PROXY_URL else None
            with httpx.Client(timeout=30, proxy=proxies, trust_env=False) as client:
                @retryable
                @track_cost(context="exa_search")
                def _post():
                    return client.post(url, json=payload, headers=headers)
                
                resp = _post()
                if resp.status_code != 200:
                    log_print(f"      ⚠️ Exa AI 报错: {resp.status_code}")
                    return None
                
                data = resp.json()
                results = []
                for r in data.get('results', []):
                    results.append({
                        "title": r.get('title', ''),
                        "body": r.get('text', '') or r.get('snippet', ''),
                        "url": r.get('url', '')
                    })
                return results
        except Exception as e:
            log_print(f"      ❌ Exa AI 调用失败: {e}")
            return None

# ================= 辅助函数 =================

def get_github_trending():
    log_print("   🔍 GitHub Trending (Weekly)...")
    url = "https://github.com/trending?since=weekly" # 全语言 Weekly，范围更广
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        with httpx.Client(proxy=PROXY_URL, timeout=15) as client:
            @retryable
            def _get():
                return client.get(url, headers=headers)

            resp = _get()
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

def _fetch_single_source(
    source: Dict[str, str],
    search_tool: Optional["WebSearchTool"]
) -> Optional[str]:
    """
    抓取单个热榜源（供并发调用）。
    隔离异常，保证单源失败不影响整体。
    """
    try:
        return _fetch_with_fallback(
            source["primary"],
            source["backup"],
            source["name"],
            search_tool
        )
    except Exception as e:
        log_print(f"      ⚠️ [{source['name']}] 抓取异常: {e}")
        return None


# ================= 趋势发现器 (Trending Discoverer) =================

class TrendingDiscoverer:
    """
    v4.5: 外部趋势接入引擎 (QQ浏览器 Agent / TrendRadar 思路)
    负责调用第三方 API 或聚合平台热搜，发现非 WATCHLIST 内的爆款话题
    """
    def __init__(self, search_tool: Optional["WebSearchTool"] = None):
        self.search_tool = search_tool
        self.logger = get_logger(__name__)

    def discover_external_hotspots(self) -> List[str]:
        """
        从外部聚合源发现热点。
        v4.6: 增加 Product Hunt, Hacker News 和 V2EX 的实时信号探测 (并发优化)
        """
        self.logger.info("   🔍 [TrendingDiscoverer] 正在探测全网社交媒体与即时热搜...")
        
        # 1. 实时信号 (利用 Jina Reader 极速扫描)
        realtime_urls = [
            "https://www.producthunt.com",
            "https://news.ycombinator.com",
            "https://www.v2ex.com/?tab=hot"
        ]
        
        # 2. 传统热搜探测 (Perplexity/Tavily)
        search_queries = [
            "微博热搜榜 site:s.weibo.com",
            "百度热搜 实时",
            "小红书 爆款 话题",
            "今日头条 热点新闻"
        ]
        
        results = []
        
        # 并发执行 Jina 抓取
        def fetch_jina(url):
            try:
                headers = {"x-no-cache": "true"}
                with httpx.Client(proxy=PROXY_URL, timeout=15) as client:
                    resp = client.get(f"https://r.jina.ai/{url}", headers=headers)
                    if resp.status_code == 200:
                        text_clean = resp.text[:1000].replace('\n', ' ')
                        return f"Source[{url}]: {text_clean}"
            except:
                pass
            return None

        # 并发执行搜索探测
        def fetch_search(q):
            if self.search_tool and self.search_tool.enabled:
                res = self.search_tool.search(q, max_results=2, days=1)
                return [f"{r['title']}: {r['body'][:100]}" for r in res]
            return []

        with ThreadPoolExecutor(max_workers=MAX_CONCURRENT_FETCHES) as executor:
            # 提交 Jina 任务
            jina_futures = {executor.submit(fetch_jina, url): url for url in realtime_urls}
            # 提交搜索任务
            search_futures = {executor.submit(fetch_search, q): q for q in search_queries}
            
            # 收集结果
            for future in as_completed(jina_futures):
                res = future.result()
                if res: results.append(res)
                
            for future in as_completed(search_futures):
                res = future.result()
                if res: results.extend(res)
        
        return results

def fetch_dynamic_trends(
    client: OpenAI,
    search_tool: Optional["WebSearchTool"] = None
) -> List[str]:
    """
    从热榜网站并发抓取实时关键词（三级容错机制）
    1. Jina Primary -> 2. Jina Backup (RSS) -> 3. Tavily Search
    
    使用 ThreadPoolExecutor 实现多源并发，显著提升采集效率。
    单个源的超时/失败不会阻塞其他源。
    """
    log_print("   🌐 [热榜抓取] 从全网热榜获取实时趋势 (并发模式)...")
    
    # 数据源配置
    sources = TREND_SOURCES
    
    # ===== Phase 0: 外部趋势探测 (TrendingDiscoverer) =====
    discoverer = TrendingDiscoverer(search_tool)
    external_hotspots = discoverer.discover_external_hotspots()
    if external_hotspots:
        log_print(f"   📡 [外部探测] 获取到 {len(external_hotspots)} 条全网原始热点")
    
    # ===== Phase 1: 并发抓取所有源 =====
    source_contents: Dict[str, Optional[str]] = {}
    
    with ThreadPoolExecutor(max_workers=MAX_CONCURRENT_FETCHES) as executor:
        future_to_source = {
            executor.submit(_fetch_single_source, src, search_tool): src
            for src in sources
        }
        
        for future in as_completed(future_to_source):
            src = future_to_source[future]
            try:
                content = future.result(timeout=FETCH_TIMEOUT_SECONDS)
                source_contents[src["name"]] = content
            except Exception as e:
                log_print(f"      ⚠️ [{src['name']}] 并发任务异常: {e}")
                source_contents[src["name"]] = None
    
    log_print(f"   📊 抓取完成: {sum(1 for v in source_contents.values() if v)}/{len(sources)} 个源成功")
    
    # ===== Phase 2: 串行提取关键词（LLM 调用不宜过度并发） =====
    all_keywords: List[str] = []
    
    # 注入外部热点进行关联分析
    if external_hotspots:
        external_context = "\n".join(external_hotspots)
        prompt = f"""
        这是当前全网社交媒体的热搜摘要：
        {external_context}
        
        请作为 Agent，执行以下动作：
        1. 挖掘上述热点中，**哪些可以与 AI 结合**？（例如：'春运' -> 'AI 抢票/攻略', '调休' -> 'AI 自动化办公')
        2. 给出 2-3 个最具“流量爆发力”的 AI 关联词。
        3. 只返回具体名词，用英文逗号分隔。如果没有合适的，返回 NONE。
        """
        try:
            @retryable
            @track_cost(context="discover_ai_hotspots")
            def _chat_hotspots():
                return client.chat.completions.create(
                    model="deepseek-chat",
                    messages=[
                        {"role": "system", "content": "你是一个擅长将社会热点与 AI 技术强关联的内容策略专家。"},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.3
                )
            resp = _chat_hotspots()
            hot_keywords = [k.strip() for k in resp.choices[0].message.content.split(',') if k.strip() and "NONE" not in k.upper()]
            if hot_keywords:
                log_print(f"   🔥 [Agent 关联] 从全网热搜锁定 AI 结合点: {hot_keywords}")
                all_keywords.extend(hot_keywords)
        except Exception as e:
            log_print(f"      ⚠️ 外部热点关联分析失败: {e}")

    for src in sources:
        content = source_contents.get(src["name"])
        if content:
            keywords = _extract_keywords_from_single_source(
                client,
                content,
                src["name"],
                src["tag"]
            )
            all_keywords.extend(keywords)
    
    if not all_keywords:
        log_print("      ⚠️ 所有热榜源提取关键词失败，返回空列表")
        return []
    
    # 去重并限制数量
    unique_keywords = list(dict.fromkeys(all_keywords))[:10]
    log_print(f"   🔥 [热榜汇总] 实时关键词: {unique_keywords}")
    return unique_keywords


def _fetch_with_fallback(
    primary_url: str,
    backup_url: str,
    source_name: str,
    search_tool: Optional["WebSearchTool"] = None
) -> Optional[str]:
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
        log_print(f"      🔄 [{source_name}] Primary 失败，尝试 Backup (RSS)...")
        content = _fetch_via_jina(jina_base + backup_url, source_name, "backup")
        if content and len(content) >= 500:
            return content

    # 3. 尝试 Tavily 终极救援
    if search_tool and search_tool.enabled:
        log_print(f"      🛡️ [{source_name}] 启用 Tavily 终极救援...")
        # 构造搜索词
        query = f"{source_name} 热门 AI 科技内容 {datetime.now().strftime('%Y-%m-%d')}"
        results = search_tool.search(query, max_results=3, days=3)
        if results:
            # 拼接 Tavily 的搜索结果作为伪造的"网页内容"
            combined_text = "\n".join([f"Title: {r['title']}\nSnippet: {r['body']}" for r in results])
            log_print(f"      ✅ [{source_name}] Tavily 救援成功: 抓取 {len(results)} 条结果")
            return combined_text
            
    log_print(f"      ❌ [{source_name}] 所有通道均失败")
    return None


def _fetch_via_jina(url: str, source_name: str, url_type: str) -> Optional[str]:
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
            @retryable
            def _get():
                return client.get(url, headers=headers)

            resp = _get()
            
            if resp.status_code != 200:
                log_print(f"      ⚠️ [{source_name}] {url_type} 状态码: {resp.status_code}")
                return None
            
            content = resp.text
            if len(content) < 500:
                log_print(f"      ⚠️ [{source_name}] {url_type} 内容过短: {len(content)} 字符")
                return None
            
            log_print(f"      ✅ [{source_name}] {url_type} 成功: {len(content)} 字符")
            return content[:8000]  # 限制长度，避免 token 过多
            
    except httpx.TimeoutException:
        log_print(f"      ⚠️ [{source_name}] {url_type} 超时")
        return None
    except Exception as e:
        log_print(f"      ⚠️ [{source_name}] {url_type} 异常: {e}")
        return None


def _extract_keywords_from_single_source(
    client: OpenAI,
    content: str,
    name: str,
    tag: str
) -> List[str]:
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
   - 社交爆款 (AI 扩图, 证件照, 语音克隆, 手机 Agent 自动化)
3. 排除娱乐明星和社会新闻。
4. 如果页面是 RSS XML 格式，请忽略 XML 标签，只提取 Title 中的技术名词。
5. 返回格式：只返回名词，用英文逗号分隔。如果不确定或无相关内容，返回 "NONE"。
6. 优先提取**知名科技公司**（如深度求索，智谱, 字节, 腾讯、阿里、OpenAI，Google ，Claude ，Bing ，月之暗面，讯飞，百度，微软，苹果，小红书）发布的**新产品名称**（如 AutoGLM, Sora），以及**在社交媒体（小红书/微博/抖音）上疯传的 AI 玩法**。

示例：
❌ 错误：Spring Boot, MySQL, React Hooks
✅ 正确：DeepSeek, Cursor, 秘塔搜索
"""
    
    try:
        @retryable
        @track_cost(context="extract_keywords")
        def _chat_create():
            return client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": "你是一个敏锐的技术趋势捕手，擅长从杂乱的网页内容中提取有价值的技术关键词，并过滤掉无关的娱乐八卦。"},
                    {"role": "user", "content": f"【{name} 热榜内容】\n{content_truncated}\n\n{prompt}"}
                ],
                temperature=0.2
            )

        response = _chat_create()
        result = response.choices[0].message.content.strip()
        
        # 处理 NONE 情况
        if result.upper() == "NONE" or "NONE" in result.upper():
            log_print(f"      ⏭️ [{name}] 无相关技术内容，跳过")
            return []
        
        # 清洗并返回
        keywords = [k.strip() for k in result.split(',') if k.strip() and len(k.strip()) < 30]
        keywords = keywords[:3]  # 每个源最多3个
        
        if keywords:
            log_print(f"      📌 [{name}] 提取: {keywords}")
        return keywords
        
    except Exception as e:
        log_print(f"      ⚠️ [{name}] 关键词提取失败: {e}")
        return []


def extract_hot_entities(client: OpenAI, search_results: List[Dict[str, Any]]) -> List[str]:
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
        @retryable
        @track_cost(context="extract_hot_entities")
        def _chat_create():
            return client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": "你是一个敏锐的技术趋势捕手。"},
                    {"role": "user", "content": f"【新闻标题列表】\n{text}\n\n{prompt}"}
                ],
                temperature=0.1
            )

        response = _chat_create()
        content = response.choices[0].message.content.strip()
        # 简单清理
        entities = [e.strip() for e in content.split(',') if e.strip() and len(e.strip()) < 20]
        return entities[:3]
    except Exception as e:
        log_print(f"      ⚠️ 热点提取失败: {e}")
        return []

# ================= 核心逻辑 =================

def _robust_json_parse(content: str) -> Any:
    """
    v4.1: 鲁棒 JSON 解析器
    无论 LLM 输出带不带 Markdown 代码块，或者 JSON 缺了逗号引号，都能正确解析
    """
    if not content:
        return []
    
    # 1. 尝试直接解析（最优情况：干净的 JSON）
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass
    
    # 2. 用正则提取第一个 JSON 对象/数组
    json_pattern = r'(\{.*\}|\[.*\])'
    match = re.search(json_pattern, content, re.DOTALL)
    
    if match:
        raw_json = match.group(1)
        try:
            # 3. 使用 json_repair 修复并解析
            repaired = repair_json(raw_json, return_objects=True)
            log_print(f"      🔧 JSON 已自动修复")
            return repaired
        except Exception as e:
            log_print(f"      ⚠️ JSON 修复失败: {e}")
    
    # 4. 终极回退：整体修复
    try:
        repaired = repair_json(content, return_objects=True)
        return repaired
    except Exception as e:
        log_print(f"      ❌ JSON 解析彻底失败: {e}")
        return []


def get_plan_prompt(history_text: str = "", directed_topic: Optional[str] = None) -> str:
    """动态生成规划提示词，注入当前日期、历史记录和用户意图"""
    today = datetime.now().strftime('%Y-%m-%d')
    
    intent_instruction = ""
    if directed_topic:
        intent_instruction = f"""
    👤 **用户核心指令**：
    用户指定了主题【{directed_topic}】。
    1. 你生成的 3 个选题中，**必须包含**至少 1 个与【{directed_topic}】深度相关的选题（作为 A 方案）。
    2. 同时，请从情报池中挖掘另外 1-2 个**高潜质**的随机热点或关联话题（作为 Plan B/C），与用户指定主题进行"价值PK"。
    3. 如果发现【{directed_topic}】目前毫无新意（无新闻、无痛点），你可以"抗旨"，全推其他更有价值的热点，但必须在分析中说明理由。
    """
    
    return f"""
    📅 今天是 {today}。你必须只关注最近 3-7 天内发生的 AI 圈最新大事件。
    ❗ 绝对禁止报道 2024 年或更早的旧闻（如 DeepSeek R1、GPT-4 发布等历史事件）。
    {intent_instruction}

    【历史发文记录 (最近7天)】
{history_text}
⚠️ 查重指令：如果上述历史记录中已存在相似选题，请必须调整切入角度（例如：从"新闻报道"转向"深度实测"或"避坑指南"）。如果无法差异化，请直接丢弃该选题。

你是“王往AI”的首席内容策略官。
请基于【全网情报】和【心理学策略】，挖掘 3 个最具“爆款潜质”的选题方向。

## 价值公式 (流量风暴版)
**选题价值** = (社会热度 × 好奇心) + (情绪共鸣 × 参与度) - 认知门槛

## 策略优先级 (TRAFFIC_STORM)
1. **大众体感优先**：比起"模型参数"，用户更关心"我手机上的 AI 变聪明了"、"AI 帮我省了 500 块"。
2. **情绪价值优先**：寻找那些能引发"卧槽"、"离谱"、"真香"、"终于等到"感叹的话题。
3. **社交货币优先**：让用户转到朋友圈显得自己"懂科技"、"会省钱"、"走在时代前沿"。

## 心理学三路策略（流量加强版）
1. **A路 - 锚点效应 (借势顶流)**：借助 DeepSeek/Cursor/Gemini 等顶流产品的知名度，关注其"隐藏功能"或"最新玩法"。用户看到熟悉的名字更容易点击。
2. **B路 - 即时满足 (效能神器)**：寻找真正的"效率神器"，主打"3分钟上手"、"下班早走1小时"。让用户觉得"看完就能用"。
3. **C路 - 损失厌恶 (避坑/认知)**：
   - 避坑类：寻找"智商税"、"翻车现场"、"平替"，触发用户害怕踩坑的心理。
   - 认知类：解读新趋势、新硬件（如 AI 耳机、手机智能体），让用户害怕"落后于时代"。

输入数据：
- 长期关注品类动态
- 本周热门工具/教程
- 用户吐槽与痛点
- 大厂新发布动态

决策标准：
- ✅ **保留**：DeepSeek 隐藏玩法（锚点）、免费画架构图（即时满足）、Cursor 收费避坑（损失厌恶）、Google AI 耳机体验（认知升级）。
- ❌ **剔除**：纯枯燥的融资新闻、过于学术的论文解读、毫无新意的"正确的废话"、冷门无名小工具。

输出格式（严格 JSON）：
[
    {{
        "event": "选题核心词 (如: DeepSeek)",
        "angle": "切入角度 (如: 隐藏玩法 / 避坑指南 / 深度评测)",
        "news_query": "功能性搜索词 (如: DeepSeek V3 file upload)",
        "social_query": "情绪性搜索词 (如: DeepSeek 报错 / DeepSeek 不好用)"
    }},
    ...
]
"""

# 保留历史兼容性
PLAN_PROMPT = get_plan_prompt()

def step1_broad_scan_and_plan(
    client: OpenAI,
    search_tool: "WebSearchTool",
    directed_topic: Optional[str] = None
) -> List[Dict[str, str]]:
    """
    Step 1: 广域价值扫描 (心理学三路策略 + 全网雷达)
    混合模式：如果传入 directed_topic，将其作为 A 路核心，同时保留 B/C 路随机探索
    """
    log_print(f"\n📡 [Step 1] 广域价值扫描 (策略: {CURRENT_CONFIG['name']})...")
    if directed_topic:
        log_print(f"   🎯 [混合模式] 核心主题: 「{directed_topic}」 + 全网随机扫描")
    
    pre_scan_results: List[Dict[str, Any]] = []
    
    # === Phase 0: 全网雷达 (Global Radar) ===
    # 破除信息茧房，主动嗅探不在 WATCHLIST 里的新黑马
    log_print(f"   🌑 [Phase 0] 全网雷达扫描 (发现新物种)...")
    for q in RADAR_QUERIES:
        res = search_tool.search(q, max_results=2, topic="news", days=1) # 只看24小时内
        pre_scan_results.extend(res)

    # === Phase 0.5: 热点提取 ===
    hot_entities = extract_hot_entities(client, pre_scan_results)
    if hot_entities:
        log_print(f"   🔥 [雷达锁定] 突发热点: {hot_entities}")

    # === Phase 0.6: 热榜动态趋势 ===
    fresh_keywords = []
    try:
        fresh_keywords = fetch_dynamic_trends(client, search_tool)
    except Exception as e:
        log_print(f"      ⚠️ 热榜抓取异常，跳过: {e}")
    
    # === A路: 顶流锚点 (Watchlist + Hotspots + Fresh) ===
    if directed_topic:
        # 定向模式：核心是 directed_topic，但也接纳突发热点
        targets = [directed_topic]
        # 适当加入热点（如果有重大突发），但也可能被 LLM 过滤
        for h in hot_entities:
            if h.lower() not in directed_topic.lower():
                targets.append(h)
        targets = targets[:4] # 保持聚焦
        
        # === v4.9: 定向搜索增强 - 扩展最新功能关键词 ===
        log_print(f"   🔍 [定向增强] 扩展搜索: {directed_topic} + 最新功能/更新...")
        # 针对常见产品的最新功能搜索扩展
        PRODUCT_FEATURE_EXPANSIONS = {
            "coze": ["Coze Studio", "Coze IDE", "Coze 对话生成工作流", "Coze 自动创建 Agent"],
            "cursor": ["Cursor Composer", "Cursor Agent", "Cursor 新功能"],
            "deepseek": ["DeepSeek V3.2", "DeepSeek Reasoner", "DeepSeek 新功能"],
            "kimi": ["Kimi 长文本", "Kimi 新功能", "Kimi k2"],
        }
        # 查找匹配的产品扩展
        for product, expansions in PRODUCT_FEATURE_EXPANSIONS.items():
            if product in directed_topic.lower():
                for exp in expansions:
                    exp_query = f"{exp} 最新 功能 更新 2025"
                    res = search_tool.search(exp_query, max_results=2, topic="news", days=7)
                    pre_scan_results.extend(res)
                    log_print(f"      → 扩展搜索: {exp_query} ({len(res)} 结果)")
                break
    else:
        # 随机模式
        targets = random.sample(WATCHLIST, 3)
        # 将热榜关键词加入 targets (最高优先级)
        for fk in fresh_keywords:
            if not any(fk.lower() in t.lower() for t in targets):
                targets.insert(0, fk)
        # 将热点加入 targets (优先侦察)
        for h in hot_entities:
            if not any(h.lower() in t.lower() for t in targets):
                targets.insert(0, h)
        targets = targets[:6]

    log_print(f"   🎯 [A路-锚点] 扫描目标: {targets}")
    for t in targets:
        # 激活僵尸关键词：同时搜"隐藏功能"和"最新更新"
        queries = [
            f"{t} 隐藏功能 玩法 教程 2025",
            f"{t} new features latest update", # 英文搜更新往往更准
            f"{t} 最新功能 上线 发布 2025"  # v4.9: 增加最新功能搜索
        ]
        for q in queries:
            res = search_tool.search(q, max_results=2, topic="news", days=7)  # v4.9: 增加结果数和时间范围
            pre_scan_results.extend(res)
        
    # === B路: 随机收益场景 (Life Hack) ===
    log_print(f"   ⚡ [B路-收益] 扫描效率神器...")
    selected_efficiency = random.sample(EFFICIENCY_KEYWORDS, 3)
    if directed_topic:
        # 混合模式：加入定向主题的效率场景
        selected_efficiency.insert(0, f"{directed_topic} 效率神器")
        
    log_print(f"      🎲 随机抽取: {selected_efficiency}")
    for kw in selected_efficiency:
        # B路: 强制追加高质量信源，过滤 SEO 垃圾
        q = f"{kw} 推荐 site:sspai.com OR site:36kr.com OR site:v2ex.com OR site:mp.weixin.qq.com"
        res = search_tool.search(q, max_results=2, days=3)
        pre_scan_results.extend(res)
        
    # === C路: 随机避坑场景 (Pain Points) ===
    log_print(f"   🛡️ [C路-损失] 扫描避坑/吐槽...")
    selected_pain = random.sample(PAIN_KEYWORDS, 3)
    if directed_topic:
        # 混合模式：加入定向主题的避坑场景
        selected_pain.insert(0, f"{directed_topic} 避坑 吐槽")
        
    log_print(f"      🎲 随机抽取: {selected_pain}")
    for kw in selected_pain:
        # C路: 强制追加社区信源
        q = f"{kw} 吐槽 避坑 site:v2ex.com OR site:reddit.com OR site:mp.weixin.qq.com"
        res = search_tool.search(q, max_results=2, days=3)
        pre_scan_results.extend(res)
    
    pre_scan_text = "\n".join([f"- {r['title']}: {r['body'][:80]}" for r in pre_scan_results])
    
    # 2. 智能筛选与规划
    log_print(f"   📝 情报聚合完毕，DeepSeek 正在应用心理学策略选题...")
    
    # 加载历史记录
    history = load_history()
    history_text = "\n".join([f"- {h['date']}: {h['topic']} ({h['angle']})" for h in history])
    if not history_text: history_text = "无（这是第一篇）"

    try:
        @retryable
        @track_cost(context="step1_broad_scan_and_plan")
        def _chat_create():
            return client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": get_plan_prompt(history_text, directed_topic)},
                    {"role": "user", "content": f"【混合情报池】\n{pre_scan_text}"}
                ],
                temperature=0.7,
                response_format={ "type": "json_object" }
            )

        response = _chat_create()
        content = response.choices[0].message.content
        
        # v4.1: 使用 json_repair 增强鲁棒性
        search_plan = _robust_json_parse(content)
        if isinstance(search_plan, dict) and "events" in search_plan:
            search_plan = search_plan["events"]
        
        # v4.4: 去重并防饥饿，若全重复则强制保留相似度最低的一个
        history_items = load_history()
        search_plan = _dedup_search_plan(search_plan, history_items)
        
        log_print(f"   🧠 选题方向已锁定: {[i['event'] + '-' + i['angle'] for i in search_plan]}\n")
        return search_plan
    except Exception as e:
        log_print(f"   ❌ 规划失败: {e}")
        return [{"event": "DeepSeek", "angle": "避坑", "news_query": "DeepSeek V3", "social_query": "DeepSeek 幻觉"}]

def _clean_text(text: Optional[str], max_len: int = 100) -> str:
    """清洗文本：移除多余空白、HTML标签、截断长度"""
    if not text:
        return ""
    # 移除多余空白和换行
    text = re.sub(r'\s+', ' ', text).strip()
    # 移除常见 HTML 标签残留
    text = re.sub(r'<[^>]+>', '', text)
    # 截断并添加省略号
    if len(text) > max_len:
        text = text[:max_len] + "..."
    return text

def step2_deep_scan(
    search_plan: List[Dict[str, str]],
    search_tool: "WebSearchTool",
    directed_topic: Optional[str] = None
) -> str:
    """
    Step 2: 深度验证 (重社交/痛点)
    输出格式：清晰的 Markdown 列表，包含摘要和来源 URL
    """
    log_print("📡 [Step 2] 启动深度价值验证...\n")
    all_results = []
    
    w_news = CURRENT_CONFIG['weights']['news']
    w_social = CURRENT_CONFIG['weights']['social']
    
    for item in search_plan:
        event = item.get("event", "未知")
        angle = item.get("angle", "通用")
        news_q = item.get("news_query", "")
        social_q = item.get("social_query", "")

        is_core = False
        if directed_topic and event:
            dt = str(directed_topic).lower()
            ev = str(event).lower()
            is_core = (dt in ev) or (ev in dt)

        # 防干扰：定向模式下，把更多检索额度留给核心主题；非核心主题降配额
        social_max_results = 4
        news_max_results = 2
        if directed_topic:
            social_max_results = 4 if is_core else 2
            news_max_results = 2 if is_core else 1
        
        log_print(f"   🔍 正在深挖: 【{event}】 ({angle}方向)")
        event_data = [f"### 🎯 选题: {event} ({angle})"]
        
        # 1. 社交/痛点搜索 (核心)
        if social_q:
            log_print(f"      💬 社交舆情 (权重 {w_social}): {social_q}")
            full_social_q = f"{social_q} site:mp.weixin.qq.com OR site:xiaohongshu.com OR site:bilibili.com"
            res = search_tool.search(full_social_q, max_results=social_max_results)
            if res:
                event_data.append(f"\n**💬 用户反馈** ({social_q})")
                for r in res:
                    title = _clean_text(r.get('title', '无标题'), 50)
                    body = _clean_text(r.get('body', ''), 100)
                    url = r.get('url', '')
                    if url:
                        event_data.append(f"- **{title}**: {body} [[来源]({url})]")
                    else:
                        event_data.append(f"- **{title}**: {body}")
                
        # 2. 官方验证 (辅助)
        if news_q:
            log_print(f"      🔥 官方验证 (权重 {w_news}): {news_q}")
            res = search_tool.search(news_q, max_results=news_max_results)
            if res:
                event_data.append(f"\n**📰 官方信息** ({news_q})")
                for r in res:
                    title = _clean_text(r.get('title', '无标题'), 60)
                    url = r.get('url', '')
                    if url:
                        event_data.append(f"- {title} [[来源]({url})]")
                    else:
                        event_data.append(f"- {title}")
        
        all_results.append("\n".join(event_data))
        log_print("")
        time.sleep(1)

    # GitHub 补充 (Weekly)
    log_print(f"   💻 GitHub Weekly Trending...")
    github_res = get_github_trending()
    all_results.append("### 💻 GitHub Weekly Trending\n" + "\n".join(github_res))
    
    return "\n\n---\n\n".join(all_results)

def step3_final_decision(
    scan_data: str,
    client: OpenAI,
    history_text: str = "无（这是第一篇）",
    directed_topic: Optional[str] = None
) -> str:
    """Step 3: 决策（带去重和新词扶持 + 用户意图加权）"""
    log_print("\n" + "="*50 + "\n📝 DeepSeek 主编审核中...\n" + "="*50)
    
    # 构造用户意图提示
    user_intent_prompt = ""
    if directed_topic:
        user_intent_prompt = f"""
    👤 **用户意图（最高优先级）**：
    用户明确希望写关于【{directed_topic}】的内容。
    **决策原则**：
    1. 默认优先：在同等价值下，优先选择与【{directed_topic}】相关的选题。
    2. 允许抗旨：只有当扫描到的其他热点（如突发重大技术更新）具有**极高的爆款潜质**时，你才建议放弃用户指定主题。
    3. 混合策略：如果可能，尝试将【{directed_topic}】与其他热点结合（例如 "用 {directed_topic} 解决这个新热点问题"）。
    """

    prompt = f"""
    {EDITOR_PROMPT}
    {user_intent_prompt}
    
    ❌ **严格去重**：以下是最近已写过的选题：
    {history_text}
    
    **绝对禁止**再次选择与上述极其相似的选题！必须换个工具或换个角度！
    
    ✨ **扶持新词**：请优先关注情报中提到的【生僻技术名词】（如 AutoGLM, Dayflow 等），如果它们有价值，优先入选。
    
    当前策略：【{CURRENT_CONFIG['name']}】
    {CURRENT_CONFIG['prompt_suffix']}
    """
    
    try:
        # 单次扫描用 chat 模型（快、便宜），综合决策才用 reasoner
        @retryable
        @track_cost(context="step3_final_decision")
        def _chat_create():
            return client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": f"【深度验证情报】\n{scan_data}"}
                ],
                stream=True
            )

        response = _chat_create()

        log_print("\n" + "="*20 + " 选题报告 " + "="*20 + "\n")
        collected = []
        for chunk in response:
            if chunk.choices[0].delta.content:
                c = chunk.choices[0].delta.content
                log_print(c, end="", flush=True)
                collected.append(c)
        return "".join(collected)
    except Exception as e:
        log_print(f"❌ 决策失败: {e}")
        return f"失败: {e}"

EDITOR_PROMPT = """
你叫"王往AI"，专注 AI 工作流的硬核博主。
请筛选 3 个【价值最高】的选题，**必须覆盖至少 2 种心理策略**以保证多样性。

## 价值公式
**选题价值** = (信息差 × 认知冲击) + (痛点强度 × 解决效率) - 阅读门槛

## 心理学策略（3 个选题必须覆盖至少 2 路）
1. **锚点效应 (借势顶流)**：借助 DeepSeek/Cursor/Gemini 等顶流产品的知名度，用户更容易点击。
2. **即时满足 (效能神器)**：让用户觉得"看完就能用"，获得正反馈。如"3分钟学会"、"免费白嫖"。
3. **损失厌恶 (避坑/认知)**：触发用户"害怕踩坑"或"害怕落后"的心理。如"翻车现场"、"新趋势解读"。

🛡️ **质量过滤红线**（必须遵守）：
1. **拒绝低质内容**：剔除毫无新意的"正确的废话"和冷门无名小工具。
2. **大厂新动作优先**：Google、OpenAI、DeepSeek、Anthropic 等大厂的新发布、新功能优先级最高。
3. **前沿趋势优先**：新的 Agent 玩法、新的开源黑马项目、新的硬件体验（如 AI 耳机/手机）值得关注。

决策逻辑：
1. **既要实操也要认知**：不要只盯着"省时间"的小工具。如果有一个新的技术趋势，即使暂时不能下载，只要能带来"认知震撼"，也是好选题。
2. **拒绝过度营销**：剔除那些只有营销噱头没有实质内容的工具。
3. **关联热点**：如果涉及 WATCHLIST 中的产品，加分。

输出格式：
### 选题 1：[标题] (需极具吸引力)
* **心理锚点**：[锚点效应 / 即时满足 / 损失厌恶]
* **核心价值**：[用户看完能得到什么？新知？技能？避坑？]
* **热度评级**：[⭐⭐⭐⭐⭐]
* **推荐理由**：[为什么这个选题现在值得写？]
---
## 今日主推
告诉我不写会后悔的那个 (价值最高的)，并说明它命中了哪个心理锚点。
"""

def auto_init_workflow() -> None:
    """自动初始化后续工作流文件夹和文件"""
    log_print("\n⚙️ 正在初始化后续工作流...")
    
    # 1. 预创建所有阶段文件夹
    from config import get_stage_dir, get_research_notes_file
    stages = ["research", "drafts", "publish", "assets"]
    for stage in stages:
        path = get_stage_dir(stage)
        log_print(f"   📂 目录就绪: {path}")
        
    # 2. 创建空白研究笔记
    notes_file = get_research_notes_file()
    if not os.path.exists(notes_file):
        with open(notes_file, "w", encoding="utf-8") as f:
            f.write("# 研究笔记\n\n说明：此文件通常由 `python run.py research` 自动生成。\n如需人工补充，请在此处追加你的关键发现与引用链接。\n")
        log_print(f"   📄 笔记文件已创建: {notes_file}")
    
    # 3. 提示下一步
    log_print("\n💡 下一步：")
    log_print("   - 可继续运行 hunt 获取更多选题")
    log_print("   - 或运行 `python run.py final` 综合所有报告，获得 3 个提示词")

def save_report(raw_data: str, analysis: str, directed_topic: Optional[str] = None) -> None:
    filename = get_topic_report_file()
    mode_info = f"定向搜索: {directed_topic}" if directed_topic else CURRENT_CONFIG['name']
    content = f"# 🚀 选题雷达报告 v4.0 ({mode_info})\n\n**时间**: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n**策略**: {CURRENT_CONFIG['strategy']}\n\n## 深度验证情报\n\n{raw_data}\n\n---\n\n## 选题分析\n\n{analysis}"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(content)
    log_print(f"\n\n📁 报告已保存: {filename}")
    
    # 保存后自动初始化工作流
    auto_init_workflow()

def main(topic=None, dry_run=False):
    """
    选题雷达主入口
    参数:
        topic: 可选，指定搜索主题。
        dry_run: 节流模式，不调用 API。
    """
    mode_text = f"定向搜索: {topic}" if topic else "全网雷达"
    if dry_run:
        mode_text += " (🧪 DRY RUN)"
    
    log_print("\n" + "="*60 + f"\n🚀 选题雷达 v4.0 ({mode_text}) - 王往AI\n" + "="*60 + "\n")
    
    if dry_run:
        log_print("🧪 [Mock] 正在生成模拟热点报告...")
        raw_data = "Source[Mock]: Trending AI news about Google Ears and Agentic workflow."
        analysis = """
### 选题 1：Google AI耳机深度评测：它真的能“听懂”你的工作流吗？
* **心理锚点**：锚点效应
* **核心价值**：抢占AI硬件首发评测认知。
* **热度评级**：⭐⭐⭐⭐⭐
* **推荐理由**：Google最新硬件动向。

---
## 今日主推
Google AI耳机评测，命中了锚点效应。
"""
        save_report(raw_data, analysis, directed_topic=topic)
        log_print("\n✅ [Mock] 选题雷达完成！")
        return

    search_tool = WebSearchTool()
    
    with httpx.Client(proxy=PROXY_URL, timeout=REQUEST_TIMEOUT) as http_client:
        client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL, http_client=http_client)
        
        # 加载历史记录用于去重
        history = load_history()
        history_text = "\n".join([f"- {h['date']}: {h['topic']} ({h['angle']})" for h in history])
        if not history_text: history_text = "无（这是第一篇）"
        
        # 1. 广域扫描 / 定向搜索
        search_plan = step1_broad_scan_and_plan(client, search_tool, directed_topic=topic)
        
        # 2. 深度验证
        raw_data = step2_deep_scan(search_plan, search_tool, directed_topic=topic)
        
        # 3. 决策（传入历史记录用于去重）
        analysis = step3_final_decision(raw_data, client, history_text, directed_topic=topic)
        
        # 4. 保存
        save_report(raw_data, analysis, directed_topic=topic)
    
    log_print("\n✅ 选题雷达完成！")

def _extract_topic_frequencies(reports_content: str) -> Dict[str, Tuple[int, float, str]]:
    """
    v4.8: 从多份报告中提取关键词出现频率，带领域权重
    返回: {keyword: (raw_count, weighted_score, category)}
    
    领域敏感度权重 (PRP要求):
    - 硬核技术类: 2.0
    - 投资金融类: 0.5
    - 通用场景类: 1.0 (但在洞察中标记为"修饰语")
    """
    from collections import Counter
    
    # 分类关键词及其权重
    KEYWORD_CATEGORIES = {
        # === 硬核技术类 (权重 2.0) ===
        "tech": {
            "weight": 2.0,
            "keywords": [
                "DeepSeek", "Cursor", "Gemini", "Claude", "GPT", "Kimi", "Copilot",
                "Windsurf", "Bolt", "Lovable", "秘塔", "豆包", "通义", "智谱", "AutoGLM",
                "Coze", "Agent", "智能体", "MCP", "RAG", "Workflow", "工作流",
                "本地部署", "Ollama", "vLLM", "Prompt", "提示词",
                "架构图", "流程图", "思维导图", "文档分析", "代码生成",
                "API", "SDK", "开源", "GitHub"
            ]
        },
        # === 投资金融类 (权重 0.5) ===
        "finance": {
            "weight": 0.5,
            "keywords": [
                "股价", "上市", "财报", "暴涨", "暴跌", "市值", "融资", "IPO",
                "投资", "股票", "韭菜", "割韭菜", "炒股"
            ]
        },
        # === 通用场景类 (权重 1.0，但标记为修饰语) ===
        "generic": {
            "weight": 1.0,
            "keywords": [
                "免费", "平替", "白嫖", "避坑", "翻车", "教程", "爆款",
                "实时翻译", "AI 耳机", "手机助手"
            ]
        }
    }
    
    results = {}
    content_lower = reports_content.lower()
    
    for category, config in KEYWORD_CATEGORIES.items():
        weight = config["weight"]
        for kw in config["keywords"]:
            count = content_lower.count(kw.lower())
            if count > 0:
                weighted_score = count * weight
                results[kw] = (count, weighted_score, category)
    
    # 按加权分数排序，返回前10
    sorted_results = dict(sorted(results.items(), key=lambda x: x[1][1], reverse=True)[:10])
    return sorted_results


def _generate_topic_insights(freq: Dict[str, Tuple[int, float, str]], reports_count: int) -> str:
    """
    v4.8: 根据频率统计生成选题洞察，带领域标签
    freq: {keyword: (raw_count, weighted_score, category)}
    """
    if not freq:
        return "暂无高频关键词统计。"
    
    CATEGORY_LABELS = {
        "tech": "🔧 硬核技术",
        "finance": "💰 金融类(降权)",
        "generic": "📝 修饰语"
    }
    
    insights = []
    insights.append(f"📊 **关键词热度统计 v4.8** (来自 {reports_count} 份报告，已应用领域权重)：")
    insights.append("   ⚠️ 注意：技术类关键词权重×2.0，金融类×0.5，修饰语仅供参考")
    insights.append("")
    
    for kw, (raw_count, weighted_score, category) in freq.items():
        label = CATEGORY_LABELS.get(category, "")
        
        if category == "tech":
            if weighted_score >= 6:
                insights.append(f"   🔥🔥🔥 **{kw}** [{label}]: {raw_count}次 → 加权{weighted_score:.1f} (极高优先级)")
            elif weighted_score >= 4:
                insights.append(f"   🔥🔥 **{kw}** [{label}]: {raw_count}次 → 加权{weighted_score:.1f} (高优先级)")
            else:
                insights.append(f"   🔥 **{kw}** [{label}]: {raw_count}次 → 加权{weighted_score:.1f}")
        elif category == "finance":
            insights.append(f"   ⚠️ **{kw}** [{label}]: {raw_count}次 → 加权{weighted_score:.1f} (需转化为技术视角)")
        else:  # generic
            insights.append(f"   📝 {kw} [{label}]: {raw_count}次 (仅作修饰，不作为核心选题依据)")
    
    return "\n".join(insights)


def final_summary(dry_run=False):
    """综合当天所有报告，给出最终选题推荐和三个提示词"""
    import glob
    from config import get_today_dir
    
    title_text = "🎯 综合选题决策 v5.0 - 单选题确定模式"
    if dry_run:
        title_text += " (🧪 DRY RUN)"
        
    log_print("\n" + "="*60)
    log_print(title_text)
    log_print("="*60 + "\n")
    
    # 1. 读取当天所有报告
    topics_dir = os.path.join(get_today_dir(), "1_topics")
    reports = glob.glob(os.path.join(topics_dir, "report_*.md"))
    
    if not reports:
        if dry_run:
            log_print("🧪 [Mock] 未找到报告，生成模拟最终决策...")
            final_report = os.path.join(topics_dir, "FINAL_DECISION.md")
            mock_decision = """
### 🏆 今日最终选题
**标题**：别乱用Cursor了！这5个隐藏设置，让你的AI编程效率翻倍
**心理锚点**：损失厌恶
**一句话卖点**：掌握隐藏设置，效率翻倍。
**关键词**：Cursor, AI编程

### 📡 提示词 1：Fast Research
```
1. 搜索 Cursor 最新隐藏设置。
```
"""
            with open(final_report, "w", encoding="utf-8") as f:
                f.write(f"# 🏆 今日最终选题决策 (🧪 Mock)\n\n{mock_decision}")
            save_topic_to_history("Cursor 效率设置", "Mock 决策")
            log_print("\n✅ [Mock] 综合选题完成！")
            return
        log_print("❌ 今日暂无报告，请先运行 `python run.py hunt`")
        return
    
    # 逻辑修正：按时间排序（文件名后缀），识别最后一份报告
    sorted_reports = sorted(reports)
    latest_report_path = sorted_reports[-1]
    
    log_print(f"📊 找到 {len(reports)} 份报告，最新报告为: {os.path.basename(latest_report_path)}")
    
    all_content = []
    latest_recommendation = ""
    directed_topics = []  # {topic: recommendation}
    directed_recommendations = {}  # v4.9: 存储每个定向主题的主推内容
    
    for r in sorted_reports:
        name = os.path.basename(r)
        with open(r, "r", encoding="utf-8") as f:
            content = f.read()
            all_content.append(f"=== {name} ===\n{content}")
            
            # 提取报告中的定向搜索主题
            directed_match = re.search(r'# 🚀 选题雷达报告 v4.0 \(定向搜索: (.*?)\)', content)
            if directed_match:
                d_topic = directed_match.group(1).strip()
                if d_topic not in directed_topics:
                    directed_topics.append(d_topic)
                
                # v4.9: 提取该定向报告的“今日主推”作为选题锚点
                rec_match = re.search(r'## 今日主推\s*(.*?)(?:\n\n|\n##|$)', content, re.DOTALL)
                if rec_match:
                    directed_recommendations[d_topic] = rec_match.group(1).strip()
            
            # 如果是最新报告，尝试提取“今日主推”
            if r == latest_report_path:
                match = re.search(r'## 今日主推\s*(.*?)(?:\n\n|\n##|$)', content, re.DOTALL)
                if match:
                    latest_recommendation = match.group(1).strip()

    combined = "\n\n".join(all_content)
    
    # === v4.1: 预处理 - 关键词频率分析 ===
    topic_freq = _extract_topic_frequencies(combined)
    topic_insights = _generate_topic_insights(topic_freq, len(reports))

    # === v4.9: 增强 Prompt - 定向锚点与发散策略 ===
    weighted_instruction = ""
    
    if directed_topics:
        # 构建定向主题及其对应的推荐选题
        directed_anchor_text = ""
        for dt in directed_topics:
            rec = directed_recommendations.get(dt, "未提取到具体推荐")
            directed_anchor_text += f"\n    - **定向主题**: {dt}\n      **该报告主推**: {rec[:200]}..."
        
        weighted_instruction += f"""
    🎯 **定向选题锚点 (ANCHOR - 最高优先级)**：
    用户通过 `-t` 参数明确指定了以下主题，这是今日选题的「核心锚点」：
    {directed_anchor_text}
    
    🚨 **强制要求 (不可违反)**：
    1. **第一选题必须是定向主题的「精确执行版」**：基于上述报告主推内容，输出可直接使用的爆款标题。
    2. **第二、第三选题必须围绕定向主题发散**：允许偏移角度（如避坑、实测、进阶），但不能偏离用户的搜索意图。
    3. **禁止输出与定向主题无关的选题**：即使其他热点很火，也不能取代定向选题的位置。
    """

    if latest_recommendation and not directed_topics:
        # 只有在没有定向主题时，才使用最新报告的主推作为参考
        weighted_instruction += f"""
    ⭐ **最新情报参考 (Reference)**：
    最近的一份报告建议：【{latest_recommendation[:200]}】
    """

    FINAL_PROMPT = f"""
    {weighted_instruction}
    
    你是"王往AI"，一个**专注硬核 AI 工作流与提效技巧**的技术博主，不是金融分析师，也不是新闻搬运工。
    你的任务：综合分析今天的所有选题报告，选出【1个最终选题】，并输出3个结构化提示词。
    
    ## 🧠 核心人设与价值观 (不可违背)
    1. **唯技术论**：即使是分析公司上市或大厂动作，落脚点也必须是**底层技术、工作流变革、Prompt 技巧**，而非股价、财报或八卦。
    2. **拒绝投机**：禁止生成纯粹的投资理测、股市分析内容。如果涉及到壁仞科技等公司，必须转化为“国产 GPU 的技术生态挑战”或“AI 算力部署避坑”。
    3. **硬核优先**：Coze, Cursor, Agent 工作流, 本地部署等内容的权重永远高于简单的“AI 趣闻”。
    
    ## 🔥 系统预处理：关键词热度分析
    {topic_insights}
    
    ⚠️ **重要决策原则**：
    1. **定向指令绝对优先**：如果用户指定了主题（见上文），必须优先以此为中心进行发散。
    2. **时效性与价值平衡**：越晚生成的报告权重越高，但“硬核价值”是唯一的一票否决权。
    3. **关键词防干扰**：不要被“避坑”、“免费”等通用高频词带偏，它们只是修饰语，核心必须是具体的技术或产品。

## 价值公式 (心理学驱动)
**选题价值** = (信息差 × 认知冲击) + (痛点强度 × 解决效率) - 阅读门槛

心理学策略（三选一，但可混搭）：
1. **锚点效应 (借势)**：借助顶流产品的知名度，用户更容易点击（如 "DeepSeek 隐藏玩法"）
2. **即时满足 (效能)**：让用户觉得"看完就能用"，获得即时正反馈（如 "3分钟学会"）
3. **损失厌恶 (避坑)**：让用户害怕错过或踩坑，触发紧迫感（如 "别再被坑了"）

## 选题标准 (按优先级)
1. **高频热点优先**：多次出现在报告中的关键词说明热度持续，优先选择
2. **大厂动作优先**：Google/OpenAI/DeepSeek 等大厂的新发布、新功能优先级最高
3. **价值多元**：
   - **认知类**：解读新趋势、新硬件（如 AI 耳机、手机智能体），满足求知欲
   - **实操类**：真正的效率神器（如 免费画图），满足即时满足心理
   - **避坑类**：翻车现场、智商税揭秘，满足损失厌恶心理
4. **拒绝平庸**：剔除那些"看起来有用但实际没啥用"的工具

## 输出格式 (v5.0: 单选题确定模式)

### 🏆 今日最终选题 (THE ONE)
**标题**：[爆款标题，15-25字，必须紧扣用户的定向搜索意图]
**心理锚点**：[锚点效应 / 即时满足 / 损失厌恶，选一个主打]
**一句话卖点**：[用户看完能得到什么？认知升级？解决痛点？避开陷阱？]
**关键词**：[3-5个搜索关键词，用于后续素材搜集]

### 💡 备选角度 (供人工调整参考，不作为主输出)
- **角度A**：[从避坑/翻车切入的标题思路]
- **角度B**：[从效率提升/即时满足切入的标题思路]

---

### 📡 提示词 1：Fast Research (用于自动研究 / research 阶段)
```
[请用中文，告诉 Researcher 需要搜索哪些具体内容，包括：
- 官方文档/发布会/Demo
- 行业专家的深度解读/评测
- 用户的真实体验/吐槽
- 竞品对比
格式要求：分条列出，每条一个明确的搜索任务]
```

### 🎨 提示词 2：视觉脚本 (用于配图方案)
```
[请用中文，建议需要准备的配图，包括：
- 关键截图 (如：新功能界面、Demo演示)
- 对比图 (新旧对比、竞品对比)
- 概念图 (如果是抽象概念，如何可视化)
- 封面图风格建议 (高大上、科技感或极简风)]
```

### 🎨 视觉配图指南 (Visual Guide)
**说明**：请为人工配图提供详细的画面建议，帮助博主快速产出高质量素材。
[请用中文列出不少于 3 张关键配图的建议：

封面图：[画面描述，如：科技感流光背景，突出核心关键词]

内页图1：[描述]

内页图2：[描述]

内页图3：[描述] ]
"""

    with httpx.Client(proxy=PROXY_URL, timeout=REQUEST_TIMEOUT) as http_client:
        client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL, http_client=http_client)
        
        try:
            @retryable
            @track_cost(context="final_summary")
            def _chat_create():
                return client.chat.completions.create(
                    model="deepseek-reasoner",
                    messages=[
                        {"role": "system", "content": FINAL_PROMPT},
                        {"role": "user", "content": f"以下是今日的所有选题报告，请综合分析后给出最终推荐：\n\n{combined}"}
                    ],
                    stream=True
                )

            response = _chat_create()
            
            log_print("\n" + "="*60)
            log_print("🏆 最终选题推荐")
            log_print("="*60 + "\n")
            
            collected = []
            for chunk in response:
                if chunk.choices[0].delta.content:
                    c = chunk.choices[0].delta.content
                    log_print(c, end="", flush=True)
                    collected.append(c)
            
            # 保存综合报告
            final_report = os.path.join(topics_dir, "FINAL_DECISION.md")
            content_str = ''.join(collected)
            with open(final_report, "w", encoding="utf-8") as f:
                f.write(f"# 🏆 今日最终选题决策\n\n**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n**综合报告数**: {len(reports)}\n\n{content_str}")
            
            log_print(f"\n\n📁 综合报告已保存: {final_report}")

            # === 自动更新历史记录 (Memory Update) ===
            try:
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
                        log_print(f"⚠️ 使用 Fallback 标题: {fallback_title}")
                    else:
                        log_print("⚠️ 警告: 无法从报告中提取最终选题标题，历史记录未更新。")
                        log_print(f"   调试信息: 内容前200字 -> {content_str[:200].replace(chr(10), ' ')}")
            
            except Exception as e:
                 log_print(f"⚠️ 历史记录更新失败: {e}")
            
        except Exception as e:
            log_print(f"❌ 综合分析失败: {e}")

    log_print("\n✅ 综合选题完成！")


# =============================================================================
# 仿写模式 (Imitate Mode) v1.0
# =============================================================================

def _parse_reference_file(file_path: str) -> str:
    """
    解析参考文章文件，支持 HTML/MD/TXT 等格式
    返回纯文本内容
    """
    import os
    
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"参考文章不存在: {file_path}")
    
    ext = os.path.splitext(file_path)[1].lower()
    
    with open(file_path, "r", encoding="utf-8") as f:
        raw_content = f.read()
    
    # HTML 格式：提取纯文本
    if ext in [".html", ".htm"]:
        soup = BeautifulSoup(raw_content, "html.parser")
        # 移除 script 和 style 标签
        for tag in soup(["script", "style", "nav", "header", "footer"]):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)
        # 清理多余空行
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        return "\n".join(lines)
    
    # Markdown 或纯文本：直接返回
    return raw_content


def _fetch_url_content(url: str) -> str:
    """
    使用 Jina Reader 抓取 URL 内容
    """
    jina_url = f"https://r.jina.ai/{url}"
    log_print(f"   🌐 正在通过 Jina Reader 抓取: {url}")
    
    try:
        with httpx.Client(proxy=PROXY_URL, timeout=REQUEST_TIMEOUT) as client:
            resp = client.get(jina_url)
            resp.raise_for_status()
            content = resp.text
            
            # 保存到本地缓存以便调试
            from config import get_today_dir
            import os
            cache_dir = os.path.join(get_today_dir(), "temp")
            os.makedirs(cache_dir, exist_ok=True)
            cache_file = os.path.join(cache_dir, "last_imitate_raw.md")
            with open(cache_file, "w", encoding="utf-8") as f:
                f.write(content)
            log_print(f"   ✅ 抓取成功，已缓存至: {cache_file}")
            
            return content
    except Exception as e:
        log_print(f"   ❌ URL 抓取失败: {e}")
        raise


def imitate_mode(reference_input: str, dry_run: bool = False):
    """
    仿写模式 v1.1：支持本地文件或 URL
    
    流程：
    1. 获取参考内容（本地解析或 URL 抓取）
    2. LLM 分析：提取主题、关键词、结构、素材类型
    3. 生成搜索计划
    4. 执行搜索并生成 report_*.md
    """
    log_print("\n" + "="*60)
    log_print("📝 仿写模式 v1.1 - 爆款内容分析与创作")
    log_print("="*60 + "\n")
    
    # 1. 获取参考内容
    article_content = ""
    is_url = reference_input.startswith(("http://", "https://"))
    
    if is_url:
        log_print(f"🔗 检测到 URL 输入: {reference_input}")
        try:
            article_content = _fetch_url_content(reference_input)
        except:
            return
    else:
        log_print(f"📖 正在解析本地参考文章: {reference_input}")
        try:
            article_content = _parse_reference_file(reference_input)
        except Exception as e:
            log_print(f"   ❌ 解析失败: {e}")
            return

    try:
        # 限制长度避免 Token 溢出
        if len(article_content) > 15000:
            article_content = article_content[:15000] + "\n\n...(内容已截断)"
            log_print(f"   ⚠️ 内容过长，已截断至 15000 字符")
        log_print(f"   ✅ 内容就绪，共 {len(article_content)} 字符")
    except Exception as e:
        log_print(f"   ❌ 内容处理失败: {e}")
        return
    
    # 2. LLM 分析文章
    log_print("\n🧠 DeepSeek 正在分析文章结构与主题...")
    
    ANALYZE_PROMPT = """你是内容分析专家。请分析以下爆款文章，提取关键信息用于仿写。

## 分析要求
请严格按以下 JSON 格式输出（不要输出其他内容）：

```json
{
    "topic": "核心主题（一句话，如：Cursor 的隐藏效率技巧）",
    "keywords": ["关键词1", "关键词2", "关键词3", "关键词4", "关键词5"],
    "structure": "文章结构（如：痛点引入-方案介绍-案例演示-总结行动）",
    "material_types": ["素材类型1", "素材类型2"],
    "psychology": "心理锚点（锚点效应/即时满足/损失厌恶）",
    "search_queries": ["搜索词1", "搜索词2", "搜索词3"]
}
```

## 字段说明
- topic: 这篇文章的核心主题是什么
- keywords: 5-8个关键词，用于后续搜索相关素材
- structure: 文章的逻辑结构
- material_types: 文章用到的素材类型（如：官方文档、用户案例、竞品对比、截图演示）
- psychology: 这篇文章主要运用了哪种心理学策略
- search_queries: 3个最有价值的搜索词，用于找到类似素材"""

    with httpx.Client(proxy=PROXY_URL, timeout=REQUEST_TIMEOUT) as http_client:
        client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL, http_client=http_client)
        
        try:
            @retryable
            @track_cost(context="imitate_analyze")
            def _analyze():
                return client.chat.completions.create(
                    model="deepseek-chat",
                    messages=[
                        {"role": "system", "content": ANALYZE_PROMPT},
                        {"role": "user", "content": f"请分析以下文章：\n\n{article_content}"}
                    ],
                    response_format={"type": "json_object"}
                )
            
            response = _analyze()
            analysis_text = response.choices[0].message.content
            
            # 解析 JSON
            try:
                analysis = json.loads(analysis_text)
            except:
                analysis = json.loads(repair_json(analysis_text))
            
            log_print(f"   ✅ 分析完成")
            log_print(f"   📌 主题: {analysis.get('topic', '未知')}")
            log_print(f"   🏷️ 关键词: {', '.join(analysis.get('keywords', []))}")
            log_print(f"   🧠 心理锚点: {analysis.get('psychology', '未知')}")
            
            if dry_run:
                log_print("\n🧪 [Dry Run] 分析结果预览:")
                log_print(json.dumps(analysis, ensure_ascii=False, indent=2))
                log_print("\n🧪 [Dry Run] 仿写模式验证成功，不执行实际操作。")
                return
            
            # 3. v5.2: 跳过 Hunt 扫描，直接生成最终决策
            log_print(f"\n🚀 [极速仿写] 跳过扫描，正在直接生成最终决策...")
            
            from config import get_stage_dir, get_research_notes_file
            topics_dir = Path(get_stage_dir("topics"))
            final_report = topics_dir / "FINAL_DECISION.md"
            
            # 保存原文素材到 research 目录，供后续 draft 参考
            research_dir = Path(get_stage_dir("research"))
            source_file = research_dir / "imitation_source.txt"
            with open(source_file, "w", encoding="utf-8-sig") as f:
                f.write(article_content)
            log_print(f"   📥 已保存仿写原文素材: {source_file}")

            # 构建符合 FINAL_DECISION.md 格式的内容
            # 选题 1 为精确仿写版
            topic_title = analysis.get("topic", "未命名仿写选题")
            keywords = ", ".join(analysis.get("keywords", []))
            psychology = analysis.get("psychology", "锚点效应")
            
            # 为 Researcher 生成任务描述
            search_queries = analysis.get("search_queries", [])
            research_tasks = "\n".join([f"{i+1}. {q}" for i, q in enumerate(search_queries)])
            
            final_decision_content = f"""# 🏆 今日最终选题决策 (极速仿写模式)

**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M')}
**仿写来源**: {reference_input if is_url else os.path.basename(reference_input)}

## 输出格式 (v5.0: 单选题确定模式)

### 🏆 今日最终选题 (THE ONE)
**标题**：{topic_title}
**心理锚点**：{psychology}
**一句话卖点**：基于深度仿写分析，旨在重现原文的爆款结构与情绪价值。
**关键词**：{keywords}

### 💡 备选角度 (仿写模式不提供备选)
- **角度A**：仿写模式下，系统全力聚焦于唯一目标。

---

### 📡 提示词 1：Fast Research (用于自动研究 / research 阶段)
```
请作为研究员，围绕选题《{topic_title}》进行深度搜索和素材搜集：
1. 核心搜索任务：
{research_tasks}
2. 结构参考：
{analysis.get("structure", "保持原文逻辑结构")}
3. 重点：结合仿写原文中的素材类型（{", ".join(analysis.get("material_types", []))}），搜集最新的可替代素材。
```

### 🎨 提示词 2：视觉脚本 (用于配图方案)
```
1. 参考原文的视觉风格，为《{topic_title}》准备配图建议。
2. 重点展示：新版功能的实际界面、操作流程。
```

### 🎨 视觉配图指南 (Visual Guide)
**说明**：请为人工配图提供详细的画面建议。
封面图：[科技感流光背景，突出主题：{topic_title}]
内页图1：[功能操作截图演示]
内页图2：[效果对比图]
"""
            with open(final_report, "w", encoding="utf-8-sig") as f:
                f.write(final_decision_content)
            
            # 更新历史记录
            save_topic_to_history(topic_title, f"仿写: {psychology}")
            
            log_print(f"✅ 极速仿写完成！FINAL_DECISION.md 已生成。")
            log_print(f"💡 下一步：直接运行 `python main.py research` 开始深度研究。")
            
        except Exception as e:
            log_print(f"❌ 仿写模式运行失败: {e}")
            import traceback
            log_print(traceback.format_exc())


if __name__ == "__main__":
    main()
