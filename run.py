"""
===============================================================================
                    🚀 王往AI 公众号工作流 - 统一入口
===============================================================================
用法：
    python run.py hunt              # 运行选题雷达 (可多次运行)
    python run.py final             # 综合多次选题报告
    python run.py draft             # 运行写作智能体
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
║    draft   - ✍️ 写作智能体 (读取笔记，生成初稿)              ║
║    format  - 🎨 排版智能体 (转换HTML，复制到剪贴板)          ║
║    todo    - 📋 提取TODO (列出草稿中需补充的内容)            ║
║    publish - 📤 自动发布 (上传图片 & 新建草稿)               ║
║    all     - 🔄 完整流程 (依次运行，需人工介入)              ║
║    help    - 📖 显示帮助                                     ║
╠══════════════════════════════════════════════════════════════╣
║  推荐工作流程:                                               ║
║    1. hunt ×N -> 多次运行选题雷达 (早/中/晚各一次)           ║
║    2. final   -> 综合所有报告，获得3个提示词                 ║
║    3. 人工    -> NotebookLM Fast Research + 整理笔记         ║
║    4. draft   -> 生成 draft.md                               ║
║    5. 人工    -> 润色，截图，保存为 final.md                 ║
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

def run_all():
    from config import get_today_dir
    today = get_today_dir()
    
    print("\n🔄 开始完整工作流...\n")
    print(f"📁 今日工作目录: {today}\n")
    print("="*60)
    print("📡 Phase 1: 选题雷达")
    print("="*60)
    run_hunter()
    
    print("\n" + "="*60)
    print("⏸️  人工介入点")
    print("="*60)
    print("请完成以下步骤后，按 Enter 继续：")
    print(f"  1. 查看 {today}/1_topics/ 下的选题报告")
    print("  2. 去 NotebookLM 做深度研究")
    print(f"  3. 整理笔记到 {today}/2_research/notes.txt")
    input("\n按 Enter 继续...")
    
    print("\n" + "="*60)
    print("✍️ Phase 2: 写作智能体")
    print("="*60)
    run_drafter()
    
    print("\n" + "="*60)
    print("⏸️  人工介入点")
    print("="*60)
    print("请完成以下步骤后，按 Enter 继续：")
    print(f"  1. 打开 {today}/3_drafts/draft.md 进行润色")
    print(f"  2. 截图保存到 {today}/5_assets/ 目录")
    print(f"  3. 保存定稿到 {today}/4_publish/final.md")
    input("\n按 Enter 继续...")
    
    print("\n" + "="*60)
    print("🎨 Phase 3: 排版智能体")
    print("="*60)
    run_formatter()
    
    print("\n" + "="*60)
    print("🎉 工作流完成！")
    print("="*60)
    print("HTML 已复制到剪贴板，去公众号后台发布吧！")

def main():
    parser = argparse.ArgumentParser(description='王往AI 公众号工作流')
    parser.add_argument('command', choices=['hunt', 'final', 'draft', 'format', 'todo', 'publish', 'all', 'help'], help='执行的命令', nargs='?', default='help')
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
    elif args.command == 'draft':
        run_drafter()
    elif args.command == 'format':
        run_formatter()
    elif args.command == 'todo':
        run_todo()
    elif args.command == 'publish':
        from agents.publisher import publish_draft
        publish_draft()
    elif args.command == 'all':
        run_all()
    else:
        print_help()

if __name__ == "__main__":
    main()
