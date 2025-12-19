"""
===============================================================================
                    ✨ 润色智能体 (Refiner Agent) v4.3 (Context-Aware Edition)
===============================================================================
根据用户的自然语言指令，结合研究笔记和草稿原文，对文章进行定向修改。

v4.3 更新：
- 新增研究笔记上下文注入，确保修改结果与原始素材一致
- 结合 notes.txt + draft.md + 用户指令 三方信息

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
import shutil
from datetime import datetime
from openai import OpenAI
import config


logger = config.get_logger(__name__)

def _backup_file(path: str):
    """Create a timestamped backup if the file exists."""
    if os.path.exists(path):
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_path = f"{path}.bak-{ts}"
        shutil.copy(path, backup_path)
        logger.info(f"🛡️ Created backup: {backup_path}")

# ================= 系统提示词 =================

SYSTEM_PROMPT = """## Role
你是一位拥有 10w+ 阅读量经验的科技公众号主编“王往AI”。你的文风硬核、真诚、口语化，擅长把复杂技术讲得像朋友聊天一样简单有趣。

## Task
请根据用户提供的【修改指令】、【研究笔记】和【文章原稿】，对文章进行定向修改。

## ❗ 三方信息融合原则 (v4.3 核心更新)
1. **研究笔记是事实来源**：笔记中的工具名称、技术细节、数据是权威参考，修改时必须与笔记一致
2. **草稿是结构框架**：保留草稿的整体结构、段落顺序、配图占位符
3. **用户指令是最高优先级**：按照用户指令进行定向修改

## ⚠️ 严格约束

### 1. 内容约束 (最重要!)
- **不要换工具**：如果笔记和草稿提到的是 AutoGLM，就不要换成阶跃星辰/其他工具
- **不要捏造数据**：所有数字、功能描述必须来自笔记或草稿
- **不要乱加章节**：除非用户指令明确要求，否则不要新增“避坑指南”等章节
- **保留核心观点**：保持草稿的核心论点和案例

### 2. 格式死线
- **绝对保留**所有 `> TODO:` 和 `![...]` 配图标记
- **绝对保留** Markdown 标题层级 (`#`, `##`, `###`) 和加粗强调 (`**`)
- 不要把文章包裹在代码块里，直接输出正文
- 保留代码块、列表等 Markdown 格式

### 3. 风格要求
- **拒绝爹味**：不要用“小编觉得”、“众所周知”、“想必大家都知道”
- **情绪递进**：开头抓痛点，中间给干货，结尾呼吁行动
- **人话翻译**：把技术黑话翻译成大白话

## Output
直接输出润色后的完整 Markdown 文章，从标题开始。
- **不要**输出“好的，这是修改后的版本...”等废话
- **不要**输出“我做了以下修改...”等解释
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

    logger.info("%s", "=" * 60)
    logger.info("✨ 润色智能体 v4.3 - 上下文感知版")
    logger.info("%s", "=" * 60)
    logger.info("📁 今日工作目录: %s", config.get_today_dir())
    
    # v4.2: 优先读取 final.md（保留用户的手动修改），降级读取 draft.md
    source_file = None
    content = None
    
    if os.path.exists(final_file):
        with open(final_file, "r", encoding="utf-8") as f:
            content = f.read()
        if content.strip():
            source_file = final_file
            logger.info("📖 读取定稿: %s", final_file)
    
    # 降级：如果 final.md 不存在或为空，读取 draft.md
    if not source_file:
        logger.info("📖 读取草稿: %s...", draft_file)
        if not os.path.exists(draft_file):
            logger.error("❌ 找不到草稿文件: %s", draft_file)
            logger.error("   请先运行 python run.py draft 生成草稿")
            return
        
        with open(draft_file, "r", encoding="utf-8") as f:
            content = f.read()
        source_file = draft_file
    
    if not content or not content.strip():
        logger.error("❌ 文章文件为空")
        return

    logger.info("✓ 共 %s 字符", len(content))
    logger.info("📝 修改指令: %s", instruction)
    
    # v4.3: 读取研究笔记作为事实来源
    notes_content = ""
    notes_file = config.get_research_notes_file()
    if os.path.exists(notes_file):
        with open(notes_file, "r", encoding="utf-8") as f:
            notes_content = f.read()
        logger.info("📚 已加载研究笔记: %s 字符", len(notes_content))
    else:
        logger.warning("⚠️ 未找到研究笔记，将仅基于草稿进行修改")
    
    # 构建 User Prompt - 三方信息融合
    user_prompt = f"""【修改指令】：
{instruction}

【研究笔记 - 事实来源，请确保修改内容与此一致】：
{notes_content[:6000] if notes_content else '（无笔记）'}

【文章原稿 - 保持结构，定向修改】：
{content}
"""
    
    # 调用 DeepSeek API
    logger.info("🚀 调用 DeepSeek Reasoner...")
    logger.info("%s", "=" * 20 + " 润色中 " + "=" * 20)

    with httpx.Client(proxy=config.PROXY_URL, timeout=getattr(config, 'REQUEST_TIMEOUT', 120)) as http_client:
        client = OpenAI(
            api_key=config.DEEPSEEK_API_KEY,
            base_url=config.DEEPSEEK_BASE_URL,
            http_client=http_client
        )

        try:
            @config.retryable
            @config.track_cost(context="refine_article")
            def _chat_create():
                return client.chat.completions.create(
                    model="deepseek-reasoner",
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt}
                    ],
                    stream=True
                )

            response = _chat_create()

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
                    sys.stdout.write(text)
                    sys.stdout.flush()
                    full_content += text

            sys.stdout.write("\n\n" + "=" * 50 + "\n")
            sys.stdout.flush()

            # 保存到 final.md
            os.makedirs(os.path.dirname(final_file), exist_ok=True)
            _backup_file(final_file)
            with open(final_file, "w", encoding="utf-8") as f:
                f.write(full_content)

            logger.info("✅ 定稿已保存: %s", final_file)
            logger.info("📋 原稿保留在: %s", draft_file)
            logger.info("📌 下一步：")
            logger.info("   1. 检查 final.md，确认修改效果")
            logger.info("   2. 如需继续修改，再次运行 python run.py refine \"新的指令\"")
            logger.info("   3. 满意后运行 python run.py format 进行排版")

        except Exception as e:
            logger.error("❌ API 调用失败: %s", e)
            raise


def main():
    """命令行入口"""
    if len(sys.argv) > 1:
        instruction = " ".join(sys.argv[1:])
    else:
        instruction = input("请输入修改意见: ").strip()
    
    if not instruction:
        logger.error("❌ 请提供修改指令")
        return
    
    refine_article(instruction)


if __name__ == "__main__":
    main()
