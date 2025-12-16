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

    llm_commands = {"hunt", "final", "research", "draft", "refine", "all"}
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

def run_drafter(topic=None, strategic_intent=None):
    from agents.drafter import main
    if topic is None or strategic_intent is None:
        parsed_topic, _, parsed_intent = _load_final_decision()
        if topic is None:
            topic = parsed_topic
        if strategic_intent is None:
            strategic_intent = parsed_intent

    main(topic=topic, strategic_intent=strategic_intent)

def run_formatter():
    from agents.formatter import main
    main()

def run_todo():
    from agents.todo_extractor import main
    main()

def _load_final_decision():
    from config import get_today_dir
    import os
    import re

    topics_dir = os.path.join(get_today_dir(), "1_topics")
    final_file = os.path.join(topics_dir, "FINAL_DECISION.md")

    if not os.path.exists(final_file):
        return None, None, None

    logger.info(f"📄 正在解析: {final_file}")
    with open(final_file, "r", encoding="utf-8") as f:
        content = f.read()

    topic = None
    queries = None

    title_match = re.search(r'\*\*标题\*\*[：:]\s*(.+)', content)
    if title_match:
        topic = title_match.group(1).strip()
    else:
        title_match = re.search(r'### 🏆 今日最终选题\s*\n+.*?\*\*标题\*\*[：:]?\s*(.+)', content)
        if title_match:
            topic = title_match.group(1).strip()

    keywords_match = re.search(r'\*\*关键词\*\*[：:]\s*(.+)', content)
    if keywords_match:
        keywords_str = keywords_match.group(1).strip()
        queries = [kw.strip() for kw in re.split(r'[,，、]', keywords_str) if kw.strip()]

    strategic_intent = content.strip() if content else None
    return topic, queries, strategic_intent


def run_researcher(topic=None, queries=None, strategic_intent=None):
    """运行研究智能体，自动搜索、爬取、整理笔记"""
    from agents.researcher import ResearcherAgent
    
    # 如果没有传入参数，尝试从 FINAL_DECISION.md 解析
    if topic is None or queries is None or strategic_intent is None:
        parsed_topic, parsed_queries, parsed_intent = _load_final_decision()
        if topic is None:
            topic = parsed_topic
        if queries is None:
            queries = parsed_queries
        if strategic_intent is None:
            strategic_intent = parsed_intent
        
        if not topic:
            logger.error("❌ 未找到选题信息，请先运行 `python run.py final`")
            logger.error("   或手动指定: researcher.run(topic='选题', queries=['关键词1', '关键词2'])")
            return None
        
        if not queries:
            # 如果没有找到关键词，用选题本身作为搜索词
            queries = [topic]
    
    logger.info(f"🎯 选题: {topic}")
    logger.info(f"🔑 关键词: {queries}")
    
    researcher = ResearcherAgent()
    return researcher.run(topic, queries, strategic_intent=strategic_intent)

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
    topic, queries, strategic_intent = _load_final_decision()
    notes = run_researcher(topic=topic, queries=queries, strategic_intent=strategic_intent)
    
    if not notes:
        logger.warning("⚠️ 研究阶段失败，工作流中断")
        return
    
    # ============ Phase 4: 写作智能体 ============
    logger.info("="*60)
    logger.info("✍️ Phase 4: 写作智能体")
    logger.info("="*60)
    run_drafter(topic=topic, strategic_intent=strategic_intent)
    
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
    parser.add_argument('command', choices=['hunt', 'final', 'research', 'draft', 'refine', 'format', 'todo', 'all', 'help'], help='执行的命令', nargs='?', default='help')
    parser.add_argument('-d', '--date', help='指定工作日期 (MMDD 或 YYYY-MM-DD)，默认今天')
    parser.add_argument('-t', '--topic', help='[hunt专用] 指定搜索主题，启用混合优先级(命题作文+自由发挥)')
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
        run_formatter()
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
    else:
        print_help()

if __name__ == "__main__":
    main()
