"""
🚀 全网选题雷达 (Trend Hunter Agent) v3.0 - Tavily 联网版
核心升级：
1. 支持 Tavily API (稳定、专为 AI 优化)
2. DeepSeek 动态生成搜索词
3. 保留 GitHub Trending 作为补充
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
import httpx
from datetime import datetime
from bs4 import BeautifulSoup
from openai import OpenAI
from config import (
    DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, PROXY_URL, REQUEST_TIMEOUT,
    TAVILY_API_KEY, get_topic_report_file, get_today_dir
)

# ================= Tavily 搜索工具 =================

class WebSearchTool:
    """Tavily AI Search - 专为 LLM 优化的搜索 API"""
    
    def __init__(self):
        self.api_key = TAVILY_API_KEY
        self.enabled = bool(self.api_key and len(self.api_key) > 10)
        if self.enabled:
            print("   ✅ Tavily Search API 已启用")
        else:
            print("   ⚠️ 未配置 Tavily API，搜索功能受限")
    
    def search(self, query, max_results=5):
        """执行 Tavily 搜索"""
        if not self.enabled:
            return []
        
        print(f"   🔍 Tavily: {query}")
        url = "https://api.tavily.com/search"
        payload = {
            "api_key": self.api_key,
            "query": query,
            "search_depth": "basic",
            "max_results": max_results,
            "include_answer": True
        }
        try:
            with httpx.Client(timeout=30) as client:
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

def get_github_trending():
    """抓取 GitHub Trending"""
    print("   🔍 GitHub Trending...")
    url = "https://github.com/trending/python?since=daily"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        with httpx.Client(proxy=PROXY_URL, timeout=15) as client:
            resp = client.get(url, headers=headers)
        soup = BeautifulSoup(resp.text, 'html.parser')
        repos = soup.select('article.Box-row')
        results = []
        for repo in repos[:8]:
            name_tag = repo.select_one('h1 a') or repo.select_one('h2 a')
            if not name_tag: continue
            name = name_tag.get_text(strip=True).replace('\n', '').replace(' ', '')
            desc = repo.select_one('p').get_text(strip=True) if repo.select_one('p') else ""
            results.append(f"- {name}: {desc}")
        return results
    except Exception as e:
        return [f"- GitHub 抓取失败: {e}"]

# ================= DeepSeek 思考链 =================

SEARCH_PLAN_PROMPT = """
你是"王往AI"的选题助理。请根据今天日期，生成 5 个最值得搜索的 AI 热点关键词。

要求：
1. 时效性：包含当前年月，如 "DeepSeek V3 December 2025"
2. 针对性：关注大模型发布、评测、GitHub 爆款、AI 工具
3. 多样性：中英文混合

输出：仅输出关键词，逗号分隔。
"""

EDITOR_PROMPT = """你叫"王往AI"，专注 AI 工作流的硬核博主。
请根据以下【全网情报】筛选 3 个最值得写的选题。

⚠️ 选题优先级：
1. **重大突发**：如 DeepSeek V3.2 发布、GPT-5 上线
2. **争议话题**：如 AI 程序员取代人类、开源 vs 闭源
3. **实战干货**：如 Cursor 深度评测、Agent 工作流

输出格式：
### 选题 1：[标题]
* **热度来源**：[具体的搜索结果]
* **推荐理由**：[为什么现在写会火]
* **核心看点**：[文章大纲]
---
## 今日主推
告诉我不写会后悔的那个。"""

def run_search_plan(client):
    """Step 1: DeepSeek 规划搜索词"""
    print("\n🧠 DeepSeek 正在思考今日搜索策略...")
    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": SEARCH_PLAN_PROMPT},
                {"role": "user", "content": f"今天是 {datetime.now().strftime('%Y-%m-%d')}"}
            ],
            temperature=0.7
        )
        keywords = [k.strip() for k in response.choices[0].message.content.strip().split(',') if k.strip()]
        print(f"📝 搜索计划: {keywords}\n")
        return keywords[:5]
    except Exception as e:
        print(f"❌ 思考失败: {e}")
        return ["DeepSeek V3 最新消息", "AI Agent 工具 2025", "LLM 评测排行"]

def execute_search(keywords, search_tool):
    """Step 2: 执行 Tavily 搜索"""
    print("📡 开始全网扫描...\n")
    all_results = []
    
    for kw in keywords:
        results = search_tool.search(kw, max_results=4)
        if results:
            all_results.append(f"\n=== 搜索: {kw} ===")
            for r in results:
                title = r.get('title', '')
                body = r.get('body', '')[:200] if r.get('body') else ''
                url = r.get('url', '')
                all_results.append(f"- [{title}]({url})\n  {body}...")
        time.sleep(0.5)
    
    # 补充 GitHub
    print("\n📡 补充扫描 GitHub Trending...")
    github_res = get_github_trending()
    all_results.append("\n=== GitHub Trending ===")
    all_results.extend(github_res)
    
    return "\n".join(all_results)

def final_decision(search_results, client):
    """Step 3: DeepSeek 生成选题报告"""
    print("\n" + "="*50 + "\n📝 DeepSeek 主编审核中...\n" + "="*50)
    try:
        response = client.chat.completions.create(
            model="deepseek-reasoner",
            messages=[
                {"role": "system", "content": EDITOR_PROMPT},
                {"role": "user", "content": f"【今日全网情报】\n{search_results}"}
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
        return search_results, "".join(collected)
    except Exception as e:
        print(f"❌ 决策失败: {e}")
        return search_results, f"失败: {e}"

def save_report(raw_data, analysis):
    filename = get_topic_report_file()
    content = f"# 🚀 选题雷达报告 v3.0\n\n**时间**: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n## 全网情报\n{raw_data}\n\n## 选题分析\n{analysis}"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"\n\n📁 报告已保存: {filename}")

def main():
    print("\n" + "="*60 + "\n🚀 全网选题雷达 v3.0 (Tavily 联网版) - 王往AI\n" + "="*60 + "\n")
    
    # 初始化搜索工具
    search_tool = WebSearchTool()
    
    with httpx.Client(proxy=PROXY_URL, timeout=REQUEST_TIMEOUT) as http_client:
        client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL, http_client=http_client)
        
        # 1. 思考：规划搜索词
        keywords = run_search_plan(client)
        
        # 2. 执行：Tavily 搜索
        raw_data = execute_search(keywords, search_tool)
        
        # 3. 决策：生成选题
        _, analysis = final_decision(raw_data, client)
        
        # 4. 保存报告
        save_report(raw_data, analysis)
    
    print("\n✅ 选题雷达完成！")

if __name__ == "__main__":
    main()
