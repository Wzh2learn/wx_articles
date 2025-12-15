"""
===============================================================================
                    ✨ 润色智能体 (Refiner Agent) v4.0 (Hardcore Edition)
===============================================================================
根据用户的自然语言指令，对草稿进行定向修改，生成定稿。

使用方法：
    python run.py refine "把开头改得更有悬念"
    python run.py refine  # 交互式输入
===============================================================================
"""

import sys
import os

# 添加项目根目录到 path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx
from openai import OpenAI
import config

# ================= 系统提示词 =================

SYSTEM_PROMPT = """## Role
你是一位拥有 10w+ 阅读量经验的科技公众号主编"王往AI"。你的文风硬核、真诚、口语化，擅长把复杂技术讲得像朋友聊天一样简单有趣。

## Task
请根据用户提供的【修改指令】和【文章原稿】，对文章进行深度润色和逻辑重组，输出一篇可以直接发布的 Markdown 定稿。

## ⚠️ 严格约束 (关键！)

### 1. 格式死线
- **绝对保留**所有 `> TODO:` 开头的配图占位符行，不要修改括号里的搜索词。
- **绝对保留** Markdown 标题层级 (`#`, `##`, `###`) 和加粗强调 (`**`)。
- 不要把文章包裹在代码块里，直接输出正文。
- 保留代码块、列表等 Markdown 格式。

### 2. 风格要求
- **拒绝爹味**：不要用"小编觉得"、"众所周知"、"想必大家都知道"。
- **情绪递进**：
  - 开头 Hook 要在 3 秒内抓住痛点，可用反问句、悬念、场景代入
  - 中间干货要密集但易读（短段落，每段不超过 3-4 行）
  - 结尾要有强烈的行动呼吁（Call to Action）
- **人话翻译**：把技术黑话翻译成大白话
  - ❌ "低延时高并发" → ✅ "快到飞起，千人同用不卡顿"
  - ❌ "端到端加密" → ✅ "只有你和对方能看到，连服务器都看不了"

### 3. 内容约束
- 保留原文的核心观点、数据和案例
- 只针对用户指令进行定向修改
- 不要凭空捏造数据或功能

## Output
直接输出润色后的完整 Markdown 文章，从标题开始。
- **不要**输出"好的，这是修改后的版本..."等废话
- **不要**输出"我做了以下修改..."等解释
- **不要**用代码块包裹整篇文章"""


def refine_article(instruction: str, date: str = None):
    """
    根据指令润色文章
    
    Args:
        instruction: 用户的修改指令
        date: 可选，指定日期 (MMDD 或 YYYY-MM-DD)
    """
    # 设置工作日期
    if date:
        config.set_working_date(date)
    
    draft_file = config.get_draft_file()
    final_file = config.get_final_file()
    
    print("\n" + "=" * 60)
    print("✨ 润色智能体 - 定向修改")
    print("=" * 60)
    print(f"\n📁 今日工作目录: {config.get_today_dir()}")
    
    # 读取草稿
    print(f"\n📖 读取 {draft_file}...")
    if not os.path.exists(draft_file):
        print(f"❌ 找不到草稿文件: {draft_file}")
        print("   请先运行 python run.py draft 生成草稿")
        return
    
    with open(draft_file, "r", encoding="utf-8") as f:
        content = f.read()
    
    if not content.strip():
        print("❌ 草稿文件为空")
        return
    
    print(f"   ✓ 共 {len(content)} 字符")
    print(f"\n📝 修改指令: {instruction}")
    
    # 构建 User Prompt
    user_prompt = f"【修改指令】：{instruction}\n\n【文章原稿】：\n{content}"
    
    # 调用 DeepSeek API
    print("\n🚀 调用 DeepSeek Reasoner...")
    print("\n" + "=" * 20 + " 润色中 " + "=" * 20 + "\n")
    
    http_client = httpx.Client(proxy=config.PROXY_URL, timeout=getattr(config, 'REQUEST_TIMEOUT', 120))
    client = OpenAI(
        api_key=config.DEEPSEEK_API_KEY,
        base_url=config.DEEPSEEK_BASE_URL,
        http_client=http_client
    )
    
    try:
        response = client.chat.completions.create(
            model="deepseek-reasoner",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            stream=True
        )
        
        # 流式输出
        full_content = ""
        for chunk in response:
            # 跳过 reasoning_content
            if hasattr(chunk.choices[0].delta, 'reasoning_content'):
                reasoning = chunk.choices[0].delta.reasoning_content
                if reasoning:
                    continue  # 不显示推理过程，保持输出简洁
            
            # 输出正文内容
            if chunk.choices[0].delta.content:
                text = chunk.choices[0].delta.content
                print(text, end="", flush=True)
                full_content += text
        
        print("\n\n" + "=" * 50)
        
        # 保存到 final.md
        os.makedirs(os.path.dirname(final_file), exist_ok=True)
        with open(final_file, "w", encoding="utf-8") as f:
            f.write(full_content)
        
        print(f"\n✅ 定稿已保存: {final_file}")
        print(f"📋 原稿保留在: {draft_file}")
        print("\n📌 下一步：")
        print("   1. 检查 final.md，确认修改效果")
        print("   2. 如需继续修改，再次运行 python run.py refine \"新的指令\"")
        print("   3. 满意后运行 python run.py format 进行排版")
        
    except Exception as e:
        print(f"\n❌ API 调用失败: {e}")
        raise


def main():
    """命令行入口"""
    if len(sys.argv) > 1:
        instruction = " ".join(sys.argv[1:])
    else:
        instruction = input("请输入修改意见: ").strip()
    
    if not instruction:
        print("❌ 请提供修改指令")
        return
    
    refine_article(instruction)


if __name__ == "__main__":
    main()
