"""
===============================================================================
                    🚀 王往AI 公众号工作流 - 统一入口
===============================================================================
用法：
    python run.py hunt              # 运行选题雷达 (可多次运行)
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

# 确保可以导入 agents 模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def print_help():
    print("""
╔══════════════════════════════════════════════════════════════╗
║           🚀 王往AI 公众号工作流 v2.0                        ║
╠══════════════════════════════════════════════════════════════╣
║  用法: python run.py <command> [-d 日期]                      ║
║                                                              ║
║  日期参数 (可选):                                               ║
║    -d 1204           指定工作日期 (MMDD 简写)                   ║
║    -d 2025-12-04     指定工作日期 (完整格式)                   ║
║                                                              ║
║  命令:                                                       ║
║    hunt    - 🎯 选题雷达 (扫描全网热点，可多次运行)          ║
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
║    3. research-> 🆕 自动联网搜索+笔记整理 (替代NotebookLM)   ║
║    4. draft   -> 生成 draft.md                               ║
║    5. refine  -> 🆕 AI定向润色 (refine "把开头改得悬念")    ║
║    6. format  -> 生成 HTML，复制到公众号发布                 ║
╚══════════════════════════════════════════════════════════════╝
""")

def run_hunter():
    from agents.trend_hunter import main
    main()

def run_drafter():
    from agents.drafter import main
    main()

def run_formatter():
    from agents.formatter import main
    main()

def run_todo():
    from agents.todo_extractor import main
    main()

def run_researcher(topic=None, queries=None):
    """运行研究智能体，自动搜索、爬取、整理笔记"""
    from agents.researcher import ResearcherAgent
    from config import get_today_dir
    import os
    import re
    
    # 如果没有传入参数，尝试从 FINAL_DECISION.md 解析
    if topic is None or queries is None:
        topics_dir = os.path.join(get_today_dir(), "1_topics")
        final_file = os.path.join(topics_dir, "FINAL_DECISION.md")
        
        if os.path.exists(final_file):
            print(f"📄 正在解析: {final_file}")
            with open(final_file, "r", encoding="utf-8") as f:
                content = f.read()
            
            # 解析选题标题
            title_match = re.search(r'\*\*标题\*\*[：:]\s*(.+)', content)
            if title_match:
                topic = title_match.group(1).strip()
            else:
                # 备用：尝试匹配其他格式
                title_match = re.search(r'### 🏆 今日最终选题\s*\n+.*?\*\*标题\*\*[：:]?\s*(.+)', content)
                if title_match:
                    topic = title_match.group(1).strip()
            
            # 解析关键词
            keywords_match = re.search(r'\*\*关键词\*\*[：:]\s*(.+)', content)
            if keywords_match:
                keywords_str = keywords_match.group(1).strip()
                # 分割关键词 (支持中英文逗号、顿号)
                queries = [kw.strip() for kw in re.split(r'[,，、]', keywords_str) if kw.strip()]
        
        if not topic:
            print("❌ 未找到选题信息，请先运行 `python run.py final`")
            print("   或手动指定: researcher.run(topic='选题', queries=['关键词1', '关键词2'])")
            return None
        
        if not queries:
            # 如果没有找到关键词，用选题本身作为搜索词
            queries = [topic]
    
    print(f"\n🎯 选题: {topic}")
    print(f"🔑 关键词: {queries}")
    
    researcher = ResearcherAgent()
    return researcher.run(topic, queries)

def run_all():
    from config import get_today_dir
    today = get_today_dir()
    
    print("\n🔄 开始完整工作流 (自动化版)...\n")
    print(f"📁 今日工作目录: {today}\n")
    
    # ============ Phase 1: 选题雷达 ============
    print("="*60)
    print("📡 Phase 1: 选题雷达")
    print("="*60)
    run_hunter()
    
    # ============ Phase 2: 综合决策 ============
    print("\n" + "="*60)
    print("🏆 Phase 2: 综合决策")
    print("="*60)
    from agents.trend_hunter import final_summary
    final_summary()
    
    # ============ Phase 3: 自动化研究 ============
    print("\n" + "="*60)
    print("🔬 Phase 3: 自动化研究 (替代 NotebookLM)")
    print("="*60)
    notes = run_researcher()
    
    if not notes:
        print("⚠️ 研究阶段失败，工作流中断")
        return
    
    # ============ Phase 4: 写作智能体 ============
    print("\n" + "="*60)
    print("✍️ Phase 4: 写作智能体")
    print("="*60)
    run_drafter()
    
    # ============ 人工介入点 ============
    print("\n" + "="*60)
    print("⏸️  人工介入点 (润色与定稿)")
    print("="*60)
    print("请完成以下步骤后，按 Enter 继续：")
    print(f"  1. 打开 {today}/3_drafts/draft.md 进行润色")
    print(f"  2. 保存定稿到 {today}/4_publish/final.md")
    input("\n按 Enter 继续...")
    
    # ============ Phase 5: 排版智能体 ============
    print("\n" + "="*60)
    print("🎨 Phase 5: 排版智能体")
    print("="*60)
    run_formatter()
    
    print("\n" + "="*60)
    print("🎉 工作流完成！")
    print("="*60)
    print("HTML 已复制到剪贴板，请去公众号后台：")
    print("1. 粘贴内容")
    print("2. 手动上传并插入图片")

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
            print("❌ 请提供修改指令")
            print("   用法: python run.py refine \"把开头改得更有悬念\"")
        return
    
    parser = argparse.ArgumentParser(description='王往AI 公众号工作流')
    parser.add_argument('command', choices=['hunt', 'final', 'research', 'draft', 'refine', 'format', 'todo', 'all', 'help'], help='执行的命令', nargs='?', default='help')
    parser.add_argument('-d', '--date', help='指定工作日期 (MMDD 或 YYYY-MM-DD)，默认今天')
    args = parser.parse_args()
    
    # 设置工作日期
    if args.date:
        from config import set_working_date
        set_working_date(args.date)

    if args.command == 'hunt':
        run_hunter()
    elif args.command == 'final':
        from agents.trend_hunter import final_summary
        final_summary()
    elif args.command == 'research':
        run_researcher()
    elif args.command == 'draft':
        run_drafter()
    elif args.command == 'format':
        run_formatter()
    elif args.command == 'todo':
        run_todo()
    elif args.command == 'all':
        run_all()
    elif args.command == 'refine':
        # 如果通过 argparse 进入（无参数），交互式获取
        instruction = input("请输入修改意见: ").strip()
        if instruction:
            run_refiner(instruction, args.date)
        else:
            print("❌ 请提供修改指令")
    else:
        print_help()

if __name__ == "__main__":
    main()
