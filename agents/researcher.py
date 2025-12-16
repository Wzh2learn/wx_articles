"""
===============================================================================
                    🔬 研究智能体 (Researcher Agent) v4.0 (Hardcore Edition)
===============================================================================
核心策略：
1. 智能聚合搜索：Exa AI (优先) + Tavily (兜底)，全网深度挖掘。
2. 批判性评估过滤器：在笔记整理阶段，自动识别并标记“智商税”工具。
3. 反套壳机制：强制提取底层技术原理，拒绝营销软文。
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
from openai import OpenAI
from tavily import TavilyClient
from config import (
    DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, 
    TAVILY_API_KEY, EXA_API_KEY,
    PROXY_URL, REQUEST_TIMEOUT, get_research_notes_file, get_logger, retryable
)


logger = get_logger(__name__)


class ResearcherAgent:
    """自动化研究智能体：Exa AI 搜索 + 内容聚合 + 笔记整理"""
    
    def __init__(self):
        # 初始化 DeepSeek 客户端
        # 使用统一配置中的代理；如不需要代理请在 config.py 中将 PROXY_URL 设为 None
        proxy_url = PROXY_URL
        self.client = OpenAI(
            api_key=DEEPSEEK_API_KEY,
            base_url=DEEPSEEK_BASE_URL,
            http_client=httpx.Client(proxy=proxy_url, timeout=REQUEST_TIMEOUT)
        )
        
        # 初始化 Tavily (备用)
        self.tavily = TavilyClient(api_key=TAVILY_API_KEY)
        
        self.exa_api_key = EXA_API_KEY
        self.proxy_url = proxy_url
        
        logger.info("✅ ResearcherAgent v4.0 初始化完成 (Exa + Tavily)")

    def search_exa(self, topic: str, queries: List[str]) -> List[Dict[str, Any]]:
        """
        使用 Exa AI 进行高级搜索 (自动包含内容)
        """
        if not self.exa_api_key:
            logger.warning("未配置 EXA_API_KEY，跳过 Exa 搜索")
            return []

        logger.info("🔍 [Step 1] Exa AI 智能搜索 (Topic: %s)...", topic)
        
        all_results = []
        headers = {
            "Authorization": f"Bearer {self.exa_api_key}",
            "Content-Type": "application/json"
        }
        
        # Exa API 端点
        url = "https://api.exa.ai/search"

        # 定义搜索批次
        # 1. 社交媒体专项 (指定域名)
        social_domains = [
            "mp.weixin.qq.com", "zhihu.com", "weibo.com", 
            "xiaohongshu.com", "v2ex.com", "juejin.cn"
        ]
        
        batches = [
            # Batch 1: 针对社交媒体的精准搜索
            {
                "query": f"{topic} 深度解析 避坑指南 教程",
                "numResults": 8,
                "includeDomains": social_domains,
                "useAutoprompt": True, # 让 Exa 优化查询
                "contents": {"text": True} # 直接获取正文
            },
            # Batch 2: 全网通用搜索 (寻找最新/高质量长文)
            {
                "query": topic,
                "numResults": 5,
                "useAutoprompt": True,
                "contents": {"text": True}
            }
        ]
        
        @retryable
        def _exa_post(client: httpx.Client, payload: dict, headers: dict):
            return client.post(url, json=payload, headers=headers)

        with httpx.Client(timeout=60, proxy=self.proxy_url) as client:
            for i, payload in enumerate(batches):
                try:
                    logger.info("🚀 Exa Batch %s 请求中...", i + 1)
                    resp = _exa_post(client, payload, headers)
                    resp.raise_for_status()
                    data = resp.json()
                    
                    results = data.get("results", [])
                    for res in results:
                        all_results.append({
                            "url": res.get("url"),
                            "title": res.get("title"),
                            "text": res.get("text", ""), # Exa 直接返回的正文
                            "source": "Exa"
                        })
                        logger.info("✓ [Exa] %s...", (res.get('title', 'Unknown') or '')[:40])
                        
                except Exception as e:
                    logger.error("❌ Exa Batch %s 失败: %s", i + 1, e)

        return all_results

    def search_tavily_fallback(self, queries: List[str]) -> List[Dict[str, Any]]:
        """
        Tavily 备用搜索 (仅获取 URL，无正文)
        """
        logger.info("🔄 [Fallback] 切换至 Tavily 并发搜索...")
        
        all_results = []
        seen_urls = set()
        
        # 构造查询
        extended_queries = []
        for q in queries:
            extended_queries.append({"q": q, "type": "general"})
            extended_queries.append({"q": f"{q} site:mp.weixin.qq.com", "type": "wechat"})
            extended_queries.append({"q": f"{q} site:zhihu.com", "type": "zhihu"})
        
        @retryable
        def _tavily_search(query: str, limit: int):
            return self.tavily.search(
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
                except Exception as e:
                    logger.error("❌ 失败: %s", e)

    def synthesize_notes(self, items: List[Dict[str, Any]], topic: str, strategic_intent: Optional[str] = None) -> str:
        """
        整理所有素材为笔记 (带批判性评估过滤器)
        
        核心逻辑：
        1. 唯技术论：只提取底层技术/Prompt/本地部署相关内容。
        2. 鄙视套壳：识别并标记国内付费套壳工具为“避坑黑名单”。
        """
        logger.info("📝 [Step 3] AI 整理笔记...")
        
        # 拼接所有素材
        raw_text = ""
        for item in items:
            text = item.get("text", "")
            if len(text) > 100:
                raw_text += f"\n{'='*50}\nSource: {item['url']}\nTitle: {item.get('title')}\n{'='*50}\n{text[:8000]}\n"
        
        if not raw_text:
            return "# 研究失败：未获取到有效内容"

        strategic_block = ("\n\n" + "="*20 + "\n" + "【选题策划书 / 战略意图（最高指令）】\n" + (strategic_intent or "") + "\n" + "="*20 + "\n") if strategic_intent else ""

        prompt = f"""你是一位专业内容研究员和资深技术博主。请根据以下多篇来源文章，为公众号文章《{topic}》整理素材。{strategic_block}
        
        ⚠️ **核心价值观（必须严格遵守）**：
        1. **唯技术论**：我们只推崇**底层大模型（DeepSeek, ChatGPT, Claude）** + **提示词工程**。
        2. **鄙视套壳**：所有国内号称“一键降重”、“AI写作神器”的付费工具（如**笔灵、小发猫、PaperYY、嘎嘎**等），一律视为**“低技术含量的套壳产品”**。
        3. **证据搜集**：如果素材中吹捧这些付费工具，请忽略其营销话术，重点挖掘它们的缺点（如收费贵、底层模型未知、隐私风险）。

        ⚠️ **战略意图对齐（必须执行）**：
        - 如果上面的“选题策划书”强调了“避坑/平替/白嫖/提效/省钱/省时/情绪共鸣”等关键词，你的笔记必须围绕它选材与组织结构。
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
        1. 核心观点 (标注来源)
        2. 关键数据/案例 (标注来源)
        3. **避坑黑名单**：将所有“付费套壳工具”归入此类，并说明理由（智商税）。
        4. **真正的高阶玩法**：寻找关于**Prompt优化、多模型交叉验证、本地部署(Ollama)**等硬核内容。
        
        输出为清晰的 Markdown 格式。
        """

        try:
            @retryable
            def _chat_create():
                return self.client.chat.completions.create(
                    model="deepseek-chat",
                    messages=[
                        {"role": "system", "content": prompt},
                        {"role": "user", "content": f"素材内容：\n{raw_text[:60000]}"} # 控制总长度
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


    def run(self, topic: str, queries: List[str], strategic_intent: Optional[str] = None) -> str:
        logger.info("%s", "="*60)
        logger.info("🔬 ResearcherAgent v4.0 (Exa AI)")
        logger.info("📌 选题: %s", topic)
        logger.info("%s", "="*60)

        # 1. Exa 搜索 (优先)
        results = self.search_exa(topic, queries)

        # 2. 如果 Exa 结果太少，使用 Tavily 补充
        if len(results) < 3:
            tavily_results = self.search_tavily_fallback(queries)
            results.extend(tavily_results)

        if not results:
            logger.warning("⚠️ 未找到任何内容")
            return ""

        # 3. 补充爬取 (针对 Tavily 来源或 Exa 没抓到正文的)
        self.scrape_missing_content(results)

        # 4. 整理笔记
        notes = self.synthesize_notes(results, topic, strategic_intent=strategic_intent)

        # 保存
        notes_file = get_research_notes_file()
        with open(notes_file, "w", encoding="utf-8") as f:
            intent_section = f"\n\n## 🎯 战略意图（来自 FINAL_DECISION.md）\n\n{strategic_intent.strip()}\n" if strategic_intent else ""
            f.write(f"# 🔬 自动研究笔记 (Exa AI)\n\n**选题**: {topic}\n**时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n{intent_section}\n---\n\n{notes}")

        logger.info("📁 笔记已保存: %s", notes_file)
        return notes

def main():
    agent = ResearcherAgent()
    agent.run("DeepSeek V3 隐藏功能", ["DeepSeek 教程"])

if __name__ == "__main__":
    main()
