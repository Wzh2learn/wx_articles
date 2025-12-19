"""
🕵️ 审计智能体 (Auditor Agent) v1.0
功能：事实核查，对比 final.md 与 notes.txt，防止幻觉。
"""
import sys
import os

# 添加项目根目录到 path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx
from openai import OpenAI
from config import (
    DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, PROXY_URL, REQUEST_TIMEOUT,
    get_research_notes_file, get_final_file, get_today_file, get_logger, retryable, track_cost
)

logger = get_logger(__name__)

SYSTEM_PROMPT = """你是一位严谨的【科技文章事实核查员】（Fact Checker）。
你的任务是对比【事实源（Research Notes）】和【待核查文章（Final Draft）】，找出文章中可能存在的“事实错误”或“AI幻觉”。

核心核查点：
1. **价格/收费模式**：文章说免费，笔记里是否确认为免费？有没有遗漏“仅限试用”等限制？
2. **版本号/模型名称**：DeepSeek V3 还是 V2？GPT-4o 还是 4.0？必须精准。
3. **核心功能**：文章吹嘘的功能，笔记里有证据吗？
4. **数据/参数**：上下文窗口大小、跑分数据等是否一致？

输出规范：
请输出一份 Markdown 格式的核查报告。

如果全篇无实质性事实错误，请直接输出：
# ✅ 核查通过
（可以附带一句简短评价）

如果有风险，请按以下格式输出：
# ⚠️ 核查发现潜在风险

## 1. [错误类型：价格/功能/版本]
- **原文**：“...”
- **笔记事实**：“...” (或者“笔记未提及”)
- **修改建议**：...

## 2. ...
"""

def audit_article():
    logger.info("🕵️ 启动审计智能体 (Fact Checker)...")
    
    # 1. 读取文件
    notes_file = get_research_notes_file()
    final_file = get_final_file()
    
    if not os.path.exists(notes_file):
        logger.error(f"❌ 找不到研究笔记: {notes_file}")
        return "## ⚠️ Audit Skipped\nReason: Missing input files (notes or draft)."
    if not os.path.exists(final_file):
        logger.error(f"❌ 找不到待核查文章: {final_file}")
        return "## ⚠️ Audit Skipped\nReason: Missing input files (notes or draft)."
        
    with open(notes_file, "r", encoding="utf-8") as f:
        notes_content = f.read()
    
    with open(final_file, "r", encoding="utf-8") as f:
        article_content = f.read()
        
    if not notes_content.strip() or not article_content.strip():
        logger.warning("⚠️ 文件内容为空，无法核查")
        return "## ⚠️ Audit Skipped\nReason: Missing input files (notes or draft)."

    logger.info(f"📚 载入笔记: {len(notes_content)} 字符")
    logger.info(f"📝 载入文章: {len(article_content)} 字符")

    # 2. 调用 LLM 进行核查
    logger.info("🔍 正在进行深度事实比对...")
    
    user_prompt = f"""
【事实源 (Research Notes)】
{notes_content[:20000]} 

【待核查文章 (Final Draft)】
{article_content}
"""
    
    try:
        with httpx.Client(proxy=PROXY_URL, timeout=REQUEST_TIMEOUT) as http_client:
            client = OpenAI(
                api_key=DEEPSEEK_API_KEY, 
                base_url=DEEPSEEK_BASE_URL,
                http_client=http_client
            )
            
            @retryable
            @track_cost(context="audit_article")
            def _chat_create():
                return client.chat.completions.create(
                    model="deepseek-chat", # 使用 chat 模型即可，reasoner 可能过慢且昂贵
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt}
                    ],
                    stream=True
                )
            
            response = _chat_create()
            
            # 流式接收
            collected = []
            print("\n" + "="*20 + " 审计报告 " + "="*20)
            for chunk in response:
                content = chunk.choices[0].delta.content
                if content:
                    sys.stdout.write(content)
                    sys.stdout.flush()
                    collected.append(content)
            print("\n" + "="*50 + "\n")
            
            report_content = "".join(collected)
            
            # 3. 保存报告
            # 保存到 publish 目录
            report_file = get_today_file("audit_report.md", "publish")
            with open(report_file, "w", encoding="utf-8") as f:
                f.write(report_content)
                
            logger.info(f"📄 审计报告已保存: {report_file}")
            
            # 简单判断结果
            if "✅" in report_content:
                logger.info("✅ 文章通过核查！")
            else:
                logger.warning("⚠️ 发现潜在问题，请根据报告修正 final.md")
            
            return report_content

    except Exception as e:
        logger.error(f"❌ 核查失败: {e}")
        return f"## ⚠️ Audit Skipped\nReason: {e}"

if __name__ == "__main__":
    audit_article()
