"""
===============================================================================
                    🔬 研究智能体 (Researcher Agent) v4.0 (硬核价值版)
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
from openai import OpenAI
from tavily import TavilyClient
from config import (
    DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, 
    TAVILY_API_KEY, EXA_API_KEY,
    PROXY_URL, REQUEST_TIMEOUT, get_research_notes_file
)


class ResearcherAgent:
    """自动化研究智能体：Exa AI 搜索 + 内容聚合 + 笔记整理"""
    
    def __init__(self):
        # 初始化 DeepSeek 客户端
        # 强制使用系统代理确保连接稳定
        proxy_url = PROXY_URL or "http://127.0.0.1:7898"
        self.client = OpenAI(
            api_key=DEEPSEEK_API_KEY,
            base_url=DEEPSEEK_BASE_URL,
            http_client=httpx.Client(proxy=proxy_url, timeout=REQUEST_TIMEOUT)
        )
        
        # 初始化 Tavily (备用)
        self.tavily = TavilyClient(api_key=TAVILY_API_KEY)
        
        self.exa_api_key = EXA_API_KEY
        self.proxy_url = proxy_url
        
        print(f"   ✅ ResearcherAgent v2.0 初始化完成 (Exa + Tavily)")

    def search_exa(self, topic: str, queries: list[str]) -> list[dict]:
        """
        使用 Exa AI 进行高级搜索 (自动包含内容)
        """
        if not self.exa_api_key:
            print("   ⚠️ 未配置 EXA_API_KEY，跳过 Exa 搜索")
            return []

        print(f"\n🔍 [Step 1] Exa AI 智能搜索 (Topic: {topic})...")
        
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
        
        with httpx.Client(timeout=60, proxy=self.proxy_url) as client:
            for i, payload in enumerate(batches):
                try:
                    print(f"   🚀 Exa Batch {i+1} 请求中...")
                    resp = client.post(url, json=payload, headers=headers)
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
                        print(f"      ✓ [Exa] {res.get('title', 'Unknown')[:40]}...")
                        
                except Exception as e:
                    print(f"      ❌ Exa Batch {i+1} 失败: {e}")

        return all_results

    def search_tavily_fallback(self, queries: list[str]) -> list[dict]:
        """
        Tavily 备用搜索 (仅获取 URL，无正文)
        """
        print(f"\n🔄 [Fallback] 切换至 Tavily 并发搜索...")
        
        all_results = []
        seen_urls = set()
        
        # 构造查询
        extended_queries = []
        for q in queries:
            extended_queries.append({"q": q, "type": "general"})
            extended_queries.append({"q": f"{q} site:mp.weixin.qq.com", "type": "wechat"})
            extended_queries.append({"q": f"{q} site:zhihu.com", "type": "zhihu"})
        
        def do_search(item):
            try:
                limit = 2 if item['type'] == "general" else 1
                resp = self.tavily.search(
                    query=item['q'], 
                    search_depth="advanced", 
                    max_results=limit,
                    days=30
                )
                return resp.get('results', [])
            except:
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
                        print(f"      ✓ [Tavily] {res['title'][:40]}...")
        
        return all_results[:8]

    def scrape_missing_content(self, items: list[dict]) -> str:
        """
        对缺少正文的条目 (如来自 Tavily) 进行补充爬取
        使用 Jina Reader + Fallback
        """
        missing_items = [i for i in items if not i.get("text") or len(i.get("text")) < 200]
        if not missing_items:
            return ""
            
        print(f"\n📖 [Step 2] 补充爬取 {len(missing_items)} 个页面 (Jina/Fallback)...")
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        
        crawled_texts = []
        
        with httpx.Client(timeout=60, proxy=self.proxy_url, follow_redirects=True) as client:
            for item in missing_items:
                url = item['url']
                print(f"   🌐 爬取: {item.get('title', '')[:30]}...")
                
                try:
                    # Jina
                    jina_resp = client.get(f"https://r.jina.ai/{url}", headers=headers)
                    if jina_resp.status_code == 200 and len(jina_resp.text) > 500:
                        item['text'] = jina_resp.text
                        print(f"      ✓ Jina 成功")
                        continue
                except:
                    pass
                
                try:
                    # Direct Fallback
                    raw_resp = client.get(url, headers=headers)
                    if raw_resp.status_code == 200:
                        # 极其简陋的文本提取
                        from bs4 import BeautifulSoup
                        soup = BeautifulSoup(raw_resp.text, 'html.parser')
                        for s in soup(['script', 'style']): s.extract()
                        item['text'] = soup.get_text()[:10000]
                        print(f"      ✓ 直连成功")
                except Exception as e:
                    print(f"      ❌ 失败: {e}")

        return ""

    def synthesize_notes(self, items: list[dict], topic: str) -> str:
        """
        整理所有素材为笔记 (带批判性评估过滤器)
        
        核心逻辑：
        1. 唯技术论：只提取底层技术/Prompt/本地部署相关内容。
        2. 鄙视套壳：识别并标记国内付费套壳工具为“避坑黑名单”。
        """
        print(f"\n📝 [Step 3] AI 整理笔记...")
        
        # 拼接所有素材
        raw_text = ""
        for item in items:
            text = item.get("text", "")
            if len(text) > 100:
                raw_text += f"\n{'='*50}\nSource: {item['url']}\nTitle: {item.get('title')}\n{'='*50}\n{text[:8000]}\n"
        
        if not raw_text:
            return "# 研究失败：未获取到有效内容"

        prompt = f"""你是一位专业内容研究员和资深技术博主。请根据以下多篇来源文章，为公众号文章《{topic}》整理素材。
        
        ⚠️ **核心价值观（必须严格遵守）**：
        1. **唯技术论**：我们只推崇**底层大模型（DeepSeek, ChatGPT, Claude）** + **提示词工程**。
        2. **鄙视套壳**：所有国内号称“一键降重”、“AI写作神器”的付费工具（如**笔灵、小发猫、PaperYY、嘎嘎**等），一律视为**“低技术含量的套壳产品”**。
        3. **证据搜集**：如果素材中吹捧这些付费工具，请忽略其营销话术，重点挖掘它们的缺点（如收费贵、底层模型未知、隐私风险）。
        
        请提取：
        1. 核心观点 (标注来源)
        2. 关键数据/案例 (标注来源)
        3. **避坑黑名单**：将所有“付费套壳工具”归入此类，并说明理由（智商税）。
        4. **真正的高阶玩法**：寻找关于**Prompt优化、多模型交叉验证、本地部署(Ollama)**等硬核内容。
        
        输出为清晰的 Markdown 格式。
        """

        try:
            response = self.client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": f"素材内容：\n{raw_text[:60000]}"} # 控制总长度
                ],
                temperature=0.3,
                max_tokens=4000,
                stream=True
            )
            
            print("\n" + "="*20 + " 笔记生成中 " + "="*20 + "\n")
            collected = []
            for chunk in response:
                content = chunk.choices[0].delta.content
                if content:
                    print(content, end="", flush=True)
                    collected.append(content)
            print("\n")
            return "".join(collected)
            
        except Exception as e:
            print(f"   ❌ 整理失败: {e}")
            return f"整理失败: {e}"

    def run(self, topic: str, queries: list[str]) -> str:
        print("\n" + "="*60)
        print(f"🔬 ResearcherAgent v2.0 (Exa AI)")
        print(f"📌 选题: {topic}")
        print("="*60)
        
        # 1. Exa 搜索 (优先)
        results = self.search_exa(topic, queries)
        
        # 2. 如果 Exa 结果太少，使用 Tavily 补充
        if len(results) < 3:
            tavily_results = self.search_tavily_fallback(queries)
            results.extend(tavily_results)
        
        if not results:
            print("⚠️ 未找到任何内容")
            return ""
            
        # 3. 补充爬取 (针对 Tavily 来源或 Exa 没抓到正文的)
        self.scrape_missing_content(results)
        
        # 4. 整理笔记
        notes = self.synthesize_notes(results, topic)
        
        # 保存
        notes_file = get_research_notes_file()
        with open(notes_file, "w", encoding="utf-8") as f:
            f.write(f"# 🔬 自动研究笔记 (Exa AI)\n\n**选题**: {topic}\n**时间**: {__import__('datetime').datetime.now()}\n\n---\n\n{notes}")
            
        print(f"\n📁 笔记已保存: {notes_file}")
        return notes

def main():
    agent = ResearcherAgent()
    agent.run("DeepSeek V3 隐藏功能", ["DeepSeek 教程"])

if __name__ == "__main__":
    main()
