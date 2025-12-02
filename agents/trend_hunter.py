"""
🚀 全网选题雷达 (Trend Hunter Agent) v2.1 - 强化版
新增：全网 AI 热点搜索，降低 GitHub 权重，提升新闻/评测权重
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx, time

# 搜索重试次数
MAX_RETRIES = 3
from datetime import datetime
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS
from openai import OpenAI
from config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, PROXY_URL, REQUEST_TIMEOUT, get_topic_report_file, get_today_dir

def get_github_trending():
    print("🔍 [1/7] 扫描 GitHub Trending...")
    url = "https://github.com/trending/python?since=daily"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    try:
        with httpx.Client(proxy=PROXY_URL, timeout=15) as client:
            resp = client.get(url, headers=headers)
            resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')
        repos = soup.select('article.Box-row') or soup.select('.Box-row')
        results = []
        for repo in repos[:10]:
            name_tag = repo.select_one('h2 a') or repo.select_one('h1 a')
            if not name_tag: continue
            name = name_tag.get_text(strip=True).replace('\n', '').replace(' ', '')
            desc_tag = repo.select_one('p.col-9') or repo.select_one('p')
            desc = desc_tag.get_text(strip=True) if desc_tag else ""
            results.append(f"{name}: {desc}")
        return results if results else ["GitHub 暂无数据"]
    except Exception as e:
        return [f"GitHub 抓取失败: {e}"]

def get_readhub_news():
    print("🔍 [2/7] 扫描 ReadHub 科技新闻...")
    url = "https://api.readhub.cn/topic?lastCursor=&pageSize=15"
    try:
        with httpx.Client(proxy=PROXY_URL, timeout=10) as client:
            resp = client.get(url)
            data = resp.json()
        items = data.get('data', [])
        return [item.get('title', '') for item in items] or ["ReadHub 暂无数据"]
    except Exception as e:
        return [f"ReadHub 抓取失败: {e}"]

def search_with_retry(query, site_domain=None, max_results=8):
    """带重试机制的 DuckDuckGo 搜索"""
    for attempt in range(MAX_RETRIES):
        try:
            with DDGS(proxy=PROXY_URL) as ddgs:
                search_query = f"site:{site_domain} {query}" if site_domain else query
                results = [r.get('title', '') for r in ddgs.text(search_query, region='cn-zh', timelimit='w', max_results=max_results) if r.get('title')]
                if results:
                    return results
        except Exception as e:
            time.sleep(1)
    return []

def get_global_ai_news():
    """全网 AI 热点搜索 - 核心新增功能"""
    print("🔍 [3/7] 扫描全网 AI 热点新闻...")
    # 增加更多新闻导向的搜索词，减少代码库干扰
    queries = [
        "AI 人工智能 最新新闻 2025",
        "大模型 发布 更新 2025",
        "GPT Claude Gemini DeepSeek 评测 2025",
        "AI 工具 爆款 推荐 2025",
        "人工智能 行业动态 2025",
        "LLM 大语言模型 最新进展"
    ]
    all_results = []
    for q in queries:
        results = search_with_retry(q, max_results=6)
        all_results.extend(results)
    unique_results = list(set(all_results))
    print(f"   ✓ 获取到 {len(unique_results)} 条全网热点")
    return unique_results if unique_results else ["全网搜索暂无结果"]

def search_platform(site_domain, site_name, query="AI 工具"):
    print(f"🔍 扫描 {site_name}...")
    results = search_with_retry(query, site_domain, max_results=8)
    return results if results else [f"{site_name} 暂无数据"]

def scan_all_sources():
    all_titles = []
    
    # 1. GitHub (降权，仅作参考，放最后收集)
    github_data = get_github_trending()
    
    # 2. ReadHub 科技新闻
    readhub_data = get_readhub_news()
    all_titles.extend(readhub_data)  # 新闻优先加入
    
    # 3. 全网 AI 热点 (核心，高权重，优先加入)
    global_news = get_global_ai_news()
    all_titles.extend(global_news)  # 全网热点优先加入
    
    # 4-6. 社交平台
    print("🔍 [4/7] 扫描小红书...")
    xiaohongshu_data = search_platform("xiaohongshu.com", "小红书", "AI工具 教程")
    all_titles.extend(xiaohongshu_data)
    
    print("🔍 [5/7] 扫描微博...")
    weibo_data = search_platform("weibo.com", "微博", "AI 人工智能")
    all_titles.extend(weibo_data)
    
    print("🔍 [6/7] 扫描少数派...")
    sspai_data = search_platform("sspai.com", "少数派", "AI 效率 工具")
    all_titles.extend(sspai_data)
    
    # GitHub 最后加入，降低其在热词提取中的权重
    all_titles.extend(github_data)
    
    return {
        "github": github_data, 
        "readhub": readhub_data, 
        "global_news": global_news,
        "xiaohongshu": xiaohongshu_data, 
        "weibo": weibo_data, 
        "sspai": sspai_data, 
        "all_titles": all_titles
    }

KEYWORD_PROMPT = """你是热点分析师。请分析以下混合了新闻、社交媒体和代码库的标题数据。

任务：提取当前 AI 圈最火的 5 个具体话题或产品名。

⚠️ 重要规则：
1. **新闻事件优先**：如 "Gemini 2.0 发布", "DeepSeek V3 评测", "OpenAI 发布会"
2. **GitHub 项目降权**：除非是现象级项目（如当年的 ChatGPT、AutoGPT），否则不要选 GitHub 仓库名
3. **关注大模型动态**：GPT、Claude、Gemini、DeepSeek、Kimi 等模型的更新、评测、对比
4. 忽略纯技术术语（如 "v0.1.0 release", "fix bug"）

输出：只输出关键词，用逗号分隔。"""

def extract_hot_keywords(all_titles, http_client):
    print("\n🧠 [7/7] DeepSeek 正在分析全网热词...\n")
    client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL, http_client=http_client)
    titles_text = "\n".join(all_titles[:80])
    try:
        response = client.chat.completions.create(
            model="deepseek-chat", messages=[{"role": "system", "content": KEYWORD_PROMPT},
            {"role": "user", "content": f"标题：\n{titles_text}"}], temperature=0.3)
        keywords = [kw.strip() for kw in response.choices[0].message.content.strip().split(',') if kw.strip()]
        print(f"📊 今日热词：{keywords}\n")
        return keywords[:5]
    except Exception as e:
        print(f"热词提取失败: {e}")
        return ["DeepSeek", "AI Agent", "效率工具"]

def search_wechat_by_keywords(keywords):
    print("🔍 搜索微信公众号竞品...\n")
    all_results = []
    for kw in keywords:
        print(f"  ├─ 关键词: {kw}")
        try:
            with DDGS(proxy=PROXY_URL) as ddgs:
                results = [f"    • {r.get('title', '')}" for r in ddgs.text(f"site:mp.weixin.qq.com {kw}", region='cn-zh', timelimit='w', max_results=3)]
                all_results.append(f"【{kw}】\n" + ("\n".join(results) if results else "    • 暂无"))
        except Exception as e:
            all_results.append(f"【{kw}】\n    • 搜索失败: {e}")
        time.sleep(0.5)
    return "\n\n".join(all_results)

EDITOR_PROMPT = """你叫"王往AI"，专注 AI 工作流的硬核博主。
请根据以下【全网情报】筛选 3 个最值得写的选题。

⚠️ 选题优先级（重要）：
1. **新闻事件 > 评测对比 > 工具教程 > 代码库介绍**
2. 优先选择：模型发布（如 Gemini/DeepSeek/Claude 更新）、评测排名、争议话题、爆款工具
3. GitHub 项目：除非它极具颠覆性（如当年的 AutoGPT），否则降权处理
4. 必须从"全网热点"中选至少 1 个话题

输出格式：
### 选题 1：[标题]
* **热度来源**：[来源，如新闻/微博/评测视频]
* **推荐理由**：[为什么现在写会火]
* **核心看点**：[具体写什么]
---
## 今日主推
告诉我不写会后悔的那个。"""

def final_decision(scan_data, hot_keywords, wechat_data, http_client):
    print("\n" + "="*50 + "\n📝 DeepSeek 主编审核中...\n" + "="*50 + "\n")
    client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL, http_client=http_client)
    # 报告顺序：全网热点优先，GitHub 降权放最后
    full_report = f"""=== 🔥 全网 AI 热点 (重点关注) ===
{chr(10).join(scan_data['global_news'])}

=== 📰 ReadHub 科技新闻 ===
{chr(10).join(scan_data['readhub'])}

=== 📱 微博/小红书/少数派 ===
{chr(10).join(scan_data['weibo'] + scan_data['xiaohongshu'] + scan_data['sspai'])}

=== 💻 GitHub Trending (仅供参考) ===
{chr(10).join(scan_data['github'])}

=== 🏷️ 提取热词 ===
{', '.join(hot_keywords)}

=== 📝 公众号竞品 ===
{wechat_data}"""
    try:
        response = client.chat.completions.create(
            model="deepseek-reasoner", messages=[{"role": "system", "content": EDITOR_PROMPT},
            {"role": "user", "content": full_report}], stream=True)
        print("\n" + "="*20 + " 选题报告 " + "="*20 + "\n")
        collected = []
        for chunk in response:
            if chunk.choices[0].delta.content:
                c = chunk.choices[0].delta.content
                print(c, end="", flush=True)
                collected.append(c)
        print("\n\n" + "="*50 + "\n")
        return full_report, "".join(collected)
    except Exception as e:
        print(f"决策失败: {e}")
        return full_report, f"失败: {e}"

def save_report(raw_data, hot_keywords, analysis):
    filename = get_topic_report_file()
    content = f"# 🚀 选题雷达报告\n\n**时间**: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n**目录**: {get_today_dir()}\n\n## 热词\n> {', '.join(hot_keywords)}\n\n## 情报\n```\n{raw_data}\n```\n\n## 分析\n{analysis}"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"📁 报告已保存: {filename}")

def main():
    print("\n" + "="*60 + "\n🚀 全网选题雷达 v2.1 (强化版) - 王往AI\n" + "="*60 + "\n")
    print("📡 Step 1/4: 广域扫描 (含全网 AI 热点)...\n")
    scan_data = scan_all_sources()
    print("\n📡 Step 2/4: 热词蒸馏...")
    with httpx.Client(proxy=PROXY_URL, timeout=REQUEST_TIMEOUT) as http_client:
        hot_keywords = extract_hot_keywords(scan_data['all_titles'], http_client)
        print("\n📡 Step 3/4: 竞品验证...")
        wechat_data = search_wechat_by_keywords(hot_keywords)
        print("\n📡 Step 4/4: 最终决策...")
        raw_data, analysis = final_decision(scan_data, hot_keywords, wechat_data, http_client)
    save_report(raw_data, hot_keywords, analysis)
    print("\n✅ 选题雷达完成！")

if __name__ == "__main__":
    main()
