"""
🚀 全网选题雷达 (Trend Hunter Agent) v7.0 - 终极价值挖掘版
核心升级：
1. 矩阵化 WATCHLIST：覆盖模型、编程、效率工具三类顶流，外加通用教程类目。
2. 心理学搜索策略：引入"即时满足"(B路)和"损失厌恶"(C路)搜索模型。
3. 价值排序算法：基于"获得感"进行加权，剔除宏大叙事。
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
    get_stage_dir, get_research_notes_file
)

# ================= 配置区 =================

# 长期关注矩阵 (流量基本盘)
WATCHLIST = [
    # 顶流模型
    "DeepSeek", "Kimi", "通义千问", "GPT-4o", "Gemini", "Grok",
    # 编程神器
    "Cursor", "Windsurf", "Claude Code", "GitHub Copilot",
    # 效率应用
    "夸克AI", "豆包", "秘塔搜索", "腾讯元宝",
    # 通用类目
    "AI教程", "AI副业", "效率神器"
]

# 运营阶段配置
OPERATIONAL_PHASE = "VALUE_HACKER" # 价值黑客

PHASE_CONFIG = {
    "VALUE_HACKER": {
        "name": "价值黑客模式",
        "weights": {"news": 0.5, "social": 2.5, "github": 1.0}, # 极度重社交和痛点
        "strategy": "利用心理学锚点(收益/损失)，挖掘能给用户带来'获得感'的选题。",
        "prompt_suffix": "⚠️ 绝对原则：像一个'生活黑客'一样思考。剔除所有'新闻报道'，只保留'解决方案'。如果是工具，必须是普通人手机/电脑能装的；如果是教程，必须是小白能看懂的。"
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
    
    def search(self, query, max_results=5, include_answer=False):
        if not self.enabled: return []
        print(f"   🔍 Tavily: {query}")
        url = "https://api.tavily.com/search"
        payload = {
            "api_key": self.api_key, "query": query, "search_depth": "basic",
            "max_results": max_results, "include_answer": include_answer
        }
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

# ================= 核心逻辑 =================

PLAN_PROMPT = """
你是"王往AI"的首席内容策略官。
请基于【全网情报】和【心理学策略】，挖掘 3 个最具"爆款潜质"的选题方向。

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
    {
        "event": "选题核心词 (如: DeepSeek)",
        "angle": "切入角度 (如: 隐藏玩法 / 避坑指南)",
        "news_query": "功能性搜索词 (如: DeepSeek V3 file upload)",
        "social_query": "情绪性搜索词 (如: DeepSeek 报错 / DeepSeek 不好用)"
    },
    ...
]
"""

def step1_broad_scan_and_plan(client, search_tool):
    """Step 1: 广域价值扫描 (心理学三路策略)"""
    print(f"\n📡 [Step 1] 广域价值扫描 (策略: {CURRENT_CONFIG['name']})...")
    
    pre_scan_results = []
    
    # === A路: 顶流锚点 (Watchlist) ===
    # 随机选 3 个顶流，搜"玩法"
    targets = random.sample(WATCHLIST, 3)
    print(f"   🎯 [A路-锚点] 扫描顶流: {targets}")
    for t in targets:
        res = search_tool.search(f"{t} 隐藏功能 玩法 教程 2025", max_results=2)
        pre_scan_results.extend(res)
        
    # === B路: 即时满足 (Life Hack) ===
    # 搜"神器"、"黑科技"
    print(f"   ⚡ [B路-收益] 扫描效率神器...")
    queries = ["本周 AI 效率神器 推荐", "AI 自动化办公 教程", "Notion AI 替代品"]
    for q in queries:
        res = search_tool.search(q, max_results=2)
        pre_scan_results.extend(res)
        
    # === C路: 损失厌恶 (Pain Points) ===
    # 搜"避坑"、"智商税"
    print(f"   🛡️ [C路-损失] 扫描避坑/吐槽...")
    queries = ["AI工具 智商税 避坑", "AI眼镜 翻车", "AI 写作 查重"]
    for q in queries:
        res = search_tool.search(q, max_results=2)
        pre_scan_results.extend(res)
    
    pre_scan_text = "\n".join([f"- {r['title']}: {r['body'][:80]}" for r in pre_scan_results])
    
    # 2. 智能筛选与规划
    print(f"   📝 情报聚合完毕，DeepSeek 正在应用心理学策略选题...")
    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": PLAN_PROMPT},
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

def step3_final_decision(scan_data, client):
    """Step 3: 决策"""
    print("\n" + "="*50 + "\n📝 DeepSeek 主编审核中...\n" + "="*50)
    
    prompt = f"""
    {EDITOR_PROMPT}
    
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
        
        # 1. 广域扫描 (Watchlist + Trend + Pain)
        search_plan = step1_broad_scan_and_plan(client, search_tool)
        
        # 2. 深度验证
        raw_data = step2_deep_scan(search_plan, search_tool)
        
        # 3. 决策
        analysis = step3_final_decision(raw_data, client)
        
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

### ✍️ 提示词 2：草稿大纲 (用于生成文章框架)
**使用方法**：复制到 NotebookLM，让它根据已导入的 Sources 来完善大纲
```
请根据来源内容来完善下面草稿大纲，输出完整的文章初稿：

[给出一个完整的文章大纲，包括：
- 开头 Hook (如何在3秒内抓住读者)
- 痛点描述 (读者共鸣)
- 解决方案 (手把手步骤)
- 进阶技巧 (额外价值)
- 结尾 Call to Action]
```

### 🎨 提示词 3：视觉脚本 (用于配图方案)
**使用方法**：复制到 NotebookLM Chat，然后点击右侧 Studio → **Infographic** 生成信息图
```
[请用中文，建议需要准备的配图，包括：
- 关键截图 (哪个界面、哪个步骤)
- 对比图 (什么 vs 什么)
- 流程图 (如果有复杂流程)
- 封面图风格建议
- 信息图要点 (适合用 Infographic 生成的数据/对比)]
```
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
            with open(final_report, "w", encoding="utf-8") as f:
                f.write(f"# 🏆 今日最终选题决策\n\n**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n**综合报告数**: {len(reports)}\n\n{''.join(collected)}")
            
            print(f"\n\n📁 综合报告已保存: {final_report}")
            
        except Exception as e:
            print(f"❌ 综合分析失败: {e}")

    print("\n✅ 综合选题完成！")

if __name__ == "__main__":
    main()
