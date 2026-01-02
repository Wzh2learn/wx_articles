"""
===============================================================================
                    🔬 研究智能体 (Researcher Agent) v4.2 (Hardcore Edition)
===============================================================================
核心策略：
1. 智能聚合搜索：Exa AI (优先) + Tavily (兜底)，全网深度挖掘。
2. 批判性评估过滤器：在笔记整理阶段，自动识别并标记“智商税”工具。
3. 反套壳机制：强制提取底层技术原理，拒绝营销软文。
4. v4.2 新增：Fast Research 指引解析 + 精准搜索查询生成
===============================================================================
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Optional, List, Dict, Any
from pathlib import Path
from openai import OpenAI
from tavily import TavilyClient
from config import (
    DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, 
    TAVILY_API_KEY, EXA_API_KEY, PERPLEXITY_API_KEY,
    PROXY_URL, REQUEST_TIMEOUT, get_research_notes_file, get_logger, retryable, track_cost
)


logger = get_logger(__name__)


class ResearcherAgent:
    """自动化研究智能体：Exa AI 搜索 + 内容聚合 + 笔记整理"""
    
    def __init__(self):
        # 初始化 DeepSeek 客户端
        proxy_url = PROXY_URL
        self.client = OpenAI(
            api_key=DEEPSEEK_API_KEY,
            base_url=DEEPSEEK_BASE_URL,
            http_client=httpx.Client(proxy=proxy_url, timeout=REQUEST_TIMEOUT)
        )
        
        # 初始化各搜索 API 状态
        self.tavily_key = TAVILY_API_KEY
        self.pplx_key = PERPLEXITY_API_KEY
        self.exa_key = EXA_API_KEY
        self.proxy_url = proxy_url
        
        self.pplx_enabled = bool(self.pplx_key and len(self.pplx_key) > 10)
        self.tavily_enabled = bool(self.tavily_key and len(self.tavily_key) > 10)
        self.exa_enabled = bool(self.exa_key and len(self.exa_key) > 10)
        
        logger.info("✅ ResearcherAgent v4.3 初始化完成 (Priority: Perplexity -> Tavily -> Exa)")

    def search_perplexity(self, query: str) -> List[Dict[str, Any]]:
        """Perplexity API: 获取模型生成的摘要作为核心研究素材"""
        if not self.pplx_enabled: return []
        logger.info("🔍 [Step 1.1] Perplexity 深度搜索摘要...")
        url = "https://api.perplexity.ai/chat/completions"
        payload = {
            "model": "sonar",
            "messages": [
                {"role": "system", "content": "你是一个专业的AI研究助手。请针对用户的查询提供详细、准确且带有来源摘要的回答。输出应包含核心技术点、行业趋势、真实案例以及用户痛点。"},
                {"role": "user", "content": query}
            ],
            "temperature": 0.2,
            "search_recency_filter": "week"
        }
        headers = {
            "Authorization": f"Bearer {self.pplx_key}",
            "Content-Type": "application/json"
        }
        try:
            with httpx.Client(timeout=45, proxy=self.proxy_url) as client:
                @retryable
                @track_cost(context="perplexity_research")
                def _post():
                    return client.post(url, json=payload, headers=headers)
                
                resp = _post()
                if resp.status_code != 200:
                    logger.warning(f"Perplexity 报错: {resp.status_code}")
                    return []
                
                data = resp.json()
                content = data['choices'][0]['message']['content']
                return [{
                    "url": "https://perplexity.ai",
                    "title": "Perplexity AI Research Summary",
                    "text": content,
                    "source": "Perplexity"
                }]
        except Exception as e:
            logger.error(f"Perplexity 调用失败: {e}")
            return []

    def search_exa(self, topic: str, queries: List[str]) -> List[Dict[str, Any]]:
        """
        使用 Exa AI 进行高级搜索 (自动包含内容)
        v4.2: 增强查询利用，使用 queries 进行多批次精准搜索
        """
        if not self.exa_api_key:
            logger.warning("未配置 EXA_API_KEY，跳过 Exa 搜索")
            return []

        logger.info("🔍 [Step 1] Exa AI 智能搜索...")
        logger.info("   📌 主题: %s", topic)
        logger.info("   🔑 查询词: %s", queries[:5])
        
        all_results = []
        seen_urls = set()  # 去重
        headers = {
            "Authorization": f"Bearer {self.exa_api_key}",
            "Content-Type": "application/json"
        }
        
        # Exa API 端点
        url = "https://api.exa.ai/search"

        # 定义搜索批次
        # 1. 社交媒体专项 (指定域名)
        social_domains = [
            "mp.weixin.qq.com", "weibo.com", 
            "xiaohongshu.com", "v2ex.com", "juejin.cn"
        ]
        
        batches = [
            # Batch 1: 针对社交媒体的精准搜索 (使用主题)
            {
                "query": f"{topic} 深度解析 避坑指南 教程",
                "numResults": 5,
                "includeDomains": social_domains,
                "useAutoprompt": True,
                "contents": {"text": True}
            },
            # Batch 2: 全网通用搜索 (使用主题)
            {
                "query": topic,
                "numResults": 3,
                "useAutoprompt": True,
                "contents": {"text": True}
            }
        ]
        
        # v4.2: 为每个精准查询词添加搜索批次
        for q in queries[:4]:  # 最多取前4个查询词
            if q != topic and len(q) > 5:
                batches.append({
                    "query": q,
                    "numResults": 3,
                    "useAutoprompt": True,
                    "contents": {"text": True}
                })
        
        @retryable
        def _exa_post(client: httpx.Client, payload: dict, headers: dict):
            return client.post(url, json=payload, headers=headers)

        with httpx.Client(timeout=60, proxy=self.proxy_url) as client:
            for i, payload in enumerate(batches):
                try:
                    logger.info("🚀 Exa Batch %s 请求中 (query: %s)...", i + 1, payload.get('query', '')[:30])
                    resp = _exa_post(client, payload, headers)
                    resp.raise_for_status()
                    data = resp.json()
                    
                    results = data.get("results", [])
                    for res in results:
                        res_url = res.get("url", "")
                        # v4.2: URL 去重
                        if res_url in seen_urls:
                            continue
                        seen_urls.add(res_url)
                        
                        all_results.append({
                            "url": res_url,
                            "title": res.get("title"),
                            "text": res.get("text", ""),
                            "source": "Exa"
                        })
                        logger.info("✓ [Exa] %s...", (res.get('title', 'Unknown') or '')[:40])
                        
                except Exception as e:
                    logger.error("❌ Exa Batch %s 失败: %s", i + 1, e)

        logger.info("   📊 Exa 共获取 %d 条去重结果", len(all_results))
        return all_results

    def search_tavily_fallback(self, queries: List[str]) -> List[Dict[str, Any]]:
        """
        Tavily 备用搜索 (仅获取 URL，无正文)
        """
        if not self.tavily_enabled: return []
        logger.info("🔄 [Fallback] 切换至 Tavily 并发搜索...")
        
        from tavily import TavilyClient
        tavily_client = TavilyClient(api_key=self.tavily_key)
        
        all_results = []
        seen_urls = set()
        
        # 构造查询
        extended_queries = []
        for q in queries:
            extended_queries.append({"q": q, "type": "general"})
            extended_queries.append({"q": f"{q} site:mp.weixin.qq.com", "type": "wechat"})
            extended_queries.append({"q": f"{q} site:xiaohongshu.com", "type": "xhs"})
        
        @retryable
        def _tavily_search(query: str, limit: int):
            return tavily_client.search(
                query=query,
                search_depth="advanced",
                max_results=limit,
                days=30
            )

        def do_search(item):
            try:
                limit = 2 if item['type'] == "general" else 1
                resp = _tavily_search(item['q'], limit)
                return resp.get('results', [])
            except Exception as e:
                logger.warning("Tavily 搜索失败: %s", e)
                return []

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(do_search, item) for item in extended_queries]
            for future in as_completed(futures):
                for res in future.result():
                    if res['url'] not in seen_urls and "pdf" not in res['url']:
                        seen_urls.add(res['url'])
                        all_results.append({
                            "url": res['url'],
                            "title": res['title'],
                            "text": "", # Tavily 不含全文，需后续爬取
                            "source": "Tavily"
                        })
                        logger.info("✓ [Tavily] %s...", (res.get('title', '') or '')[:40])
        
        return all_results[:8]

    def scrape_missing_content(self, items: List[Dict[str, Any]]) -> None:
        """
        对缺少正文的条目 (如来自 Tavily) 进行补充爬取
        使用 Jina Reader + Fallback
        """
        missing_items = [i for i in items if not i.get("text") or len(i.get("text")) < 200]
        if not missing_items:
            return
            
        logger.info("📖 [Step 2] 补充爬取 %s 个页面 (Jina/Fallback)...", len(missing_items))
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        
        crawled_texts = []
        
        @retryable
        def _http_get(client: httpx.Client, url: str, headers: Optional[dict] = None):
            return client.get(url, headers=headers)

        with httpx.Client(timeout=60, proxy=self.proxy_url, follow_redirects=True) as client:
            for item in missing_items:
                url = item['url']
                logger.info("🌐 爬取: %s...", (item.get('title', '') or '')[:30])
                
                try:
                    # Jina
                    jina_resp = _http_get(client, f"https://r.jina.ai/{url}", headers=headers)
                    if jina_resp.status_code == 200 and len(jina_resp.text) > 500:
                        item['text'] = jina_resp.text
                        logger.info("✓ Jina 成功")
                        continue
                except:
                    pass
                
                try:
                    # Direct Fallback
                    raw_resp = _http_get(client, url, headers=headers)
                    if raw_resp.status_code == 200:
                        # 极其简陋的文本提取
                        from bs4 import BeautifulSoup
                        soup = BeautifulSoup(raw_resp.text, 'html.parser')
                        for s in soup(['script', 'style']): s.extract()
                        item['text'] = soup.get_text()[:10000]
                        logger.info("✓ 直连成功")
                        continue
                except Exception as e:
                    pass

                # 3. Tavily 兜底 (作为提取器)
                try:
                    if self.tavily:
                        #以此 URL 为 query 进行搜索，并请求 raw_content
                        tavily_resp = self.tavily.search(
                            query=url,
                            include_raw_content=True,
                            max_results=1
                        )
                        if tavily_resp and 'results' in tavily_resp and tavily_resp['results']:
                            raw_content = tavily_resp['results'][0].get('raw_content')
                            if raw_content:
                                item['text'] = raw_content[:10000]
                                logger.info("✓ Tavily 兜底成功 (Raw Content)")
                                continue
                except Exception as e:
                    logger.error("❌ Tavily 兜底失败: %s", e)
                
                logger.error("❌ 所有获取手段均失败")

    def synthesize_notes(self, items: List[Dict[str, Any]], topic: str, strategic_intent: Optional[str] = None, imitation_source: str = "") -> str:
        """
        整理所有素材为笔记 (带批判性评估过滤器)
        
        核心逻辑：
        1. 唯技术论：只提取底层技术/Prompt/本地部署相关内容。
        2. 鄙视套壳：识别并标记国内付费套壳工具为“避坑黑名单”。
        """
        logger.info("📝 [Step 3] AI 整理笔记...")
        
        # 聚合所有文本
        combined_text = ""
        if imitation_source:
            combined_text += f"=== 仿写原文素材 (重点参考) ===\n{imitation_source}\n\n"
        
        for item in items:
            text = item.get("text", "")
            if not text or len(text.strip()) < 50:
                logger.warning(f"⚠️ [内容缺失] 忽略条目: {item.get('title', 'Unknown')} (无正文)")
                continue
                
            if len(text) > 100:
                combined_text += f"\n{'='*50}\nSource: {item['url']}\nTitle: {item.get('title')}\n{'='*50}\n{text[:8000]}\n"
        
        if not combined_text:
            return "# 研究失败：未获取到有效内容"

        strategic_block = ("\n\n" + "="*20 + "\n" + "【选题策划书 / 战略意图（最高指令）】\n" + (strategic_intent or "") + "\n" + "="*20 + "\n") if strategic_intent else ""

        prompt = f"""你是一位专业内容研究员和资深技术博主。请根据以下多篇来源文章，为公众号文章《{topic}》整理素材。{strategic_block}
        
        ⚠️ **流量与社交调研增强 (Social Packaging)**：
        1. **搜集爆款角度**：除了技术实现，必须挖掘该话题在社交媒体（小红书/微博/公众号）上的“爆款因子”。
        2. **神评论与吐槽**：寻找用户对该工具/现象的最真实吐槽、神评论或体感变化描述。
        3. **转发动机**：分析为什么普通人会想转发这篇文章？（是因为能省钱、能装逼、还是能避坑？）

        ⚠️ **核心价值观（必须严格遵守）**：
        1. **唯技术论**：我们只推崇**底层大模型（DeepSeek, ChatGPT, Claude）** + **提示词工程**。
        2. **鄙视套壳**：所有国内号称“一键降重”、“AI写作神器”的付费工具（如**笔灵、小发猫、PaperYY、嘎嘎**等），一律视为**“低技术含量的套壳产品”**。
        3. **证据搜集**：如果素材中吹捧这些付费工具，请忽略其营销话术，重点挖掘它们的缺点（如收费贵、底层模型未知、隐私风险）。

        - 你的输出必须显式覆盖策划书中的：
          1) 一句话卖点（读者获得感）
          2) 心理锚点（读者为什么会点开/会焦虑什么）
          3) 核心看点（文章必须覆盖的要点/结构）
        - 如果素材与策划书冲突：优先保留“可证据支持”的内容，并在笔记中标注“与策划书假设不一致”。

        ⚠️ **信息不足兜底（必须执行）**：
        - 如果“选题策划书”里点名了某个具体工具/项目（例如 block/goose），但在素材中搜不到足够信息，请在笔记中明确标注：**“信息不足”**，并解释缺失点（如：缺官方文档/缺真实体验/缺近期更新）。
        - 同时，你必须主动寻找一个“同类型的 GitHub 高星项目 / 官方替代方案”作为备选，并写清楚：
          1) 为什么它是同类型
          2) 它的核心能力
          3) 它与策划书目标的匹配度（卖点/锚点/核心看点）
        - 目的：不允许写作端出现“开天窗”。
        
        请提取：
        1. **## 社交货币与舆情分析**：包含 3 个爆款角度、用户神评论/吐槽、以及读者的转发动机分析。
        2. **核心观点 (标注来源)**：重点关注“场景”而非“参数”。
        3. **关键数据/案例 (标注来源)**：特别是那些具有“视觉冲击力”或“戏剧性结果”的案例。
        4. **避坑黑名单**：将所有“付费套壳工具”归入此类，并说明理由（智商税）。
        5. **真正的高阶玩法**：寻找关于**Prompt优化、多模型交叉验证、本地部署(Ollama)**等硬核内容。
        
        输出为清晰的 Markdown 格式。
        """

        try:
            @retryable
            @track_cost(context="synthesize_notes")
            def _chat_create():
                return self.client.chat.completions.create(
                    model="deepseek-chat",
                    messages=[
                        {"role": "system", "content": prompt},
                        {"role": "user", "content": f"素材内容：\n{combined_text[:60000]}"} # 控制总长度
                    ],
                    temperature=0.3,
                    max_tokens=4000,
                    stream=True
                )

            response = _chat_create()

            logger.info("%s", "="*20 + " 笔记生成中 " + "="*20)

            collected = []
            for chunk in response:
                content = chunk.choices[0].delta.content
                if content:
                    sys.stdout.write(content)
                    sys.stdout.flush()
                    collected.append(content)
            sys.stdout.write("\n")
            sys.stdout.flush()

            return "".join(collected)

        except Exception as e:
            logger.error("❌ 整理失败: %s", e)
            return f"整理失败: {e}"


    def _generate_search_queries_from_fast_research(self, fast_research: str, topic: str) -> List[str]:
        """
        v4.2: 从 Fast Research 指引中提取精准搜索查询
        使用 LLM 将结构化指引转换为实际搜索查询
        """
        logger.info("🧠 [Step 0] 从 Fast Research 指引生成精准搜索查询...")
        
        prompt = f"""你是一个搜索查询生成专家。根据以下"研究指引"，生成 5-8 个精准的搜索查询词。

【研究指引】
{fast_research}

【文章主题】
{topic}

【输出要求】
1. 每行一个搜索查询，不要编号
2. 查询要具体、精准，能找到高质量的技术文章/教程/评测
3. 优先包含：项目名称、技术术语、教程/评测/对比等关键词
4. 避免过于宽泛的查询

直接输出搜索查询列表，不要其他内容："""

        try:
            @retryable
            @track_cost(context="generate_search_queries")
            def _chat_create():
                return self.client.chat.completions.create(
                    model="deepseek-chat",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.3,
                    max_tokens=500
                )
            
            response = _chat_create()
            queries_text = response.choices[0].message.content.strip()
            queries = [q.strip() for q in queries_text.split('\n') if q.strip() and len(q.strip()) > 3]
            
            logger.info("   ✅ 生成了 %d 个精准搜索查询", len(queries))
            for q in queries[:5]:
                logger.info("      - %s", q[:50])
            
            return queries
        except Exception as e:
            logger.error("   ❌ 查询生成失败: %s", e)
            return []

    def run(self, topic: str, queries: List[str], strategic_intent: Optional[str] = None, fast_research: Optional[str] = None, dry_run: bool = False) -> str:
        logger.info("%s", "="*60)
        logger.info("🔬 ResearcherAgent v4.3 (Multi-Search)%s", " (🧪 DRY RUN)" if dry_run else "")
        logger.info("📌 选题: %s", topic)
        logger.info("%s", "="*60)

        if dry_run:
            # ... (keep dry run logic)
            logger.info("🧪 [Mock] 正在生成模拟研究笔记...")
            mock_notes = f"""
## 1. 社交货币与舆情分析
- **爆款角度**：Cursor 的隐藏设置是典型的“信息差”红利，普通人还在搜指令，高手已经在立规矩。
- **神评论**：'开了这几个开关，Cursor 终于不乱删我代码了！'
- **转发动机**：避坑、省钱、提效。

## 2. 核心观点
- Cursor Rules (.mdc) 是控制 AI 的核心。
- MCP Server 让 AI 具备实时联网能力。

## 3. 关键数据/案例
- 开启 Rules 后，代码重构出错率降低 60%。

## 4. 避坑黑名单
- 严禁无脑 Accept All。
- 拒绝使用国内昂贵的套壳工具。

## 5. 真正的高阶玩法
- 使用 .cursor/rules 定义项目级规范。
- 接入 Perplexity MCP 获取最新 API 文档。
"""
            # 保存 Mock 笔记
            notes_file = get_research_notes_file()
            with open(notes_file, "w", encoding="utf-8") as f:
                intent_section = f"\n\n## 🎯 战略意图摘要\n\n{strategic_intent.strip()}\n" if strategic_intent else ""
                f.write(f"# 🔬 自动研究笔记 v4.3 (🧪 Mock)\n\n**选题**: {topic}\n**时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n{intent_section}\n---\n\n{mock_notes}")
            logger.info("📁 [Mock] 笔记已保存: %s", notes_file)
            return mock_notes

        # v4.2: 如果有 Fast Research 指引，生成更精准的搜索查询
        if fast_research:
            generated_queries = self._generate_search_queries_from_fast_research(fast_research, topic)
            if generated_queries:
                queries = generated_queries + queries  # 合并：精准查询优先
                queries = list(dict.fromkeys(queries))[:10]  # 去重，限制数量

        results = []
        
        # 1. 首选 Perplexity 获取摘要
        pplx_results = self.search_perplexity(topic)
        if pplx_results:
            results.extend(pplx_results)
            logger.info("   ✅ 已获取 Perplexity 研究摘要")

        # 2. 无论是否有 pplx，都通过 Tavily 或 Exa 获取更多参考链接和正文
        # 优先 Tavily (因为快且稳)，Exa 作为兜底
        search_results = []
        if self.tavily_enabled:
            search_results = self.search_tavily_fallback(queries)
        
        # 3. 如果 Tavily 失败或没结果，尝试 Exa 兜底
        if not search_results and self.exa_enabled:
            search_results = self.search_exa(topic, queries)
            
        results.extend(search_results)

        if not results:
            logger.warning("⚠️ 所有搜索通道均未找到有效内容")
            return ""

        # 4. 补充爬取 (针对 Tavily 来源或 Exa 没抓到正文的)
        # 注意：Perplexity 结果已经自带 content (text 字段)，不需要爬取
        self.scrape_missing_content(results)

        # v5.2: 检查是否有仿写原文素材，如果有，将其加入研究背景
        imitation_source = ""
        from config import get_stage_dir
        source_file = Path(get_stage_dir("research")) / "imitation_source.txt"
        if source_file.exists():
            try:
                imitation_source = source_file.read_text(encoding="utf-8")
                logger.info("   📄 发现仿写原文素材，已加入研究背景")
            except Exception as e:
                logger.warning("   ⚠️ 读取仿写素材失败: %s", e)

        # 5. 整理笔记
        notes = self.synthesize_notes(results, topic, strategic_intent=strategic_intent, imitation_source=imitation_source)

        # 保存
        notes_file = get_research_notes_file()
        with open(notes_file, "w", encoding="utf-8") as f:
            intent_section = f"\n\n## 🎯 战略意图摘要\n\n{strategic_intent.strip()}\n" if strategic_intent else ""
            f.write(f"# 🔬 自动研究笔记 v4.3\n\n**选题**: {topic}\n**时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n{intent_section}\n---\n\n{notes}")

        logger.info("📁 笔记已保存: %s", notes_file)
        return notes

def main():
    agent = ResearcherAgent()
    agent.run("DeepSeek V3 隐藏功能", ["DeepSeek 教程"])

if __name__ == "__main__":
    main()
