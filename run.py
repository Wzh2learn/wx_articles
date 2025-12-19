"""
===============================================================================
                    🚀 王往AI 公众号工作流 v4.0 (Hardcore Edition)
===============================================================================
用法：
    python run.py hunt              # 运行选题雷达 (可多次运行，支持 -t)
    python run.py final             # 综合多次选题报告
    python run.py research          # 运行研究智能体 (自动搜索+爬取+整理)
    python run.py draft             # 运行写作智能体
    python run.py refine "指令"     # 运行润色智能体 (定向修改)
    python run.py format            # 运行排版智能体
    python run.py draft -d 1204     # 指定日期 (MMDD 或 YYYY-MM-DD)
===============================================================================
"""

import sys
import os
import argparse

from config import get_logger, DEEPSEEK_API_KEY, EXA_API_KEY, TAVILY_API_KEY

logger = get_logger(__name__)

# 确保可以导入 agents 模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def print_help():
    logger.info("""
╔══════════════════════════════════════════════════════════════╗
║           🚀 王往AI 公众号工作流 v4.0 (硬核价值版)           ║
╠══════════════════════════════════════════════════════════════╣
║  用法: python run.py <command> [-d 日期]                      ║
║                                                              ║
║  日期参数 (可选):                                               ║
║    -d 1204           指定工作日期 (MMDD 简写)                   ║
║    -d 2025-12-04     指定工作日期 (完整格式)                   ║
║                                                              ║
║  命令:                                                       ║
║    hunt    - 🎯 选题雷达 (扫描全网热点，支持 -t 混合优先级)  ║
║    final   - 🏆 综合决策 (整合多次报告，输出3个提示词)       ║
║    research- 🔬 研究智能体 (自动搜索、爬取、整理笔记)        ║
║    draft   - ✍️ 写作智能体 (读取笔记，生成初稿)              ║
║    refine  - ✨ 润色智能体 (定向修改: refine "指令")        ║
║    audit   - 🕵️ 审计智能体 (核查事实，防幻觉)                ║
║    format  - 🎨 排版智能体 (转换HTML，复制到剪贴板)          ║
║    todo    - 📋 提取TODO (列出草稿中需补充的内容)            ║
║    all     - 🔄 完整流程 (依次运行，需人工介入)              ║
║    help    - 📖 显示帮助                                     ║
╠══════════════════════════════════════════════════════════════╣
║  推荐工作流程:                                               ║
║    1. hunt ×N -> 多次运行选题雷达 (早/中/晚各一次)           ║
║    2. final   -> 综合所有报告，获得最终选题                  ║
║    3. research-> 🆕 自动联网搜索+笔记整理 (Exa + Tavily)     ║
║    4. draft   -> 生成 draft.md                               ║
║    5. refine  -> 🆕 AI定向润色 (refine "把开头改得悬念")    ║
║    6. format  -> 生成 HTML，复制到公众号发布                 ║
╚══════════════════════════════════════════════════════════════╝
""")


def check_environment(command: str):
    missing = []

    llm_commands = {"hunt", "final", "research", "draft", "refine", "audit", "all"}
    if command in llm_commands:
        if not DEEPSEEK_API_KEY:
            missing.append("DEEPSEEK_API_KEY")

    if command in {"research", "all"}:
        if not EXA_API_KEY and not TAVILY_API_KEY:
            missing.append("EXA_API_KEY 或 TAVILY_API_KEY（至少配置一个）")

    if missing:
        logger.error("❌ 环境配置缺失，无法启动：%s", ", ".join(missing))
        logger.error("   请在环境变量中设置，或在 config.py 中配置对应 Key")
        raise SystemExit(1)

def run_hunter(topic=None):
    from agents.trend_hunter import main
    main(topic=topic)

def run_drafter(topic=None, strategic_intent=None, visual_script=None):
    from agents.drafter import main
    if topic is None or strategic_intent is None:
        parsed = _load_final_decision()
        if parsed:
            if topic is None:
                topic = parsed.get('topic')
            if strategic_intent is None:
                strategic_intent = parsed.get('strategic_summary')
            if visual_script is None:
                visual_script = parsed.get('visual_script')

    main(topic=topic, strategic_intent=strategic_intent, visual_script=visual_script)

def run_formatter(style: str = "green"):
    from agents.formatter import main
    main(style=style)

def run_todo():
    from agents.todo_extractor import main
    main()

def _load_final_decision():
    """
    v4.2: 智能解析 FINAL_DECISION.md，提取结构化信息
    
    Returns:
        dict: {
            'topic': 文章标题,
            'keywords': 关键词列表,
            'hook': 一句话卖点,
            'anchor': 心理锚点,
            'fast_research': Fast Research 提示词 (用于精准搜索),
            'strategic_summary': 精简的战略意图摘要 (不含视觉脚本)
        }
    """
    from config import get_today_dir
    import os
    import re

    topics_dir = os.path.join(get_today_dir(), "1_topics")
    final_file = os.path.join(topics_dir, "FINAL_DECISION.md")

    if not os.path.exists(final_file):
        return None

    logger.info(f"📄 正在解析: {final_file}")
    with open(final_file, "r", encoding="utf-8") as f:
        content = f.read()

    result = {
        'topic': None,
        'keywords': [],
        'hook': None,
        'anchor': None,
        'fast_research': None,
        'strategic_summary': None
    }

    # 提取标题
    title_match = re.search(r'\*\*标题\*\*[：:]\s*(.+)', content)
    if title_match:
        result['topic'] = title_match.group(1).strip()

    # 提取关键词
    keywords_match = re.search(r'\*\*关键词\*\*[：:]\s*(.+)', content)
    if keywords_match:
        keywords_str = keywords_match.group(1).strip()
        result['keywords'] = [kw.strip() for kw in re.split(r'[,，、]', keywords_str) if kw.strip()]

    # 提取一句话卖点
    hook_match = re.search(r'\*\*一句话卖点\*\*[：:]\s*(.+)', content)
    if hook_match:
        result['hook'] = hook_match.group(1).strip()

    # 提取心理锚点
    anchor_match = re.search(r'\*\*心理锚点\*\*[：:]\s*(.+)', content)
    if anchor_match:
        result['anchor'] = anchor_match.group(1).strip()

    # 提取 Fast Research 提示词（关键！用于精准搜索）
    fast_research_match = re.search(
        r'###\s*📡\s*提示词\s*1[：:]?\s*Fast Research.*?```\s*(.*?)```',
        content, re.DOTALL | re.IGNORECASE
    )
    if fast_research_match:
        result['fast_research'] = fast_research_match.group(1).strip()
        logger.info("   ✅ 已提取 Fast Research 搜索指引")

    # 提取 Visual Script (JSON)
    visual_script_match = re.search(
        r'###\s*🎨\s*视觉脚本.*?```json\s*(.*?)```',
        content, re.DOTALL | re.IGNORECASE
    )
    if visual_script_match:
        try:
            from json_repair import repair_json
            vs_json = repair_json(visual_script_match.group(1).strip(), return_objects=True)
            if isinstance(vs_json, dict) and 'visual_script' in vs_json:
                result['visual_script'] = vs_json['visual_script']
                logger.info("   ✅ 已提取 Visual Script (JSON)")
            else:
                 # 兼容直接返回 visual_script 内容的情况
                result['visual_script'] = vs_json
                logger.info("   ✅ 已提取 Visual Script (JSON - Direct)")
        except Exception as e:
            logger.warning(f"   ⚠️ Visual Script 解析失败: {e}")
            result['visual_script'] = None

    # 构建精简的战略意图摘要（不含视觉脚本）
    strategic_parts = []
    if result['topic']:
        strategic_parts.append(f"**标题**: {result['topic']}")
    if result['anchor']:
        strategic_parts.append(f"**心理锚点**: {result['anchor']}")
    if result['hook']:
        strategic_parts.append(f"**一句话卖点**: {result['hook']}")
    if result['keywords']:
        strategic_parts.append(f"**关键词**: {', '.join(result['keywords'])}")
    
    result['strategic_summary'] = '\n'.join(strategic_parts) if strategic_parts else None

    return result


def _load_final_decision_legacy():
    """兼容旧版：返回 (topic, queries, strategic_intent) 三元组"""
    result = _load_final_decision()
    if not result:
        return None, None, None
    return result['topic'], result['keywords'], result.get('strategic_summary')


def run_researcher(topic=None, queries=None, strategic_intent=None):
    """
    v4.2: 运行研究智能体，自动搜索、爬取、整理笔记
    
    核心改进：
    1. 从 FINAL_DECISION.md 提取 Fast Research 搜索指引
    2. 使用结构化搜索指引进行精准搜索
    3. 只传递精简的战略意图摘要（不含视觉脚本）
    """
    from agents.researcher import ResearcherAgent
    
    # v4.2: 使用新的结构化解析
    parsed = _load_final_decision()
    
    if not parsed:
        logger.error("❌ 未找到选题信息，请先运行 `python run.py final`")
        return None
    
    # 使用解析结果填充缺失参数
    if topic is None:
        topic = parsed.get('topic')
    if queries is None:
        queries = parsed.get('keywords', [])
    if strategic_intent is None:
        strategic_intent = parsed.get('strategic_summary')  # 使用精简摘要，不含视觉脚本
    
    if not topic:
        logger.error("❌ 未找到选题标题，请检查 FINAL_DECISION.md 格式")
        return None
    
    if not queries:
        queries = [topic]
    
    # v4.2: 提取 Fast Research 搜索指引
    fast_research = parsed.get('fast_research')
    
    logger.info(f"🎯 选题: {topic}")
    logger.info(f"🔑 关键词: {queries}")
    if fast_research:
        logger.info(f"📡 已加载 Fast Research 搜索指引 ({len(fast_research)} 字符)")
    
    researcher = ResearcherAgent()
    return researcher.run(
        topic=topic, 
        queries=queries, 
        strategic_intent=strategic_intent,
        fast_research=fast_research  # v4.2: 传递搜索指引
    )

def run_all():
    from config import get_today_dir
    today = get_today_dir()
    
    logger.info("🔄 开始完整工作流 (自动化版)...")
    logger.info(f"📁 今日工作目录: {today}")
    
    # ============ Phase 1: 选题雷达 ============
    logger.info("="*60)
    logger.info("📡 Phase 1: 选题雷达")
    logger.info("="*60)
    run_hunter()
    
    # ============ Phase 2: 综合决策 ============
    logger.info("="*60)
    logger.info("🏆 Phase 2: 综合决策")
    logger.info("="*60)
    from agents.trend_hunter import final_summary
    final_summary()
    
    # ============ Phase 3: 自动化研究 ============
    logger.info("="*60)
    logger.info("🔬 Phase 3: 自动化研究 (Exa + Tavily)")
    logger.info("="*60)
    parsed = _load_final_decision()
    if parsed:
        topic = parsed.get('topic')
        queries = parsed.get('keywords')
        strategic_intent = parsed.get('strategic_summary')
    else:
        topic, queries, strategic_intent = None, None, None
    notes = run_researcher(topic=topic, queries=queries, strategic_intent=strategic_intent)
    
    if not notes:
        logger.warning("⚠️ 研究阶段失败，工作流中断")
        return
    
    # ============ Phase 4: 写作智能体 ============
    logger.info("="*60)
    logger.info("✍️ Phase 4: 写作智能体")
    logger.info("="*60)
    
    # 重新加载以获取 visual_script
    if parsed:
        visual_script = parsed.get('visual_script')
    else:
        visual_script = None
        
    run_drafter(topic=topic, strategic_intent=strategic_intent, visual_script=visual_script)
    
    # ============ 人工介入点 ============
    logger.info("="*60)
    logger.info("⏸️  人工介入点 (润色与定稿)")
    logger.info("="*60)
    logger.info("请完成以下步骤后，按 Enter 继续：")
    logger.info(f"  1. 打开 {today}/3_drafts/draft.md 进行润色")
    logger.info(f"  2. 保存定稿到 {today}/4_publish/final.md")
    input("\n按 Enter 继续...")
    
    # ============ Phase 5: 排版智能体 ============
    logger.info("="*60)
    logger.info("🎨 Phase 5: 排版智能体")
    logger.info("="*60)
    run_formatter()
    
    logger.info("="*60)
    logger.info("🎉 工作流完成！")
    logger.info("="*60)
    logger.info("HTML 已复制到剪贴板，请去公众号后台：")
    logger.info("1. 粘贴内容")
    logger.info("2. 手动上传并插入图片")

def run_refiner(instruction: str, date: str = None):
    """运行润色智能体"""
    from agents.refiner import refine_article
    refine_article(instruction, date)


def main():
    # 特殊处理 refine 命令（因为它需要接收额外的指令参数）
    if len(sys.argv) >= 2 and sys.argv[1] == 'refine':
        # 解析日期参数
        date = None
        instruction_parts = []
        i = 2
        while i < len(sys.argv):
            if sys.argv[i] in ['-d', '--date'] and i + 1 < len(sys.argv):
                date = sys.argv[i + 1]
                i += 2
            else:
                instruction_parts.append(sys.argv[i])
                i += 1
        
        # 设置工作日期
        if date:
            from config import set_working_date
            set_working_date(date)
        
        # 获取指令
        instruction = " ".join(instruction_parts)
        if not instruction:
            instruction = input("请输入修改意见: ").strip()
        
        if instruction:
            run_refiner(instruction, date)
        else:
            logger.error("❌ 请提供修改指令")
            logger.error("   用法: python run.py refine \"把开头改得更有悬念\"")
        return
    
    parser = argparse.ArgumentParser(description='王往AI 公众号工作流')
    parser.add_argument('command', choices=['hunt', 'final', 'research', 'draft', 'refine', 'audit', 'format', 'todo', 'all', 'help'], help='执行的命令', nargs='?', default='help')
    parser.add_argument('-d', '--date', help='指定工作日期 (MMDD 或 YYYY-MM-DD)，默认今天')
    parser.add_argument('-t', '--topic', help='[hunt专用] 指定搜索主题，启用混合优先级(命题作文+自由发挥)')
    parser.add_argument('-s', '--style', default='green', help='[format专用] 排版风格: green/blue/orange/minimal/purple')
    args = parser.parse_args()
    
    # 设置工作日期
    if args.date:
        from config import set_working_date
        set_working_date(args.date)

    if args.command == 'hunt':
        check_environment("hunt")
        run_hunter(topic=args.topic)
    elif args.command == 'final':
        check_environment("final")
        from agents.trend_hunter import final_summary
        final_summary()
    elif args.command == 'research':
        check_environment("research")
        run_researcher()
    elif args.command == 'draft':
        check_environment("draft")
        run_drafter()
    elif args.command == 'format':
        check_environment("format")
        run_formatter(style=args.style)
    elif args.command == 'todo':
        check_environment("todo")
        run_todo()
    elif args.command == 'all':
        check_environment("all")
        run_all()
    elif args.command == 'refine':
        # 如果通过 argparse 进入（无参数），交互式获取
        instruction = input("请输入修改意见: ").strip()
        if instruction:
            run_refiner(instruction, args.date)
        else:
            logger.error("❌ 请提供修改指令")
    elif args.command == 'audit':
        check_environment("audit")
        from agents.auditor import audit_article
        audit_article()
    else:
        print_help()

if __name__ == "__main__":
    main()
